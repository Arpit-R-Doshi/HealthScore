# HealthScore Feature Harmonization & Lineage Audit

**Document Version:** 1.0  
**Audit Date:** October 2026  
**Auditor:** Antigravity Autonomous Research Agent  
**Repository Branch:** `feature/ml-pipeline-rebuild`  
**Audit Scope:** Phase 1 Training Feature Engineering vs. Phase 2 External Validation & Structured Intake  

---

## 1. Executive Summary

A discrepancy was identified between the feature engineering formulas used during Phase 1 training (`ml_model/data_pipeline.py`) and the initial draft of the Phase 2 external validation scripts (`validate_hc256.py` and `validate_hc257.py` v1.0).

Specifically:
1. **Integer Sums vs. Severity Tiers:** The Phase 1 training pipeline engineered condition clusters as **unweighted integer sums of discrete MEPS binary indicators** (e.g. `Cardio_ACG` $\in [0, 4]$, `Musculoskeletal_ACG` $\in [0, 2]$). In contrast, draft validation scripts had substituted heuristic clinical severity tiers capped at 2.
2. **Omission of Joint Pain:** In Phase 1 training, `Musculoskeletal_ACG` was engineered as `ARTHDX + JTPAIN31_M18`. Initial external scripts checked only `ARTHDX`, omitting `JTPAIN31_M18` (and its longitudinal equivalent `JTPAIN1_M18`).
3. **Gender Defaulting:** `validate_input` previously defaulted missing gender to `"male"`. It has now been hardened to require explicit gender entry, rejecting missing or invalid values.
4. **Structured Intake Parity:** Structured condition intake has been reconciled to map clinical concepts directly to discrete MEPS survey indicators before computing cluster sums, and unmapped concepts (such as bipolar disorder or anxiety) are quarantined rather than inflating feature sums.

All validation scripts and runtime intake modules have been updated to enforce **exact mathematical parity** with the frozen Phase 1 training data.

---

## 2. Authoritative Feature Engineering Lineage Table

The table below contrasts the exact transformations used in Phase 1 training with the initial draft and the reconciled implementation:

| Feature Name | MEPS Training Source (`HC-251`) | MEPS External Source (`HC-256` / `HC-257`) | Phase 1 Training Formula (`data_pipeline.py`) | Initial Draft Formula (Discrepant) | Reconciled Implementation (`v2.0`) | Mathematical Range |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **`AGE23X`** | `AGE23X` | `AGE24X` (HC-256) / `AGEY1X` (HC-257) | Filtered $\ge 0$. Direct float. Top-coded at 85 in MEPS. | Direct float. | Direct float (`AGE24X` / `AGEY1X`). Column named `AGE23X` for model compatibility. | $[0, 85]$ |
| **`Gender_Male`** | `SEX` | `SEX` | `(SEX == 1).astype(int)` | `(SEX == 1).astype(int)` | `(SEX == 1).astype(int)`. In runtime `validate_input`, missing gender raises `ValueError`. | $\{0, 1\}$ |
| **`Cardio_ACG`** | `HIBPDX`, `CHDDX`, `MIDX`, `STRKDX` | Same (with `*Y1` in HC-257) | `HIBPDX + CHDDX + MIDX + STRKDX` | Tier logic: 2 if Stroke/MI/CAD/Angina else 1 if HTN else 0 | **`HIBPDX + CHDDX + MIDX + STRKDX`** (Discrete integer sum of 4 confirmed indicators). | $[0, 4]$ |
| **`Metabolic_ACG`** | `DIABDX_M18`, `CHOLDX` | Same (with `*Y1` in HC-257) | `DIABDX_M18 + CHOLDX` | Tier logic: 2 if both else 1 if either else 0 | **`DIABDX_M18 + CHOLDX`** (Discrete integer sum of 2 confirmed indicators). | $[0, 2]$ |
| **`Respiratory_ACG`** | `ASTHDX`, `EMPHDX`, `CHBRON31` | `CHBRON31` (HC-256) / `CHBRON1` (HC-257) | `ASTHDX + EMPHDX + CHBRON31` | Tier logic: 2 if COPD/emphysema/bronchitis else 1 if asthma else 0 | **`ASTHDX + EMPHDX + CHBRON`** (Discrete integer sum of 3 confirmed indicators). | $[0, 3]$ |
| **`Oncology_ACG`** | `CANCERDX` | `CANCERDX` (HC-256) / `CANCERY1` (HC-257) | `(CANCERDX == 1).astype(int)` | `(CANCERDX == 1).astype(int)` | **`CANCERDX`** (Binary diagnosis indicator). | $\{0, 1\}$ |
| **`Musculoskeletal_ACG`** | `ARTHDX`, `JTPAIN31_M18` | `JTPAIN31_M18` (HC-256) / `JTPAIN1_M18` (HC-257) | `ARTHDX + JTPAIN31_M18` | Checked only `ARTHDX` (omitted `JTPAIN`) | **`ARTHDX + JTPAIN`** (Discrete integer sum of arthritis and joint pain indicators). | $[0, 2]$ |
| **`Psychiatric_ACG`** | `ADDPRS42`, `ADHDADDX` | `ADDPRS42` (HC-256) / `ADDPRS2` (HC-257), `ADHDADY1` | `ADDPRS42 (in [1,2,3]) + ADHDADDX` | Checked `ADDPRS42 in [1,2,3] or ADHDADDX == 1` (capped at 1) | **`ADDPRS + ADHD`** (Discrete integer sum of depressive symptoms and pediatric ADHD). | $[0, 2]$ |
| **`Comorbidity_Count`** | Derived | Derived | $\sum_{k=1}^6 \mathbb{I}(\text{Cluster}_k > 0)$ | Same | **$\sum_{k=1}^6 \mathbb{I}(\text{Cluster}_k > 0)$** | $[0, 6]$ |
| **`Multimorbidity_Penalty`** | Derived | Derived | $\text{Comorbidity\_Count}^2$ | Same | **$\text{Comorbidity\_Count}^2$** | $[0, 36]$ |
| **`Age_x_Comorbidity`** | Derived | Derived | $\text{AGE23X} \times \text{Comorbidity\_Count}$ | Same | **$\text{AGE23X} \times \text{Comorbidity\_Count}$** | $[0, 510]$ |

