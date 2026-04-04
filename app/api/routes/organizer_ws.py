from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.ngo import NGO
from app.models.user import User
from app.utils.auth import verify_firebase_token
from app.websocket.manager import manager

router = APIRouter()


@router.websocket("/ws/organizer")
async def organizer_websocket(websocket: WebSocket, token: str | None = None):
    db: Session = SessionLocal()
    organizer_user_id = None

    try:
        if not token:
            await websocket.close(code=1008)
            return

        normalized_token = token.strip()
        if normalized_token.startswith("Bearer "):
            normalized_token = normalized_token.replace("Bearer ", "", 1).strip()

        user_data = verify_firebase_token(normalized_token)

        db_user = db.query(User).filter(
            User.firebase_uid == user_data["uid"]
        ).first()

        if not db_user or db_user.role != "event_organizer":
            await websocket.close()
            return

        organizer_user_id = db_user.id

        await manager.connect_organizer(organizer_user_id, websocket)

        while True:
            await websocket.receive_text()

    except HTTPException:
        await websocket.close(code=1008)
    except WebSocketDisconnect:
        if organizer_user_id is not None:
            manager.disconnect_organizer(organizer_user_id)

    finally:
        db.close()


@router.websocket("/ws/{firebase_uid}")
async def notifications_websocket(
    websocket: WebSocket,
    firebase_uid: str,
    token: str | None = None,
):
    db: Session = SessionLocal()
    connection_id = None
    connection_type = None
    personal_user_id: int | None = None

    try:
        # Support token via query param injection, raw query params, or Authorization header.
        token_value = token or websocket.query_params.get("token") or websocket.headers.get("authorization")
        if token_value:
            normalized_token = token_value.strip()
            if normalized_token.startswith("Bearer "):
                normalized_token = normalized_token.replace("Bearer ", "", 1).strip()

            user_data = verify_firebase_token(normalized_token)
            if user_data.get("uid") != firebase_uid:
                await websocket.close(code=1008)
                return

        db_user = db.query(User).filter(
            User.firebase_uid == firebase_uid
        ).first()

        if not db_user:
            await websocket.close(code=1008)
            return

        personal_user_id = db_user.id

        if db_user.role == "event_organizer":
            connection_id = db_user.id
            connection_type = "organizer"
            await manager.connect_organizer(connection_id, websocket)
        elif db_user.role == "ngo":
            ngo = db.query(NGO).filter(
                NGO.firebase_uid == firebase_uid
            ).first()

            if not ngo:
                await websocket.close(code=1008)
                return

            connection_id = ngo.id
            connection_type = "ngo"
            await manager.connect_ngo(connection_id, websocket)
            # Allow direct/personal notifications via DB user id too.
            manager.active_connections[str(personal_user_id)] = websocket
        else:
            # Allow caterers and unassigned users to connect for personal notifications.
            connection_id = personal_user_id
            connection_type = "personal"
            await websocket.accept()
            manager.active_connections[str(personal_user_id)] = websocket

        while True:
            await websocket.receive_text()

    except HTTPException:
        await websocket.close(code=1008)
    except WebSocketDisconnect:
        if connection_id is not None and connection_type == "organizer":
            manager.disconnect_organizer(connection_id)
        elif connection_id is not None and connection_type == "ngo":
            manager.disconnect_ngo(connection_id)
            if personal_user_id is not None:
                manager.active_connections.pop(str(personal_user_id), None)
        elif connection_id is not None and connection_type == "personal":
            manager.active_connections.pop(str(connection_id), None)
    finally:
        db.close()
