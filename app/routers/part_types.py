from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PartType
from app.schemas import PartTypeCreate, PartTypeRead

router = APIRouter(prefix="/part_types", tags=["Part Types"])


@router.get("", response_model=List[PartTypeRead])
def list_part_types(db: Session = Depends(get_db)):
    return db.query(PartType).order_by(PartType.code).all()


@router.post("", response_model=PartTypeRead, status_code=201)
def create_part_type(payload: PartTypeCreate, db: Session = Depends(get_db)):
    exists = db.query(PartType).filter(PartType.code == payload.code).first()
    if exists:
        raise HTTPException(status_code=409, detail="Part type already exists")
    pt = PartType(code=payload.code, label=payload.label, parent_id=payload.parent_id)
    db.add(pt)
    db.commit()
    db.refresh(pt)
    return pt
