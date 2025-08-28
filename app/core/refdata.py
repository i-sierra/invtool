from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

import yaml

# Allow overriding via 'env' variables if needed
REF_TYPES_FILE = Path(os.environ.get("REF_TYPES_FILE", "app/config/ref_types.yaml"))

# Simple file-mtime based cache
_cache: Optional[Dict[str, str]] = None
_mtime: Optional[float] = None


def get_ref_types() -> Dict[str, str]:
    """Return a mapping {code -> prefix} loaded from YAML, cached by mtime"""
    global _cache, _mtime
    try:
        current_mtime = REF_TYPES_FILE.stat().st_mtime
    except FileNotFoundError:
        # Safe default if file is missing
        return {
            "PO": "PO-",
            "RMA": "RMA-",
            "WO": "WO-",
            "JOB": "JOB-",
            "COUNT": "COUNT-",
            "SCRAP": "SCRAP-",
            "MOVE": "MOV-",
            "ADJ": "ADJ-",
        }

    if _cache is not None and _mtime == current_mtime:
        return _cache

    with REF_TYPES_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Normalize: uppercase keys, string prefixes
    mapping = {str(k).upper(): str(v) for k, v in data.items()}
    _cache = mapping
    _mtime = current_mtime
    return _cache
