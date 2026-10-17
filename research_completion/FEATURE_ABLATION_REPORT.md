# HealthScore Controlled Feature Ablation and Sensitivity Report

**Document ID:** `HS-REP-03-FEATURE-ABLATION`
**Evaluation Date:** October 2026 (Fine-Grained Composite Isolation Edition)
**Primary Reference Model:** 11-Feature Observable Tweedie GLM (Regression) and 11-Feature Observable Logistic Regression (Classification Target 2)
**Evaluation Set:** MEPS HC-251 Held-Out Test Set ($N = 3,755$, Seed = 42)
**Authoritative Registry:** [`experiment_registry.json`](../experiments/experiment_registry.json)
**Visualization:** [`fig4_feature_ablations.png`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/figures/fig4_feature_ablations.png)

---

## 1. Executive Summary

This report delivers a systematic, controlled feature ablation study assessing the marginal predictive contribution of demographic features, custom ACG-inspired clinical condition clusters, non-linear composite terms (`Comorbidity_Count`, squared `Multimorbidity_Penalty`, and `Age_x_Comorbidity` interaction), and survey-only self-administered questionnaire (SAQ) variables.

All ablation models were trained using identical training partitions ($N = 15,016$), random seeds (`seed=42`), hyperparameter policies (Tweedie with $p=1.5, \alpha=1.0$; Logistic regression on survey-weighted Target 2 with normalized sampling weights), and evaluation records ($N = 3,755$) to ensure strictly controlled comparisons.

---

## 2. Systematic 17-Configuration Feature Ablation Matrix

The table below details performance across 17 distinct ablation configurations, transcribed directly from `experiment_registry.json`:

| Ablation Configuration | Feature Count | Features Included | Tweedie MAE ($) | Tweedie Dollar $R^2$ | $\Delta R^2$ vs Ref | Classifier ROC-AUC | Weighted Brier Skill Score | $\Delta$ BSS vs Ref |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full Observable Reference** | **11** | All 11 Observable Features | **$8,987.94** | **0.0798** | **0.0000** | **0.7654** | **+0.1025** | **0.0000** |
| Demographics Only (Age + Sex) | 2 | `AGE23X`, `Gender_Male` | $9,701.48 | 0.0395 | -0.0403 | 0.7099 | +0.0506 | -0.0519 |
| Condition Clusters Alone (No Composites) | 8 | Demographics + 6 ACG Clusters | $9,076.62 | 0.0771 | -0.0027 | 0.7640 | +0.1005 | -0.0020 |
| Clusters + Comorbidity Count | 9 | Demographics + 6 Clusters + Count | $9,064.08 | 0.0787 | -0.0011 | 0.7641 | +0.1004 | -0.0021 |
| Clusters + Multimorbidity Penalty | 9 | Demographics + 6 Clusters + $\text{Count}^2$ | $9,065.73 | 0.0769 | -0.0029 | 0.7648 | +0.1017 | -0.0008 |
| Clusters + Age $\times$ Comorbidity | 9 | Demographics + 6 Clusters + Age $\times$ Count | $9,088.22 | 0.0766 | -0.0032 | 0.7643 | +0.1007 | -0.0018 |
| Without Multimorbidity Penalty | 10 | 11 Features minus $\text{Count}^2$ | $9,036.00 | 0.0783 | -0.0015 | 0.7649 | +0.1009 | -0.0016 |
| Without Age $\times$ Comorbidity | 10 | 11 Features minus Age $\times$ Count | $8,995.12 | **0.0804** | **+0.0006** | **0.7654** | **+0.1027** | **+0.0001** |
| Without Multimorbidity & Interaction | 9 | Demographics + 6 Clusters + Count | $9,064.08 | 0.0787 | -0.0011 | 0.7641 | +0.1004 | -0.0021 |
| Clinical Conditions Only (No Demographics) | 8 | 6 Clusters + Count + Penalty | $9,015.05 | 0.0791 | -0.0007 | 0.7619 | +0.0996 | -0.0029 |
| Without Cardiovascular | 10 | 11 Features minus `Cardio_ACG` | $9,080.23 | 0.0785 | -0.0013 | 0.7634 | +0.0970 | -0.0056 |
| Without Metabolic | 10 | 11 Features minus `Metabolic_ACG` | $9,024.35 | 0.0792 | -0.0006 | 0.7628 | +0.0957 | -0.0069 |
| Without Respiratory | 10 | 11 Features minus `Respiratory_ACG` | $9,016.55 | 0.0764 | -0.0035 | 0.7635 | +0.0979 | -0.0046 |
| Without Oncology | 10 | 11 Features minus `Oncology_ACG` | $9,065.05 | 0.0788 | -0.0010 | 0.7645 | +0.0969 | -0.0056 |
| Without Musculoskeletal | 10 | 11 Features minus `Musculoskeletal_ACG`| $9,024.09 | 0.0802 | +0.0004 | 0.7651 | +0.1012 | -0.0013 |
| Without Psychiatric Condition | 10 | 11 Features minus `Psychiatric_ACG` | $9,013.37 | 0.0774 | -0.0024 | 0.7653 | +0.1026 | +0.0001 |
| **Oracle 14 Features (Upper Bound)** | **14** | Observable + SAQ Survey Variables | **$8,784.16** | **0.0927** | **+0.0129** | **0.7904** | **+0.1314** | **+0.0289** |

