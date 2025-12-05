"""
Schema and Rules Management Endpoints

Provides endpoints to:
- View status of downloaded schemas/rules
- Trigger sync from GitHub/OASIS
- List available validation rule sets
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional

from app.services.rules_sync import get_rules_sync_service

router = APIRouter()


@router.get("/status")
async def get_schemas_status():
    """
    Get status of all schema and rule sources.

    Returns counts of downloaded XSD schemas and Schematron rules,
    along with sync status for each source.
    """
    service = get_rules_sync_service()
    return service.get_status()


@router.post("/sync")
async def sync_all_schemas(background_tasks: BackgroundTasks):
    """
    Sync all schema and rule sources.

    Downloads:
    - UBL 2.1 XSD schemas from OASIS
    - Peppol BIS 3.0 Schematron from OpenPeppol GitHub
    - EN 16931 validation rules from CEN GitHub

    This runs in the background - check /status for progress.
    """
    service = get_rules_sync_service()

    # Run sync in background
    background_tasks.add_task(service.sync_all)

    return {
        "message": "Sync started in background",
        "check_status": "/api/v1/schemas/status",
    }


@router.post("/sync/{source_id}")
async def sync_source(source_id: str):
    """
    Sync a specific schema/rule source.

    Available sources:
    - ubl: UBL 2.1 XSD schemas
    - peppol-bis: Peppol BIS 3.0 Schematron rules
    - en16931-ubl: EN 16931 validation rules
    """
    service = get_rules_sync_service()
    result = service.sync_source(source_id)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))

    return {
        "source": source_id,
        "success": True,
        "files_copied": result.get("files_copied", 0),
    }


@router.get("/xsd")
async def list_xsd_schemas():
    """List available XSD schemas."""
    from pathlib import Path

    xsd_dir = Path(__file__).parent.parent.parent.parent / "schemas" / "xsd"
    if not xsd_dir.exists():
        return {"schemas": [], "count": 0}

    schemas = []
    for xsd in xsd_dir.glob("*.xsd"):
        schemas.append({
            "name": xsd.stem,
            "filename": xsd.name,
        })

    return {
        "schemas": schemas,
        "count": len(schemas),
        "has_common": (xsd_dir / "common").exists(),
    }


@router.get("/schematron")
async def list_schematron_rules():
    """List available Schematron rule sets."""
    from pathlib import Path

    sch_dir = Path(__file__).parent.parent.parent.parent / "schemas" / "schematron"
    if not sch_dir.exists():
        return {"rule_sets": [], "count": 0}

    rule_sets = []

    # List subdirectories (rule sets)
    for subdir in sch_dir.iterdir():
        if subdir.is_dir():
            files = list(subdir.glob("*.xslt")) + list(subdir.glob("*.sch"))
            rule_sets.append({
                "name": subdir.name,
                "files": len(files),
                "types": {
                    "xslt": len(list(subdir.glob("*.xslt"))),
                    "sch": len(list(subdir.glob("*.sch"))),
                },
            })

    # Also list files in root
    root_files = list(sch_dir.glob("*.xslt")) + list(sch_dir.glob("*.sch"))

    return {
        "rule_sets": rule_sets,
        "root_files": len(root_files),
        "total_sets": len(rule_sets),
    }
