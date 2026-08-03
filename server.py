from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import joblib
import pandas as pd
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sakh-ai")

MODEL_PATH = "Lightgbm_credit2.pkl"
FEATURES_PATH = "Model_feature2.pkl"

model = joblib.load(MODEL_PATH)
model_features = joblib.load(FEATURES_PATH)

EMPLOYMENT_CATEGORIES = ["Commercial associate", "Pensioner", "State servant", "Working"]

def _normalize_key(s: str) -> str:
    return s.strip().lower().replace("-", "").replace("_", "").replace(" ", "")

EMPLOYMENT_TYPE_LOOKUP = {_normalize_key(c): c for c in EMPLOYMENT_CATEGORIES}

APPROVAL_THRESHOLD = 0.35

class ValidationError(Exception):
    pass

def parse_and_validate(payload: dict) -> dict:
    def require(key, cast, lo=None, hi=None, label=None):
        label = label or key
        if key not in payload or payload[key] in (None, ""):
            raise ValidationError(f"Missing field: {label}")
        try:
            value = cast(payload[key])
        except (TypeError, ValueError):
            raise ValidationError(f"Invalid value for {label}")
        if lo is not None and value < lo:
            raise ValidationError(f"{label} must be >= {lo}")
        if hi is not None and value > hi:
            raise ValidationError(f"{label} must be <= {hi}")
        return value

    age = require("age", int, 18, 100, "age")
    city_tier = require("city_tier", int, 1, 3, "city_tier")
    monthly_income = require("salary", float, 0.01, None, "salary")
    cibil_score = require("cibil_score", int, 300, 900, "cibil_score")
    foir_percentage = require("foir_score", float, 0, 100, "foir")

    raw_employment = payload.get("employment_type", "")
    employment_type = EMPLOYMENT_TYPE_LOOKUP.get(_normalize_key(str(raw_employment)))
    if employment_type is None:
        raise ValidationError(
            f"Invalid employment_type: '{raw_employment}'. "
            f"Expected one of: {EMPLOYMENT_CATEGORIES}"
        )

    return {
        "age": age,
        "city_tier": city_tier,
        "employment_type": employment_type,
        "monthly_income": monthly_income,
        "cibil_score": cibil_score,
        "foir_percentage": foir_percentage,
    }

def run_model(features: dict):
    df = pd.DataFrame([features])
    df["employment_type"] = pd.Categorical(
        df["employment_type"], categories=EMPLOYMENT_CATEGORIES
    )
    df = df[model_features]

    probability_approved = float(model.predict_proba(df)[0][1])
    approved = probability_approved >= APPROVAL_THRESHOLD
    return approved, probability_approved

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/docs")
def docs():
    return render_template("docs.html")

@app.route("/check")
def check():
    return render_template("check.html")

@app.route("/predict", methods=["POST"])
def predict():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Expected a JSON body."}), 400

    try:
        features = parse_and_validate(payload)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    try:
        approved, probability_approved = run_model(features)
    except Exception as e:
        log.exception("Model inference failed")
        return jsonify({"error": "Prediction failed on the server."}), 500

    if approved:
        message = f"You're likely to be approved — estimated {probability_approved * 100:.1f}% approval confidence."
    else:
        message = f"You're unlikely to be approved right now — estimated {probability_approved * 100:.1f}% approval confidence."

    return jsonify({
        "approved": approved,
        "probability": round(probability_approved, 4),
        "score": round(probability_approved * 100, 1),
        "message": message,
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)