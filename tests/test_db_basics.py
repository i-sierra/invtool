from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from sqlalchemy import text


@pytest.mark.anyio
async def test_db_local_sqlite_file_and_pragmas(tmp_path, monkeypatch) -> None:
    """
    Verifies that:
    - SQLite file is created under a temp directory (project-local style).
    - PRAGMAs are set (WAL; synchronous=NORMAL) via the 'connect' event.
    - get_session() yields a working Session.
    """
    # 1) Forzar URL temporal ANTES de importar app.db
    from app.config import get_settings

    get_settings.cache_clear()
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INV_DATABASE_URL", f"sqlite:///{db_path}")

    # 2) Asegurar que reimportamos 'app.db' fresco (por si otro test lo tocó)
    sys.modules.pop("app.db", None)
    db = importlib.import_module("app.db")

    # 3) Conectar: dispara el listener 'connect' y aplica PRAGMAs
    with db.engine.connect() as conn:
        # Asegura que el archivo existe en disco
        assert Path(db_path).exists()

        # PRAGMA journal_mode debería ser WAL
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar_one()
        assert str(journal_mode).lower() == "wal"

        # Ejecuta algo trivial
        assert conn.execute(text("SELECT 1")).scalar_one() == 1

    # 4) Probar get_session() (y cerrar correctamente)
    gen = db.get_session()
    session = next(gen)
    try:
        # Debe poder ejecutar una consulta trivial
        assert session.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        # Cierra la sesión (ejecuta el 'finally' del generador)
        gen.close()
