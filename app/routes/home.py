"""Web routes (HTML) using Jinja2 + HTMX."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.templating import _TemplateResponse

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


@router.get("/", response_class=HTMLResponse, tags=["web"])
def index(request: Request) -> _TemplateResponse:
    """Render home page."""
    return templates.TemplateResponse(request, "index.html", {"title": "Inventory Manager"})
