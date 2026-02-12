from fastapi import APIRouter, Body, Depends, HTTPException, File, UploadFile
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

router = APIRouter(prefix="/api/caterers", tags=["Caterers"])

# =====================================================
# CREATE CATERER PROFILE
# =====================================================

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

    # Save services
    for service in data.services:
        db.add(CatererService(
            caterer_id=caterer.id,
            service_type=service
        ))

    db.commit()

    return {"message": "Caterer profile created successfully"}


# =====================================================
# MATCH CATERERS (CATER NINJA STYLE - DELHI NCR)
# =====================================================

@router.get("/match/{event_id}")
def match_caterers(
    event_id: int,
    min_price: float = None,
    max_price: float = None,
    min_rating: float = None,
    veg_only: bool = False,
    nonveg_only: bool = False,
    sort_by: str = "distance",
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    event = db.query(Event).filter(
        Event.id == event_id,
        Event.firebase_uid == user["uid"]
    ).first()

    if not event:
        return []

    event_location = db.query(EventLocation).filter(
        EventLocation.event_id == event.id
    ).first()

    if not event_location:
        return []

    MAX_DISTANCE_KM = 30
    DELHI_NCR = ["delhi", "gurgaon", "noida", "ghaziabad", "faridabad"]

    caterers = db.query(Caterer).all()
    result = []

    for caterer in caterers:

        # 1️⃣ Delhi NCR filter
        if caterer.city.lower() not in DELHI_NCR:
            continue

        # 2️⃣ Capacity filter
        if event.attendees < caterer.min_capacity or event.attendees > caterer.max_capacity:
            continue

        # 3️⃣ Service-type filter
        caterer_services = [s.service_type for s in caterer.services]
        if event.event_type not in caterer_services:
            continue

        # 4️⃣ Distance filter
        distance = calculate_distance(
            event_location.latitude,
            event_location.longitude,
            caterer.latitude,
            caterer.longitude
        )

        if distance > MAX_DISTANCE_KM:
            continue

        # 5️⃣ Price filter
        if min_price is not None and caterer.price_per_plate < min_price:
            continue

        if max_price is not None and caterer.price_per_plate > max_price:
            continue

        # 6️⃣ Rating filter
        if min_rating is not None and caterer.rating < min_rating:
            continue

        # 7️⃣ Veg / Nonveg filter
        if veg_only and not caterer.veg_supported:
            continue

        if nonveg_only and not caterer.nonveg_supported:
            continue

        result.append({
            "id": caterer.id,
            "business_name": caterer.business_name,
            "city": caterer.city,
            "price_per_plate": caterer.price_per_plate,
            "rating": caterer.rating,
            "veg_supported": caterer.veg_supported,
            "nonveg_supported": caterer.nonveg_supported,
            "distance_km": round(distance, 2),
            "image_url": caterer.image_url,
            "min_capacity": caterer.min_capacity,
            "max_capacity": caterer.max_capacity
        })

    # Sorting logic
    if sort_by == "price_low":
        result.sort(key=lambda x: x["price_per_plate"])
    elif sort_by == "price_high":
        result.sort(key=lambda x: x["price_per_plate"], reverse=True)
    elif sort_by == "rating":
        result.sort(key=lambda x: x["rating"], reverse=True)
    else:
        result.sort(
            key=lambda x: (
                x["distance_km"],
                -x["rating"],
                x["price_per_plate"]
            )
        )

    return result


# =====================================================
# BOOK CATERER
# =====================================================

@router.post("/book/{event_id}/{caterer_id}")
def book_caterer(
    event_id: int,
    caterer_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    event = db.query(Event).filter(
        Event.id == event_id,
        Event.firebase_uid == user["uid"]
    ).first()

    if not event:
        raise HTTPException(404, "Event not found")

    if db.query(EventBooking).filter(
        EventBooking.event_id == event_id
    ).first():
        raise HTTPException(400, "Booking already requested")

    booking = EventBooking(
        event_id=event_id,
        caterer_id=caterer_id,
        status="PENDING"
    )

    event.status = "BOOKING_REQUESTED"

    db.add(booking)
    db.commit()

    return {"message": "Booking request sent successfully"}


# =====================================================
# GET MY PROFILE
# =====================================================

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


# =====================================================
# UPDATE PROFILE
# =====================================================

@router.put("/profile/me")
def update_caterer_profile(
    data: CatererCreate = Body(...),
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

    # Replace services
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


# =====================================================
# UPLOAD IMAGE (UPLOAD + UPDATE DB)
# =====================================================

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

    image_url = result.get("secure_url")

    caterer.image_url = image_url
    db.commit()

    return {
        "image_url": image_url,
        "message": "Image uploaded successfully"
    }
