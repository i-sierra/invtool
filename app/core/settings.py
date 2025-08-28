from __future__ import annotations
import os
from pathlib import Path

DOCS_BASE = Path(os.environ.get("DOCS_BASE", "data/docs")).resolve()


def ensure_dirs():
    DOCS_BASE.mkdir(parents=True, exist_ok=True)
