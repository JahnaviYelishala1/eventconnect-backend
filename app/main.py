import logging

from fastapi import APIRouter, FastAPI
from sqlalchemy import text

# Routers
from app.api.routes import (
    chat,
    health,
    ngo_ws,
    organizer,
    organizer_ws,
    payment as payment_router,
    preparation,
    protected,
    surplus,
    user,
    food_prediction,
    event,
    menu,
    websocket,
    ngo_profile as ngo_profile_router
)

# Database
from app.database import Base, engine
from app.models import caterer, ngo_profile, user as user_model
from app.models import event as event_model
from app.core import firebase
from app.api.routes import ngo
from app.api.routes import admin
from app.models import ngo_profile as ngo_profile_model
from app.models import event_location as event_location_model
from app.api.routes import booking
from app.models import caterer as caterer_model
from app.api.routes import caterer
from app.models import payment as payment_model

# Create FastAPI app
app = FastAPI(
    title="EventConnect API",
    version="1.0.0",
    description="Backend API for EventConnect Platform"
)

logger = logging.getLogger(__name__)

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
payment_model.Base.metadata.create_all(bind=engine)


def _apply_schema_hotfixes() -> None:
    # Keep old databases compatible with request-based chat where booking_id is optional.
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE IF EXISTS chat_messages "
                "ALTER COLUMN booking_id DROP NOT NULL"
            )
        )


try:
    _apply_schema_hotfixes()
except Exception as exc:
    logger.warning("Schema hotfix skipped: %s", str(exc))


# ---------------- ROUTERS ----------------
app.include_router(health.router, prefix="/api")
app.include_router(protected.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(ngo.router)
app.include_router(admin.router)
app.include_router(ngo_profile_router.router)
app.include_router(caterer.router)
app.include_router(booking.router)
app.include_router(organizer.router)
app.include_router(menu.router)
app.include_router(websocket.router)
app.include_router(payment_router.router)
app.include_router(chat.router)
app.include_router(preparation.router)
app.include_router(surplus.router)
app.include_router(ngo_ws.router)
app.include_router(organizer_ws.router)

# ML & Events
app.include_router(food_prediction.router)
app.include_router(event.router)

event_location_model.Base.metadata.create_all(bind=engine)
