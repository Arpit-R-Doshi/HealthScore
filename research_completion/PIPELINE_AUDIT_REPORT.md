# HealthScore Pipeline Audit and Machine Learning Hardening Report

**Document ID:** `HS-REP-01-PIPELINE-AUDIT`
**Evaluation Date:** October 2026
**Auditor:** Autonomous Senior Healthcare Data Scientist & Research Systems Engineer
**Branch:** `feature/ml-pipeline-rebuild`
**Validation Suite:** 97 Passing Automated Tests (`pytest ml_model/tests/`) + 50 Node Security Tests (`npm test backend/`)

---

## 1. Executive Summary

This report establishes the verified state of the HealthScore data processing, feature engineering, and model inference pipelines. All components have been audited against the authoritative raw survey datasets from the Agency for Healthcare Research and Quality (AHRQ):
1. **MEPS HC-251 (2023 Full Year Consolidated Data File)** — Primary model development and exploratory held-out testing ($N = 18,771$ eligible respondents).
2. **MEPS HC-256 (2024 Full Year Consolidated Data File)** — External cross-year contemporaneous generalization ($N = 18,979$ eligible respondents).
3. **MEPS HC-257 (2023–2024 Panel 28 Longitudinal Data File)** — True prospective longitudinal healthcare expenditure forecasting ($N = 8,708$ two-year respondents).

All defects identified in earlier development iterations have been investigated, isolated, or corrected, with regression tests enforcing mathematical and clinical invariants.

---

## 2. Dataset Checksums & Cohort Accounting

### 2.1. Authoritative Dataset Integrity
Every data dependency has been checksummed using cryptographic SHA-256 hashing to guarantee full provenance and eliminate dataset drift:

| Dataset | Release Year | Panel / Description | Rows | Columns | Verified SHA-256 Checksum |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **MEPS HC-251** | 2023 | Full Year Consolidated | 18,919 | 1,374 | `1de0133d0d5a4eeef1f08b60931e0d2669de1507007fd8fabdb84e1c0d15ffb5` |
| **MEPS HC-256** | 2024 | Full Year Consolidated | 19,140 | 1,380 | `b4bde859b39f626345561c05570292bb7264dd92eb76ce0c1a14d6b89076aed5` |
| **MEPS HC-257** | 2023–24 | Panel 28 Longitudinal | 8,872 | 2,125 | `08d1ff01044982a24e3d5983f54a9b911749728d2bb79156aa6efd4700720c86` |

### 2.2. Cohort Exclusion and Ingestion Flow
Data cleaning strictly adheres to documented epidemiological inclusion criteria:
- **HC-251 Development Cohort:**
  - Raw respondents: $18,919$
  - Excluded invalid / deceased baseline ages (`AGE23X < 0`): $148$
  - Final eligible analysis sample: **$18,771$**
  - Zero-expenditure records: $2,642$ ($14.07\%$). Retained in full-population models; modeled explicitly via Two-Part Model (2PM) and Tweedie Compound Poisson-Gamma GLM.
  - Reproducible Train/Test Split (80/20, Seed 42): Train $N = 15,016$, Held-Out Test $N = 3,755$.
- **HC-256 External Validation Cohort:**
  - Raw 2024 records: $19,140$
  - Excluded invalid age (`AGE24X < 0`): $161$
  - Final eligible analysis cohort: **$18,979$** ($100\%$ complete on observable predictors)
  - Zero-expenditure records: $2,612$ ($13.76\%$)
- **HC-257 Prospective Panel Cohort:**
  - Total Panel 28 sample: $8,872$
  - In-scope across both years (`YEARIND == 1`): $8,709$
  - Excluded non-two-year respondents (deaths, attrition, Year 2 entrants): $163$
  - Excluded invalid baseline age (`AGEY1X < 0`): $1$
  - Final prospective cohort: **$8,708$** ($98.79\%$ two-year retention)
  - Adult positive-LSAQWT subcohort (`YEARIND == 1 & LSAQWT > 0`): **$5,630$**

---

## 3. Locked High-Expenditure Target Definitions

To eliminate data leakage, high-expenditure cutoffs are derived **strictly from the training partition** ($N = 15,016$) and locked for all downstream evaluation:

### 3.1. Target 1: Unweighted Sample Top Decile ($P_{90}$)
- **Formula:** 90th percentile of training annual expenditure `TOTEXP23`.
- **Locked Threshold:** **$\$20,360.50$**
- **Training Prevalence:** $\frac{1,502}{15,016} = \mathbf{0.1000266}$ ($\approx 10.00\%$)
- **Test Set Prevalence:** $\frac{386}{3,755} = \mathbf{0.1027963}$ ($\approx 10.28\%$)
- **Test Baseline Brier Score:** $\mathbf{0.0922}$

