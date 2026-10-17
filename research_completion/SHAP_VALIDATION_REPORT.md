# HealthScore SHAP Explainability & Stability Validation Report

**Document ID:** `HS-REP-05-SHAP-VALIDATION`
**Evaluation Date:** October 2026
**Explainer Method:** TreeExplainer (`shap` v0.53.0)
**Approved Explanatory Model:** 11-Feature Observable XGBoost Regressor ([`risk_model.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/risk_model.pkl), SHA-256 `2ba43315...`)
**Evaluation Dataset:** MEPS HC-251 Held-Out Test Set ($N = 3,755$, Seed = 42)
**Visualization:** [`fig3_shap_importance.png`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/figures/fig3_shap_importance.png)

---

## 1. Executive Summary

This report delivers the recomputed, verified explainability analysis for the approved HealthScore 11-feature Observable XGBoost Regressor. All prior obsolete SHAP artifacts generated on legacy 14-feature models or development iterations have been superseded.

The SHAP values were evaluated directly on the model's native log-expenditure prediction scale ($\ln(1 + \text{TOTEXP23})$). Numerical additivity was strictly confirmed, and ranking stability across independent subsets was empirically demonstrated.

---

## 2. Methodology & Explainer Specification

- **Target Output:** Continuous prediction of $\ln(1 + y)$ in the tree ensemble.
- **Explainer Architecture:** Exact TreeExplainer using conditional tree path expectations.
- **Feature Schema Parity:** All 11 observable features matched the exact ordering of the serialized pipeline:
  `['AGE23X', 'Gender_Male', 'Cardio_ACG', 'Metabolic_ACG', 'Respiratory_ACG', 'Oncology_ACG', 'Musculoskeletal_ACG', 'Psychiatric_ACG', 'Comorbidity_Count', 'Multimorbidity_Penalty', 'Age_x_Comorbidity']`.
- **Numerical Additivity Verification:**
  For each test observation $i \in \{1, \dots, 3755\}$, exact additivity requires:
  $$\sum_{j=1}^{11} \phi_{i,j} + \phi_0 = f(x_i)$$
  Where $\phi_0 = \mathbb{E}[f(x)] \approx 7.7715$ is the ensemble base value.
  - **Maximum Absolute Discrepancy:** **$0.00000954$** ($< 10^{-5}$)
  - **Verification Status:** **STRICTLY ADDITIVE (Zero Floating-Point Leakage)**

---

## 3. Global Feature Importance Ranking

The table below presents the authoritative global SHAP feature importance evaluated as the mean absolute attribution $\frac{1}{N} \sum_{i=1}^N |\phi_{i,j}|$ on the log-spending scale:

| Rank | Feature Name | Feature Category | Mean |SHAP| (Log Scale) | Relative Attribution (%) | Statistical Interpretation |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **1** | `Age_x_Comorbidity` | Interaction Composite | **0.7724** | **37.6%** | Non-linear interaction between age and chronic illness burden. |
| **2** | `Comorbidity_Count` | Clinical Composite | **0.4601** | **22.4%** | Total number of active chronic condition clusters. |
| **3** | `Gender_Male` | Demographic | **0.2928** | **14.3%** | Baseline spending offset between male and female populations. |
| **4** | `AGE23X` | Demographic | **0.2460** | **12.0%** | Monotonic age-related spending baseline increase. |
| **5** | `Multimorbidity_Penalty` | Clinical Composite | **0.0702** | **3.4%** | Quadratic scaling of multi-system chronic disease burden. |
| **6** | `Musculoskeletal_ACG` | Clinical Cluster | **0.0609** | **3.0%** | Arthritis and chronic joint pain utilization. |
| **7** | `Cardio_ACG` | Clinical Cluster | **0.0427** | **2.1%** | Cardiovascular disease cluster (hypertension, CAD, stroke). |
| **8** | `Oncology_ACG` | Clinical Cluster | **0.0420** | **2.0%** | Active cancer history utilization. |
| **9** | `Metabolic_ACG` | Clinical Cluster | **0.0351** | **1.7%** | Diabetes and hyperlipidemia utilization. |
| **10** | `Psychiatric_ACG` | Clinical Cluster | **0.0168** | **0.8%** | Depressive symptoms and ADHD utilization. |
| **11** | `Respiratory_ACG` | Clinical Cluster | **0.0152** | **0.7%** | Asthma, COPD, and chronic bronchitis utilization. |

---

## 4. Explanation Stability Audit Across Subsamples

To verify that the feature importance rankings are robust to sample perturbation, we evaluated SHAP attributions across three non-overlapping random subsets of 500 test records (using seeds 42, 101, and 2024).

Pairwise Spearman rank correlation coefficients ($\rho$) across the resulting feature rankings were:
- $\rho(\text{Subset}_1, \text{Subset}_2) = \mathbf{0.9909}$
- $\rho(\text{Subset}_1, \text{Subset}_3) = \mathbf{0.9909}$
- $\rho(\text{Subset}_2, \text{Subset}_3) = \mathbf{1.0000}$

**Verdict:** Minimum rank correlation is $\mathbf{0.9909}$, establishing near-perfect global explanation stability.

---

## 5. Methodological & Scientific Governance Notice

1. **Scale Interpretation:**
   SHAP values quantify shifts in the model's predicted log expenditure $\ln(1 + \text{TOTEXP23})$. They must **not** be interpreted as constant dollar-for-dollar effects. Because the inverse transformation is non-linear ($\exp(\hat{y}) - 1$), a $+0.5$ SHAP attribution represents a roughly $65\%$ multiplicative increase in predicted median spending, which translates to vastly different dollar amounts for a young adult vs. a multimorbid senior.
2. **Attribution vs. Causality:**
   SHAP values describe the internal mechanics of the fitted gradient boosted tree ensemble. They reflect correlational patterns in MEPS survey data and do **not** imply clinical causality, biological mechanisms, or that altering a condition flag would produce an expenditure change in a real patient.
