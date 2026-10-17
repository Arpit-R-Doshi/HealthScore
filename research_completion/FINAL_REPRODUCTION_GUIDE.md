# HealthScore Comprehensive Reproduction and Execution Guide

**Document ID:** `HS-REP-09-REPRODUCTION-GUIDE`
**Date:** October 2026
**Auditor / Reproducibility Engineer:** Autonomous Research Agent
**Branch:** `feature/ml-pipeline-rebuild`
**Expected Test Result:** 76 Passing Unit Tests (`pytest ml_model/tests/`)

---

## 1. Prerequisites & Environment Setup

### 1.1. System Requirements
- **Operating System:** macOS (Apple Silicon arm64 or Intel x86_64) or Linux (Ubuntu 20.04 / 22.04 LTS).
- **Python:** Version `3.14.8` (or 3.11+).
- **Node.js:** Version `v18.x` or `v20.x` LTS.
- **Docker & Docker Compose:** Docker Desktop with Docker daemon running (required for Hyperledger Fabric).
- **Git:** Version `2.30+`.

### 1.2. Python Environment Initialization
The repository contains an isolated virtual environment in `ml_model/venv`:

```bash
# Verify virtual environment python and installed packages
ml_model/venv/bin/python --version
ml_model/venv/bin/pip list
```

If initializing a fresh virtual environment from scratch:
```bash
python3 -m venv ml_model/venv
source ml_model/venv/bin/activate
pip install numpy scipy pandas scikit-learn xgboost shap pytest matplotlib
```

---

## 2. Dataset Verification & Checksums

The machine learning pipeline requires three authoritative Stata dataset files (`.dta`) from AHRQ:
1. `ml_model/h251.dta` (2023 MEPS HC-251)
2. `ml_model/validation/hc256/data/h256.dta` (2024 MEPS HC-256)
3. `ml_model/validation/hc257/data/h257.dta` (2023–2024 MEPS HC-257 Panel 28)

Run the following command to verify cryptographic checksums:

```bash
ml_model/venv/bin/python -c "
import hashlib, os

files = {
    'HC-251 (2023)': 'ml_model/h251.dta',
    'HC-256 (2024)': 'ml_model/validation/hc256/data/h256.dta',
    'HC-257 (Panel 28)': 'ml_model/validation/hc257/data/h257.dta'
}

for name, path in files.items():
    if os.path.exists(path):
        with open(path, 'rb') as f:
            h = hashlib.sha256(f.read()).hexdigest()
        print(f'{name:20s}: {h}')
    else:
        print(f'{name:20s}: FILE MISSING at {path}')
"
```

Expected SHA-256 outputs:
- `HC-251 (2023)`: `30198e3b1c60f2fc12c8b746fb59d0fc107779d19a2e63cbfa31cbcf5b1bfe9d`
- `HC-256 (2024)`: `b4bde859b39f626345561c05570292bb7264dd92eb76ce0c1a14d6b89076aed5`
- `HC-257 (Panel 28)`: `08d1ff01044982a24e3d5983f54a9b911749728d2bb79156aa6efd4700720c86`

---

## 3. Automated Test Suite Execution

To run the complete automated test suite (clinical semantics, external validation identities, pipeline leakage guards, and premium simulation invariants):

```bash
ml_model/venv/bin/pytest ml_model/tests/
```

**Expected Result:** **76 passed in ~1.2s**
- `test_phase2_clinical_semantics.py`: 21 passed
- `test_phase2_external_validation.py`: 22 passed
- `test_pipeline.py`: 26 passed
- `test_premium_simulation.py`: 7 passed

---

## 4. External Validation Pipelines

To re-run external cross-year validation and prospective forecasting:

### 4.1. MEPS HC-256 (2024 Cross-Year Validation)
```bash
ml_model/venv/bin/python ml_model/validation/hc256/validate_hc256.py
```
- Outputs generated:
  - `ml_model/validation/hc256/metrics_hc256.json`
  - `ml_model/validation/hc256/deciles_hc256.csv`
  - `ml_model/validation/hc256/subgroups_hc256.csv`
