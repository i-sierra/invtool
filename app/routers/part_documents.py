from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from decimal import Decimal

from app.db import get_db
from app.models import Part, Document, DocumentKind
from app.services.files import delete_document_quietly, save_document

router = APIRouter(prefix="/parts", tags=["Part Documents"])


@router.get("/{part_id}/documents")
def list_part_documents(part_id: int, db: Session = Depends(get_db)):
    part = db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    docs = (
        db.query(Document)
        .filter(Document.part_id == part.id)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "kind": d.kind.value if hasattr(d.kind, "value") else d.kind,
            "file_name": d.file_name,
            "created_at": d.created_at,
        }
        for d in docs
    ]


@router.post("/{part_id}/documents", status_code=201)
def upload_part_document(
    part_id: int,
    kind: DocumentKind = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    part = db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")

    # Save file under `parts/<IPN>/` (without yearly subfolder)
    subdir = f"parts/{part.ipn}"
    path = save_document(file, subdir, use_year_subfolder=False)

    doc = Document(
        part_id=part.id,
        kind=kind,
        file_name=file.filename,
        file_path=path,
        mime_type=file.content_type,
        size=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{part_id}/documents/{doc_id}", status_code=204)
def delete_part_document(
    part_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
):
    doc = db.get(Document, doc_id)
    if not doc or doc.part_id != part_id:
        raise HTTPException(404, "Document not found")
    # Delete file first
    delete_document_quietly(doc.file_path)
    db.delete(doc)
    db.commit()
