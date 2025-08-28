from decimal import Decimal
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
    status,
    UploadFile,
    File,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Distributor, Location, Part, POLine, POStatus, PurchaseOrder
from app.schemas import POCreate, POLineCreate, POReceiveLineRequest

templates = Jinja2Templates(directory="app/web/templates")
router = APIRouter(prefix="/ui/po", tags=["UI: Purchase Orders"])


@router.get("", response_class=HTMLResponse)
def ui_list(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(PurchaseOrder)
        .options(joinedload(PurchaseOrder.distributor))
        .order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "purchase_orders/list.html",
        {"request": request, "title": "Purchase Orders", "items": rows},
    )


@router.get("/new", response_class=HTMLResponse)
def ui_new(request: Request, db: Session = Depends(get_db)):
    dists = db.query(Distributor).order_by(Distributor.code).all()
    return templates.TemplateResponse(
        "purchase_orders/form.html",
        {"request": request, "title": "New PO", "dists": dists},
    )


@router.post("/new")
def ui_create(
    code: str = Form(...),
    distributor_id: int = Form(...),
    currency: str = Form("EUR"),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
):
    if db.query(PurchaseOrder).filter(PurchaseOrder.code == code).first():
        raise HTTPException(409, "Purchase order code already exists")
    po = PurchaseOrder(
        code=code,
        distributor_id=distributor_id,
        currency=currency.upper(),
        status=POStatus.OPEN,
    )
    db.add(po)
    db.commit()
    return RedirectResponse(
        url=f"/ui/po/{po.id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/{po_id}", response_class=HTMLResponse)
def ui_detail(po_id: int, request: Request, db: Session = Depends(get_db)):
    po = (
        db.query(PurchaseOrder)
        .options(
            joinedload(PurchaseOrder.distributor),
            joinedload(PurchaseOrder.lines).joinedload(POLine.part),
            joinedload(PurchaseOrder.lines).joinedload(POLine.default_location),
        )
        .get(po_id)
    )
    if not po or not isinstance(po, PurchaseOrder):
        raise HTTPException(404, "Purchase order not found")
    parts = db.query(Part).order_by(Part.ipn).limit(1000).all()
    locs = db.query(Location).order_by(Location.code).all()
    return templates.TemplateResponse(
        "purchase_orders/detail.html",
        {"request": request, "title": po.code, "po": po, "parts": parts, "locs": locs},
    )


@router.post("/{po_id}/lines/new")
def ui_add_line(
    po_id: int,
    part_id: int = Form(...),
    ordered_qty: float = Form(...),
    unit_price: float | None = Form(None),
    distributor_pn: str | None = Form(None),
    default_location_id: int | None = Form(None),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
):
    line = POLine(
        po_id=po_id,
        part_id=part_id,
        ordered_qty=ordered_qty,
        unit_price=unit_price,
        distributor_pn=distributor_pn,
        default_location_id=(
            default_location_id
            if default_location_id not in (None, "", "None")
            else None
        ),
        note=note,
    )
    db.add(line)
    db.commit()
    return RedirectResponse(
        url=f"/ui/po/{po_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{po_id}/lines/{line_id}/receive")
def ui_receive_line(
    po_id: int,
    line_id: int,
    qty: float = Form(...),
    location_code: str | None = Form(None),
    note: str | None = Form(None),
    document: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    from app.services.receiving import receive_po_line

    try:
        receive_po_line(
            db, po_id, line_id, Decimal(qty), location_code, note, upload_file=document
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(
        url=f"/ui/po/{po_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{po_id}/cancel")
def ui_cancel_po(po_id: int, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(404, "Purchase order not found")
    if po.status == POStatus.CLOSED:
        raise HTTPException(409, "Purchase order already closed")
    po.status = POStatus.CANCELLED
    db.commit()
    return RedirectResponse(url="/ui/po", status_code=status.HTTP_303_SEE_OTHER)
