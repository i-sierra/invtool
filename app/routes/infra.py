"""Infra/diagnostic routes (non-prod helpers)."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from app.config import get_settings
from app.utils.htmx import hx_redirect, is_htmx
from app.utils.messages import add_message

router = APIRouter()


@router.get("/demo/flash", tags=["infra"])
def demo_flash(request: Request, msg: str = "Operation completed") -> Response:
    """Add a one-time message and redirect to home (HTMX-aware)."""
    add_message(request, msg, level="success")
    if is_htmx(request):
        return hx_redirect("/")
    return RedirectResponse("/", status_code=303)


@router.get("/debug/error", tags=["infra"])
def debug_error() -> None:
    """Intentionally raise an error to exercise the 500 handler in non-prod."""
    settings = get_settings()
    if settings.env == "prod":
        raise HTTPException(404, "Not found")
    raise RuntimeError("Simulated failure for testing purposes")