---

## 3. Detailed Audit of Specific Methodological Inconsistencies

### 3.1. Angina in `Cardio_ACG`
- **Finding:** In `ml_model/data_pipeline.py`, `ANGIDX` was included in the binarization list `binary_dx_cols` (line 146), but was **omitted from the summation formula** in line 168:
  ```python
  df_clean['Cardio_ACG'] = df_clean['HIBPDX'] + df_clean['CHDDX'] + df_clean['MIDX'] + df_clean['STRKDX']
  ```
- **Resolution:** In external validation and runtime inference, `Cardio_ACG` strictly sums the 4 condition indicators that the frozen model learned from (`HIBPDX`, `CHDDX`, `MIDX`, `STRKDX`). Mentions of angina are quarantined or mapped to CAD/coronary indicators where clinically documented.

### 3.2. Musculoskeletal Joint Pain (`JTPAIN`)
- **Finding:** In Phase 1 training, `Musculoskeletal_ACG` is the sum of `ARTHDX` (arthritis diagnosis) and `JTPAIN31_M18` (joint pain during the past 12 months). The initial draft of `validate_hc256.py` and `validate_hc257.py` only checked `ARTHDX`, omitting joint pain.
- **Impact:** Omitting `JTPAIN` artificially lowered musculoskeletal comorbidity counts in external cohorts, understating predicted spending.
- **Resolution:** `JTPAIN31_M18` was integrated into `validate_hc256.py`, and `JTPAIN1_M18` was integrated into `validate_hc257.py`.

### 3.3. Psychiatric Feature Semantics: Screener vs. Diagnosis
- **Finding:** `Psychiatric_ACG` combines two distinct data-generation processes:
  1. `ADDPRS42` (or `ADDPRS2` in HC-257): A self-administered questionnaire (SAQ) PHQ-2 symptom screener administered to adults $\ge 18$, measuring symptom frequency over the past 2 weeks (codes 1=Few days, 2=Half days, 3=Nearly every day).
  2. `ADHDADDX` (or `ADHDADY1` in HC-257): A doctor-diagnosed condition asked of children aged 5–17.
- **Resolution:** Discrete integer addition is preserved. Bipolar disorder and generalized anxiety disorder are **not** mapped into this feature, because the MEPS training dataset does not contain separate observable survey indicators for them. In structured intake, they are recorded in `unmapped_clinical_concepts` to avoid artificial feature inflation.

### 3.4. Missing-Data & Gender Policy
- **Finding:** `validate_input` in `risk_engine.py` previously defaulted missing gender to `"male"`.
- **Resolution:** Hardened to reject missing or invalid gender entries with an explicit `ValueError("Missing required field: 'gender' (must be 'male' or 'female')")`.

### 3.5. Negative MEPS Response Codes & Age Top-Coding
- **Finding:** In MEPS, negative codes represent survey non-response (`-1` Inapplicable, `-7` Refused, `-8` Don't Know, `-9` Not Ascertained).
- **Resolution:** All condition indicators are strictly evaluated as `(col == 1).astype(int)`, ensuring that negative codes evaluate to 0 (absence of confirmed diagnosis), matching the training pipeline. Age is top-coded at 85 per MEPS public-use file privacy protections.

---

## 4. Verification & Status

- **Lineage Audit:** **COMPLETE.**
- **Pipeline Consistency:** **CONFIRMED & HARMONIZED.**
- **Automated Test Coverage:** Verified via `test_feature_parity_with_training_pipeline` in `test_phase2_external_validation.py`.
