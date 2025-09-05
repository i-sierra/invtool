"""Application settings using Pydantic."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = Field(default="Inventory Manager")
    env: str = Field(default="dev")
    debug: bool = Field(default=True)
    database_url: str = Field(default="sqlite:///./instance/app.db")
    max_upload_mb: int = Field(default=10)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="INV_",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
