from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    Location,
    MovementReason,
    Part,
    POStatus,
    PurchaseOrder,
    POLine,
    StockMovement,
)
from app.schemas import (
    AdjustRequest,
    IssueRequest,
    ReceiptRequest,
    StockByLocation,
    StockSnapshot,
    TransferRequest,
)
from app.services.codes import next_movement_code

router = APIRouter(prefix="/stock", tags=["Stock"])

# -------- Helpers --------


def get_part_by_ipn(db: Session, ipn: str) -> Part:
    part = db.query(Part).filter(Part.ipn == ipn).first()
    if not part:
        raise HTTPException(404, f"Part with IPN '{ipn}' not found")
    return part


def get_location_by_code(db: Session, code: str) -> Location:
    location = db.query(Location).filter(Location.code == code).first()
    if not location:
        raise HTTPException(404, f"Location with code '{code}' not found")
    return location


def stock_on_hand(
    db: Session, part_id: int, location_id: Optional[int] = None
) -> Decimal:
    qry = select(func.coalesce(func.sum(StockMovement.qty), 0)).where(
        StockMovement.part_id == part_id
    )
    if location_id is not None:
        qry = qry.where(StockMovement.location_id == location_id)
    return Decimal(db.execute(qry).scalar_one())


def assert_sufficient(db: Session, part_id: int, location_id: int, qty_needed: Decimal):
    current = stock_on_hand(db, part_id, location_id)
    if current < qty_needed:
        raise HTTPException(
            409,
            f"Insufficient stock at location (have: {current}, need: {qty_needed})",
        )


# -------- Endpoints --------


@router.post("/receipt")
def receipt(payload: ReceiptRequest, db: Session = Depends(get_db)):
    part = get_part_by_ipn(db, payload.ipn)
    loc = get_location_by_code(db, payload.location_code)
    mv = StockMovement(
        ts=datetime.now(),
        part_id=part.id,
        location_id=loc.id,
        qty=payload.qty,
        reason=MovementReason.RECEIPT,
        ref_type=payload.ref_type,
        ref_id=payload.ref_id,
        note=payload.note,
    )
    mv.code = next_movement_code(db, reason=MovementReason.RECEIPT.value)
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return {"status": "ok", "movement_id": mv.id}


@router.post("/issue")
def issue(payload: IssueRequest, db: Session = Depends(get_db)):
    part = get_part_by_ipn(db, payload.ipn)
    loc = get_location_by_code(db, payload.location_code)
    assert_sufficient(db, part.id, loc.id, payload.qty)
    mv = StockMovement(
        part_id=part.id,
        location_id=loc.id,
        qty=-Decimal(payload.qty),
        reason=MovementReason.ISSUE,
        ref_type=payload.ref_type,
        ref_id=payload.ref_id,
        note=payload.note,
    )
    mv.code = next_movement_code(db, reason=MovementReason.ISSUE.value)
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return {"status": "ok", "movement_id": mv.id}


@router.post("/transfer")
def transfer(payload: TransferRequest, db: Session = Depends(get_db)):
    if payload.from_location == payload.to_location:
        raise HTTPException(400, "Source and destination are the same location")
    part = get_part_by_ipn(db, payload.ipn)
    loc_from = get_location_by_code(db, payload.from_location)
    loc_to = get_location_by_code(db, payload.to_location)
    qty = Decimal(payload.qty)

    assert_sufficient(db, part.id, loc_from.id, qty)

    try:
        # Atomic operation: output movement
        mv_out = StockMovement(
            part_id=part.id,
            location_id=loc_from.id,
            qty=-qty,
            reason=MovementReason.TRANSFER_OUT,
            ref_type=payload.ref_type,
            ref_id=payload.ref_id,
            note=payload.note,
        )
        mv_out.code = next_movement_code(db, reason=MovementReason.TRANSFER_OUT.value)
        db.add(mv_out)
        # Atomic operation: input movement
        mv_in = StockMovement(
            part_id=part.id,
            location_id=loc_to.id,
            qty=qty,
            reason=MovementReason.TRANSFER_IN,
            ref_type=payload.ref_type,
            ref_id=payload.ref_id,
            note=payload.note,
        )
        mv_in.code = next_movement_code(db, reason=MovementReason.TRANSFER_IN.value)
        db.add(mv_in)

        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    return {"status": "ok", "movement_id": mv_in.id}


@router.post("/adjust")
def adjust(payload: AdjustRequest, db: Session = Depends(get_db)):
    if payload.direction not in (-1, 1):
        raise HTTPException(400, "Direction must be +1 or -1")

    part = get_part_by_ipn(db, payload.ipn)
    loc = get_location_by_code(db, payload.location_code)
    qty_signed = Decimal(payload.qty) * Decimal(payload.direction)

    # If adjusting downwards, check for sufficient stock
    if qty_signed < 0:
        assert_sufficient(db, part.id, loc.id, -qty_signed)

    mv = StockMovement(
        part_id=part.id,
        location_id=loc.id,
        qty=qty_signed,
        reason=MovementReason.ADJUST,
        ref_type=payload.ref_type,
        ref_id=payload.ref_id,
        note=payload.note,
    )
    mv.code = next_movement_code(db, reason=MovementReason.ADJUST.value)
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return {"status": "ok", "movement_id": mv.id}


@router.get("/parts/{ipn}/onhand", response_model=StockSnapshot)
def get_on_hand_stock(ipn: str, db: Session = Depends(get_db)):
    part = get_part_by_ipn(db, ipn)
    # Total stock on hand
    total = stock_on_hand(db, part.id)
    # Stock on hand per location
    rows = (
        db.query(Location.code, func.coalesce(func.sum(StockMovement.qty), 0))
        .join(StockMovement, StockMovement.location_id == Location.id)
        .filter(StockMovement.part_id == part.id)
        .group_by(Location.code)
        .order_by(Location.code)
        .all()
    )
    by_loc = [StockByLocation(location_code=r[0], qty=r[1]) for r in rows]
    return StockSnapshot(ipn=ipn, total_on_hand=total, by_location=by_loc)


@router.get("/parts/{ipn}/onorder")
def on_order(ipn: str, db: Session = Depends(get_db)):
    part = db.query(Part).filter(Part.ipn == ipn).first()
    if not part:
        raise HTTPException(404, "Part not found")
    q = (
        db.query(
            func.coalesce(
                func.sum(POLine.ordered_qty - POLine.received_qty),
                0,
            )
        )
        .join(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
        .filter(
            POLine.part_id == part.id,
            PurchaseOrder.status.in_((POStatus.DRAFT, POStatus.OPEN)),
            (POLine.ordered_qty - POLine.received_qty) > 0,
        )
    ).scalar()
    return {"ipn": ipn, "on_order": float(q or 0)}
