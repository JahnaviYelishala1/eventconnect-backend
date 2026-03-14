from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / "food_quantity_model.pkl"

try:
    model = joblib.load(MODEL_PATH)
except FileNotFoundError as exc:
    raise RuntimeError(f"Food quantity model file not found at: {MODEL_PATH}") from exc


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