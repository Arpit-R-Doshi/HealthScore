# HealthScore Machine Learning Engine

This directory contains the canonical machine learning pipeline, clinical feature engineering, risk models, and actuarial inference engine for the **HealthScore** platform.

---

## 1. Directory Structure

```
ml_model/
├── data_pipeline.py            # Authoritative MEPS data loading, cleaning & feature engineering
├── train_model.py              # Canonical training pipeline, 5-fold CV & artifact export
├── risk_engine.py              # Production inference engine with schema validation & Monte Carlo VaR
├── run_engine.py               # Subprocess CLI runner for Node.js backend
├── h251.dta                    # Raw MEPS HC-251 (2023 Full Year Consolidated File)
├── risk_model.pkl              # Production XGBoost regressor (backward-compatible)
├── benchmark_costs.pkl         # Clean 5-fold Out-Of-Fold (OOF) cost benchmark distribution
├── artifacts/                  # Versioned model artifacts & provenance metadata
│   ├── feature_schema.json     # Feature names, types, and encodings
│   ├── training_metadata.json  # Timestamps, SHAP rankings, sample sizes
│   ├── evaluation_metrics.json # Full test-set regression & classification metrics
│   ├── risk_model_regressor.pkl
│   ├── risk_model_classifier.pkl
│   └── benchmark_costs_oof.pkl
└── tests/
    └── test_pipeline.py        # Automated pytest suite (14 unit & integration tests)
```

---

## 2. Environment Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.14.8 on macOS Apple Silicon / Linux)
- `libomp` (on macOS Apple Silicon: `brew install libomp`)

### Setup Virtual Environment
```bash
cd ml_model
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install numpy scipy pandas xgboost scikit-learn shap pytest
```

---

## 3. Training the Models

To execute the complete training pipeline from raw data to exported artifacts:
```bash
python train_model.py
```

This command will:
1. Load `h251.dta` (18,919 raw survey records).
2. Clean and engineer the 14 clinical ACG features (preserving all 18,771 eligible records, including zero-expenditure individuals).
3. Split the data into an 80% Train set ($N=15,016$) and a 20% Held-Out Test set ($N=3,755$).
4. Run 5-fold cross-validation across regression and classification candidates.
5. Generate an unbiased **Out-of-Fold (OOF)** cost distribution (`benchmark_costs.pkl`) on the training set to eliminate in-sample leakage.
6. Train the production **Dual-XGBoost** models (Expenditure Regressor + High-Cost Classifier).
7. Calculate SHAP feature importance values on the held-out test set.
8. Save artifacts to `artifacts/` and update `risk_model.pkl` and `benchmark_costs.pkl`.

---

## 4. Running Automated Tests

Run the full automated test suite:
```bash
pytest tests/test_pipeline.py -v
```

All 14 tests cover:
- MEPS data schema and row-count flow
- Mental health variable coding bug fix (`ADDPRS42`)
- Strict train/test separation (zero leakage)
- Feature schema parity between training and inference
- Model artifact serialization and loading
- Clean OOF benchmark distribution bounds
- Validated patient inferences across demographic and multimorbid profiles
- Input schema validation and rejection of malformed inputs

---

## 5. Running Inference

### CLI Test Execution
```bash
python run_engine.py '{"age": 45, "gender": "male", "diseaseInput": "Hypertension, Diabetes"}'
```

Output:
```json
{
  "risk_score": 452.88,
  "health_score": 62.14,
  "premium": 1642.11,
  "high_cost_probability": 0.3125,
  "confidence": {
    "p5": 542.10,
    "p95": 1642.11
  },
  "top_risk_factors": [
    "2 chronic condition cluster(s)",
    "Cardiovascular risk",
    "Metabolic risk"
  ]
}
```
