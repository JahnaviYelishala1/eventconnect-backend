from typing import List
from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.caterer import Caterer
from app.models.caterer_service import CatererService
from app.models.event import Event
from app.models.event_booking import EventBooking
from app.models.event_location import EventLocation
from app.schemas.caterer import CatererCreate, CatererResponse
from app.utils.auth import get_current_user
from app.utils.distance import calculate_distance
import cloudinary.uploader
from typing import List, Optional
from fastapi import Query
from sqlalchemy.orm import Session


router = APIRouter(prefix="/api/caterers", tags=["Caterers"])

MAX_DISTANCE_KM = 30
DELHI_NCR = ["delhi", "gurgaon", "noida", "ghaziabad", "faridabad"]


@router.post("/profile")
def create_caterer_profile(
    data: CatererCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    if db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first():
        raise HTTPException(400, "Profile already exists")

    caterer = Caterer(
        user_id=db_user.id,
        business_name=data.business_name,
        city=data.city.lower(),
        min_capacity=data.min_capacity,
        max_capacity=data.max_capacity,
        price_per_plate=data.price_per_plate,
        veg_supported=data.veg_supported,
        nonveg_supported=data.nonveg_supported,
        latitude=data.latitude,
        longitude=data.longitude,
        image_url=data.image_url
    )

    db.add(caterer)
    db.commit()
    db.refresh(caterer)

    for service in data.services:
        db.add(CatererService(
            caterer_id=caterer.id,
            service_type=service
        ))

    db.commit()

    return {"message": "Caterer profile created successfully"}

@router.get("/profile/me", response_model=CatererResponse)
def get_my_caterer_profile(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Not authorized")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    if not caterer:
        raise HTTPException(404, "Profile not created yet")

    return caterer

@router.put("/profile/me")
def update_caterer_profile(
    data: CatererCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Not authorized")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    if not caterer:
        raise HTTPException(404, "Profile not found")

    caterer.business_name = data.business_name
    caterer.city = data.city.lower()
    caterer.min_capacity = data.min_capacity
    caterer.max_capacity = data.max_capacity
    caterer.price_per_plate = data.price_per_plate
    caterer.veg_supported = data.veg_supported
    caterer.nonveg_supported = data.nonveg_supported
    caterer.latitude = data.latitude
    caterer.longitude = data.longitude
    caterer.image_url = data.image_url

    db.query(CatererService).filter(
        CatererService.caterer_id == caterer.id
    ).delete()

    for service in data.services:
        db.add(CatererService(
            caterer_id=caterer.id,
            service_type=service
        ))

    db.commit()

    return {"message": "Profile updated successfully"}

@router.post("/upload-image")
async def upload_caterer_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    if not caterer:
        raise HTTPException(404, "Create profile first")

    result = cloudinary.uploader.upload(
        file.file,
        folder="caterer_profiles",
        resource_type="image"
    )

    caterer.image_url = result.get("secure_url")
    db.commit()

    return {
        "image_url": caterer.image_url,
        "message": "Image uploaded successfully"
    }

@router.get("/match/{event_id}", response_model=List[CatererResponse])
def match_caterers(
    event_id: int,
    veg_only: Optional[bool] = Query(None),
    nonveg_only: Optional[bool] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    meal_style: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    # 1️⃣ Get Event
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.firebase_uid == user["uid"]
    ).first()

    if not event:
        return []

    # 2️⃣ Get Location
    location = db.query(EventLocation).filter(
        EventLocation.event_id == event.id
    ).first()

    if not location:
        return []

    # 3️⃣ Fetch Caterers
    caterers = db.query(Caterer).all()
    matched = []

    for caterer in caterers:

        # Capacity filter
        if event.attendees < caterer.min_capacity or event.attendees > caterer.max_capacity:
            continue

        # Distance filter
        distance = calculate_distance(
            location.latitude,
            location.longitude,
            caterer.latitude,
            caterer.longitude
        )

        if distance > MAX_DISTANCE_KM:
            continue

        # Veg filter
        if veg_only is True and not caterer.veg_supported:
            continue

        if nonveg_only is True and not caterer.nonveg_supported:
            continue

        # Budget filter
        if min_price is not None and caterer.price_per_plate < min_price:
            continue

        if max_price is not None and caterer.price_per_plate > max_price:
            continue

        # Meal style filter
        if meal_style:
            if event.meal_style != meal_style:
                continue

        matched.append({
            "id": caterer.id,
            "business_name": caterer.business_name,
            "city": caterer.city,
            "min_capacity": caterer.min_capacity,
            "max_capacity": caterer.max_capacity,
            "price_per_plate": caterer.price_per_plate,
            "veg_supported": caterer.veg_supported,
            "nonveg_supported": caterer.nonveg_supported,
            "rating": caterer.rating,
            "latitude": caterer.latitude,
            "longitude": caterer.longitude,
            "image_url": caterer.image_url,
            "distance_km": round(distance, 2),
            "services": [
                {
                    "id": s.id,
                    "service_type": s.service_type
                }
                for s in caterer.services
            ]
        })

    # Sort after loop finishes
    matched.sort(key=lambda x: x["distance_km"])

    return matched
