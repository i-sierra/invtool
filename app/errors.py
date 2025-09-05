"""Exception handlers and error pages."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.utils.htmx import is_htmx
from app.web import render

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register application-wide exception handlers."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> HTMLResponse | JSONResponse:
        """Handle HTTP exceptions."""

        # Error 404 - Not Found
        if exc.status_code == 404:
            return render(request, "errors/404.html", {"title": "Page Not Found"}, status_code=404)

        # If JSON is preferred and this is not an HTMX request, answer JSON
        accepts_json = "application/json" in request.headers.get("Accept", "")
        if accepts_json and not is_htmx(request):
            return JSONResponse(
                {"detail": exc.detail, "status_code": exc.status_code}, status_code=exc.status_code
            )

        return render(
            request,
            "errors/500.html",
            {"title": "Error", "code": exc.status_code},
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception(request: Request, exc: RequestValidationError) -> HTMLResponse:
        """Handle request validation errors."""
        context: dict[str, Any] = {"title": "Unprocessable Entity", "errors": exc.errors()}
        return render(request, "errors/422.html", context, status_code=422)

    @app.exception_handler(Exception)
    async def server_exception(request: Request, exc: Exception) -> HTMLResponse:
        """Handle uncaught server exceptions."""
        logger.error("Unhandled exception", exc_info=exc)
        return render(request, "errors/500.html", {"title": "Server Error"}, status_code=500)
