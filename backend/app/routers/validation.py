from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import base64
import zipfile
import io
from pathlib import Path

import lxml.etree as ET
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.validators import ValidatorRegistry, HelgerValidator, XSDValidator
from app.services.transformer import get_transformer, TransformerService
from app.exceptions import MapperNotFoundError, TransformationError, XMLParseError

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Shared instances
_registry = ValidatorRegistry()


# ==================== SCHEMAS ====================

class TransformRequest(BaseModel):
    xml_content: str  # base64 encoded
    mapper: str


class MapperUploadResponse(BaseModel):
    name: str
    xslt_version: str
    type: str


# ==================== HELPER FUNCTIONS ====================

def transform_xml(xml_bytes: bytes, mapper_name: str) -> bytes:
    """Apply XSLT transformation using the transformer service."""
    transformer = get_transformer()
    result = transformer.transform_with_mapper(xml_bytes, mapper_name)
    if not result.success:
        if "not found" in (result.error or "").lower():
            raise MapperNotFoundError(mapper_name)
        raise TransformationError(result.error or "Transform failed")
    return result.output


# ==================== ENDPOINTS ====================

@router.get("/validators")
async def list_validators():
    """List all available validators"""
    return {
        "validators": _registry.list_validators(),
    }


@router.get("/mappers")
async def list_mappers():
    """
    List available XSL mappers (built-in and user-uploaded).
    Includes XSLT version detection.
    """
    transformer = get_transformer()
    mappers = transformer.list_mappers()
    return {
        "mappers": mappers,
        "saxon_available": TransformerService.is_saxon_available(),
        "supported_versions": ["1.0"] if not TransformerService.is_saxon_available() else ["1.0", "2.0", "3.0"],
    }


@router.post("/mappers/upload")
async def upload_mapper(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
):
    """
    Upload a custom XSLT mapper for reuse.

    The mapper will be saved and can be referenced by name in transform operations.
    """
    transformer = get_transformer()
    content = await file.read()

    # Use provided name or original filename
    mapper_name = name or file.filename or "custom_mapper.xsl"

    # Detect version before saving
    version = transformer.detect_xslt_version(content)

    # Check if Saxon is needed
    if version.value != "1.0" and not TransformerService.is_saxon_available():
        raise HTTPException(
            status_code=400,
            detail=f"XSLT {version.value} requires Saxon. Only XSLT 1.0 is currently supported."
        )

    # Save the mapper
    path = transformer.save_user_mapper(mapper_name, content)

    return {
        "name": path.name,
        "xslt_version": version.value,
        "type": "user",
        "message": f"Mapper uploaded successfully. Use '{path.name}' in transform operations.",
    }


@router.delete("/mappers/{mapper_name}")
async def delete_mapper(mapper_name: str):
    """Delete a user-uploaded mapper."""
    transformer = get_transformer()
    if transformer.delete_user_mapper(mapper_name):
        return {"message": f"Mapper '{mapper_name}' deleted"}
    raise HTTPException(status_code=404, detail=f"Mapper not found: {mapper_name}")


@router.get("/vesids")
async def list_vesids():
    """List common VESIDs for Helger validation"""
    return {
        "vesids": [
            {"id": "eu.peppol.bis3:invoice:2025.5", "name": "Peppol BIS3 Invoice", "format": "ubl"},
            {"id": "eu.peppol.bis3:creditnote:2025.5", "name": "Peppol BIS3 Credit Note", "format": "ubl"},
            {"id": "eu.cen.en16931:ubl:1.3.15", "name": "EN 16931 UBL Invoice", "format": "ubl"},
            {"id": "eu.cen.en16931:ubl-creditnote:1.3.15", "name": "EN 16931 UBL Credit Note", "format": "ubl"},
            {"id": "eu.cen.en16931:cii:1.3.15", "name": "EN 16931 CII", "format": "cii"},
            {"id": "de.zugferd:en16931:2.3.3", "name": "ZUGFeRD 2.3.3 EN16931", "format": "cii"},
            {"id": "de.zugferd:extended:2.3.3", "name": "ZUGFeRD 2.3.3 Extended", "format": "cii"},
            {"id": "de.zugferd:basic:2.3.3", "name": "ZUGFeRD 2.3.3 Basic", "format": "cii"},
            {"id": "fr.factur-x:en16931:1.0.7-3", "name": "Factur-X EN16931", "format": "cii"},
            {"id": "de.xrechnung:ubl-invoice:3.0.2", "name": "XRechnung 3.0.2 Invoice", "format": "ubl"},
        ]
    }


