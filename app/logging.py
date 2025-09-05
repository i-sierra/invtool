"""Basic logging configuration."""

import logging


def configure_logging() -> None:
    """Configure logging for the application."""
    # Keep simple, Uvicorn config remains for access logs
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
