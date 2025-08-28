import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_data_dir: str = Field("./data", alias="APP_DATA_DIR")
    database_filename: str = Field("inventory.db", alias="DATABASE_FILENAME")
    database_url: Optional[str] = Field(None, alias="DATABASE_URL")

    app_env: str = Field("dev", alias="APP_ENV")

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        data_dir = Path(self.app_data_dir).expanduser().resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / self.database_filename

        return f"sqlite:///{db_path.as_posix()}"

    @property
    def attachments_dir(self) -> Path:
        p = Path(self.app_data_dir).expanduser().resolve() / "attachments"
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