@router.post("/transform")
async def transform_files(
    files: list[UploadFile] = File(...),
    mapper: str = Form(...),
):
    """Transform XML files using specified XSL mapper (XSLT 1.0/2.0/3.0)"""
    transformer = get_transformer()
    results = []

    for file in files:
        content = await file.read()
        result = transformer.transform_with_mapper(content, mapper)

        if result.success:
            results.append({
                "filename": file.filename,
                "success": True,
                "transformed_xml": base64.b64encode(result.output).decode("utf-8"),
                "xslt_version": result.xslt_version.value if result.xslt_version else None,
                "processor": result.processor,
                "error": None,
            })
        else:
            results.append({
                "filename": file.filename,
                "success": False,
                "transformed_xml": None,
                "xslt_version": result.xslt_version.value if result.xslt_version else None,
                "processor": result.processor,
                "error": result.error,
            })

    return {"results": results}


@router.post("/transform/download")
async def transform_and_download(
    file: UploadFile = File(...),
    mapper: str = Form(...),
):
    """
    Transform a single XML file and return as downloadable file.
    Supports XSLT 1.0, 2.0, and 3.0.
    """
    content = await file.read()
    transformed = transform_xml(content, mapper)

    # Generate output filename
    original_name = file.filename or "document.xml"
    base_name = original_name.rsplit(".", 1)[0]
    output_filename = f"{base_name}_transformed.xml"

    return Response(
        content=transformed,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{output_filename}"'
        }
    )


@router.post("/transform/zip")
async def transform_zip(
    file: UploadFile = File(...),
):
    """
    Transform XMLs from a ZIP file containing XSLT mapper(s) and XML files.

    Expected ZIP structure:
    - *.xsl or *.xslt - XSLT mapper (uses first found, or specify in mapper.txt)
    - *.xml - XML files to transform
    - mapper.txt (optional) - Name of the mapper to use

    Returns a ZIP with transformed XMLs.
    """
    transformer = get_transformer()
    content = await file.read()

    try:
        with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
            # Find files by extension
            xslt_files = [n for n in zf.namelist() if n.lower().endswith(('.xsl', '.xslt'))]
            xml_files = [n for n in zf.namelist() if n.lower().endswith('.xml')]

            if not xslt_files:
                raise HTTPException(status_code=400, detail="No XSLT file found in ZIP")
            if not xml_files:
                raise HTTPException(status_code=400, detail="No XML files found in ZIP")

            # Check for mapper.txt to specify which XSLT to use
            mapper_name = xslt_files[0]
            if 'mapper.txt' in zf.namelist():
                specified = zf.read('mapper.txt').decode('utf-8').strip()
                if specified in xslt_files:
                    mapper_name = specified

            # Read XSLT
            xslt_bytes = zf.read(mapper_name)

            # Process each XML
            results = []
            output_zip = io.BytesIO()

            with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as out_zf:
                for xml_name in xml_files:
                    xml_bytes = zf.read(xml_name)
                    result = transformer.transform(xml_bytes, xslt_bytes)

                    base_name = xml_name.rsplit('.', 1)[0]
                    if result.success:
                        out_filename = f"{base_name}_transformed.xml"
                        out_zf.writestr(out_filename, result.output)
                        results.append({
                            "input": xml_name,
                            "output": out_filename,
                            "success": True,
                            "xslt_version": result.xslt_version.value,
                        })
                    else:
                        results.append({
                            "input": xml_name,
                            "output": None,
                            "success": False,
                            "error": result.error,
                        })

                # Add results manifest
                import json
                out_zf.writestr("_results.json", json.dumps(results, indent=2))

            output_zip.seek(0)

            return StreamingResponse(
                output_zip,
                media_type="application/zip",
                headers={
                    "Content-Disposition": 'attachment; filename="transformed.zip"'
                }
            )

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")