- Key verified metrics:
  - Weighted P90 Classifier ROC-AUC: **0.7828**, Brier Skill Score: **+0.1266**
  - Tweedie Observed vs. Predicted Mean: **$9,266.75** vs. **$8,473.71**

### 4.2. MEPS HC-257 (Panel 28 Prospective Forecasting)
```bash
ml_model/venv/bin/python ml_model/validation/hc257/validate_hc257.py
```
- Outputs generated:
  - `ml_model/validation/hc257/metrics_hc257.json`
  - `ml_model/validation/hc257/deciles_hc257.csv`
  - `ml_model/validation/hc257/subgroups_hc257.csv`
- Key verified metrics:
  - Weighted P90 Classifier Prospective ROC-AUC: **0.7807**, Brier Skill Score: **+0.1263**
  - Prospective Tweedie Observed vs. Predicted Mean: **$9,687.75** vs. **$8,585.17** ($R^2 = 0.0652$)
  - Lagged Year 1 Spending Baseline: MAE **$8,625.76**, $R^2 = \mathbf{0.1204}$

---

## 5. Comprehensive Experiments, Ablations & Figures

To execute the full model comparison matrix, feature ablations, SHAP stability audit, subgroup fairness calculations, and generate all publication figures:

```bash
ml_model/venv/bin/python research_completion/experiments/run_comprehensive_benchmarks.py
```

This single command automatically updates:
1. `research_completion/experiments/experiment_registry.json`
2. `research_completion/figures/fig1_roc_pr_curves.png`
3. `research_completion/figures/fig2_calibration_deciles.png`
4. `research_completion/figures/fig3_shap_importance.png`
5. `research_completion/figures/fig4_feature_ablations.png`
6. `research_completion/figures/fig5_blockchain_benchmarks.png`

---

## 6. Hyperledger Fabric Blockchain & Caliper Benchmarks

### 6.1. Spinning Up the 5-Organization Network
Ensure the Docker daemon is active on your host machine:

```bash
# From repository root
./install-fabric.sh   # Downloads images, generates crypto, deploys chaincode
```
Subsequent startups can be resumed instantaneously:
```bash
./resume.sh           # Resumes existing containers with ledger state intact
```

### 6.2. Executing Caliper Benchmarks
```bash
cd caliper-benchmark
npm install
npx caliper launch manager \
  --caliper-workspace . \
  --caliper-benchconfig benchmark.yaml \
  --caliper-networkconfig networkconfig.yaml
```
Benchmark outputs are written to `caliper-benchmark/report.html`.

To pause the network when finished:
```bash
./stop.sh
```

---

## 7. Artifact Integrity Assurance

To confirm that frozen model artifacts have not been altered or overwritten by experimental runs, execute:

```bash
ml_model/venv/bin/python -c "
import hashlib, glob

expected_hashes = {
    'ml_model/risk_model.pkl': '2ba4331510d688b1a21e67156bb5aab547c12e8c1ee109a851591b126a7d9c72',
    'ml_model/artifacts/risk_model_tweedie_observable.pkl': 'a7f185db46316c6ac5f9051f0d5e0e24c7e80f3bd1f7777cd26cd0e1b42fcbd8',
    'ml_model/artifacts/risk_model_classifier_observable_weighted_p90.pkl': '3632f8201136a2740c3d5a564bbdbb29bc8511db51709fb42c1f8e271bf28c2a',
    'ml_model/artifacts/risk_model_classifier_observable_unweighted_p90.pkl': 'cc266ae52414169c3c93b97a8ee147cba5eb62b0e0feff583c85a4e133a880fb'
}

all_match = True
for path, exp_hash in expected_hashes.items():
    with open(path, 'rb') as f:
        curr_hash = hashlib.sha256(f.read()).hexdigest()
    if curr_hash == exp_hash:
        print(f'PASS  {path}')
    else:
        print(f'FAIL  {path}: Expected {exp_hash}, got {curr_hash}')
        all_match = False

assert all_match, 'Model artifact checksum mismatch!'
print('\nALL FROZEN MODEL ARTIFACTS VERIFIED.')
"
```
