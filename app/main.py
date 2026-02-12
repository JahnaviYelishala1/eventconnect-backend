from fastapi import FastAPI

# Routers
from app.api.routes import (
    health,
    profile,
    protected,
    user,
    food_prediction,
    event
)

# Database
from app.database import Base, engine
from app.models import caterer, user as user_model
from app.models import event as event_model
from app.core import firebase
from app.api.routes import ngo
from app.api.routes import admin
from app.models import ngo_profile as ngo_profile_model
from app.models import event_location as event_location_model
from app.api.routes import booking
from app.models import caterer as caterer_model
from app.api.routes import caterer

# Create FastAPI app
app = FastAPI(
    title="EventConnect API",
    version="1.0.0",
    description="Backend API for EventConnect Platform"
)

# ---------------- ROOT ----------------
@app.get("/")
def root():
    return {"message": "EventConnect backend is running"}

# ---------------- DATABASE INIT ----------------
# ⚠️ IMPORTANT: models must be imported BEFORE create_all
Base.metadata.create_all(bind=engine)
user_model.Base.metadata.create_all(bind=engine)
event_model.Base.metadata.create_all(bind=engine)
ngo_profile_model.Base.metadata.create_all(bind=engine)
caterer_model.Base.metadata.create_all(bind=engine)


# ---------------- ROUTERS ----------------
app.include_router(health.router, prefix="/api")
app.include_router(protected.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(ngo.router)
app.include_router(admin.router)
app.include_router(profile.router)
app.include_router(caterer.router)
app.include_router(booking.router)


# ML & Events
app.include_router(food_prediction.router)
app.include_router(event.router)
event_location_model.Base.metadata.create_all(bind=engine)
