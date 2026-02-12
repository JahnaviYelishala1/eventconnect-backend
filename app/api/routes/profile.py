from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ngo_profile import NGOProfile
from app.models.user import User
from app.core.firebase import get_current_user

router = APIRouter(prefix="/api/ngo", tags=["NGO Profile"])


# ---------------- SCHEMA ----------------
class NgoProfilePayload(BaseModel):
    name: str | None = None
    established_year: str | None = None
    about: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    image_url: str | None = None


# ---------------- CREATE / UPDATE PROFILE ----------------
@router.post("/profile")
def create_or_update_ngo_profile(
    payload: NgoProfilePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = (
        db.query(NGOProfile)
        .filter(NGOProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        profile = NGOProfile(user_id=current_user.id)
        db.add(profile)

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)

    return {"message": "NGO profile saved successfully"}


# ---------------- GET PROFILE ----------------
@router.get("/profile")
def get_ngo_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = (
        db.query(NGOProfile)
        .filter(NGOProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        raise HTTPException(status_code=404, detail="NGO profile not found")

    return {
        "name": profile.name,
        "established_year": profile.established_year,
        "about": profile.about,
        "email": profile.email,
        "phone": profile.phone,
        "address": profile.address,
        "latitude": profile.latitude,
        "longitude": profile.longitude,
        "image_url": profile.image_url,
    }


@router.put("/profile")
def update_ngo_profile(
    payload: NgoProfilePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(NGOProfile).filter(
        NGOProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="NGO profile not found"
        )

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)

    return {"message": "NGO profile updated successfully"}
