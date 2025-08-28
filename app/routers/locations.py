from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Location
from app.schemas import LocationCreate, LocationRead

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get("", response_model=list[LocationRead])
def list_locations(db: Session = Depends(get_db)):
    return db.query(Location).order_by(Location.code).all()


@router.post("", response_model=LocationRead, status_code=201)
def create_location(payload: LocationCreate, db: Session = Depends(get_db)):
    exists = db.query(Location).filter(Location.code == payload.code).first()
    if exists:
        raise HTTPException(status_code=409, detail="Location code already exists")
    loc = Location(code=payload.code, name=payload.name, parent_id=payload.parent_id)
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc
