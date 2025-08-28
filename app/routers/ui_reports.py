from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.routers.reports import shortages as shortages_api, po_overdue as po_overdue_api
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/web/templates")
router = APIRouter(prefix="/ui/reports", tags=["UI: Reports"])


@router.get("/shortages", response_class=HTMLResponse)
def ui_shortages(request: Request, db: Session = Depends(get_db)):
    rows = shortages_api(db)
    return templates.TemplateResponse(
        "reports/shortages.html",
        {"request": request, "title": "Shortages", "items": rows},
    )


@router.get("/po-overdue", response_class=HTMLResponse)
def ui_po_overdue(request: Request, db: Session = Depends(get_db)):
    rows = po_overdue_api(db)
    return templates.TemplateResponse(
        "reports/po_overdue.html",
        {"request": request, "title": "PO Overdue", "items": rows},
    )
