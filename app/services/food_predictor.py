from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / "food_quantity_model.pkl"

try:
    model = joblib.load(MODEL_PATH)
except FileNotFoundError as exc:
    raise RuntimeError(f"Food quantity model file not found at: {MODEL_PATH}") from exc

def predict_food_quantities(attendees, items, meal_type):

    predictions = {}

    for item in items:

        df = pd.DataFrame({
            "attendees": [attendees],
            "category": [item.category],
            "meal_type": [meal_type],
            "food_type": ["veg"]   
        })

        qty = model.predict(df)[0]

        predictions[item.name] = round(float(qty), 2)

    return predictions