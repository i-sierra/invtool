from fastapi import APIRouter
from app.core.refdata import get_ref_types

router = APIRouter(prefix="/config", tags=["Config"])


@router.get("/ref-types")
def read_ref_types():
    """Returns the reference types mapping as JSON: { "PO": "PO-", ... }."""
    return get_ref_types()
