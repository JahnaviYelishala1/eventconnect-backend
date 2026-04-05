from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

import firebase_admin
from fastapi import HTTPException
from firebase_admin import auth, credentials

logger = logging.getLogger(__name__)

def _build_firebase_credential() -> credentials.Base:
    """Build a Firebase credential from environment variables.

    Supported sources (in order):
    - FIREBASE_SERVICE_ACCOUNT_JSON_B64: base64-encoded JSON
    - FIREBASE_SERVICE_ACCOUNT_JSON: raw JSON
    - FIREBASE_SERVICE_ACCOUNT: raw JSON (alias)
    - FIREBASE_SERVICE_ACCOUNT_PATH: path to JSON
    - GOOGLE_APPLICATION_CREDENTIALS: path to JSON
    """

    json_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_B64")
    json_raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or os.getenv("FIREBASE_SERVICE_ACCOUNT")
    path_raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if json_b64:
        try:
            json_raw = base64.b64decode(json_b64).decode("utf-8")
        except Exception:
            logger.exception("Invalid FIREBASE_SERVICE_ACCOUNT_JSON_B64")
            raise

    if json_raw:
        try:
            info = json.loads(json_raw)
        except json.JSONDecodeError:
            logger.exception("Invalid FIREBASE_SERVICE_ACCOUNT_JSON (not valid JSON)")
            raise

        return credentials.Certificate(info)

    if path_raw:
        path = Path(path_raw)
        if path.exists():
            return credentials.Certificate(str(path))

        raise FileNotFoundError(f"Firebase service account file not found: {path}")

    raise FileNotFoundError(
        "Firebase service account is not configured. Provide FIREBASE_SERVICE_ACCOUNT_JSON(_B64) "
        "or FIREBASE_SERVICE_ACCOUNT_PATH/GOOGLE_APPLICATION_CREDENTIALS."
    )


def ensure_firebase_initialized() -> bool:
    """Initialize the default Firebase app if possible.

    Returns True if initialized (or already initialized), otherwise False.
    Never raises due to missing credentials so app startup won't crash.
    """

    if firebase_admin._apps:
        return True

    try:
        cred = _build_firebase_credential()
    except Exception as exc:
        logger.warning("Firebase not initialized: %s", str(exc))
        return False

    try:
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized")
        return True
    except Exception:
        logger.exception("Firebase initialization failed")
        return False


def verify_firebase_token(token: str):
    if not ensure_firebase_initialized():
        raise HTTPException(status_code=503, detail="Firebase is not configured on this service")

    try:
        return auth.verify_id_token(token, clock_skew_seconds=60)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")