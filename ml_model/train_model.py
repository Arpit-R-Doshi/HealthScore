import pandas as pd
import numpy as np
import pickle
import os
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

CSV_FILE = "new_responses.csv"
MODEL_FILE = "risk_model.pkl"
SCALER_FILE = "scaler.pkl"

def train():
    print("--- Starting HealthScore Model Training ---")

    if not os.path.exists(CSV_FILE):
        print(f"Error: Could not find '{CSV_FILE}'")
        return

    try:
        df = pd.read_csv(CSV_FILE)
        # Clean column names (lowercase and remove spaces)
        df.columns = [c.strip().lower() for c in df.columns]
        print(f"Mapping Columns: {list(df.columns)}")

        # 1. Map your specific CSV columns to the model variables
        df['bmi'] = df['weight (in kgs)'] / ((df['height (in cms)'] / 100) ** 2)
        df['age_quadratic'] = (df['age'] - 30) ** 2
        
        # 2. Encode Gender (Assume 'male' or 'm' is 1, else 0)
        df['gender_male'] = df['gender'].apply(lambda x: 1 if str(x).lower().startswith('m') else 0)

        # 3. Handle Diseases (Check if 'disease 1-4' contain specific strings)
        # We create binary columns for the model
        for d in ['diabetes', 'hypertension', 'asthma', 'heart disease']:
            df[d] = df[['disease 1', 'disease 2', 'disease 3', 'disease 4']].apply(
                lambda x: 1 if x.astype(str).str.contains(d, case=False).any() else 0, axis=1
            )

        # 4. Interaction term
        df['obesity_x_diabetes'] = df['bmi'] * df['diabetes']

        # 5. CREATE A TARGET (Since your CSV is missing 'Base_RiskScore')
        # We calculate a simple risk score for training purposes
        df['base_riskscore'] = (df['age'] * 0.1) + (df['bmi'] * 0.2) + (df['diabetes'] * 5) + (df['heart disease'] * 8)

        # 6. Define Features and Target
        features = ['age_quadratic', 'bmi', 'gender_male', 'obesity_x_diabetes', 
                    'diabetes', 'hypertension', 'asthma', 'heart disease']
        
        X = df[features]
        y = df['base_riskscore']

        print(f"Training on: {features}")

        # 7. Scaling and Training
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        model = Ridge(alpha=1.0)
        model.fit(X_scaled, y)

        # 8. Save
        with open(MODEL_FILE, "wb") as f:
            pickle.dump(model, f)
        with open(SCALER_FILE, "wb") as f:
            pickle.dump(scaler, f)

        print(f"✅ SUCCESS: Model saved as '{MODEL_FILE}'")

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    train()