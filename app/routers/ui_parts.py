from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import (
    Distributor,
    Document,
    DocumentKind,
    Lifecycle,
    Location,
    Part,
    PartDistributor,
    PartType,
    Preference,
    PriceBreak,
    StockMovement,
)
from app.routers.parts import IPN_FORMAT
from app.schemas import (
    PartCreate,
    PartDistributorCreate,
    PartDistributorUpdate,
    PartUpdate,
    PriceBreakCreate,
    ReceiptRequest,
    IssueRequest,
    TransferRequest,
    AdjustRequest,
)
from app.routers import stock as stock_api
from app.services.files import delete_document_quietly, save_document
from app.services.ipn import allocate_ipn

templates = Jinja2Templates(directory="app/web/templates")
router = APIRouter(prefix="/ui/parts", tags=["UI: Parts"])


def _location_codes(db: Session) -> list[str]:
    """Returns a list of location codes for display."""
    return [row[0] for row in db.query(Location.code).order_by(Location.code).all()]


def _recent_movements_for_part(db: Session, part_id: int, limit: int = 20):
    # Join to get location code in one go
    rows = (
        db.query(
            StockMovement.ts,
            StockMovement.reason,
            Location.code.label("location_code"),
            StockMovement.qty,
            StockMovement.ref_type,
            StockMovement.ref_id,
            StockMovement.note,
            StockMovement.user,
        )
        .join(Location, Location.id == StockMovement.location_id)
        .filter(StockMovement.part_id == part_id)
        .order_by(StockMovement.id.desc())
        .limit(limit)
        .all()
    )
    return rows


def _render_movements_fragment(
    request: Request, db: Session, part: Part, message: Optional[str], error: bool
):
    return templates.TemplateResponse(
        "parts/_movements.html",
        {
            "request": request,
            "part": part,
            "location_codes": _location_codes(db),
            "rows": _recent_movements_for_part(db, part.id),
            "message": message,
            "error": error,
        },
    )


def _type_dict(db: Session) -> dict[int, str]:
    """Returns map {part_type_id: 'CODE – Label'} for display."""
    rows = db.query(PartType.id, PartType.code, PartType.label).all()
    return {r[0]: f"{r[1]} – {r[2]}" for r in rows}


def _list_part_docs(db: Session, part_id: int):
    from app.models import Document

    rows = (
        db.query(Document)
        .filter(Document.part_id == part_id)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .all()
    )
    # Format for template
    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "kind": r.kind.value if hasattr(r.kind, "value") else r.kind,
                "file_name": r.file_name,
                "created_at": r.created_at,
            }
        )
    return out


@router.get("", response_class=HTMLResponse)
def ui_list(request: Request, q: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Part)
    if q:
        query = query.filter(
            Part.ipn.ilike(f"%{q}%")
            | Part.manufacturer.ilike(f"%{q}%")
            | Part.description.ilike(f"%{q}%")
        )
    parts = query.order_by(Part.ipn).limit(100).all()
    return templates.TemplateResponse(
        "parts/list.html",
        {
            "request": request,
            "title": "Parts",
            "parts": parts,
            "type_map": _type_dict(db),
            "q": q or "",
        },
    )


@router.get("/table", response_class=HTMLResponse)
def ui_table(request: Request, q: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Part)
    if q:
        query = query.filter(
            Part.ipn.ilike(f"%{q}%")
            | Part.manufacturer.ilike(f"%{q}%")
            | Part.description.ilike(f"%{q}%")
        )
    parts = query.order_by(Part.ipn).limit(100).all()
    return templates.TemplateResponse(
        "parts/_table.html",
        {"request": request, "parts": parts, "type_map": _type_dict(db)},
    )


@router.get("/new", response_class=HTMLResponse)
def ui_new_part(request: Request, db: Session = Depends(get_db)):
    types = db.query(PartType).order_by(PartType.code).all()
    return templates.TemplateResponse(
        "parts/form.html",
        {
            "request": request,
            "title": "New Part",
            "part": None,
            "types": types,
            "action": "/ui/parts",
        },
    )


