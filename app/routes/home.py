"""Web routes (HTML) using Jinja2 + HTMX."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web import render

router = APIRouter()


@router.get("/", response_class=HTMLResponse, tags=["web"])
def index(request: Request) -> HTMLResponse:
    """Render home page."""
    return render(request, "index.html", {"title": "Inventory Manager"})
