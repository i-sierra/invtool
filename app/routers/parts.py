import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Part, StockMovement
from app.schemas import PartCreate, PartRead, PartUpdate
from app.services.ipn import allocate_ipn

router = APIRouter(prefix="/parts", tags=["Parts"])


@router.get("", response_model=list[PartRead])
def list_parts(
    q: Optional[str] = Query(
        None, description="Search by IPN, description or manufacturer PN"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Part)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Part.ipn.ilike(like),
                Part.description.ilike(like),
                Part.manufacturer_pn.ilike(like),
            )
        )
    items = query.order_by(Part.ipn).limit(limit).offset(offset).all()
    return items


@router.get("/{part_id}", response_model=PartRead)
def get_part(part_id: int, db: Session = Depends(get_db)):
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(404, "Part not found")
    return part


IPN_FORMAT = re.compile(r"^\d{6}-\d{2}$")


@router.post("", response_model=PartRead, status_code=201)
def create_part(
    payload: PartCreate,
    ipn_base_family: Optional[str] = None,
    ipn_suffix: Optional[int] = None,
    db: Session = Depends(get_db),
):
    # If no IPN or invalid format, allocate a new one
    if payload.ipn is None or not IPN_FORMAT.match(payload.ipn):
        payload.ipn = allocate_ipn(
            db,
            use_base=ipn_base_family if ipn_base_family else None,
            suffix=ipn_suffix,
        )
        
    # Enforce unique IPN
    exists = db.query(Part).filter(Part.ipn == payload.ipn).first()
    if exists:
        raise HTTPException(400, "Part with this IPN already exists")
    part = Part(**payload.model_dump())
    db.add(part)
    db.commit()
    db.refresh(part)
    return part


@router.put("/{part_id}", response_model=PartRead)
def update_part(part_id: int, payload: PartUpdate, db: Session = Depends(get_db)):
    part = db.query(Part).get(part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(part, k, v)
    db.commit()
    db.refresh(part)
    return part


@router.delete("/{part_id}", status_code=204)
def delete_part(part_id: int, db: Session = Depends(get_db)):
    part = db.query(Part).get(part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    # For safety, prevent deleting parts referenced by stock movements
    used = db.query(StockMovement.id).filter(StockMovement.part_id == part_id).first()
    if used:
        raise HTTPException(409, "Part has stock movements; cannot delete")
    db.delete(part)
    db.commit()