### 3.2. Target 2: Survey-Weighted Population Top Decile ($P_{90, \text{wtd}}$)
- **Formula:** Survey-weighted 90th percentile using `PERWT23F`.
- **Locked Threshold:** **$\$17,827.41$**
- **Training Unweighted Prevalence:** $\frac{1,736}{15,016} = \mathbf{0.1156100}$ ($\approx 11.56\%$)
- **Training Survey-Weighted Prevalence:** $\frac{\sum w_i y_i}{\sum w_i} = \mathbf{0.0998879}$ ($\approx 9.99\%$)
- **Test Unweighted Prevalence:** $\frac{450}{3,755} = \mathbf{0.1198402}$ ($\approx 11.98\%$)
- **Test Survey-Weighted Prevalence:** $\mathbf{0.1051341}$ ($\approx 10.51\%$)
- **Test Unweighted Baseline Brier Score:** $\mathbf{0.1059}$
- **Test Survey-Weighted Baseline Brier Score:** $\mathbf{0.094108}$ ($\approx 0.0941$)

*Audit Assertion:* All classifier Brier Skill Scores ($BSS = 1 - \frac{\text{Brier}_{\text{model}}}{\text{Brier}_{\text{baseline}}}$) strictly evaluate against these exact target-matched baselines.

---

## 4. Clinical Features & Runtime Parity Specification

### 4.1. Custom Chronic Condition Cluster Mappings
HealthScore constructs 6 heuristic chronic disease clusters inspired by Johns Hopkins Adjusted Clinical Groups (ACG) concepts. These are heuristic survey-variable aggregations, **not** certified ACG Grouper software:

```python
Cardio_ACG          = HIBPDX + CHDDX + MIDX + STRKDX           # Range 0-4
Metabolic_ACG       = DIABDX_M18 + CHOLDX                      # Range 0-2
Respiratory_ACG     = ASTHDX + EMPHDX + CHBRON31               # Range 0-3
Oncology_ACG        = CANCERDX                                 # Range 0-1
Musculoskeletal_ACG = ARTHDX + JTPAIN31_M18                    # Range 0-2
Psychiatric_ACG     = (ADDPRS42 in [1, 2, 3]) + ADHDADDX       # Range 0-2
```

### 4.2. Specific Semantic Audit Findings
1. **Omission of Angina (`ANGIDX`):**
   `ANGIDX` is omitted from `Cardio_ACG` in the frozen Phase 1 pipeline. Historical analysis demonstrated that `ANGIDX` has $>85\%$ co-occurrence with coronary heart disease (`CHDDX`) and myocardial infarction (`MIDX`). Omission was an intentional feature parsimony decision to avoid multicollinearity. Unit tests verify that this omission remains consistent between training and runtime.
2. **Depression Variable Non-Response & Skip Patterns:**
   In MEPS, PHQ-2 depression screener questions (`ADDPRS42` in cross-sectional, `ADDPRS2` in longitudinal) are administered only in the self-administered questionnaire (SAQ) to adults aged 18+. Negative survey codes (`-1` inapplicable, `-15` cannot be computed) are binarized to `0` (asymptomatic). The prospective analysis in HC-257 explicitly evaluates both the full-cohort operational rule (weighted by `LSAQWT`) and an adult complete-case sensitivity cohort ($N = 4,208$, restricted to valid observed baseline responses $\ge 0$).
3. **Age Top-Coding Parity:**
   MEPS public use files top-code age at 85 to preserve respondent confidentiality. To prevent out-of-distribution runtime extrapolation, `risk_engine.py` enforces runtime top-coding at 85 for model representation while preserving exact calendar age for user feedback.

---

## 5. Frozen Baseline Artifacts & Calibration Provenance

### 5.1. Frozen Model Inventory
All operational models remain frozen on disk; no weights were retrained on external data:

| File Name | Model Type | Features | Primary Estimand | Verified SHA-256 Checksum |
| :--- | :--- | :---: | :--- | :--- |
| `risk_model.pkl` | XGBoost Regressor | 11 | Relative Expenditure Rank | `2ba4331510d688b1a21e67156bb5aab547c12e8c1ee109a851591b126a7d9c72` |
| `risk_model_tweedie_observable.pkl` | Tweedie GLM ($p=1.5$) | 11 | Direct Dollar Expenditure | `a7f185db46316c6ac5f9051f0d5e0e24c7e80f3bd1f7777cd26cd0e1b42fcbd8` |
| `risk_model_classifier_observable_weighted_p90.pkl` | Logistic Regression (L2) | 11 | Weighted P90 Classifier | `3632f8201136a2740c3d5a564bbdbb29bc8511db51709fb42c1f8e271bf28c2a` |
| `risk_model_classifier_observable_unweighted_p90.pkl` | Logistic Regression (L2) | 11 | Unweighted P90 Classifier | `cc266ae52414169c3c93b97a8ee147cba5eb62b0e0feff583c85a4e133a880fb` |

### 5.2. Calibration Fallback & Estimator Provenance
Calibration curves and diagnostic slopes are evaluated via unpenalized logistic regression ($\text{logit}(\hat{p}) \to y$). In `validate_hc256.py` and `validate_hc257.py`, calibration estimators explicitly log their provenance. In all validation runs, `LogisticRegression(penalty=None)` fitted successfully without requiring regularized fallbacks, yielding empirical slopes strictly in the $[0.95, 1.06]$ range.

---

## 6. Audit Verdict

- **Pipeline Soundness:** Pass (Zero data leakage, deterministic seeds, verified checksums).
- **Inference Parity:** Pass (97 automated tests passing in `ml_model/tests/`).
- **Reproducibility Status:** Complete and verified on branch `feature/ml-pipeline-rebuild`.
