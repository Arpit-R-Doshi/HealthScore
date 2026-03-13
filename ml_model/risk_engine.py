import numpy as np
import pickle
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "risk_model.pkl")
SCALER_PATH = os.path.join(BASE_DIR, "scaler.pkl")

with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)
with open(SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

def calculate_bmi(height, weight):
    return weight / ((height / 100) ** 2)

def calculate_risk(data):
    # 1. Base Metrics
    bmi = calculate_bmi(data["height"], data["weight"])
    age_quad = (data["age"] - 30) ** 2
    gender_male = 1 if str(data["gender"]).lower() == "male" else 0
    
    # 2. Extract Diseases from Text (Keyword Extraction)
    user_text = str(data.get("diseaseInput", "")).lower()
    
    # NLP-style keyword search
    diabetes_flag = 1 if "diabetes" in user_text or "sugar" in user_text else 0
    hypertension_flag = 1 if "hypertension" in user_text or "bp" in user_text or "pressure" in user_text else 0
    asthma_flag = 1 if "asthma" in user_text or "breathing" in user_text else 0
    heart_disease_flag = 1 if "heart" in user_text or "cardiac" in user_text or "artery" in user_text else 0

    # 3. Interaction Term
    obesity_x_diabetes = bmi * diabetes_flag

    # 4. Feature Set (Order must match trained model)
    features = [[
        age_quad,
        bmi,
        gender_male,
        obesity_x_diabetes,
        diabetes_flag,
        hypertension_flag,
        asthma_flag,
        heart_disease_flag
    ]]

    # Scaling and Prediction
    features_scaled = scaler.transform(features)
    prediction = model.predict(features_scaled)[0]

    # Monte Carlo Confidence Check
    simulations = np.random.normal(prediction, 0.15, 5000)

    return {
        "risk_score": float(prediction),
        "confidence_interval": {
            "p5": float(np.percentile(simulations, 5)),
            "p95": float(np.percentile(simulations, 95))
        }
    }