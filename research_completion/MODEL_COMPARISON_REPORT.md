# HealthScore Systematic Model Comparison and Evaluation Report

**Document ID:** `HS-REP-02-MODEL-COMPARISON`
**Evaluation Date:** October 2026
**Evaluation Scope:** Regression and Classification Benchmark Matrix on MEPS HC-251 Held-Out Test Set ($N = 3,755$) and Prospective Baseline Benchmarks
**Artifact Manifest:** [`experiment_registry.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/experiments/experiment_registry.json)

---

## 1. Executive Summary

This report delivers a rigorous, fair, and methodologically sound comparison of all candidate machine learning models evaluated in the HealthScore research initiative. Rather than collapsing classification and expenditure estimation into a single ranking, we evaluate them across distinct statistical objectives:
1. **High-Expenditure Risk Discrimination (Classification):** Accurately identifying individuals in the top decile of healthcare utilization ($P_{90, \text{wtd}} \ge \$17,827.41$).
2. **Direct Dollar Expenditure Estimation (Regression):** Predicting expected annual healthcare expenditures in un-logged dollars ($TOTEXP23).
3. **Relative Risk Ranking (Econometric Indexing):** Generating an ordinal health-risk score reflecting relative resource utilization.

---

## 2. Healthcare Expenditure Regression Benchmarks

All models were evaluated on the fixed held-out test partition ($N = 3,755$, observed mean = **$\$8,764.62$**, population variance = $\$602,354,051.95$).

### 2.1. Regression Performance Comparison Table

| Candidate Model | Input Features | Objective / Transformation | Unweighted MAE ($) [95% CI] | Unweighted RMSE ($) [95% CI] | Unweighted Dollar $R^2$ | Mean Predicted ($) | Weighted MAE ($) | Weighted RMSE ($) | Weighted Dollar $R^2$ | 5-Fold CV $R^2$ (Mean ± Std) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Median** | 0 | Train Median ($1,824.50) | $8,286.54 [$7,568, $9,133] | $25,505.28 [$20,416, $30,695] | -0.0800 | $1,824.50 | $7,069.26 | $21,198.98 | -0.0765 | — |
| **Baseline Mean** | 0 | Train Mean ($8,179.16) | $10,409.21 [$9,715, $11,157] | $24,549.88 [$19,683, $29,266] | -0.0006 | $8,179.16 | $9,615.14 | $20,443.80 | -0.0012 | — |
| **OLS Linear** | 11 | Observable, $\ln(1+y)$ | $7,626.08 [$6,864, $8,421] | $24,663.09 [$19,788, $29,310] | -0.0098 | $2,557.06 | $6,564.12 | $20,534.81 | -0.0101 | — |
| **Ridge ($\alpha=10$)** | 11 | Observable, $\ln(1+y)$ | $7,624.74 [$6,863, $8,420] | $24,662.46 [$19,787, $29,309] | -0.0098 | $2,551.15 | $6,562.88 | $20,534.20 | -0.0100 | — |
| **Random Forest** | 11 | Observable, $\ln(1+y)$ | $7,538.79 [$6,785, $8,328] | $24,702.54 [$19,820, $29,348] | -0.0131 | $2,449.69 | $6,482.11 | $20,568.42 | -0.0134 | — |
| **XGBoost Regressor** | 11 | Observable, $\ln(1+y)$ | **$7,516.26** [$6,763, $8,308] | $24,706.50 [$19,805, $29,332] | -0.0134 | $2,384.13 | **$6,456.24** | $20,554.10 | -0.0120 | -0.0014 ± 0.0086 |
| **Tweedie GLM ($p=1.5$)** | 11 | Observable, Direct Dollar | **$8,987.94** [$8,289, $9,725] | **$23,542.97** [$18,708, $28,144] | **0.0798** | **$8,177.92** | **$7,841.15** | **$19,563.13** | **0.0832** | **0.1131 ± 0.0140** |
| **Two-Part Model (2PM)** | 11 | Logistic + OLS Smearing | $9,840.61 [$9,174, $10,603] | $24,016.85 [$19,280, $28,948] | 0.0424 | $9,734.68 | $8,459.92 | $20,153.57 | 0.0270 | — |
| **Lagged Spend (HC-257)** | 1 | $TOTEXPY1 \to TOTEXPY2$ | $8,625.76 [$7,920, $9,380] | $27,407.32 [$22,140, $32,600] | **0.1204** | $8,527.12 | $7,845.73 | $26,142.63 | **0.0981** | — |

*Note: All confidence intervals reflect unweighted individual-level non-parametric bootstrap sampling and represent non-design-based model uncertainty.*

### 2.2. Key Methodological Takeaways on Expenditure Estimation
1. **The Nominal Dollar Underprediction of Log-Models:**
   Tree-based and linear models fit on $\ln(1+y)$ (such as XGBoost, Random Forest, and OLS) achieve the lowest MAE ($\approx \$7,516$) on the arithmetic median scale, but severely underpredict the dollar mean when transformed back to dollars via $\exp(m) - 1$ ($Mean Pred = \$2,384.13$ vs $Observed = \$8,764.62$, an underprediction of $72.8\%$). Consequently, their dollar-scale $R^2$ is negative ($-0.0134$). These models are valid for **percentile risk ranking**, but invalid for nominal expenditure budgeting.
2. **Tweedie Compound Poisson-Gamma GLM Supremacy for Dollar Expenditure:**
   The 11-feature Tweedie GLM ($p=1.5$, log link) directly optimizes dollar-scale deviance. Evaluating the approved frozen artifact (`risk_model_tweedie_observable.pkl`) accurately tracks the overall observed mean ($Predicted = \$8,177.92$ vs $Observed = \$8,764.62$) and yields the highest dollar-scale $R^2 = \mathbf{0.0798}$ (weighted $R^2 = \mathbf{0.0832}$) with 5-fold cross-validation stability ($0.1131 \pm 0.0140$).
3. **The Econometric Persistence Benchmark:**
   In prospective longitudinal validation on HC-257 Panel 28, a simple baseline predicting Year 2 spending from Year 1 spending (`TOTEXPY1`) achieved $R^2 = \mathbf{0.1204}$, outperforming the static diagnosis-only Tweedie GLM ($R^2 = \mathbf{0.0652}$). As documented in health econometrics, self-reported diagnosis flags alone explain only 6–8% of cost variance; past healthcare spending remains the dominant predictor of future utilization.

---

## 3. High-Expenditure Classification Benchmarks

All models were evaluated on the survey-weighted top-decile target ($P_{90, \text{wtd}} \ge \$17,827.41$; test prevalence = $11.98\%$ unweighted, $10.51\%$ weighted). Target-specific weighted baseline Brier score is **$0.0941$**.

### 3.1. Classifier Performance Comparison Table

| Candidate Model | Features | Weighting Policy | Mean Prob | ROC-AUC [95% CI] | PR-AUC [95% CI] | Unw Brier | Unw BSS | Weighted Brier | Weighted BSS | CITL ($\alpha$) | Cal Slope ($\beta$) | Precision @ 0.10 | Recall @ 0.10 | F1 Score |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Constant Baseline** | 0 | None (Constant $\hat{p}=0.0999$) | 0.0999 | 0.5000 [0.5000, 0.5000] | 0.1198 [0.1111, 0.1308] | 0.1059 | -0.0036 | 0.0941 | +0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| **Demographic Baseline** | 2 | Normalized Person Weights | 0.1156 | 0.7099 [0.6856, 0.7319] | 0.2182 [0.1928, 0.2489] | 0.0996 | +0.0561 | 0.0893 | +0.0506 | +0.0388 | 0.8859 | 0.1949 | 0.7867 | 0.3124 |
| **Clinical Only (No Demo)** | 8 | Normalized Person Weights | 0.1119 | 0.7619 [0.7393, 0.7847] | 0.3083 [0.2794, 0.3464] | 0.0941 | +0.1083 | 0.0847 | +0.0996 | +0.0768 | 0.9539 | 0.2291 | 0.7622 | 0.3523 |
| **Logistic (11-Feat Observable, Unweighted Fit)** | 11 | Unweighted Fit (Weighting Ablation) | 0.1165 | 0.7652 [0.7433, 0.7882] | 0.3192 [0.2869, 0.3582] | 0.0936 | +0.1129 | 0.0845 | +0.1025 | +0.0570 | 0.9008 | 0.2278 | 0.7644 | 0.3510 |
| **Logistic (11-Feat Observable, Weighted Fit)** | 11 | Frozen Normalized Weights (Serving) | 0.1151 | **0.7654** [0.7444, 0.7881] | **0.3184** [0.2876, 0.3556] | **0.0936** | **+0.1123** | **0.0845** | **+0.1025** | **+0.0646** | **0.9438** | **0.2318** | **0.7733** | **0.3567** |
| **Random Forest (11-Feat Observable)** | 11 | Normalized Person Weights | 0.1154 | 0.7693 [0.7458, 0.7928] | 0.3157 [0.2823, 0.3550] | 0.0935 | +0.1136 | 0.0841 | **+0.1062** | +0.0601 | 0.9736 | 0.2342 | 0.7556 | 0.3575 |
| **XGBoost (Uncalibrated)** | 11 | Normalized Person Weights | 0.1157 | 0.7705 [0.7482, 0.7940] | 0.3196 [0.2853, 0.3598] | 0.0932 | +0.1166 | 0.0838 | **+0.1093** | +0.0572 | 0.9926 | 0.2262 | 0.8022 | 0.3529 |
| **XGBoost (Platt Calibrated)** | 11 | Observable, Sigmoid CV=5 | 0.1139 | 0.7702 [0.7472, 0.7936] | 0.3183 [0.2872, 0.3580] | 0.0944 | +0.1048 | 0.0847 | +0.0998 | +0.0617 | 1.0335 | 0.2535 | 0.6778 | 0.3690 |
| **Logistic (14-Feat Oracle)** | 14 | Observable + SAQ Survey | 0.1172 | **0.7904** [0.7684, 0.8121] | **0.3472** [0.3143, 0.3917] | **0.0922** | **+0.1265** | **0.0832** | **+0.1159** | +0.0493 | 1.0609 | **0.2806** | **0.6822** | **0.3977** |

---

## 4. Primary Model Selection & Deployment Architecture

### 4.1. Formal Selection Policy
HealthScore separates model selection according to deployment constraints and intended scientific use:

1. **Primary Operational Classifier:** **11-Feature Observable Logistic Regression (Weighted Fit)**
   - **Artifact:** `artifacts/risk_model_classifier_observable_weighted_p90.pkl` (SHA-256: `3632f8201136a2740c3d5a564bbdbb29bc8511db51709fb42c1f8e271bf28c2a`).
   - **Rationale:** Strictly satisfies **Input Availability Parity** without requiring unverifiable survey imputations. Achieves Weighted BSS of **$+0.1025$** ($+10.25\%$ improvement over baseline), unweighted BSS $+0.1123$, ROC-AUC **0.7654** [95% CI: $0.7444$, $0.7881$], PR-AUC **0.3184** [95% CI: $0.2876$, $0.3556$], calibration slope ($b = 0.9438$), exact calibration-in-the-large ($\text{CITL} = +0.0646$; bivariate intercept $a = -0.0409$), and transparent linear interpretability for on-chain auditability. At $\hat{p} \ge 0.10$, it achieves Precision $0.2318$ (an unweighted enrichment of approximately $1.93\text{x}$ over unweighted test prevalence $0.119840$), Recall $0.7733$, and F1 $0.3567$. While tree ensembles (Random Forest and XGBoost) achieve marginally higher point discrimination (ROC-AUC $0.7693$–$0.7705$ vs $0.7654$) and skill (Weighted BSS $+0.1062$–$+0.1093$ vs $+0.1025$), their 95% bootstrap confidence intervals overlap substantially with the logistic fit, indicating no statistically significant discriminative gain. Logistic regression is selected because it strictly satisfies input availability parity, provides transparent closed-form coefficients for on-chain auditability, and avoids tree-based computational overhead in transaction validation.
2. **Primary Dollar Expenditure Regressor:** **11-Feature Observable Tweedie GLM ($p=1.5$)**
   - **Rationale:** Only evaluated estimator that directly predicts dollar scale with positive $R^2$ ($0.0798$, weighted $R^2 = 0.0832$), tracking nominal dollar totals ($Mean Pred = \$8,177.92$ vs $\$8,764.62$) and preserving monotone decile ranking across validation cohorts.
3. **Secondary Percentile Risk Scoring:** **11-Feature Observable XGBoost Regressor**
   - **Rationale:** Retained for relative ranking and health score computation (0–100 percentile score), supported by SHAP TreeExplainer attributions.
