from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Distributor
from app.schemas import DistributorCreate, DistributorRead, DistributorUpdate

router = APIRouter(prefix="/distributors", tags=["distributors"])


@router.get("", response_model=list[DistributorRead])
def list_distributors(q: Optional[str] = Query(None), db: Session = Depends(get_db)):
    qry = db.query(Distributor)
    if q:
        like = f"%{q}%"
        qry = qry.filter(
            (Distributor.code.ilike(like)) | (Distributor.name.ilike(like))
        )
    return qry.order_by(Distributor.code).all()


@router.post("", response_model=DistributorRead, status_code=201)
def create_distributor(payload: DistributorCreate, db: Session = Depends(get_db)):
    if db.query(Distributor).filter(Distributor.code == payload.code).first():
        raise HTTPException(status_code=409, detail="Distributor code already exists")
    d = Distributor(**payload.model_dump())
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@router.put("/{dist_id}", response_model=DistributorRead)
def update_distributor(
    dist_id: int, payload: DistributorUpdate, db: Session = Depends(get_db)
):
    d = db.query(Distributor).get(dist_id)
    if not d or not isinstance(d, Distributor):
        raise HTTPException(status_code=404, detail="Distributor not found")
    d.name = payload.name
    db.commit()
    db.refresh(d)
    return d


@router.delete("/{dist_id}", status_code=204)
def delete_distributor(dist_id: int, db: Session = Depends(get_db)):
    d = db.query(Distributor).get(dist_id)
    if not d:
        raise HTTPException(status_code=404, detail="Distributor not found")
    # Prevent deletion if linked to parts
    if d.part_distributors:
        raise HTTPException(
            status_code=400, detail="Cannot delete distributor: in use by parts"
        )
    db.delete(d)
    db.commit()
