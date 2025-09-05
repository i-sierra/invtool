"""API entrypoint and composition."""

from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from app.config import get_settings
from app.errors import register_exception_handlers
from app.logging import configure_logging
from app.middleware import install_middlewares
from app.routes import health, home
from app.routes import infra as infra_routes

settings = get_settings()
configure_logging()


def create_app(*, force_debug: bool | None = None) -> FastAPI:
    """
    Create and configure a FastAPI application instance.

    force_debug:
        - None: use settings.debug.
        - True: enable debug mode.
        - False: force non-debug mode (for 500.html testing).
    """
    # Clear cached settings to ensure fresh config on app creation (tests with monkeypatch)
    get_settings.cache_clear()
    settings = get_settings()

    debug = settings.debug if force_debug is None else bool(force_debug)
    app = FastAPI(title=settings.app_name, debug=debug)

    # Static files (Bootstrap overrides & compiled CSS live under /static/)
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Middlewares
    install_middlewares(app)

    # Include routers
    app.include_router(health.router)
    app.include_router(home.router)
    app.include_router(infra_routes.router)

    # Error handlers
    register_exception_handlers(app)

    return app


app = create_app()
