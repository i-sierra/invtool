from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentKind,
    Location,
    Part,
    POLine,
    POStatus,
    PurchaseOrder,
)
from app.routers import stock as stock_api
from app.schemas import ReceiptRequest
from app.services.files import save_document


def receive_po_line(
    db: Session,
    po_id: int,
    line_id: int,
    qty: Decimal,
    location_code: Optional[str],
    note: Optional[str],
    upload_file: Optional[UploadFile] = None,
):
    # Load PO and line
    po = db.get(PurchaseOrder, po_id)
    if not po:
        raise ValueError(f"Purchase order not found")
    if po.status not in (POStatus.OPEN, POStatus.DRAFT):
        raise ValueError(f"Purchase order is not opened")
    line = db.get(POLine, line_id)
    if not line or line.po_id != po.id:
        raise ValueError(f"Purchase order line not found")

    # Compute outstanding and overreceipt
    outstanding = Decimal(line.ordered_qty) - Decimal(line.received_qty)
    if qty <= 0:
        raise ValueError(f"Quantity must be greater than 0 (got {qty})")
    overreceipt = Decimal("0")
    if qty > outstanding and outstanding > 0:
        overreceipt = qty - outstanding

    # Resolve location
    if not location_code:
        if line.default_location_id:
            loc = db.get(Location, line.default_location_id)
            location_code = loc.code if loc else None
        if not location_code:
            raise ValueError(f"Default location not provided or invalid")

    # Build stock receipt request referencing the PO
    part = db.get(Part, line.part_id)
    if not part:
        raise ValueError(f"Part not found")
    payload = ReceiptRequest(
        ipn=part.ipn,
        location_code=location_code,
        qty=qty,
        ref_type="PO",
        ref_id=po.code,
        note=note or "",
    )

    # Perform stock movement via existing API logic (using same DB session)
    created = stock_api.receipt(payload, db)

    # Update line quantities
    line.received_qty = Decimal(line.received_qty) + qty

    # Save attachment if provided
    if upload_file:
        p = save_document(upload_file, subdir="delivery-notes")
        doc = Document(
            kind=DocumentKind.DELIVERY,
            file_path=str(p),
            file_name=upload_file.filename or p.name,
            mime_type=upload_file.content_type,
            size=None,
            stock_movement_id=(
                created.get("movement_id") if isinstance(created, dict) else None
            ),
        )
        db.add(doc)

    # Close PO if all lines fully received
    if all((l.ordered_qty - l.received_qty) <= 0 for l in po.lines):
        po.status = POStatus.CLOSED

    db.commit()
    return {
        "po_id": po.id,
        "line_id": line.id,
        "received": str(qty),
        "overreceipt": str(overreceipt) if overreceipt > 0 else "0",
        "movement_id": (
            created.get("movement_id") if isinstance(created, dict) else None
        ),
    }
