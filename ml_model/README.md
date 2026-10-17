# HealthScore Machine Learning Engine

This directory contains the canonical machine learning pipeline, clinical feature engineering, risk models, artifact integrity safeguards, and actuarial inference engine for the **HealthScore** platform.

---

## 1. Directory Structure

```
ml_model/
├── data_pipeline.py                  # Authoritative MEPS data loading, cleaning & feature engineering
├── train_model.py                    # Training pipeline, 5-fold CV & safe candidate artifact export
├── risk_engine.py                    # Production inference engine with manifest integrity & Monte Carlo VaR
├── run_engine.py                     # Subprocess CLI runner for Node.js backend
├── model_manifest.json               # Cryptographic SHA-256 manifest & schema specification
├── h251.dta                          # Raw MEPS HC-251 (2023 Full Year Consolidated File)
├── benchmark_costs.pkl               # Clean 5-fold Out-Of-Fold (OOF) cost benchmark distribution
├── artifacts/                        # Approved frozen production artifacts
│   ├── risk_model_regressor.pkl      # Approved observable expenditure ranker (Random Forest)
│   ├── tweedie_regressor.pkl         # Approved observable dollar regressor (Tweedie GLM)
│   ├── risk_model_classifier.pkl     # Approved observable high-cost classifier (Survey-Weighted Platt-Calibrated LogReg)
│   ├── feature_schema.json           # Observable feature names, types, and ordering (11 features)
│   ├── training_metadata.json        # Timestamps, train/test counts, locked target thresholds
│   ├── evaluation_metrics.json       # Full test-set regression & classification metrics
│   └── candidates/                   # Unapproved retraining candidates (default export destination)
└── tests/                            # Comprehensive automated pytest suite (92 tests)
    ├── test_pipeline.py              # MEPS data pipeline, leakage prevention, and model export
    ├── test_phase2_clinical_semantics.py # Clinical ACG feature parsing and semantics
    ├── test_phase2_external_validation.py # External validation cohorts (HC-256, HC-257) & calibration
    ├── test_premium_simulation.py    # Actuarial pricing, Monte Carlo VaR, and premium bounds
    └── test_runtime_parity.py        # Manifest cryptographic integrity, schema parity & fail-closed security
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

## 3. Approved Production Models & Target Definitions

Production inference does **not** use uncalibrated heuristic models. It uses three research-approved, frozen artifacts operating strictly on the 11 observable features (age, gender, 6 ACG condition indicators, comorbidity count, quadratic multimorbidity penalty, and age-by-comorbidity interaction):

1. **Relative Expenditure Ranker (`risk_model_regressor.pkl`)**:
   - Model: Random Forest Regressor trained on $\log(1 + \text{TOTEXP})$.
   - Primary role: Population expenditure ranking, percentile anchoring, and clinical condition scoring.
2. **Direct Dollar Regressor (`tweedie_regressor.pkl`)**:
   - Model: Tweedie Generalized Linear Model (power $p=1.5$, $\alpha=1.0$) trained on untransformed dollar expenditure.
   - Primary role: Expected annual dollar loss estimation for actuarial pure premium calculations.
3. **High-Cost Classifier (`risk_model_classifier.pkl`)**:
   - Model: Survey-weighted Platt-calibrated Logistic Regression.
   - Target: **Target 2 (Survey-Weighted Top Decile)**, locked at annual expenditure threshold $\ge \$17,827.41$.
   - Primary role: Catastrophic high-loss probability estimation.

---

## 4. Model Artifact Integrity & Threat Model

### Cryptographic Manifest (`model_manifest.json`)
Every artifact loaded by `risk_engine.py` (including models and the `benchmark_costs.pkl` distribution) is verified at startup against `model_manifest.json`:
- **SHA-256 Digest**: Exact byte-level digest verified before deserialization.
- **Feature Count & Ordering**: Exact 11-feature observable schema checked against scikit-learn attributes.
- **Fail-Closed Loading**: If `model_manifest.json` is missing or any hash mismatches, inference raises an immediate `RuntimeError` or `FileNotFoundError`. Raw, unverified `pickle.load` fallback is prohibited.

### Threat Model & Colocated Hash Limitations
Colocated file hashes detect unintentional drift, truncation, corrupted downloads, and local file modification. However, an attacker with write access to both the artifact directory and `model_manifest.json` could modify weights and update the manifest simultaneously.

To defend against simultaneous tampering:
- In production environments, set the `HEALTHSCORE_MANIFEST_SHA256` environment variable (pinned via KMS, deployment secrets, or container signature).
- `risk_engine.py` validates the SHA-256 digest of `model_manifest.json` against `HEALTHSCORE_MANIFEST_SHA256` before parsing, creating a root of trust outside the filesystem repository.

### Safe Retraining & Candidate Isolation
Running `train_model.py` **does not overwrite frozen approved production artifacts** by default:
- By default, newly trained models are exported to `artifacts/candidates/` with a candidate metadata manifest.
- Retraining cannot silently replace production models or break running inference engines.
- Overwriting production artifacts requires explicit administrative flags: `--overwrite-approved-artifacts` and `--update-manifest`.

---

## 5. Running Automated Tests

Run the complete automated test suite (92 tests):
```bash
pytest tests/ -v
```

The test suite covers:
- **`test_pipeline.py` (26 tests)**: MEPS survey ingestion, zero-cost preservation, leakage prevention, feature engineering, and model training.
- **`test_phase2_clinical_semantics.py` (21 tests)**: Clinical text parsing, ACG diagnostic category mapping, and semantic boundary invariants.
- **`test_phase2_external_validation.py` (22 tests)**: Out-of-cohort generalization on MEPS HC-256 (2024 full year) and HC-257 (2024 SAQ), calibration intercept/slope recovery, and unpenalized logistic fit fallback diagnostics.
- **`test_premium_simulation.py` (9 tests)**: Monte Carlo copula loss simulation, Value-at-Risk (VaR), tail risk metrics, and premium loading invariants.
- **`test_runtime_parity.py` (14 tests)**: Cryptographic manifest verification, auxiliary benchmark hash validation, feature schema order parity, root-of-trust enforcement, and fail-closed security.

---

## 6. Running Inference

### CLI Execution via Subprocess
```bash
python run_engine.py '{"age": 55, "gender": "male", "diseaseInput": "hypertension, type 2 diabetes"}'
```

Output includes transparent distinction between relative ranking score, expected annual dollar expenditure, high-cost probability, and actuarial premium:
```json
{
  "risk_score": 487.65,
  "health_score": 58.76,
  "expected_annual_dollar_expenditure": 6420.50,
  "high_cost_probability": 0.2854,
  "premium": 1845.20,
  "simulated_loss_percentiles": {
    "p50": 3410.00,
    "p90": 14200.00,
    "p95": 21500.00,
    "p99": 48200.00
  },
  "data_parity_diagnostics": {
    "features_observed": ["age", "gender", "diseaseInput"],
    "features_imputed": [],
    "age_representation_parity": {
      "intake_age": 55,
      "model_encoded_age": 55.0,
      "is_top_coded_meps": false
    }
  }
}
```
