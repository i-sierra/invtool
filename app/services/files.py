from __future__ import annotations
from pathlib import Path
from datetime import datetime
import re
from fastapi import UploadFile
from app.core.settings import DOCS_BASE, ensure_dirs


SAFE_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


def _safe_filename(name: str) -> str:
    """Convert a filename to a safe version, stripping path and unsafe characters."""
    base = name.rsplit("/")[-1].rsplit("\\")[-1]
    base = SAFE_CHARS.sub("_", base.strip()) or "file"
    return base[:128]


def save_document(
    upload: UploadFile, subdir: str, use_year_subfolder: bool = True
) -> Path:
    """
    Save file under `<DOCS_BASE>/<subdir>/<YYYY>` with timestamped basename.
    Returns the absolute path.
    """
    ensure_dirs()
    year = datetime.now().strftime("%Y")
    folder = DOCS_BASE / subdir
    if use_year_subfolder:
        folder = folder / year
    folder.mkdir(parents=True, exist_ok=True)
    stem = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = _safe_filename(upload.filename or "document")
    path = folder / f"{stem}-{safe}"
    with path.open("wb") as f:
        f.write(upload.file.read())
    return path


def delete_document_quietly(path: str | Path) -> bool:
    try:
        p = Path(path)
        p.unlink(missing_ok=True)
        return True
    # Fallback in case `missing_ok` is not supported
    except FileNotFoundError:
        return True
    except Exception:
        return False
