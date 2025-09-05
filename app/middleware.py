"""Application middlewares (sessions, etc.)."""

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings


def install_middlewares(app: FastAPI) -> None:
    """Install required middlewares."""
    settings = get_settings()
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=24 * 60 * 60)
