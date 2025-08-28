from __future__ import annotations
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

"""
This module manages the generation of sequential codes for documents, movements, and parts,
using a counters table in the database. It ensures uniqueness and order of codes.
"""


def _yy() -> str:
    return datetime.now().strftime("%y")


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _next_seq(
    db: Session,
    name: str,
    scope1: Optional[str],
    scope2: Optional[str],
    start_at: int = 1,
) -> int:
    """
    Atomic-ish counter using SQLite's UPSERT. Works on Postgres too.
    Tries RETURNING; falls back to SELECT when RETURNING unsupported.
    """
    conn = db.connection()
    try:
        row = conn.execute(
            text(
                """
INSERT INTO counters (name, scope1, scope2, seq, updated_at)
VALUES (:n, :s1, :s2, :start_minus_1, :ts)
ON CONFLICT(name, scope1, scope2)
DO UPDATE SET seq = counters.seq + 1, updated_at = :ts
RETURNING seq
"""
            ),
            {
                "n": name,
                "s1": scope1,
                "s2": scope2,
                "start_minus_1": start_at - 1,
                "ts": _now_str(),
            },
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to get next sequence")
        return int(row[0])
    except Exception:
        # Fallback: manual upsert within the transaction
        cur = conn.execute(
            text(
                "SELECT seq FROM counters WHERE name=:n AND scope1 IS :s1 AND scope2 IS :s2"
            ),
            {"n": name, "s1": scope1, "s2": scope2},
        ).fetchone()
        if cur is None:
            conn.execute(
                text(
                    "INSERT OR IGNORE INTO counters (name, scope1, scope2, seq, updated_at) VALUES (:n,:s1,:s2,:seq,:ts)"
                ),
                {
                    "n": name,
                    "s1": scope1,
                    "s2": scope2,
                    "seq": start_at - 1,
                    "ts": _now_str(),
                },
            )
        conn.execute(
            text(
                "UPDATE counters SET seq = seq + 1, updated_at = :ts WHERE name=:n AND scope1 IS :s1 AND scope2 IS :s2"
            ),
            {"n": name, "s1": scope1, "s2": scope2, "ts": _now_str()},
        )
        row = conn.execute(
            text(
                "SELECT seq FROM counters WHERE name=:n AND scope1 IS :s1 AND scope2 IS :s2"
            ),
            {"n": name, "s1": scope1, "s2": scope2},
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to get next sequence")
        return int(row[0])


MOV_PREFIX = {
    "receipt": "RCV",
    "issue": "ISS",
    "transfer-in": "TRI",
    "transfer-out": "TRO",
    "adjust": "ADJ",
}


# ----- Purchase Orders -----
def next_po_code(db: Session) -> str:
    yy = _yy()
    seq = _next_seq(db, name="PO", scope1=yy, scope2=None, start_at=1)
    return f"PO-{yy}-{seq:04d}"


# ----- Movements -----
def next_movement_code(db: Session, reason: str) -> str:
    """Generates the next movement code according to the type (receipt, issue, etc)."""
    yy = _yy()
    prefix = MOV_PREFIX.get(reason)
    if not prefix:
        prefix = "MOV"
    seq = _next_seq(db, name=f"MOV:{prefix}", scope1=yy, scope2=None, start_at=1)
    return f"{prefix}-{yy}-{seq:04d}"


# ----- Parts IPN -----
def next_ipn_base(db: Session, start: int = 100000) -> str:
    """
    Returns the next 6-digit base (as string), starting at 'start'.
    """
    seq = _next_seq(db, name="IPN_BASE", scope1="GLOBAL", scope2=None, start_at=start)
    return f"{seq:06d}"


def next_ipn_variant(
    db: Session, base: str, *, preferred_suffix: Optional[int] = None
) -> str:
    """
    Returns the 2-digit suffix for the given base.
    - If preferred_suffix is given, reserve it (if free) and bump the counter if needed.
    - Blocks when suffix would exceed 99.
    """
    if len(base) != 6 or not base.isdigit():
        raise ValueError("Invalid base")
    if preferred_suffix is not None:
        if not (0 <= preferred_suffix <= 99):
            raise ValueError("Suffix must be between 00 and 99")

    # We use counter name 'IPN_VAR' scoped by base
    if preferred_suffix is None:
        n = _next_seq(
            db, name="IPN_VAR", scope1=base, scope2=None, start_at=0
        )  # start at 0 -> "-00"
        if n > 99:
            raise ValueError("Family exhausted (00-99)")
        return f"{n:02d}"
    else:
        # Ensure counter >= preferred_suffix
        conn = db.connection()
        row = conn.execute(
            text(
                "SELECT seq FROM counters WHERE name='IPN_VAR' AND scope1=:b AND scope2 IS NULL"
            ),
            {"b": base},
        ).fetchone()
        cur = int(row[0]) if row else -1
        if preferred_suffix <= cur:
            # OK, the counter is already ahead; just return if free
            return f"{preferred_suffix:02d}"
        if preferred_suffix > 99:
            raise ValueError("Family exhausted (00-99)")
        # Upsert counter to the chosen suffix (so next will be >= chosen)
        if row is None:
            conn.execute(
                text(
                    "INSERT INTO counters (name, scope1, scope2, seq, updated_at) VALUES ('IPN_VAR', :b, NULL, :seq, :ts)"
                ),
                {"b": base, "seq": preferred_suffix, "ts": _now_str()},
            )
        else:
            conn.execute(
                text(
                    "UPDATE counters SET seq=:seq, updated_at=:ts WHERE name='IPN_VAR' AND scope1=:b AND scope2 IS NULL"
                ),
                {"b": base, "seq": preferred_suffix, "ts": _now_str()},
            )
        return f"{preferred_suffix:02d}"
