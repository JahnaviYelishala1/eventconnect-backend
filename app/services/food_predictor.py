from __future__ import annotations

import logging
import os
import shutil
import threading
import urllib.request
from pathlib import Path

import joblib
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parent / "food_quantity_model.pkl"
_MODEL = None
_MODEL_LOCK = threading.Lock()


def _download_model(url: str, destination: Path, timeout_seconds: float = 30.0) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")

    logger.info("Downloading food quantity model", extra={"url": url, "destination": str(destination)})

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "eventconnect-backend/food-predictor",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response, tmp_path.open("wb") as out:
            shutil.copyfileobj(response, out)

        tmp_path.replace(destination)
        logger.info("Food quantity model downloaded", extra={"path": str(destination)})
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        except Exception:
            logger.exception("Failed cleaning up partial model download", extra={"tmp_path": str(tmp_path)})

        logger.exception(
            "Failed to download food quantity model",
            extra={"url": url, "destination": str(destination)},
        )
        raise


def _load_model_from_disk(path: Path):
    logger.info("Loading food quantity model", extra={"path": str(path)})
    return joblib.load(path)


def get_food_quantity_model():
    """Return the cached model instance.

    Lazy-loads the model on first use. If the model file is missing, optionally
    downloads it from FOOD_MODEL_URL and saves it at MODEL_PATH.

    This function intentionally does NOT raise during module import so the app
    can start without the model present.
    """

    global _MODEL

    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL

        if MODEL_PATH.exists():
            try:
                _MODEL = _load_model_from_disk(MODEL_PATH)
                return _MODEL
            except Exception:
                logger.exception("Food quantity model exists but failed to load", extra={"path": str(MODEL_PATH)})
                _MODEL = None
                raise

        url = os.getenv("FOOD_MODEL_URL")
        if not url:
            logger.warning(
                "Food quantity model missing and FOOD_MODEL_URL not set",
                extra={"expected_path": str(MODEL_PATH)},
            )
            return None

        try:
            _download_model(url=url, destination=MODEL_PATH)
        except Exception:
            _MODEL = None
            return None

        try:
            _MODEL = _load_model_from_disk(MODEL_PATH)
            return _MODEL
        except Exception:
            logger.exception("Downloaded food quantity model but failed to load", extra={"path": str(MODEL_PATH)})
            _MODEL = None
            return None


_CATEGORY_ALIASES = {
    "starter": "starter",
    "starters": "starter",
    "appetizer": "starter",
    "appetizers": "starter",
    "main": "main_course",
    "maincourse": "main_course",
    "main_course": "main_course",
    "main course": "main_course",
    "dessert": "dessert",
    "desserts": "dessert",
    "sweet": "dessert",
    "sweets": "dessert",
    "beverage": "beverages",
    "beverages": "beverages",
    "drink": "beverages",
    "drinks": "beverages",
    "cold drink": "beverages",
    "cold drinks": "beverages",
    "juice": "beverages",
    "snack": "snacks",
    "snacks": "snacks",
}


def _normalize_category(raw_category: str | None) -> str | None:
    if not raw_category:
        return None

    key = str(raw_category).strip().lower().replace("-", " ").replace("_", " ")
    return _CATEGORY_ALIASES.get(key, key.replace(" ", "_"))


def _infer_category_from_name(item_name: str) -> str:
    name = item_name.lower()

    dessert_keywords = [
        "sweet", "dessert", "halwa", "laddu", "gulab", "jamun", "kheer", "rasgulla", "ice cream"
    ]
    beverage_keywords = [
        "drink", "juice", "cola", "soda", "water", "lassi", "tea", "coffee", "shake", "mocktail"
    ]
    starter_keywords = [
        "tikka", "kabab", "kebab", "roll", "65", "starter", "manchurian", "pakoda"
    ]

    if any(keyword in name for keyword in dessert_keywords):
        return "dessert"
    if any(keyword in name for keyword in beverage_keywords):
        return "beverages"
    if any(keyword in name for keyword in starter_keywords):
        return "starter"

    return "main_course"


def predict_food_quantities(attendees, items, meal_type):

    model = get_food_quantity_model()
    if model is None:
        raise RuntimeError(
            "Food quantity model is not available. Set FOOD_MODEL_URL or place the model at "
            f"{MODEL_PATH}"
        )

    predictions = {}

    for item in items:

        normalized_category = _normalize_category(getattr(item, "category", None))
        category = normalized_category or _infer_category_from_name(item.name)

        df = pd.DataFrame({
            "attendees": [attendees],
            "category": [category],
            "meal_type": [meal_type],
        })

        qty = model.predict(df)[0]

        predictions[item.name] = round(float(qty), 2)

    return predictions