@router.post("", response_class=HTMLResponse)
def ui_create_part(
    request: Request,
    ipn: Optional[str] = Form(None),
    ipn_family_base: Optional[str] = Form(None),
    ipn_suffix: Optional[int] = Form(None),
    description: str = Form(...),
    manufacturer: Optional[str] = Form(None),
    manufacturer_pn: Optional[str] = Form(None),
    uom: str = Form("pcs"),
    lifecycle: str = Form("active"),
    part_type_id: Optional[int] = Form(None),
    is_compound: str = Form(None),
    db: Session = Depends(get_db),
):
    # Normalize `lifecycle`
    try:
        lc = Lifecycle(lifecycle)
    except ValueError:
        lc = Lifecycle.ACTIVE

    # Build IPN
    if not ipn or not IPN_FORMAT.match(ipn):

        # Validate base if provided
        base = ipn_family_base.strip() if ipn_family_base else None
        if base and not (len(base) == 6 and base.isdigit() and int(base) >= 100000):
            return templates.TemplateResponse(
                "parts/new.html",
                {
                    "request": request,
                    "types": db.query(PartType).all(),
                    "message": "Invalid IPN family base (must be 6 digits ≥ 100000).",
                    "error": True,
                },
                status_code=400,
            )

        # Validate suffix if provided
        if ipn_suffix is not None and not (0 <= ipn_suffix <= 99):
            return templates.TemplateResponse(
                "parts/new.html",
                {
                    "request": request,
                    "types": db.query(PartType).all(),
                    "message": "Invalid IPN suffix (must be between 0 and 99).",
                    "error": True,
                },
                status_code=400,
            )

        try:
            ipn_value = allocate_ipn(db, use_base=base, suffix=ipn_suffix)
        except ValueError as e:
            return templates.TemplateResponse(
                "parts/new.html",
                {
                    "request": request,
                    "types": db.query(PartType).all(),
                    "message": str(e),
                    "error": True,
                },
                status_code=400,
            )
    # Manual IPN (expert mode)
    else:
        ipn_value = ipn.strip()
        if not IPN_FORMAT.match(ipn_value):
            return templates.TemplateResponse(
                "parts/new.html",
                {
                    "request": request,
                    "types": db.query(PartType).all(),
                    "message": "Invalid IPN format (must be XXXXXX-XX)",
                    "error": True,
                },
                status_code=400,
            )

    if db.query(Part).filter(Part.ipn == ipn).first():
        raise HTTPException(status_code=409, detail="Part with this IPN already exists")

    p = Part(
        ipn=ipn_value,
        description=description.strip(),
        manufacturer=(manufacturer or None),
        manufacturer_pn=(manufacturer_pn or None),
        lifecycle=lc,
        uom=(uom or "pcs"),
        part_type_id=part_type_id,
        is_compound=False if is_compound in (None, "", "None") else True,
    )
    db.add(p)
    try:
        db.commit()
    except Exception:
        db.rollback()
        return templates.TemplateResponse(
            "parts/new.html",
            {
                "request": request,
                "types": db.query(PartType).all(),
                "message": "IPN already exists.",
                "error": True,
            },
            status_code=409,
        )
    return RedirectResponse(
        url=f"/ui/parts/{p.id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/{part_id}", response_class=HTMLResponse)
def ui_part_detail(part_id: int, request: Request, db: Session = Depends(get_db)):
    part = db.query(Part).get(part_id)
    if not part or not isinstance(part, Part):
        raise HTTPException(status_code=404, detail="Part not found")
    tlabel = None
    if part.part_type_id:
        t = db.query(PartType).get(part.part_type_id)
        if not t or not isinstance(t, PartType):
            raise HTTPException(status_code=404, detail="Part type not found")
        tlabel = f"{t.code} – {t.label}"
    return templates.TemplateResponse(
        "parts/detail.html",
        {"request": request, "title": part.ipn, "part": part, "type_label": tlabel},
    )


@router.get("/{part_id}/stock", response_class=HTMLResponse)
def ui_detail_stock(part_id: int, _: Request, db: Session = Depends(get_db)):
    part = db.query(Part).get(part_id)
    if not part or not isinstance(part, Part):
        raise HTTPException(status_code=404, detail="Part not found")
    # Aggregate stock by location
    rows = (
        db.query(Location.code, func.coalesce(func.sum(StockMovement.qty), 0))
        .join(StockMovement, StockMovement.location_id == Location.id)
        .filter(StockMovement.part_id == part_id)
        .group_by(Location.code)
        .order_by(Location.code)
        .all()
    )
    total = sum(r[1] for r in rows) if rows else 0
    # Render a very small HTML fragment
    html = ["<table><thead><tr><th>Location</th><th>Quantity</th></tr></thead><tbody>"]
    if not rows:
        html.append("<tr><td colspan='2'>No stock.</td></tr>")
    else:
        for code, qty in rows:
            html.append(f"<tr><td>{code}</td><td>{qty}</td></tr>")
        html.append(
            f"<tr><td><strong>Total</strong></td><td><strong>{total}</strong></td></tr>"
        )
    html.append("</tbody></table>")
    return HTMLResponse("".join(html))


