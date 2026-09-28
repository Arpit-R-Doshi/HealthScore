import numpy as np
import pandas as pd
from scipy.stats import percentileofscore
from sklearn.model_selection import train_test_split
import xgboost as xgb
import warnings

warnings.filterwarnings('ignore')

# =====================================================
# 1. DATA LOADING AND CLEANING (MEPS - STATA)
# =====================================================

def load_and_clean_meps(filepath="h251.dta"):  
    try:
        print(f"Loading Stata file: {filepath} (This might take a minute...)")
        df = pd.read_stata(filepath, convert_categoricals=False)
    except FileNotFoundError:
        print(f"\n[ERROR] Could not find {filepath}.")
        print("Please ensure your MEPS .dta file is in the exact same folder as this Python script.")
        raise

    df = df[(df['AGE23X'] >= 0)]
    df = df[df['TOTEXP23'] > 0] 

    if 'SEX' in df.columns:
        df['Gender_Male'] = (df['SEX'] == 1).astype(int)
    else:
        df['Gender_Male'] = 0

    binary_dx_cols =[
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
    
    cluster_cols =['Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 
                    'Oncology_ACG', 'Musculoskeletal_ACG', 'Psychiatric_ACG']
    
    df['Comorbidity_Count'] = (df[cluster_cols] > 0).sum(axis=1)
    df['Multimorbidity_Penalty'] = df['Comorbidity_Count'] ** 2 
    df['Frailty_Index'] = df['ADGENH42'] + (df['ANYLMI23'] * 2) + (df['DFCOG42'] * 2)

    df['Age_x_Frailty'] = df['AGE23X'] * df['Frailty_Index']
    df['Age_x_Comorbidity'] = df['AGE23X'] * df['Comorbidity_Count']

    features =[
        'AGE23X', 'Gender_Male', 
        'Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG', 
        'Musculoskeletal_ACG', 'Psychiatric_ACG', 
        'Comorbidity_Count', 'Multimorbidity_Penalty', 'Frailty_Index', 
        'Age_x_Frailty', 'Age_x_Comorbidity', 'K6SUM42'
    ]
    
    return df, features

# =====================================================
# 3. XGBOOST MODEL TRAINING
# =====================================================

def train_xgboost_pipeline(df, features):
    print("Training XGBoost Engine...")
    
    X = df[features]
    y_log_cost = np.log1p(df['TOTEXP23']) 

    X_train, X_test, y_train_log, y_test_log = train_test_split(
        X, y_log_cost, test_size=0.20, random_state=42
    )

    xgb_regressor = xgb.XGBRegressor(
        objective='reg:squarederror', n_estimators=500, learning_rate=0.01,      
        max_depth=5, subsample=0.8, colsample_bytree=0.8, gamma=2, reg_alpha=1, reg_lambda=1, random_state=42
    )
    
    xgb_regressor.fit(X_train, y_train_log)

    # Attach the model predictions to the dataframe for percentile calculation later
    df['Predicted_Cost'] = np.expm1(xgb_regressor.predict(X))

    return xgb_regressor, df

# =====================================================
# 4. MONTE CARLO SIMULATION
# =====================================================

def monte_carlo_simulation(predicted_mean_cost, n_simulations=5000):
    shape = 1.5 
    scale = predicted_mean_cost / shape
    base_cost = 500.0  
    
    simulated_costs = np.random.gamma(shape, scale, n_simulations) + base_cost
    target_premium = np.percentile(simulated_costs, 95)
    
    return target_premium

# =====================================================
# 5. NEW PATIENT INFERENCE & OUTPUT
# =====================================================

def analyze_new_patient(model, benchmark_df, features):
    print("\n--- Enter Patient Details ---")
    age = float(input("Age: "))
    gender = input("Gender (Male/Female): ").strip().lower()
    
    print("\n-- Medical Conditions (Enter 1 for Yes, 0 for No) --")
    cardio = int(input("Any Cardiovascular conditions (BP/Heart)? "))
    metabolic = int(input("Any Metabolic conditions (Diabetes/Cholesterol)? "))
    respiratory = int(input("Any Respiratory conditions (Asthma/COPD)? "))
    oncology = int(input("Any Cancer diagnosis? "))
    msk = int(input("Any Musculoskeletal conditions (Arthritis)? "))
    psych = int(input("Any Psychiatric conditions (Depression/ADHD)? "))
    
    print("\n-- General Health Status --")
    perceived_health = int(input("Perceived Physical Health (1=Excellent, 5=Poor): "))
    limitation = int(input("Any physical limitation? (1=Yes, 0=No): "))
    cognitive = int(input("Any cognitive impairment? (1=Yes, 0=No): "))

    comorbidity_count = cardio + metabolic + respiratory + oncology + msk + psych
    frailty = perceived_health + (limitation * 2) + (cognitive * 2)

    patient_data = pd.DataFrame([{
        'AGE23X': age,
        'Gender_Male': 1 if gender == 'male' else 0,
        'Cardio_ACG': cardio,
        'Metabolic_ACG': metabolic,
        'Respiratory_ACG': respiratory,
        'Oncology_ACG': oncology,
        'Musculoskeletal_ACG': msk,
        'Psychiatric_ACG': psych,
        'Comorbidity_Count': comorbidity_count,
        'Multimorbidity_Penalty': comorbidity_count ** 2,
        'Frailty_Index': frailty,
        'Age_x_Frailty': age * frailty,
        'Age_x_Comorbidity': age * comorbidity_count,
        'K6SUM42': 0 
    }])[features]

    # Predict expected cost
    pred_log = model.predict(patient_data)[0]
    expected_cost = np.expm1(pred_log)

    # Calculate relative HealthScore percentile
    percentile = percentileofscore(benchmark_df['Predicted_Cost'], expected_cost, kind='rank')
    health_score = 100 - percentile  

    # Calculate Value-at-Risk Premium using Monte Carlo
    target_premium = monte_carlo_simulation(expected_cost)

    print("\n" + "="*50)
    print("      HEALTHSCORE & SMART CONTRACT PROFILE")
    print("="*50)
    print(f"HealthScore:             {health_score:.1f}th Percentile (100 is best)")
    print(f"Expected Medical Cost:   ${expected_cost:,.2f}")
    print(f"Contract Premium (VaR):  ${target_premium:,.2f}")
    print("="*50)


# =====================================================
# MAIN EXECUTION
# =====================================================
if __name__ == "__main__":
    print("Initializing HealthScore Actuarial Engine...")
    
    stata_filename = "h251.dta"  
    
    try:
        df_clean = load_and_clean_meps(stata_filename)
        df_engineered, feature_cols = build_acg_features(df_clean)
        
        # Train XGBoost model
        trained_model, benchmark_df = train_xgboost_pipeline(df_engineered, feature_cols)
        
        # Interactive loop for patients
        while True:
            analyze_new_patient(trained_model, benchmark_df, feature_cols)
            cont = input("\nAnalyze another patient? (yes/no): ")
            if cont.lower() not in ['y', 'yes']:
                break
                
    except FileNotFoundError:
        print(f"\n[SYSTEM ALERT] Please place your MEPS dataset ({stata_filename}) in the same directory as this code.")