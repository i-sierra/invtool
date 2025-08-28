from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.db import get_db
from app.models import Part, PurchaseOrder, POLine, POStatus, StockMovement

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/shortages")
def shortages(db: Session = Depends(get_db)):
    """
    Parts where on_hand + on_order < safety_stock.
    Returns ipn, description, on_hand, on_order, safety_stock, gap.
    """
    # on_hand = sum(StockMovement.qty) per part
    onhand_subq = (
        db.query(
            StockMovement.part_id.label("pid"),
            func.coalesce(func.sum(StockMovement.qty), 0).label("on_hand"),
        )
        .group_by(StockMovement.part_id)
        .subquery()
    )
    # on_order = sum(ordered - received) per part for OPEN/DRAFT POs
    onorder_subq = (
        db.query(
            POLine.part_id.label("pid"),
            func.coalesce(func.sum(POLine.ordered_qty - POLine.received_qty), 0).label(
                "on_order"
            ),
        )
        .join(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
        .filter(PurchaseOrder.status.in_([POStatus.OPEN, POStatus.DRAFT]))
        .group_by(POLine.part_id)
        .subquery()
    )
    rows = (
        db.query(
            Part.ipn,
            Part.description,
            func.coalesce(onhand_subq.c.on_hand, 0).label("on_hand"),
            func.coalesce(onorder_subq.c.on_order, 0).label("on_order"),
            Part.safety_stock.label("safety_stock"),
            (
                func.coalesce(onhand_subq.c.on_hand, 0)
                + func.coalesce(onorder_subq.c.on_order, 0)
                - Part.safety_stock
            ).label("available_minus_ss"),
        )
        .outerjoin(onhand_subq, onhand_subq.c.pid == Part.id)
        .outerjoin(onorder_subq, onorder_subq.c.pid == Part.id)
        .filter(
            (
                func.coalesce(onhand_subq.c.on_hand, 0)
                + func.coalesce(onorder_subq.c.on_order, 0)
            )
            < Part.safety_stock
        )
        .order_by(Part.ipn)
        .all()
    )
    out = []
    for ipn, desc, on_hand, on_order, ss, avail in rows:
        gap = float(ss) - float(on_hand or 0) - float(on_order or 0)
        out.append(
            {
                "ipn": ipn,
                "description": desc,
                "on_hand": float(on_hand or 0),
                "on_order": float(on_order or 0),
                "safety_stock": float(ss or 0),
                "shortage": max(0.0, gap),
            }
        )
    return out


@router.get("/po-overdue")
def po_overdue(db: Session = Depends(get_db)):
    """
    PO lines with outstanding qty and ETA in the past.
    Returns po_code, ipn, outstanding, eta_days_late.
    """
    today = datetime.now()
    rows = (
        db.query(
            PurchaseOrder.code,
            POLine.id,
            POLine.eta,
            POLine.ordered_qty,
            POLine.received_qty,
            Part.ipn,
        )
        .join(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
        .join(Part, Part.id == POLine.part_id)
        .filter(
            PurchaseOrder.status.in_([POStatus.OPEN, POStatus.DRAFT]),
            (POLine.ordered_qty - POLine.received_qty) > 0,
            POLine.eta.isnot(None),
            POLine.eta < today,
        )
        .order_by(POLine.eta.asc())
        .all()
    )
    out = []
    for code, line_id, eta, ordered, received, ipn in rows:
        outstanding = float(ordered) - float(received or 0)
        days_late = (today - eta).days
        out.append(
            {
                "po": code,
                "line_id": line_id,
                "ipn": ipn,
                "outstanding": outstanding,
                "eta": str(eta),
                "days_late": days_late,
            }
        )
    return out
