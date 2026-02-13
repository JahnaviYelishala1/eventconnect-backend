from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.organizer import Organizer
from app.schemas.organizer import OrganizerCreate, OrganizerResponse
from app.utils.auth import get_current_user
import cloudinary.uploader

router = APIRouter(prefix="/api/organizers", tags=["Organizer"])


@router.post("/profile")
def create_profile(
    data: OrganizerCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "event_organizer":
        raise HTTPException(403, "Only organizers allowed")

    if db.query(Organizer).filter(
        Organizer.user_id == db_user.id
    ).first():
        raise HTTPException(400, "Profile already exists")

    organizer = Organizer(
        user_id=db_user.id,
        full_name=data.full_name,
        phone=data.phone,
        organization_name=data.organization_name,
        city=data.city.lower(),
        profile_image_url=data.profile_image_url
    )

    db.add(organizer)
    db.commit()
    db.refresh(organizer)

    return organizer


@router.get("/profile", response_model=OrganizerResponse)
def get_profile(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "event_organizer":
        raise HTTPException(403, "Not authorized")

    organizer = db.query(Organizer).filter(
        Organizer.user_id == db_user.id
    ).first()

    if not organizer:
        raise HTTPException(404, "Profile not found")

    return organizer


@router.put("/profile")
def update_profile(
    data: OrganizerCreate = Body(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "event_organizer":
        raise HTTPException(403, "Not authorized")

    organizer = db.query(Organizer).filter(
        Organizer.user_id == db_user.id
    ).first()

    if not organizer:
        raise HTTPException(404, "Profile not found")

    organizer.full_name = data.full_name
    organizer.phone = data.phone
    organizer.organization_name = data.organization_name
    organizer.city = data.city.lower()
    organizer.profile_image_url = data.profile_image_url

    db.commit()
    db.refresh(organizer)

    return {
        "message": "Profile updated successfully"
    }


@router.post("/upload-image")
async def upload_organizer_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "event_organizer":
        raise HTTPException(403, "Only organizers allowed")

    organizer = db.query(Organizer).filter(
        Organizer.user_id == db_user.id
    ).first()

    if not organizer:
        raise HTTPException(404, "Create profile first")

    # Upload to Cloudinary
    result = cloudinary.uploader.upload(
        file.file,
        folder="organizer_profiles",
        resource_type="image"
    )

    image_url = result.get("secure_url")

    # Save to database
    organizer.profile_image_url = image_url
    db.commit()

    return {
        "image_url": image_url,
        "message": "Image uploaded successfully"
    }

