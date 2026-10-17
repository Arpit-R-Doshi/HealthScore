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

The table below details performance across 11 distinct ablation configurations, reconciled with the canonical experiment registry:

| Ablation Configuration | Feat Count | Features Included | Tweedie MAE ($) | Tweedie Dollar $R^2$ | $\Delta R^2$ vs Ref | Classifier ROC-AUC | Weighted Brier Skill Score | $\Delta$ BSS vs Ref |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full Observable Reference** | **11** | All 11 Observable Features | **$8,987.94** | **0.0798** | **0.0000** | **0.7654** | **+0.1025** | **0.0000** |
| **Demographics Only** | 2 | `AGE23X`, `Gender_Male` | $9,701.48 | 0.0395 | -0.0403 | 0.7099 | +0.0506 | -0.0519 |
| **Clinical Conditions Only** | 8 | 6 ACG Clusters + Count + Penalty | $9,015.05 | 0.0791 | -0.0007 | 0.7619 | +0.0996 | -0.0029 |
| **Without Psychiatric** | 10 | Drop `Psychiatric_ACG` | $9,013.37 | 0.0774 | -0.0024 | 0.7634 | +0.1026 | +0.0001 |
| **Without Multimorbidity / Int** | 9 | Drop Penalty & Age $\times$ Comorb | $9,064.08 | 0.0787 | -0.0011 | 0.7657 | +0.1004 | -0.0021 |
| **Without Oncology** | 10 | Drop `Oncology_ACG` | $9,065.05 | 0.0788 | -0.0010 | 0.7626 | +0.0969 | -0.0056 |
| **Without Cardiovascular** | 10 | Drop `Cardio_ACG` | $9,080.23 | 0.0785 | -0.0013 | 0.7611 | +0.0970 | -0.0056 |
| **Without Metabolic** | 10 | Drop `Metabolic_ACG` | $9,024.35 | 0.0792 | -0.0006 | 0.7605 | +0.0957 | -0.0069 |
| **Without Respiratory** | 10 | Drop `Respiratory_ACG` | $9,016.55 | 0.0764 | -0.0035 | 0.7632 | +0.0979 | -0.0046 |
| **Without Musculoskeletal** | 10 | Drop `Musculoskeletal_ACG` | $9,024.09 | 0.0802 | +0.0004 | 0.7622 | +0.1012 | -0.0013 |
| **Oracle 14 Features** | 14 | Adding Frailty & K6 Distress | **$8,784.16** | **0.0927** | **+0.0129** | **0.7904** | **+0.1314** | **+0.0289** |

---

## 3. Scientific Findings & Methodological Interpretation

1. **The Core Clinical Signal:**
   Removing all clinical condition clusters (**Demographics Only**) causes the single largest performance collapse: Dollar $R^2$ plummets from $0.0798$ to $0.0395$ (a $50.5\%$ relative drop), and Weighted Brier Skill Score drops from $+0.1025$ to $+0.0506$ (a $50.6\%$ relative drop). This confirms that clinical chronic disease indicators carry roughly half of the total predictable expenditure signal.
2. **Clinical Redundancy and Collinearity:**
   Individually dropping any single condition cluster (Cardiovascular, Metabolic, Oncology, Musculoskeletal) produces only modest performance drops ($\Delta R^2 \le 0.0013$, $\Delta \text{BSS} \le 0.0069$). This occurs because multi-condition patients frequently trigger multiple clusters simultaneously (e.g. hypertension + diabetes + arthritis), allowing correlated conditions and the aggregate `Comorbidity_Count` to absorb marginal explanatory power.
3. **Respiratory Conditions Carry Unique Outlier Variance:**
   Dropping `Respiratory_ACG` produced the largest individual clinical condition drop ($\Delta R^2 = -0.0035$). Severe chronic respiratory illness (COPD, emphysema, persistent asthma) is known to drive high acute emergency room and inpatient expenditures not fully captured by metabolic or cardiovascular flags.
4. **The Oracle Gap (The SAQ Survey Advantage):**
   Incorporating survey-only self-administered questionnaire (SAQ) variables (**Oracle 14 Features**: `Frailty_Index`, `Age_x_Frailty`, `K6SUM42`) increases Dollar $R^2$ from $0.0798$ to $0.0927$ ($\Delta = +0.0129$) and Brier Skill Score from $+0.1025$ to $+0.1314$ ($\Delta = +0.0289$). While these psychological distress and functional limitation measures enhance predictive accuracy, they are unavailable at runtime onboarding. The 11-feature model remains the leading deployment candidate because it achieves input availability parity without requiring imputed non-response approximations.

---

## 4. Methodological Disclaimer on Causality
Feature ablation measures marginal predictive value in a specific statistical model; it does **not** establish causal disease mechanisms, clinical etiologies, or the cost-effectiveness of medical interventions.
