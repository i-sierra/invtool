"""Jinja integration and helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.utils.messages import pop_messages

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def render(
    request: Request, name: str, context: dict[str, Any] | None = None, status_code: int = 200
) -> HTMLResponse:
    """Render a template injecting one-time messages from the session."""
    ctx: dict[str, Any] = {
        "messages": pop_messages(request),
    }
    if context:
        ctx.update(context)
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