---

## 3. Detailed Scientific Findings (RQ3)

### 3.1. Primary Explanatory Lift from ACG-Inspired Disease Clusters
Comparing **Demographics Only** to **Condition Clusters Alone (No Composites)** reveals where the core predictive signal originates:
- Dollar $R^2$ jumps from $0.0395$ to $0.0771$ ($\Delta R^2 = +0.0376$, a $+95.2\%$ relative improvement).
- Weighted Brier Skill Score doubles from $+0.0506$ to $+0.1005$ ($\Delta \text{BSS} = +0.0499$, a $+98.6\%$ relative improvement).
- ROC-AUC increases from $0.7099$ to $0.7640$ ($\Delta = +0.0541$).
This demonstrates empirically that mapping clinical conditions into structured ACG-inspired clusters captures nearly half of all predictable expenditure variation.

### 3.2. Incremental Contribution of Multimorbidity Composites and Interactions
Evaluating the composite terms independently resolves a key question regarding interaction terms:
- Adding `Comorbidity_Count` to clusters alone marginally increases $R^2$ from $0.0771$ to $0.0787$ ($\Delta = +0.0016$).
- Adding the squared penalty (`Multimorbidity_Penalty`) or interaction term (`Age_x_Comorbidity`) in isolation yields $R^2 = 0.0769$ and $0.0766$, providing no linear benefit over count alone.
- In leave-one-out testing, dropping `Age_x_Comorbidity` actually yields $R^2 = 0.0804$ and $\text{BSS} = +0.1027$ (slightly outperforming the 11-feature full design). This occurs because `Age_x_Comorbidity` exhibits high collinearity with age and count. While gradient-boosted trees rely heavily on this non-linear interaction ($39.0\%$ of SHAP TreeExplainer attribution), in generalized linear models it adds collinearity without expanding linear explanatory power.

### 3.3. Condition Outlier Dynamics
- Dropping `Respiratory_ACG` produces the largest single clinical condition penalty ($\Delta R^2 = -0.0035$), reflecting high hospitalization and prescription costs associated with severe asthma and COPD.
- Dropping `Metabolic_ACG` causes the largest BSS drop ($\Delta \text{BSS} = -0.0069$), reflecting diabetes as a primary risk driver for top-decile spending.

### 3.4. The Oracle Gap
Adding unobservable survey variables (`Frailty_Index`, `Age_x_Frailty`, `K6SUM42`) yields an upper bound of $R^2 = 0.0927$ and $\text{BSS} = +0.1314$. However, because self-administered questionnaires cannot be gathered in light digital intakes, the 11-feature model remains the leading deployment candidate due to strict input availability parity.

---

## 4. Methodological Disclaimer on Causality
Feature ablation measures marginal predictive information within a specific observational model; it does **not** establish causal disease mechanisms, clinical etiologies, or the cost-effectiveness of medical interventions.
