from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Distributor, Part, PartDistributor, Preference, PriceBreak
from app.schemas import (
    PartDistributorCreate,
    PartDistributorRead,
    PartDistributorUpdate,
    PriceBreakCreate,
    PriceBreakRead,
)

router = APIRouter(prefix="/parts/{part_id}/distributors", tags=["Part-Distributors"])


def get_part(db: Session, part_id: int) -> Part:
    p = db.query(Part).get(part_id)
    if not p:
        raise HTTPException(404, "Part not found")
    return p


@router.get("", response_model=list[PartDistributorRead])
def list_part_distributors(part_id: int, db: Session = Depends(get_db)):
    get_part(db, part_id)
    rows = (
        db.query(PartDistributor)
        .options(
            joinedload(PartDistributor.distributor),
            joinedload(PartDistributor.price_breaks),
        )
        .filter(PartDistributor.part_id == part_id)
        .order_by(PartDistributor.id)
        .all()
    )
    return rows


@router.post("", response_model=PartDistributorRead, status_code=201)
def add_part_distributor(
    part_id: int, payload: PartDistributorCreate, db: Session = Depends(get_db)
):
    p = get_part(db, part_id)
    d = db.query(Distributor).get(payload.distributor_id)
    if not d:
        raise HTTPException(404, "Distributor not found")

    pd = PartDistributor(
        part_id=p.id,
        distributor_id=d.id,
        distributor_pn=payload.distributor_pn,
        preference=Preference(payload.preference),
        note=payload.note,
    )
    db.add(pd)

    # Ensure only one PREFERRED per part: demote others if this becomes preferred
    if pd.preference == Preference.PREFERRED:
        db.query(PartDistributor).filter(
            PartDistributor.part_id == p.id, PartDistributor.id != pd.id
        ).update({"preference": Preference.ALTERNATE}, synchronize_session=False)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # Likely uniqueness violation
        raise HTTPException(409, "Duplicate distributor + PN for this part") from e

    db.refresh(pd)
    return (
        db.query(PartDistributor)
        .options(
            joinedload(PartDistributor.distributor),
            joinedload(PartDistributor.price_breaks),
        )
        .get(pd.id)
    )


@router.put("/{pd_id}", response_model=PartDistributorRead)
def update_part_distributor(
    part_id: int,
    pd_id: int,
    payload: PartDistributorUpdate,
    db: Session = Depends(get_db),
):
    get_part(db, part_id)
    pd = (
        db.query(PartDistributor)
        .options(
            joinedload(PartDistributor.distributor),
            joinedload(PartDistributor.price_breaks),
        )
        .get(pd_id)
    )
    if not pd or pd.part_id != part_id:
        raise HTTPException(404, "Part-Distributor link not found")

    data = payload.model_dump(exclude_unset=True)
    if "preference" in data and data["preference"] is not None:
        data["preference"] = Preference(data["preference"])
    for k, v in data.items():
        setattr(pd, k, v)

    if pd.preference == Preference.PREFERRED:
        db.query(PartDistributor).filter(
            PartDistributor.part_id == part_id, PartDistributor.id != pd.id
        ).update({"preference": Preference.ALTERNATE}, synchronize_session=False)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(409, "Update violates constraints") from e

    db.refresh(pd)
    return pd


@router.delete("/{pd_id}", status_code=204)
def delete_part_distributor(part_id: int, pd_id: int, db: Session = Depends(get_db)):
    get_part(db, part_id)
    pd = db.query(PartDistributor).get(pd_id)
    if not pd or pd.part_id != part_id:
        raise HTTPException(404, "Part-Distributor link not found")

    db.delete(pd)
    db.commit()


# -------- Price breaks --------


@router.post("/{pd_id}/pricebreaks", response_model=PriceBreakRead, status_code=201)
def add_price_break(
    part_id: int,
    pd_id: int,
    payload: PriceBreakCreate,
    db: Session = Depends(get_db),
):
    get_part(db, part_id)
    pd = db.query(PartDistributor).get(pd_id)
    if not pd or pd.part_id != part_id:
        raise HTTPException(404, "Part-Distributor link not found")

    pb = PriceBreak(
        part_distributor_id=pd.id,
        min_qty=payload.min_qty,
        unit_price=payload.unit_price,
        currency=payload.currency.upper(),
    )
    db.add(pb)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            409, "Duplicate minimum quantity price break for this distributor"
        ) from e

    db.refresh(pb)
    return pb


@router.delete("/{pd_id}/pricebreaks/{pb_id}", status_code=204)
def delete_price_break(
    part_id: int, pd_id: int, pb_id: int, db: Session = Depends(get_db)
):
    get_part(db, part_id)
    pb = db.query(PriceBreak).get(pb_id)
    if not pb or pb.part_distributor_id != pd_id:
        raise HTTPException(404, "Price break not found")

    db.delete(pb)
    db.commit()
