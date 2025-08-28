from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Distributor

templates = Jinja2Templates(directory="app/web/templates")
router = APIRouter(prefix="/ui/distributors", tags=["UI: Distributors"])


@router.get("", response_class=HTMLResponse)
def ui_list(request: Request, db: Session = Depends(get_db)):
    rows = db.query(Distributor).order_by(Distributor.code).all()
    return templates.TemplateResponse(
        "distributors/list.html",
        {"request": request, "title": "Distribuidores", "items": rows},
    )


@router.post("/new")
def ui_create(
    code: str = Form(...), name: str = Form(...), db: Session = Depends(get_db)
):
    if db.query(Distributor).filter(Distributor.code == code).first():
        raise HTTPException(409, "Code already exists")
    db.add(Distributor(code=code, name=name))
    db.commit()
    return RedirectResponse(
        url="/ui/distributors", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{dist_id}/edit")
def ui_update(dist_id: int, name: str = Form(...), db: Session = Depends(get_db)):
    d = db.query(Distributor).get(dist_id)
    if not d:
        raise HTTPException(404, "Distributor not found")
    d.name = name
    db.commit()
    return RedirectResponse(
        url="/ui/distributors", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{dist_id}/delete")
def ui_delete(dist_id: int, db: Session = Depends(get_db)):
    d = db.query(Distributor).get(dist_id)
    if not d:
        raise HTTPException(404, "Distributor not found")
    if d.part_distributors:
        raise HTTPException(409, "Distributor in use")
    db.delete(d)
    db.commit()
    return RedirectResponse(
        url="/ui/distributors", status_code=status.HTTP_303_SEE_OTHER
    )