@router.get("/{part_id}/edit", response_class=HTMLResponse)
def ui_edit(part_id: int, request: Request, db: Session = Depends(get_db)):
    part = db.query(Part).get(part_id)
    if not part or not isinstance(part, Part):
        raise HTTPException(status_code=404, detail="Part not found")
    types = db.query(PartType).order_by(PartType.code).all()
    return templates.TemplateResponse(
        "parts/form.html",
        {
            "request": request,
            "title": f"Edit {part.ipn}",
            "part": part,
            "types": types,
            "action": f"/ui/parts/{part.id}/edit",
        },
    )


@router.post("/{part_id}/edit", response_class=HTMLResponse)
def ui_update(
    part_id: int,
    request: Request,
    description: str = Form(...),
    manufacturer: Optional[str] = Form(None),
    manufacturer_pn: Optional[str] = Form(None),
    uom: str = Form("pcs"),
    part_type_id: Optional[int] = Form(None),
    is_compound: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    part = db.query(Part).get(part_id)
    if not part or not isinstance(part, Part):
        raise HTTPException(status_code=404, detail="Part not found")
    payload = PartUpdate(
        description=description,
        manufacturer=manufacturer,
        manufacturer_pn=manufacturer_pn,
        uom=uom,
        part_type_id=part_type_id if part_type_id not in (None, "", "None") else None,
        is_compound=bool(is_compound),
    )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(part, k, v)
    db.commit()
    return RedirectResponse(
        url=f"/ui/parts/{part.id}", status_code=status.HTTP_303_SEE_OTHER
    )


# ---- Part Distributors ----


@router.get("/{part_id}/distributors", response_class=HTMLResponse)
def ui_part_distributors(part_id: int, request: Request, db: Session = Depends(get_db)):
    part = db.query(Part).get(part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    items = (
        db.query(PartDistributor)
        .options(
            joinedload(PartDistributor.distributor),
            joinedload(PartDistributor.price_breaks),
        )
        .filter(PartDistributor.part_id == part.id)
        .order_by(PartDistributor.id)
        .all()
    )
    return templates.TemplateResponse(
        "parts/_distributors.html",
        {"request": request, "part": part, "items": items},
    )


@router.get("/{part_id}/distributors/new", response_class=HTMLResponse)
def ui_part_distributor_new(
    part_id: int, request: Request, db: Session = Depends(get_db)
):
    part = db.query(Part).get(part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    dists = db.query(Distributor).order_by(Distributor.code).all()
    return templates.TemplateResponse(
        "parts/distributor_form.html",
        {
            "request": request,
            "title": "Añadir distribuidor",
            "part": part,
            "pd": None,
            "distributors": dists,
            "action": f"/ui/parts/{part_id}/distributors/new",
        },
    )


@router.post("/{part_id}/distributors/new")
def ui_part_distributor_create(
    part_id: int,
    distributor_id: int = Form(...),
    distributor_pn: str = Form(...),
    preference: str = Form("alternate"),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
):
    part = db.query(Part).get(part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    payload = PartDistributorCreate(
        distributor_id=distributor_id,
        distributor_pn=distributor_pn,
        preference=preference,
        note=note,
    )
    # Reuse API logic
    from app.routers.part_distributors import add_part_distributor

    add_part_distributor(part_id, payload, db)  # raises on error
    return RedirectResponse(
        url=f"/ui/parts/{part_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/{part_id}/distributors/{pd_id}/edit", response_class=HTMLResponse)
def ui_part_distributor_edit(
    part_id: int, pd_id: int, request: Request, db: Session = Depends(get_db)
):
    part = db.query(Part).get(part_id)
    if not part:
        raise HTTPException(404, "Part not found")
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
    dists = db.query(Distributor).order_by(Distributor.code).all()
    return templates.TemplateResponse(
        "parts/distributor_form.html",
        {
            "request": request,
            "title": "Editar distribuidor",
            "part": part,
            "pd": pd,
            "distributors": dists,
            "action": f"/ui/parts/{part_id}/distributors/{pd_id}/edit",
        },
    )


@router.post("/{part_id}/distributors/{pd_id}/edit")
def ui_part_distributor_update(
    part_id: int,
    pd_id: int,
    distributor_pn: str = Form(...),
    preference: str = Form("alternate"),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
):
    payload = PartDistributorUpdate(
        distributor_pn=distributor_pn, preference=preference, note=note
    )
    from app.routers.part_distributors import update_part_distributor

    update_part_distributor(part_id, pd_id, payload, db)
    return RedirectResponse(
        url=f"/ui/parts/{part_id}", status_code=status.HTTP_303_SEE_OTHER
    )


# ---- Price breaks ----


@router.post("/{part_id}/distributors/{pd_id}/pricebreaks/new")
def ui_part_pricebreak_create(
    part_id: int,
    pd_id: int,
    min_qty: int = Form(...),
    unit_price: float = Form(...),
    currency: str = Form("EUR"),
    db: Session = Depends(get_db),
):
    from app.routers.part_distributors import add_price_break

    add_price_break(
        part_id,
        pd_id,
        PriceBreakCreate(
            part_distributor_id=pd_id,
            min_qty=min_qty,
            unit_price=Decimal(unit_price),
            currency=currency,
        ),
        db,
    )
    return RedirectResponse(
        url=f"/ui/parts/{part_id}/distributors/{pd_id}/edit",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{part_id}/distributors/{pd_id}/pricebreaks/{pb_id}/delete")
def ui_part_pricebreak_delete(
    part_id: int, pd_id: int, pb_id: int, db: Session = Depends(get_db)
):
    from app.routers.part_distributors import delete_price_break

    delete_price_break(part_id, pd_id, pb_id, db)
    return RedirectResponse(
        url=f"/ui/parts/{part_id}/distributors/{pd_id}/edit",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ---- Stock movements ----


@router.get("/{part_id}/movements", response_class=HTMLResponse)
def ui_part_movements(part_id: int, request: Request, db: Session = Depends(get_db)):
    part = db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    ctx = {
        "request": request,
        "part": part,
        "location_codes": _location_codes(db),
        "rows": _recent_movements_for_part(db, part_id),
        "message": None,
        "error": None,
    }
    return templates.TemplateResponse("parts/_movements.html", ctx)


@router.post("/{part_id}/movements/receive", response_class=HTMLResponse)
def ui_receive(
    part_id: int,
    request: Request,
    location_code: str = Form(...),
    qty: str = Form(...),
    ref_type: str | None = Form(None),
    ref_id: str | None = Form(None),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
):
    part = db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    try:
        q = Decimal(qty)
        payload = ReceiptRequest(
            ipn=part.ipn,
            location_code=location_code,
            qty=q,
            ref_type=ref_type,
            ref_id=ref_id,
            note=note,
        )
        stock_api.receipt(payload, db)
        return _render_movements_fragment(
            request, db, part, "Received successfully.", False
        )
    except (HTTPException, InvalidOperation) as e:
        msg = e.detail if isinstance(e, HTTPException) else "Invalid quantity"
        return _render_movements_fragment(request, db, part, f"Error: {msg}", True)


@router.post("/{part_id}/movements/issue", response_class=HTMLResponse)
def ui_issue(
    part_id: int,
    request: Request,
    location_code: str = Form(...),
    qty: str = Form(...),
    ref_type: Optional[str] = Form(None),
    ref_id: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    part = db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    try:
        q = Decimal(qty)
        payload = IssueRequest(
            ipn=part.ipn,
            location_code=location_code,
            qty=q,
            ref_type=ref_type,
            ref_id=ref_id,
            note=note,
        )
        stock_api.issue(payload, db)
        return _render_movements_fragment(
            request, db, part, "Issued successfully.", False
        )
    except (HTTPException, InvalidOperation) as e:
        msg = e.detail if isinstance(e, HTTPException) else "Invalid quantity"
        return _render_movements_fragment(request, db, part, f"Error: {msg}", True)


@router.post("/{part_id}/movements/transfer", response_class=HTMLResponse)
def ui_transfer(
    part_id: int,
    request: Request,
    from_location: str = Form(...),
    to_location: str = Form(...),
    qty: str = Form(...),
    ref_type: Optional[str] = Form(None),
    ref_id: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    part = db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    try:
        q = Decimal(qty)
        payload = TransferRequest(
            ipn=part.ipn,
            from_location=from_location,
            to_location=to_location,
            qty=q,
            ref_type=ref_type,
            ref_id=ref_id,
            note=note,
        )
        stock_api.transfer(payload, db)
        return _render_movements_fragment(
            request, db, part, "Transfer successful.", False
        )
    except (HTTPException, InvalidOperation) as e:
        msg = e.detail if isinstance(e, HTTPException) else "Invalid quantity"
        return _render_movements_fragment(request, db, part, f"Error: {msg}", True)


@router.post("/{part_id}/movements/adjust", response_class=HTMLResponse)
def ui_adjust(
    part_id: int,
    request: Request,
    location_code: str = Form(...),
    qty: str = Form(...),
    direction: int = Form(...),
    ref_type: Optional[str] = Form(None),
    ref_id: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    part = db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    try:
        q = Decimal(qty)
        payload = AdjustRequest(
            ipn=part.ipn,
            location_code=location_code,
            qty=q,
            direction=direction,
            ref_type=ref_type,
            ref_id=ref_id,
            note=note,
        )
        stock_api.adjust(payload, db)
        return _render_movements_fragment(
            request, db, part, "Adjustment successful.", False
        )
    except (HTTPException, InvalidOperation) as e:
        msg = e.detail if isinstance(e, HTTPException) else "Invalid quantity"
        return _render_movements_fragment(request, db, part, f"Error: {msg}", True)


@router.get("/{part_id}/documents", response_class=HTMLResponse)
def ui_part_documents(part_id: int, request: Request, db: Session = Depends(get_db)):
    part = db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    return templates.TemplateResponse(
        "parts/_documents.html",
        {
            "request": request,
            "part": part,
            "docs": _list_part_docs(db, part.id),
            "message": None,
            "error": False,
        },
    )


@router.post("/{part_id}/documents", response_class=HTMLResponse)
def ui_upload_part_document(
    part_id: int,
    request: Request,
    kind: str = Form(...),
    file: Optional[UploadFile] = Form(None),
    db: Session = Depends(get_db),
):
    part = db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")

    # Validate inputs to avoid 422 at dependency level
    if not kind:
        return templates.TemplateResponse(
            "parts/_documents.html",
            {
                "request": request,
                "part": part,
                "docs": _list_part_docs(db, part.id),
                "message": "Document kind is required.",
                "error": True,
            },
        )
    if not file or not (file.filename and file.file):
        return templates.TemplateResponse(
            "parts/_documents.html",
            {
                "request": request,
                "part": part,
                "docs": _list_part_docs(db, part.id),
                "message": "No file provided.",
                "error": True,
            },
        )

    # Map kind safely to enum
    try:
        dk = DocumentKind(kind)
    except ValueError:
        dk = DocumentKind.OTHER

    subdir = f"parts/{part.ipn}"
    p = save_document(file, subdir=subdir, use_year_subfolder=False)

    doc = Document(
        part_id=part.id,
        kind=dk,
        file_path=str(p),
        file_name=file.filename or p.name,
        mime_type=file.content_type,
        size=None,
    )
    db.add(doc)
    db.commit()
    return templates.TemplateResponse(
        "parts/_documents.html",
        {
            "request": request,
            "part": part,
            "docs": _list_part_docs(db, part.id),
            "message": "File uploaded successfully.",
            "error": False,
        },
    )


@router.post("/{part_id}/documents/{doc_id}/delete", response_class=HTMLResponse)
def ui_delete_part_document(
    part_id: int, doc_id: int, request: Request, db: Session = Depends(get_db)
):
    part = db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")

    doc = db.get(Document, doc_id)
    if not doc or doc.part_id != part.id:
        raise HTTPException(404, "Document not found")

    deleted = delete_document_quietly(doc.file_path)
    db.delete(doc)
    db.commit()

    msg = "Document deleted"
    if not deleted:
        msg += " (file could not be removed)"

    return templates.TemplateResponse(
        "parts/_documents.html",
        {
            "request": request,
            "part": part,
            "docs": _list_part_docs(db, part.id),
            "message": "Document deleted successfully.",
            "error": False,
        },
    )
