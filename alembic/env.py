from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Ensure 'app' is importable even if 'alembic' runs from a different CWD
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.db import Base  # noqa: E402

settings = get_settings()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Single source of truth: use runtime DB URL (e.g., ./instance/app.db)
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    conf = config.get_section(config.config_ini_section)
    connectable = engine_from_config(conf or {}, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
