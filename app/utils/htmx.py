"""HTMX helpers."""

from fastapi import Request, Response


def is_htmx(request: Request) -> bool:
    """Check if request is from HTMX."""
    return request.headers.get("HX-Request", "false").lower() == "true"


def hx_redirect(url: str) -> Response:
    """
    Instruct HTMX to redirect client-side.
    For non-HTMX clients, use a standard 303 RedirectResponse instead.
    """
    return Response(status_code=204, headers={"HX-Redirect": url})
