from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ngo import NGO
from app.models.ngo_document import NGODocument
from app.utils.auth import get_current_user
from app.utils.admin import admin_only

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"]
)

# -------------------------------------------------
# LIST ALL NGOs WITH DOCUMENTS
# -------------------------------------------------
@router.get("/ngos")
def list_ngos(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    admin_only(user)

    ngos = db.query(NGO).order_by(NGO.created_at.desc()).all()
    result = []

    for ngo in ngos:
        documents = db.query(NGODocument).filter(
            NGODocument.ngo_id == ngo.id
        ).all()

        result.append({
            "id": ngo.id,
            "name": ngo.name,
            "registration_number": ngo.registration_number,
            "status": ngo.status,
            "documents": [
                {
                    "id": doc.id,
                    "document_type": doc.document_type,
                    "file_url": doc.file_url,
                    "status": doc.status
                } for doc in documents
            ]
        })

    return result


# -------------------------------------------------
# APPROVE NGO DOCUMENT
# -------------------------------------------------
@router.patch("/documents/{doc_id}/approve")
def approve_document(
    doc_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    admin_only(user)

    doc = db.query(NGODocument).filter(NGODocument.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    doc.status = "APPROVED"
    db.commit()

    _auto_verify_ngo(db, doc.ngo_id)
    return {"message": "Document approved"}


# -------------------------------------------------
# REJECT NGO DOCUMENT
# -------------------------------------------------
@router.patch("/documents/{doc_id}/reject")
def reject_document(
    doc_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    admin_only(user)

    doc = db.query(NGODocument).filter(NGODocument.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    doc.status = "REJECTED"
    db.commit()

    ngo = db.query(NGO).filter(NGO.id == doc.ngo_id).first()
    ngo.status = "REJECTED"
    db.commit()

    return {"message": "Document rejected"}


# -------------------------------------------------
# AUTO VERIFY NGO IF ALL DOCS APPROVED
# -------------------------------------------------
def _auto_verify_ngo(db: Session, ngo_id: int):
    docs = db.query(NGODocument).filter(
        NGODocument.ngo_id == ngo_id
    ).all()

    if docs and all(d.status == "APPROVED" for d in docs):
        ngo = db.query(NGO).filter(NGO.id == ngo_id).first()
        ngo.status = "VERIFIED"
        db.commit()
