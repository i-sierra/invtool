from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from app.db import get_db
from app.models import (
    PurchaseOrder,
    POLine,
    Distributor,
    Part,
    Location,
    POStatus,
)
from app.schemas import POCreate, PORead, POLineCreate, POLineRead, POReceiveLineRequest
from app.services.receiving import receive_po_line
from app.services.codes import next_po_code

router = APIRouter(prefix="/po", tags=["Purchase Orders"])


@router.get("", response_model=list[PORead])
def list_purchase_orders(db: Session = Depends(get_db)):
    rows = (
        db.query(PurchaseOrder)
        .options(joinedload(PurchaseOrder.lines))
        .order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
        .limit(200)
        .all()
    )
    return rows


@router.post("", response_model=PORead, status_code=201)
def create_purchase_order(payload: POCreate, db: Session = Depends(get_db)):
    code = (payload.code or "").strip()
    if not code:
        code = next_po_code(db)

    if db.query(PurchaseOrder).filter(PurchaseOrder.code == payload.code).first():
        raise HTTPException(409, "Purchase order with this code already exists")
    if not db.get(Distributor, payload.distributor_id):
        raise HTTPException(400, "Distributor ID not found")
    po = PurchaseOrder(
        code=code,
        distributor_id=payload.distributor_id,
        currency=payload.currency.upper(),
        eta=payload.eta,
        note=payload.note,
        status=POStatus.DRAFT,
        created_at=datetime.now(),
    )
    db.add(po)
    db.commit()
    db.refresh(po)
    return po


@router.get("/{po_id}", response_model=PORead)
def get_purchase_order(po_id: int, db: Session = Depends(get_db)):
    po = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.lines)).get(po_id)
    if not po:
        raise HTTPException(404, "Purchase order not found")
    return po


@router.post("/{po_id}/lines", response_model=POLineRead, status_code=201)
def add_purchase_order_line(
    po_id: int, payload: POLineCreate, db: Session = Depends(get_db)
):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(404, "Purchase order not found")
    if po.status not in (POStatus.DRAFT, POStatus.OPEN):
        raise HTTPException(409, "Purchase order is not opened")
    if not db.get(Part, payload.part_id):
        raise HTTPException(404, "Part ID not found")
    if payload.default_location_id and not db.get(
        Location, payload.default_location_id
    ):
        raise HTTPException(404, "Default location not found")

    line = POLine(
        po_id=po.id,
        part_id=payload.part_id,
        distributor_pn=payload.distributor_pn,
        ordered_qty=payload.ordered_qty,
        unit_price=payload.unit_price,
        eta=payload.eta,
        default_location_id=payload.default_location_id,
        note=payload.note,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@router.post("/{po_id}/receive")
def receive_line(
    po_id: int, payload: POReceiveLineRequest, db: Session = Depends(get_db)
):
    try:
        return receive_po_line(
            db=db,
            po_id=po_id,
            line_id=payload.line_id,
            qty=payload.qty,
            location_code=payload.location_code,
            note=payload.note,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{po_id}/cancel", status_code=204)
def cancel_purchase_order(po_id: int, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(404, "Purchase order not found")
    if po.status == POStatus.CLOSED:
        raise HTTPException(409, "Purchase order is already closed")
    po.status = POStatus.CANCELLED
    db.commit()
    return
