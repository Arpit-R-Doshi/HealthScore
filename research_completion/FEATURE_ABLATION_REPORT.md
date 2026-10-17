# HealthScore Controlled Feature Ablation and Sensitivity Report

**Document ID:** `HS-REP-03-FEATURE-ABLATION`
**Evaluation Date:** October 2026
**Primary Reference Model:** 11-Feature Observable Tweedie GLM (Regression) and 11-Feature Observable Logistic Regression (Classification Target 2)
**Evaluation Set:** MEPS HC-251 Held-Out Test Set ($N = 3,755$, Seed = 42)
**Visualization:** [`fig4_feature_ablations.png`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/figures/fig4_feature_ablations.png)

---

## 1. Executive Summary

This report delivers a systematic, controlled feature ablation study assessing the marginal contribution of demographic features, clinical condition clusters, non-linear interactions, and survey-only self-administered questionnaire (SAQ) variables.

All ablation models were trained using identical partitions, random seeds, hyperparameter policies, and evaluation records to ensure fair comparisons.

---

## 2. Controlled Feature Ablation Matrix

The table below details performance across 11 distinct ablation configurations:

| Ablation Configuration | Feat Count | Features Included | Tweedie MAE ($) | Tweedie Dollar $R^2$ | $\Delta R^2$ vs Ref | Classifier ROC-AUC | Weighted Brier Skill Score | $\Delta$ BSS vs Ref |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full Observable Reference** | **11** | All 11 Observable Features | **$8,993.97** | **0.0786** | **0.0000** | **0.7652** | **+0.1025** | **0.0000** |
| **Demographics Only** | 2 | `AGE23X`, `Gender_Male` | $9,380.12 | 0.0394 | -0.0392 | 0.7099 | +0.0501 | -0.0524 |
| **Clinical Conditions Only** | 8 | 6 ACG Clusters + Count + Penalty | $9,012.45 | 0.0780 | -0.0006 | 0.7617 | +0.0998 | -0.0027 |
| **Without Psychiatric** | 10 | Drop `Psychiatric_ACG` | $9,008.21 | 0.0763 | -0.0023 | 0.7651 | +0.1035 | +0.0010 |
| **Without Multimorbidity / Int** | 9 | Drop Penalty & Age $\times$ Comorb | $9,004.18 | 0.0772 | -0.0013 | 0.7629 | +0.0997 | -0.0027 |
| **Without Oncology** | 10 | Drop `Oncology_ACG` | $8,998.42 | 0.0783 | -0.0003 | 0.7621 | +0.0966 | -0.0058 |
| **Without Cardiovascular** | 10 | Drop `Cardio_ACG` | $8,997.10 | 0.0779 | -0.0007 | 0.7624 | +0.0969 | -0.0056 |
| **Without Metabolic** | 10 | Drop `Metabolic_ACG` | $8,995.84 | 0.0784 | -0.0002 | 0.7618 | +0.0957 | -0.0068 |
| **Without Respiratory** | 10 | Drop `Respiratory_ACG` | $9,015.30 | 0.0751 | -0.0035 | 0.7628 | +0.0971 | -0.0054 |
| **Without Musculoskeletal** | 10 | Drop `Musculoskeletal_ACG` | $8,988.12 | 0.0795 | +0.0009 | 0.7648 | +0.1014 | -0.0011 |
| **Oracle 14 Features** | 14 | Adding Frailty & K6 Distress | **$8,861.53** | **0.0907** | **+0.0121** | **0.7869** | **+0.1300** | **+0.0275** |

---

## 3. Scientific Findings & Methodological Interpretation

1. **The Core Clinical Signal:**
   Removing all clinical condition clusters (**Demographics Only**) causes the single largest performance collapse: Dollar $R^2$ plummets from $0.0786$ to $0.0394$ (a $49.9\%$ relative drop), and Weighted Brier Skill Score drops from $+0.1025$ to $+0.0501$ (a $51.1\%$ relative drop). This confirms that clinical chronic disease indicators carry roughly half of the total predictable expenditure signal.
2. **Clinical Redundancy and Collinearity:**
   Individually dropping any single condition cluster (Cardiovascular, Metabolic, Oncology, Musculoskeletal) produces only modest performance drops ($\Delta R^2 < 0.001$, $\Delta \text{BSS} \approx 0.005$). This occurs because multi-condition patients frequently trigger multiple clusters simultaneously (e.g. hypertension + diabetes + arthritis), allowing correlated conditions and the aggregate `Comorbidity_Count` to absorb marginal explanatory power.
3. **Respiratory Conditions Carry Unique Outlier Variance:**
   Dropping `Respiratory_ACG` produced the largest individual clinical condition drop ($\Delta R^2 = -0.0035$). Severe chronic respiratory illness (COPD, emphysema, persistent asthma) is known to drive high acute emergency room and inpatient expenditures not fully captured by metabolic or cardiovascular flags.
4. **The Oracle Gap (The SAQ Survey Advantage):**
   Incorporating survey-only self-administered questionnaire (SAQ) variables (**Oracle 14 Features**: `Frailty_Index`, `Age_x_Frailty`, `K6SUM42`) increases Dollar $R^2$ from $0.0786$ to $0.0907$ ($\Delta = +0.0121$) and Brier Skill Score from $+0.1025$ to $+0.1300$ ($\Delta = +0.0275$). While these psychological distress and functional limitation measures enhance predictive accuracy, they are unavailable at runtime onboarding. The 11-feature model remains the leading deployment candidate because it achieves input availability parity without requiring imputed non-response approximations.

---

## 4. Methodological Disclaimer on Causality
Feature ablation measures marginal predictive value in a specific statistical model; it does **not** establish causal disease mechanisms, clinical etiologies, or the cost-effectiveness of medical interventions.
