from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ngo import NGO
from app.utils.auth import get_current_user

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"]
)

# 🔐 TEMP ADMIN CHECK (MVP)
def admin_only(user):
    ADMIN_EMAILS = [
        "admin@gmail.com"  # 👈 replace with YOUR Firebase email
    ]

    if user.get("email") not in ADMIN_EMAILS:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

# -------------------------------
# LIST ALL NGOs (FOR REVIEW)
# -------------------------------
@router.get("/ngos")
def list_ngos(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    admin_only(user)

    ngos = db.query(NGO).order_by(NGO.created_at.desc()).all()
    return ngos


# -------------------------------
# VERIFY NGO
# -------------------------------
@router.patch("/ngos/{ngo_id}/verify")
def verify_ngo(
    ngo_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    admin_only(user)

    ngo = db.query(NGO).filter(NGO.id == ngo_id).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")

    ngo.status = "VERIFIED"
    db.commit()

    return {"message": "NGO verified successfully"}


# -------------------------------
# REJECT NGO
# -------------------------------
@router.patch("/ngos/{ngo_id}/reject")
def reject_ngo(
    ngo_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    admin_only(user)

    ngo = db.query(NGO).filter(NGO.id == ngo_id).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")

    ngo.status = "REJECTED"
    db.commit()

    return {"message": "NGO rejected"}


# -------------------------------
# SUSPEND NGO
# -------------------------------
@router.patch("/ngos/{ngo_id}/suspend")
def suspend_ngo(
    ngo_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    admin_only(user)

    ngo = db.query(NGO).filter(NGO.id == ngo_id).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")

    ngo.status = "SUSPENDED"
    db.commit()

    return {"message": "NGO suspended"}