@router.post("/transform/inline")
async def transform_inline(
    files: list[UploadFile] = File(...),
    xslt: UploadFile = File(...),
):
    """
    Transform XML files using an uploaded XSLT (not saved).

    Use this for one-off transformations where you don't want to save the mapper.
    """
    transformer = get_transformer()
    xslt_bytes = await xslt.read()

    results = []
    for file in files:
        content = await file.read()
        result = transformer.transform(content, xslt_bytes)

        if result.success:
            results.append({
                "filename": file.filename,
                "success": True,
                "transformed_xml": base64.b64encode(result.output).decode("utf-8"),
                "xslt_version": result.xslt_version.value if result.xslt_version else None,
                "processor": result.processor,
                "error": None,
            })
        else:
            results.append({
                "filename": file.filename,
                "success": False,
                "transformed_xml": None,
                "xslt_version": result.xslt_version.value if result.xslt_version else None,
                "processor": result.processor,
                "error": result.error,
            })

    return {"results": results}


@router.post("/validate")
@limiter.limit("10/minute")
async def validate_files(
    request: Request,
    files: list[UploadFile] = File(...),
    validators: str = Form("helger"),  # comma-separated: "helger,xsd,schematron"
    vesid: Optional[str] = Form(None),
    mapper: Optional[str] = Form(None),
):
    """
    Validate XML files with one or more validators.

    - validators: Comma-separated list (helger, xsd, schematron)
    - vesid: Required for Helger validator
    - mapper: Optional XSL mapper to transform before validation
    """
    validator_types = [v.strip() for v in validators.split(",") if v.strip()]

    results = []
    for file in files:
        content = await file.read()

        try:
            # Transform if mapper specified
            if mapper:
                content = transform_xml(content, mapper)

            # Run validation
            multi_result = await _registry.validate(
                content,
                validator_types=validator_types,
                vesid=vesid,
            )

            results.append({
                "filename": file.filename,
                **multi_result.to_dict(),
                "transformed": mapper is not None,
                "transformed_xml": base64.b64encode(content).decode("utf-8") if mapper else None,
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "overall_success": False,
                "error": str(e),
            })

    return {"results": results}


@router.post("/validate/compare")
@limiter.limit("10/minute")
async def validate_and_compare(
    request: Request,
    files: list[UploadFile] = File(...),
    validators: str = Form("helger,xsd"),  # Run multiple
    vesid: Optional[str] = Form(None),
    mapper: Optional[str] = Form(None),
):
    """
    Validate with multiple validators and compare results.
    Shows which validators agree/disagree on each issue.
    """
    validator_types = [v.strip() for v in validators.split(",") if v.strip()]

    results = []
    for file in files:
        content = await file.read()

        try:
            if mapper:
                content = transform_xml(content, mapper)

            comparison = await _registry.validate_with_comparison(
                content,
                validator_types=validator_types,
                vesid=vesid,
            )

            results.append({
                "filename": file.filename,
                **comparison,
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "error": str(e),
            })

    return {"results": results}


@router.post("/validate/quick")
async def validate_quick(
    files: list[UploadFile] = File(...),
    mapper: Optional[str] = Form(None),
):
    """
    Quick validation using only local validators (XSD, Schematron).
    No rate limits, no external API calls.
    """
    results = []
    for file in files:
        content = await file.read()

        try:
            if mapper:
                content = transform_xml(content, mapper)

            multi_result = await _registry.validate_local_only(content)

            results.append({
                "filename": file.filename,
                **multi_result.to_dict(),
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "error": str(e),
            })

    return {"results": results}
