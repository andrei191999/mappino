from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.lookup_service import LookupService
from app.services.codelist_service import CodeListService
from app.exceptions import SchemeNotFoundError

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class LookupRequest(BaseModel):
    ids: list[str]
    schemes: list[str] = []  # ICDs like ["0208", "0088", "0106"]
    use_test_sml: bool = False
    merge_pd_discovery: bool = True


class LookupResult(BaseModel):
    input: str
    participant: str
    registered: bool | str
    business_name: str
    country: str
    doc_types: int | str
    error: str


class ValidateIdRequest(BaseModel):
    icd: str
    identifier: str


@router.post("/", response_model=list[LookupResult])
@limiter.limit("30/minute")
async def lookup_participants(request: Request, req: LookupRequest):
    """
    Lookup Peppol participants by ID.
    - ids: list of identifiers (BE numbers, GLN, ISO6523, etc.)
    - schemes: fallback ICD schemes to try if no scheme detected
    """
    svc = LookupService(
        fallback_icds=req.schemes if req.schemes else None,
        use_test_sml=req.use_test_sml,
        merge_pd_discovery=req.merge_pd_discovery,
    )
    results = []
    for raw_id in req.ids:
        rows = svc.lookup(raw_id)
        results.extend(rows)
    return results


# ==================== CODE LIST ENDPOINTS ====================

@router.get("/schemes")
async def list_schemes(
    country: Optional[str] = Query(None, description="Filter by country code (e.g., BE, NL, DE)"),
    include_inactive: bool = Query(False, description="Include deprecated/removed schemes"),
    search: Optional[str] = Query(None, description="Search by name, ICD, or country"),
):
    """
    List Peppol participant identifier schemes (ICDs).
    Data is auto-synced from OpenPeppol code lists.
    """
    svc = CodeListService()

    if search:
        schemes = svc.search_schemes(search)
    elif country:
        schemes = svc.get_schemes_by_country(country)
    else:
        schemes = svc.get_all_schemes(include_inactive=include_inactive)

    return {
        "schemes": [
            {
                "icd": s.get("iso6523"),
                "scheme_id": s.get("schemeid"),
                "name": s.get("scheme-name"),
                "country": s.get("country"),
                "state": s.get("state"),
                "registrable": s.get("registrable", False),
                "validation_rules": s.get("validation-rules"),
            }
            for s in schemes
        ],
        "count": len(schemes),
    }


@router.get("/schemes/status")
async def codelist_status():
    """Get code list sync status"""
    svc = CodeListService()
    return svc.get_status()


@router.post("/schemes/refresh")
async def refresh_codelists():
    """Force refresh code lists from OpenPeppol"""
    svc = CodeListService()
    return svc.force_refresh()


@router.post("/schemes/validate")
async def validate_identifier(req: ValidateIdRequest):
    """Validate an identifier against a scheme's rules"""
    svc = CodeListService()
    result = svc.validate_identifier(req.icd, req.identifier)
    scheme = svc.get_scheme_by_icd(req.icd)
    return {
        **result,
        "icd": req.icd,
        "identifier": req.identifier,
        "scheme_name": scheme.get("scheme-name") if scheme else None,
    }


@router.get("/schemes/{icd}")
async def get_scheme(icd: str):
    """Get details for a specific ICD scheme"""
    svc = CodeListService()
    scheme = svc.get_scheme_by_icd(icd)
    if not scheme:
        raise SchemeNotFoundError(icd)
    return {
        "icd": scheme.get("iso6523"),
        "scheme_id": scheme.get("schemeid"),
        "name": scheme.get("scheme-name"),
        "country": scheme.get("country"),
        "state": scheme.get("state"),
        "issuing_agency": scheme.get("issuing-agency"),
        "structure": scheme.get("structure"),
        "display": scheme.get("display"),
        "examples": scheme.get("examples"),
        "validation_rules": scheme.get("validation-rules"),
        "registrable": scheme.get("registrable", False),
    }
