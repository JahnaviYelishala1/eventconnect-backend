from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ngo import NGO
from app.models.ngo_document import NGODocument
from app.schemas.ngo import NGOCreate
from app.schemas.ngo_document import NGODocumentCreate
from app.utils.auth import get_current_user
from app.schemas.ngo_document import NGODocumentStatusResponse
from app.utils.image_upload import upload_ngo_image
from app.core.cloudinary_config import cloudinary
import cloudinary.uploader

router = APIRouter(
    prefix="/api/ngos",
    tags=["NGO"]
)

# -----------------------------
# REGISTER NGO
# -----------------------------
@router.post("/register")
def register_ngo(
    data: NGOCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    existing = db.query(NGO).filter(
        NGO.firebase_uid == user["uid"]
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="NGO already registered"
        )

    ngo = NGO(
        firebase_uid=user["uid"],
        name=data.name,
        registration_number=data.registration_number,
        status="PENDING"
    )

    db.add(ngo)
    db.commit()
    db.refresh(ngo)

    return {"message": "NGO registered successfully"}

# -----------------------------
# UPLOAD DOCUMENT
# -----------------------------
@router.post("/documents")
def upload_ngo_document(
    data: NGODocumentCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    ngo = db.query(NGO).filter(
        NGO.firebase_uid == user["uid"]
    ).first()

    if not ngo:
        raise HTTPException(404, "NGO not registered")

    document = NGODocument(
        ngo_id=ngo.id,
        document_type=data.document_type,
        file_url=data.file_url
    )

    db.add(document)
    db.commit()

    return {"message": "Document uploaded successfully"}


@router.get("/me")
def get_my_ngo(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    ngo = db.query(NGO).filter(
        NGO.firebase_uid == user["uid"]
    ).first()

    if not ngo:
        return {
            "exists": False
        }

    docs_count = db.query(NGODocument).filter(
        NGODocument.ngo_id == ngo.id
    ).count()

    return {
        "exists": True,
        "ngo_id": ngo.id,
        "status": ngo.status,
        "documents_uploaded": docs_count > 0
    }


@router.get("/documents/status", response_model=NGODocumentStatusResponse)
def get_document_status(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    ngo = db.query(NGO).filter(
        NGO.firebase_uid == user["uid"]
    ).first()

    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not registered")

    document_exists = db.query(NGODocument).filter(
        NGODocument.ngo_id == ngo.id
    ).first()

    return {
        "uploaded": document_exists is not None
    }

@router.get("/documents")
def get_my_ngo_documents(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    ngo = db.query(NGO).filter(
        NGO.firebase_uid == user["uid"]
    ).first()

    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not registered")

    documents = db.query(NGODocument).filter(
        NGODocument.ngo_id == ngo.id
    ).all()

    return {
        "count": len(documents),
        "documents": [
            {
                "id": d.id,
                "document_type": d.document_type,
                "file_url": d.file_url,
                "uploaded_at": d.uploaded_at
            }
            for d in documents
        ]
    }


@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    url = upload_ngo_image(file.file)
    return {"image_url": url}

