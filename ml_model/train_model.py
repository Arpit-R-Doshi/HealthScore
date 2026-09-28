import numpy as np
import pandas as pd
from scipy.stats import percentileofscore
from sklearn.model_selection import train_test_split
import xgboost as xgb
import pickle
import os
import warnings

warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_FILE = os.path.join(BASE_DIR, "h251.dta")
MODEL_FILE = os.path.join(BASE_DIR, "risk_model.pkl")
SCALER_FILE = os.path.join(BASE_DIR, "benchmark_costs.pkl")

# Feature list used by the model — must match risk_engine.py exactly
FEATURE_COLS = [
    'AGE23X', 'Gender_Male',
    'Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG',
    'Musculoskeletal_ACG', 'Psychiatric_ACG',
    'Comorbidity_Count', 'Multimorbidity_Penalty', 'Frailty_Index',
    'Age_x_Frailty', 'Age_x_Comorbidity', 'K6SUM42'
]

# =====================================================
# 1. DATA LOADING AND CLEANING (MEPS - STATA)
# =====================================================

def load_and_clean_meps(filepath):
    try:
        print(f"Loading Stata file: {filepath} (This might take a minute...)")
        df = pd.read_stata(filepath, convert_categoricals=False)
    except FileNotFoundError:
        print(f"\n[ERROR] Could not find {filepath}.")
        print("Please ensure your MEPS .dta file is in the ml_model directory.")
        raise

    df = df[(df['AGE23X'] >= 0)]
    df = df[df['TOTEXP23'] > 0]

    if 'SEX' in df.columns:
        df['Gender_Male'] = (df['SEX'] == 1).astype(int)
    else:
        df['Gender_Male'] = 0

    binary_dx_cols = [
        'HIBPDX', 'CHDDX', 'MIDX', 'STRKDX', 'DIABDX_M18', 'CHOLDX',
        'ASTHDX', 'EMPHDX', 'CHBRON31', 'CANCERDX', 'ARTHDX', 'JTPAIN31_M18',
        'ADDPRS42', 'ADHDADDX', 'DFCOG42', 'ANYLMI23'
    ]

    for col in binary_dx_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: 1 if x == 1 else 0)
        else:
            df[col] = 0

    if 'ADGENH42' in df.columns:
        df['ADGENH42'] = df['ADGENH42'].apply(lambda x: x if x > 0 else 3)
    else:
        df['ADGENH42'] = 3

    if 'K6SUM42' in df.columns:
        df['K6SUM42'] = df['K6SUM42'].apply(lambda x: x if x >= 0 else 0)
    else:
        df['K6SUM42'] = 0

    return df

# =====================================================
# 2. FEATURE ENGINEERING (Johns Hopkins ACG & Interactions)
# =====================================================

def build_acg_features(df):
    df['Cardio_ACG'] = df['HIBPDX'] + df['CHDDX'] + df['MIDX'] + df['STRKDX']
    df['Metabolic_ACG'] = df['DIABDX_M18'] + df['CHOLDX']
    df['Respiratory_ACG'] = df['ASTHDX'] + df['EMPHDX'] + df['CHBRON31']
    df['Oncology_ACG'] = df['CANCERDX']
    df['Musculoskeletal_ACG'] = df['ARTHDX'] + df['JTPAIN31_M18']
    df['Psychiatric_ACG'] = df['ADDPRS42'] + df['ADHDADDX']

    cluster_cols = ['Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG',
                    'Oncology_ACG', 'Musculoskeletal_ACG', 'Psychiatric_ACG']

    df['Comorbidity_Count'] = (df[cluster_cols] > 0).sum(axis=1)
    df['Multimorbidity_Penalty'] = df['Comorbidity_Count'] ** 2
    df['Frailty_Index'] = df['ADGENH42'] + (df['ANYLMI23'] * 2) + (df['DFCOG42'] * 2)

    df['Age_x_Frailty'] = df['AGE23X'] * df['Frailty_Index']
    df['Age_x_Comorbidity'] = df['AGE23X'] * df['Comorbidity_Count']

    return df

# =====================================================
# 3. XGBOOST MODEL TRAINING
# =====================================================

def train_xgboost_pipeline(df):
    print("Training XGBoost Engine...")

    X = df[FEATURE_COLS]
    y_log_cost = np.log1p(df['TOTEXP23'])

    X_train, X_test, y_train_log, y_test_log = train_test_split(
        X, y_log_cost, test_size=0.20, random_state=42
    )

    xgb_regressor = xgb.XGBRegressor(
        objective='reg:squarederror', n_estimators=500, learning_rate=0.01,
        max_depth=5, subsample=0.8, colsample_bytree=0.8, gamma=2,
        reg_alpha=1, reg_lambda=1, random_state=42
    )

    xgb_regressor.fit(X_train, y_train_log)

    # Attach the model predictions to the dataframe for percentile calculation later
    df['Predicted_Cost'] = np.expm1(xgb_regressor.predict(X))

    # Evaluate
    from sklearn.metrics import r2_score, mean_absolute_error
    y_pred_test = xgb_regressor.predict(X_test)
    r2 = r2_score(y_test_log, y_pred_test)
    mae = mean_absolute_error(np.expm1(y_test_log), np.expm1(y_pred_test))
    print(f"  R² Score: {r2:.4f}")
    print(f"  MAE (USD): ${mae:,.2f}")

    return xgb_regressor, df

# =====================================================
# MAIN TRAINING EXECUTION
# =====================================================
def train():
    print("--- Starting HealthScore XGBoost Model Training ---")
    print(f"  Dataset: {DATASET_FILE}")

    # 1. Load and clean
    df_clean = load_and_clean_meps(DATASET_FILE)
    print(f"  Records after cleaning: {len(df_clean)}")

    # 2. Feature engineering
    df_engineered = build_acg_features(df_clean)

    # 3. Train XGBoost model
    trained_model, benchmark_df = train_xgboost_pipeline(df_engineered)

    # 4. Save model
    with open(MODEL_FILE, "wb") as f:
        pickle.dump(trained_model, f)
    print(f"  ✅ Model saved: {MODEL_FILE}")

    # 5. Save benchmark cost distribution (for percentile scoring at inference time)
    benchmark_costs = benchmark_df['Predicted_Cost'].values
    with open(SCALER_FILE, "wb") as f:
        pickle.dump(benchmark_costs, f)
    print(f"  ✅ Benchmark costs saved: {SCALER_FILE}")

    print("\n--- Training Complete ---")

if __name__ == "__main__":
    train()