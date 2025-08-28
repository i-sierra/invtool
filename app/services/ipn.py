from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import Part
from app.services.codes import next_ipn_base, next_ipn_variant

def ipn_exists(db: Session, ipn: str) -> bool:
    return db.execute(select(Part.id).where(Part.ipn == ipn)).first() is not None

def allocate_ipn(db: Session, *, use_base: Optional[str] = None, suffix: Optional[int] = None) -> str:
    """
    Allocate a new IPN (Internal Part Number).
    If `use_base` is `None`, new family (auto base), suffix default `00` (or given).
    If `use_base` is provided, add variant on that family (suffix default next; or given).
    Block when suffix exceeds 99 or IPN already exists.
    """
    if use_base is None:
        base = next_ipn_base(db)
    else:
        if not (len(use_base) == 6 and use_base.isdigit()):
            raise ValueError("Invalid base format")
        base = use_base
        
    # Suffix: user-chosen or auto
    if suffix is None:
        sfx = next_ipn_variant(db, base)
    else:
        sfx = next_ipn_variant(db, base, preferred_suffix=suffix)

    ipn = f"{base}-{sfx}"
    if ipn_exists(db, ipn):
        # Extremely rare with concurrency / manual edits
        raise ValueError("IPN already exists")

    return ipn