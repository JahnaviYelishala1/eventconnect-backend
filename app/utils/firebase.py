"""Firebase utilities.

This module previously initialized Firebase at import time by reading a local
`firebase_service_account.json`. Deploys (e.g. Render) should use env vars.
"""

from app.core.firebase import ensure_firebase_initialized


def initialize_firebase() -> bool:
    """Backward-compatible initializer.

    Returns True if Firebase is initialized, else False.
    """

    return ensure_firebase_initialized()
