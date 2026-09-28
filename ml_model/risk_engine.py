import numpy as np
import pickle
import os
from scipy.stats import percentileofscore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "risk_model.pkl")
BENCHMARK_COSTS_PATH = os.path.join(BASE_DIR, "benchmark_costs.pkl")

# Load the trained XGBoost model
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

# Load the benchmark cost distribution for percentile scoring
with open(BENCHMARK_COSTS_PATH, "rb") as f:
    benchmark_costs = pickle.load(f)

# Feature list — must match train_model.py exactly
FEATURE_COLS = [
    'AGE23X', 'Gender_Male',
    'Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG',
    'Musculoskeletal_ACG', 'Psychiatric_ACG',
    'Comorbidity_Count', 'Multimorbidity_Penalty', 'Frailty_Index',
    'Age_x_Frailty', 'Age_x_Comorbidity', 'K6SUM42'
]


def monte_carlo_simulation(predicted_mean_cost, n_simulations=5000):
    """Monte Carlo Value-at-Risk premium calculation using Gamma distribution."""
    shape = 1.5
    scale = predicted_mean_cost / shape
    base_cost = 500.0

    simulated_costs = np.random.gamma(shape, scale, n_simulations) + base_cost
    target_premium = np.percentile(simulated_costs, 95)

    return target_premium, simulated_costs


def calculate_risk(data):
    """
    Calculate HealthScore, expected cost, and insurance premium for a patient.
    
    Input data (from frontend):
      - age, gender, height, weight, diseaseInput (free text)
    
    Returns:
      - risk_score (expected medical cost in USD)
      - health_score (0-100 percentile, 100 = healthiest)
      - premium (Monte Carlo VaR-based insurance premium)
      - confidence_interval (5th and 95th percentile of simulated costs)
    """
    age = float(data.get("age", 30))
    gender_male = 1 if str(data.get("gender", "")).lower() == "male" else 0

    # NLP-style keyword extraction from disease input
    user_text = str(data.get("diseaseInput", "")).lower()

    # Cardiovascular conditions
    cardio = 0
    if any(kw in user_text for kw in ["hypertension", "bp", "pressure", "heart", "cardiac", "artery", "stroke", "coronary"]):
        cardio = 1 + sum(1 for kw in ["heart", "stroke", "coronary"] if kw in user_text)
    
    # Metabolic conditions
    metabolic = 0
    if any(kw in user_text for kw in ["diabetes", "sugar", "cholesterol", "thyroid"]):
        metabolic = 1 + (1 if "cholesterol" in user_text else 0)
    
    # Respiratory conditions
    respiratory = 0
    if any(kw in user_text for kw in ["asthma", "breathing", "copd", "bronchitis", "emphysema"]):
        respiratory = 1 + sum(1 for kw in ["copd", "emphysema"] if kw in user_text)
    
    # Oncology
    oncology = 1 if any(kw in user_text for kw in ["cancer", "tumor", "malignant", "oncology"]) else 0
    
    # Musculoskeletal
    msk = 0
    if any(kw in user_text for kw in ["arthritis", "joint", "pain", "orthopedic", "fracture"]):
        msk = 1 + (1 if "arthritis" in user_text else 0)
    
    # Psychiatric
    psych = 0
    if any(kw in user_text for kw in ["depression", "anxiety", "adhd", "mental", "psychiatric", "bipolar"]):
        psych = 1 + (1 if "adhd" in user_text else 0)

    # Derived features
    cluster_vals = [cardio, metabolic, respiratory, oncology, msk, psych]
    comorbidity_count = sum(1 for v in cluster_vals if v > 0)
    multimorbidity_penalty = comorbidity_count ** 2

    # Approximate frailty from perceived health (use moderate defaults)
    # In the frontend, we don't have ADGENH42/ANYLMI23/DFCOG42 directly,
    # so we estimate frailty from comorbidity as a proxy
    perceived_health = 3  # default moderate
    limitation = 1 if comorbidity_count >= 2 else 0
    cognitive = 1 if "cognitive" in user_text or "dementia" in user_text else 0
    frailty_index = perceived_health + (limitation * 2) + (cognitive * 2)

    age_x_frailty = age * frailty_index
    age_x_comorbidity = age * comorbidity_count

    # Build feature vector (order must match FEATURE_COLS)
    import pandas as pd
    patient_df = pd.DataFrame([{
        'AGE23X': age,
        'Gender_Male': gender_male,
        'Cardio_ACG': cardio,
        'Metabolic_ACG': metabolic,
        'Respiratory_ACG': respiratory,
        'Oncology_ACG': oncology,
        'Musculoskeletal_ACG': msk,
        'Psychiatric_ACG': psych,
        'Comorbidity_Count': comorbidity_count,
        'Multimorbidity_Penalty': multimorbidity_penalty,
        'Frailty_Index': frailty_index,
        'Age_x_Frailty': age_x_frailty,
        'Age_x_Comorbidity': age_x_comorbidity,
        'K6SUM42': 0  # default — not available from frontend
    }])[FEATURE_COLS]

    # Predict expected medical cost
    pred_log = model.predict(patient_df)[0]
    expected_cost = float(np.expm1(pred_log))

    # HealthScore: 100 - percentile rank (lower cost = higher score)
    percentile = percentileofscore(benchmark_costs, expected_cost, kind='rank')
    health_score = 100.0 - percentile

    # Monte Carlo VaR premium
    target_premium, simulated_costs = monte_carlo_simulation(expected_cost)

    return {
        "risk_score": round(expected_cost, 2),
        "health_score": round(health_score, 2),
        "premium": round(target_premium, 2),
        "confidence_interval": {
            "p5": round(float(np.percentile(simulated_costs, 5)), 2),
            "p95": round(float(np.percentile(simulated_costs, 95)), 2)
        }
    }