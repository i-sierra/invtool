"""Infra endpoints: health."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["Infra"])
def health() -> dict[str, str]:
    """Return basic service health."""
    return {"status": "ok"}
