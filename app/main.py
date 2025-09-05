"""API entrypoint and composition."""

from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from app.config import get_settings
from app.routes import health, home

settings = get_settings()


def create_app() -> FastAPI:
    """Create and configure FastAPI app instance."""
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    # Static files (Bootstrap overrides & compiled CSS live under /static/)
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Include routers
    app.include_router(health.router)
    app.include_router(home.router)

    return app


app = create_app()
