from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ngo import NGO
from app.models.ngo_document import NGODocument
from app.schemas.ngo import NGOCreate, NGOResponse
from app.schemas.ngo_document import NGODocumentCreate
from app.utils.auth import get_current_user

router = APIRouter(
    prefix="/api/ngos",
    tags=["NGO"]
)


@router.post("/register", response_model=NGOResponse)
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
        registration_number=data.registration_number
    )

    db.add(ngo)
    db.commit()
    db.refresh(ngo)

    return ngo

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
        raise HTTPException(
            status_code=404,
            detail="NGO not registered"
        )

    document = NGODocument(
        ngo_id=ngo.id,
        document_type=data.document_type,
        file_url=data.file_url
    )

    db.add(document)
    db.commit()

    return {"message": "Document uploaded successfully"}


@router.get("/me", response_model=NGOResponse)
def get_my_ngo(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    ngo = db.query(NGO).filter(
        NGO.firebase_uid == user["uid"]
    ).first()

    if not ngo:
        raise HTTPException(
            status_code=404,
            detail="NGO not registered"
        )

    return ngo
