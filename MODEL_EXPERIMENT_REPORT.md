# HealthScore: Model Experiment & Research Evaluation Report (Phase D & E)

**Document Version:** 5.1 (Synchronized Authoritative Run, Qualified Dollar Stratification, Input Availability Parity Table & Updated AHRQ Status)
**Date:** October 2026
**Auditor / Healthcare Data Scientist:** Senior Healthcare Data Scientist & Research-Methodology Reviewer
**Dataset:** MEPS HC-251 (2023 Full Year Consolidated Data File; N = 18,771 eligible individuals)
**Partition Protocol:** Reproducible 80/20 Train/Test Split (Train N = 15,016; Held-Out Test N = 3,755; Seed = 42)
**Target Population:** Civilian noninstitutionalized U.S. population in calendar year 2023.

> [!NOTE]
> **Methodological Scope & Validation Protocol Notice:**
> - **Exploratory Held-Out Evaluation:** All model comparisons reported below were performed on the exact same fixed held-out test partition ($N=3,755$, Population Variance $\text{Var}_{\text{pop}}(y_{\text{test}}) = \$602,354,051.95$ [$\text{ddof}=0$], Sample Variance $\text{Var}_{\text{sample}}(y_{\text{test}}) = \$602,514,508.54$ [$\text{ddof}=1$], Observed Test Mean = **$\$8,764.62$**). Because this held-out partition was repeatedly accessed during iterative development, these metrics represent exploratory held-out benchmarks rather than a pristine confirmatory validation.
> - **Completed Phase 2 AHRQ Validation (Roadmap Completed):** The Phase 2 validation roadmap has been fully executed and reported in [`EXTERNAL_VALIDATION_REPORT.md`](EXTERNAL_VALIDATION_REPORT.md):
>   - **MEPS HC-256 (2024 Full Year Consolidated Data File):** Evaluated contemporaneous out-of-year external transfer across $N = 18,979$ individuals (ROC-AUC $0.7828$, PR-AUC $0.3229$, Weighted BSS $+0.1266$).
>   - **MEPS HC-257 (2023–2024 Longitudinal Data File, Panel 28):** Evaluated true prospective multi-year forecasting across $N = 8,708$ individuals (ROC-AUC $0.7807$, PR-AUC $0.3296$, Weighted BSS $+0.1263$).
> - **Variance Convention Reconciliation:** Scikit-learn's `r2_score(y_true, y_pred)` evaluates $R^2 = 1 - \frac{\text{SS}_{\text{res}}}{\text{SS}_{\text{tot}}}$. Because $\text{SS}_{\text{tot}} = N \cdot \text{Var}_{\text{pop}} (\text{ddof}=0)$ and $\text{SS}_{\text{res}} = N \cdot \text{RMSE}^2$, the identity $R^2 = 1 - \frac{\text{RMSE}^2}{\text{Var}}$ strictly holds against population variance ($\text{ddof}=0$, $\$602,354,051.95$). Using sample variance ($\text{ddof}=1$, $\$602,514,508.54$) produces a mathematical discrepancy.
> - **Bootstrap Confidence Interval Reconciliation:** While this historical training report utilized $B=1,000$ resamples for initial development diagnostics, the canonical comprehensive benchmark suite (`run_comprehensive_benchmarks.py`) and manuscript reporting utilize $B=200$ resamples ($n\_boot=200$, seed 42) for computational consistency with the benchmark registry. Both reflect ordinary row-level percentile resampling uncertainty on the exploratory test split; they do **not** account for the complex survey design (clustering via `VARPSU` or stratification via `VARSTR`) and must not be interpreted as design-based population standard errors.
> - **Exploratory Loss Simulation Notice:** Monte Carlo parametric loss simulations and "premium" outputs are exploratory Value-at-Risk heuristics for technical demonstration; current MEPS prediction metrics do **not** validate commercial insurance pricing, premium calculation, underwriting adequacy, or reserve solvency.

---

## 1. Executive Summary & Methodological Findings

1. **Reconciliation of Survey-Weighted Classifier Baseline Arithmetic:**
   The exact values are audited, reconciled, and verified by unit test assertions:
   - **Training Survey-Weighted Prevalence:** $\hat{p} = \frac{\sum w_{i,\text{train}} y_{i,\text{train}}}{\sum w_{i,\text{train}}} = \mathbf{0.0999}$ ($0.099888$).
   - **Constant Baseline Prediction:** Predicts constant $\hat{p} = 0.099888$ for all test instances.
   - **Test Survey-Weighted Outcome Prevalence:** $\bar{y}_{\text{test, wtd}} = \frac{\sum w_{i,\text{test}} y_{i,\text{test}}}{\sum w_{i,\text{test}}} = \mathbf{0.1051}$ ($0.105134$).
   - **Test Unweighted Outcome Prevalence:** $\bar{y}_{\text{test, unw}} = \frac{1}{N_{\text{test}}} \sum y_{i,\text{test}} = \mathbf{0.1198}$ ($0.119840$).
   - **Test Survey-Weighted Baseline Brier Score:**
     $$\text{Brier}_{\text{wtd}}(\hat{p}) = \bar{y}_{\text{test, wtd}}(1 - 2\hat{p}) + \hat{p}^2 = 0.105134(1 - 2(0.099888)) + (0.099888)^2 = \mathbf{0.0941} \quad (0.094108)$$
   - **Test Unweighted Baseline Brier Score:**
     $$\text{Brier}_{\text{unw}}(\hat{p}) = \bar{y}_{\text{test, unw}}(1 - 2\hat{p}) + \hat{p}^2 = 0.119840(1 - 2(0.099888)) + (0.099888)^2 = \mathbf{0.1059} \quad (0.105877)$$
   All Brier Skill Scores for Target 2 are evaluated against these exact baselines.

2. **Evaluation of Exact Deployment Candidates & Qualified Dollar Stratification:**
   The 11-feature Observable Tweedie Compound Poisson-Gamma GLM is evaluated separately from the 14-feature models across all tables:
   - **Observable Tweedie GLM (11 Features, Input Availability Parity):** Overall predicted mean = **$\$8,177.92$** (vs. observed $\$8,764.62$; aggregate underprediction $6.7\%$), Dollar RMSE = **$\$23,542.97$**, Dollar $R^2 = \mathbf{0.0798}$, Weighted Dollar $R^2 = \mathbf{0.0832}$.
   - **Qualified Dollar-Scale Stratification Analysis:** The decile stratification of the Observable Tweedie model was evaluated using its own predictions (`p_tw_obs`). Decile counts sum exactly to $3,755$, count-weighted observed mean equals **$\$8,764.62$**, and count-weighted predicted mean equals **$\$8,177.92$** ($\Delta = 0.0022 < 0.05$). While aggregate and top-decile spending are tracked closely (Decile 10 predicted $\$23,846.37$ vs observed $\$24,659.24$, ratio 1.034x), observed-to-predicted ratios vary from 1.766x in Decile 1 to 0.789x in Decile 4. Tweedie is the leading candidate for un-logged dollar prediction, but cannot be described as fully calibrated across all deciles.
   - **Observable XGBoost Regressor:** Retained strictly for relative expenditure ranking ($\ln(1+y)$ objective; overall dollar mean predicted $\$2,384.13$, underpredicting observed dollar mean by $72.8\%$).

3. **Classifier Input Conditions & Declared Targets:**
   - **11-Feature Observable Logistic Regression:** Achieves Target 2 Weighted Brier = $0.0845$, Weighted Brier Skill Score = **$+0.1025$** ($+10.25\%$), ROC-AUC = $0.7654$, PR-AUC = $0.3184$.
   - **14-Feature Deployment-Imputed Logistic Regression:** Evaluated with unobserved SAQ variables imputed via age/comorbidity conditional expectations. Achieves Weighted Brier = $0.0849$, Weighted BSS = **$+0.0978$** ($+9.78\%$).
   - **14-Feature Oracle Ground Truth Logistic Regression:** Achieves Weighted Brier = $0.0817$, Weighted BSS = $+0.1314$ ($+13.14\%$).
   - **Inference Recommendation:** Observable 11-feature Logistic Regression ($+0.1025$ Wtd BSS) strictly outperforms the 14-feature model under zero imputation ($+0.0978$ Wtd BSS), justifying the 11-feature model as the leading classifier candidate for integration testing. Every serialized artifact declares its target explicitly in `training_metadata.json`.

4. **Condition-Level Negation Handling & Explicit Distinction:**
   The clinical text parser (`risk_engine.py`) preserves condition-level negation and affirmation before cluster aggregation:
   - Same-cluster mixed statements (e.g. `"no hypertension, but prior stroke"`, `"no asthma, but COPD"`) correctly preserve affirmed conditions (e.g. stroke $\implies \text{cardio}=2$, COPD $\implies \text{respiratory}=2$).
   - Statements with negative qualifiers evaluate to $0$ and never trigger positive condition flags.
   - Engine distinguishes explicitly affirmed, explicitly negated, and unmentioned conditions. Absent or unparseable input is flagged as unmentioned (warning returned) rather than confirmed absence of disease.
   - Regex flags remain heuristic intake features; equal feature counts establish **Input Availability Parity; Semantic Validation Pending**, not clinical equivalence to MEPS survey diagnoses.

---

## 2. Healthcare Expenditure Regressor Benchmarks

All models were evaluated on the fixed held-out test partition ($N=3,755$, observed mean = $\$8,764.62$, population variance = $\$602,354,051.95$ [$\text{ddof}=0$], sample variance = $\$602,514,508.54$ [$\text{ddof}=1$]).

### 2.1. Regressor Performance Comparison Table

| Candidate Model | Features | Input Condition / Objective | Unweighted MAE ($) [95% CI] | Unweighted RMSE ($) [95% CI] | Dollar R² (ddof=0) | Mean Predicted ($) | Weighted MAE ($) | Weighted RMSE ($) | Weighted Dollar R² |
|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Baseline Median** | 0 | Train Median ($1,824.50) | $8,286.54 [$7,502.44, $9,132.40] | $25,505.28 [$20,685.85, $30,170.84] | -0.0800 | $1,824.50 | $7,069.26 | $21,198.98 | -0.0765 |
| **Baseline Mean** | 0 | Train Mean ($8,179.16) | $10,409.21 [$9,711.53, $11,157.29] | $24,549.88 [$19,683.09, $29,266.14] | -0.0006 | $8,179.16 | $9,615.14 | $20,443.80 | -0.0012 |
| **XGBoost (Observable-Only, Unw)** | 11 | Observable features, $\ln(1+y)$ | **$7,516.26** [$6,766.71, $8,312.72] | $24,706.50 [$19,821.60, $29,347.89] | -0.0134 | $2,384.13 | $6,464.45 | $20,571.27 | -0.0137 |
| **XGBoost (Observable-Only, Wtd)** | 11 | Observable features, normalized wtd | **$7,511.06** [$6,765.89, $8,307.69] | $24,724.64 [$19,850.29, $29,380.31] | -0.0149 | $2,382.41 | **$6,455.21** | $20,580.31 | -0.0146 |
| **XGBoost 14-Feat (Deployment Imputed)**| 14 | 14 features, SAQ imputed via training table | $7,495.29 [$6,765.08, $8,293.55] | $24,579.85 [$19,703.26, $29,228.95] | -0.0030 | $2,797.33 | $6,439.15 | $20,435.34 | -0.0004 |
| **XGBoost 14-Feat (Oracle Survey Data)**| 14 | 14 features, survey SAQ ground truth | $7,393.00 [$6,651.32, $8,193.44] | $24,483.64 [$19,581.42, $29,197.13] | 0.0048 | $2,560.56 | $6,375.95 | $20,373.53 | 0.0057 |
| **Tweedie GLM (Observable-Only)** | 11 | Observable features, direct dollars | $8,987.94 [$8,288.70, $9,724.82] | $23,542.97 [$18,707.60, $28,143.67] | 0.0798 | **$8,177.92** | $7,841.15 | $19,563.13 | 0.0832 |
| **Tweedie GLM (14-Feat, Deployment Imputed)** | 14 | 14 features, SAQ imputed via training table | $8,972.22 [$8,274.73, $9,718.04] | $23,652.41 [$18,741.57, $28,291.38] | 0.0712 | $7,974.15 | $7,815.22 | $19,592.24 | 0.0805 |
| **Tweedie GLM (14-Feat, Oracle Survey Data)**| 14 | 14 features, survey SAQ ground truth | $8,784.13 [$8,077.37, $9,508.28] | **$23,377.73** [$18,537.32, $28,083.43] | **0.0927** | **$8,216.41** | $7,605.82 | **$19,370.18** | **0.1012** |
| **Tweedie GLM (14-Feat, Weighted, Oracle)** | 14 | 14 features, normalized wtd fit | $8,861.53 [$8,161.20, $9,592.24] | $23,404.73 [$18,561.96, $28,101.47] | 0.0906 | $8,359.35 | $7,675.65 | $19,377.44 | 0.1005 |
| **Two-Part Model (Duan Smearing, 14-Feat)** | 14 | Part 1 Logistic + Part 2 OLS ($s=2.9989$) | $9,650.22 [$8,961.44, $10,387.30] | $23,842.28 [$19,327.10, $28,327.42] | 0.0563 | $9,781.06 | $8,204.84 | $19,892.29 | 0.0521 |
| **Linear Regression (OLS, 14-Feat)** | 14 | 14 features, $\ln(1+y)$, unweighted fit | $7,530.51 [$6,779.12, $8,331.05] | $24,524.75 [$19,657.68, $29,193.89] | 0.0015 | $2,696.24 | $6,481.02 | $20,450.72 | -0.0019 |
| **Ridge Regression (14-Feat, α=10)** | 14 | 14 features, $\ln(1+y)$, L2 penalty | $7,529.85 [$6,778.33, $8,331.60] | $24,524.27 [$19,656.65, $29,192.33] | 0.0015 | $2,692.32 | $6,480.62 | $20,450.32 | -0.0018 |

> [!NOTE]
> **Variance Identity Check:**
> For the Observable XGBoost model, $\text{RMSE} = \$24,706.50$.
> Evaluating against population variance ($\text{ddof}=0$, $\$602,354,051.95$):
> $$R^2 = 1 - \frac{(24,706.50)^2}{602,354,051.95} = 1 - 1.013376 = -0.013376 \approx \mathbf{-0.0134}$$
> This strictly reconciles with `sklearn.metrics.r2_score(y_test, y_pred) = -0.013376`.

---

## 3. High-Expenditure Classification Benchmarks

### 3.1. Target 1: Unweighted Sample Top Decile ($\text{TOTEXP23} \ge \$20,360.50$, Test Prevalence = $10.28\%$)
Target-specific constant baseline probability is $\hat{p} = 0.1000$ (test baseline Brier score = **$0.0922$**).

| Candidate Model | Features | Input Condition | Mean Pred Prob | Brier Score | Brier Skill Score | ROC-AUC [95% CI] | PR-AUC [95% CI] | Cal Intercept (α) | Cal Slope (β) | F1 @ 0.10 |
|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Constant Baseline** | 0 | None (Constant $\hat{p}=0.1000$) | 0.1000 | 0.0922 | +0.0000 | 0.5000 | 0.1028 | 0.000 | 0.000 | 0.1864 |
| **Logistic (Observable-Only)** | 11 | Observable Features | 0.1007 | 0.0839 | +0.0906 | 0.7599 [0.7341, 0.7830] | 0.2706 [0.2327, 0.3133] | -0.165 | 0.896 | 0.3208 |
| **Logistic (14-Feat, Deployment Imputed)** | 14 | Imputed via Training Lookup | 0.0975 | 0.0842 | +0.0866 | 0.7552 [0.7300, 0.7781] | 0.2569 [0.2228, 0.2974] | -0.051 | 0.938 | 0.3248 |
| **Logistic (14-Feat, Oracle Survey Data)** | 14 | Survey Ground Truth | 0.1009 | **0.0810** | **+0.1221** | 0.7826 [0.7567, 0.8054] | 0.3147 [0.2742, 0.3601] | -0.100 | 0.930 | 0.3457 |
| **Logistic (14-Feat, Weighted Fit, Oracle)**| 14 | Survey Ground Truth (Wtd Fit) | 0.1013 | **0.0809** | **+0.1226** | 0.7833 [0.7579, 0.8062] | **0.3172** [0.2761, 0.3621] | -0.093 | 0.936 | 0.3550 |
| **XGBoost (Platt, 14-Feat, Imputed)** | 14 | Imputed via Training Lookup | 0.0993 | 0.0847 | +0.0813 | 0.7588 [0.7342, 0.7825] | 0.2589 [0.2239, 0.2971] | +0.071 | 1.015 | 0.3299 |
| **XGBoost (Platt, 14-Feat, Oracle)** | 14 | Survey Ground Truth | 0.1010 | 0.0834 | +0.0960 | **0.7850** [0.7598, 0.8079] | 0.2959 [0.2575, 0.3393] | -0.017 | 0.980 | **0.3677** |

---

### 3.2. Target 2: Survey-Weighted Population Top Decile ($\text{TOTEXP23} \ge \$17,827.41$, Prevalence = $11.98\%$ unweighted / $10.51\%$ weighted)
- **Baseline Parameters:** Training-set survey-weighted prevalence $\hat{p} = \mathbf{0.0999}$ ($0.099888$), Test survey-weighted prevalence $\bar{y}_{\text{test, wtd}} = \mathbf{0.1051}$ ($0.105134$).
- **Baseline Brier Scores:** Unweighted Test Baseline Brier = **$0.1059$**, Survey-Weighted Test Baseline Brier = **$0.0941$** ($0.094108$).

| Candidate Model | Features | Input Condition | Mean Prob | Unw Brier | Unw BSS (vs 0.1059) | Survey-Wtd Brier | Survey-Wtd BSS (vs 0.0941) | ROC-AUC [95% CI] | PR-AUC [95% CI] | Cal Slope (β) |
|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Constant Baseline** | 0 | Constant ($\hat{p}=0.0999$) | 0.0999 | 0.1059 | +0.0000 | 0.0941 | +0.0000 | 0.5000 | 0.1051 | 0.000 |
| **Logistic (Observable-Only)** | 11 | Observable Features | 0.1151 | 0.0936 | +0.1155 | 0.0845 | **+0.1025** | 0.7654 [0.7414, 0.7874] | 0.3184 [0.2820, 0.3606] | 0.979 |
| **Logistic (14-Feat, Deployment Imputed)** | 14 | Imputed via Training Lookup | 0.1141 | 0.0946 | +0.1067 | 0.0849 | +0.0978 | 0.7594 [0.7359, 0.7808] | 0.2982 [0.2636, 0.3401] | 0.994 |
| **Logistic (14-Feat, Oracle Survey Data)** | 14 | Survey Ground Truth | 0.1170 | **0.0901** | **+0.1491** | **0.0817** | **+0.1314** | 0.7876 [0.7637, 0.8086] | **0.3637** [0.3233, 0.4086] | 0.995 |
| **XGBoost (Platt, 14-Feat, Imputed)** | 14 | Imputed via Training Lookup | 0.1169 | 0.0946 | +0.1062 | 0.0848 | +0.0989 | 0.7650 [0.7414, 0.7877] | 0.3087 [0.2737, 0.3503] | 1.062 |
| **XGBoost (Platt, 14-Feat, Oracle)** | 14 | Survey Ground Truth | 0.1172 | 0.0922 | +0.1296 | 0.0832 | +0.1159 | **0.7904** [0.7676, 0.8119] | 0.3472 [0.3086, 0.3911] | 1.016 |

> [!IMPORTANT]
> **Inference Recommendation Grounding:**
> When evaluated on deployment-accessible inputs, the **11-feature Observable-Only Logistic Regression** achieves a higher survey-weighted Brier Skill Score (**$+0.1025$**) than the 14-feature model under deployment imputation (**$+0.0978$**). The higher performance of the 14-feature oracle model ($+0.1314$) is driven entirely by survey variables that cannot be collected at runtime. Therefore, the 11-feature Observable model is mathematically and methodologically justified as the leading classifier candidate for integration testing.

---

## 4. Expenditure Stratification & Group-Level Calibration

### 4.1. Observable Tweedie Compound Poisson-Gamma GLM (Dollar-Scale Stratification & Group Ratios)
Evaluated by binning held-out test predictions generated directly by the 11-feature Observable Tweedie model (`p_tw_obs`, $N=3,755$):

| Decile | Count | Predicted Range ($) [Observable Tweedie] | Mean Predicted ($) [Observable Tweedie] | Mean Observed ($) | Observed-to-Predicted Ratio | % Zero Spenders | % Top Decile Spenders |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | 390 | $1,844.66 - $2,249.21 | $2,057.32 | $3,632.68 | 1.766x | 15.6% | 3.6% |
| **2** | 368 | $2,256.89 - $2,633.23 | $2,438.26 | $2,022.39 | 0.829x | 27.7% | 1.6% |
| **3** | 374 | $2,653.33 - $3,282.25 | $2,968.74 | $2,870.91 | 0.967x | 35.6% | 2.9% |
| **4** | 370 | $3,299.93 - $4,251.23 | $3,751.75 | $2,960.69 | 0.789x | 24.6% | 2.2% |
| **5** | 378 | $4,254.04 - $5,600.57 | $4,937.54 | $5,446.51 | 1.103x | 14.0% | 5.0% |
| **6** | 373 | $5,609.69 - $7,516.12 | $6,514.51 | $7,450.31 | 1.144x | 9.4% | 8.0% |
| **7** | 375 | $7,517.41 - $9,932.57 | $8,715.17 | $10,009.06 | 1.148x | 7.2% | 13.3% |
| **8** | 377 | $9,948.90 - $13,026.17 | $11,490.37 | $11,316.24 | 0.985x | 1.3% | 14.6% |
| **9** | 375 | $13,038.06 - $17,897.15 | $15,123.32 | $17,270.42 | 1.142x | 1.1% | 21.1% |
| **10** | 375 | $17,961.25 - $67,676.68 | $23,846.37 | $24,659.24 | 1.034x | 2.1% | 30.4% |
| **Total / Overall** | **3,755** | **$1,844.66 - $67,676.68** | **$8,177.92** | **$8,764.62** | **1.072x** | **13.9%** | **10.5%** |

#### Reconciliation Summary (Observable Tweedie Model):
- **Test Sample Size:** $3,755$ (exact decile count sum = $3,755$)
- **Overall Observed Mean:** **$\$8,764.62$** $\implies$ Count-weighted decile observed mean: **$\$8,764.62$** ($\Delta = \$0.0000$)
- **Overall Predicted Tweedie Observable Mean:** **$\$8,177.92$** $\implies$ Count-weighted decile predicted mean: **$\$8,177.92$** ($\Delta = \$0.0022 < 0.05$)
- **Status:** **STRICTLY RECONCILED (< 0.05)**

> [!NOTE]
> **Dollar Calibration Qualification:**
> The Observable Tweedie GLM predicts directly on the raw dollar scale without logarithmic retransformation. While its count-weighted mean ($8,177.92 vs $8,764.62 observed) and top-decile mean ($23,846.37 vs $24,659.24, ratio 1.034x) track upper-tail expenditures closely, group-level calibration varies considerably across the spending spectrum. In Decile 1, it substantially underpredicts low spending (1.766x observed-to-predicted ratio), while in Decile 4 it overpredicts (0.789x ratio). Tweedie is designated as the leading candidate for dollar-scale expenditure prediction, but claims of full dollar calibration are not statistically justified.

---

### 4.2. Observable XGBoost Regressor (Ordinal Ranking Stratification)
Binned by predicted rank from the 11-feature Observable XGBoost Regressor (`p_xgb_obs`, $\text{expm1}$ of log predictions, $N=3,755$):

| Decile | Count | Predicted Range ($) [Observable Model] | Mean Predicted ($) [Observable Model] | Mean Observed ($) | Observable Underprediction Ratio | % Zero Spenders | % Top Decile Spenders |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | 376 | $25.81 - $103.07 | $61.88 | $1,979.90 | 31.99x | 39.6% | 1.6% |
| **2** | 381 | $103.18 - $230.43 | $182.74 | $3,387.33 | 18.54x | 23.9% | 2.4% |
| **3** | 377 | $230.64 - $274.61 | $255.14 | $3,686.97 | 14.45x | 22.5% | 4.2% |
| **4** | 382 | $275.13 - $411.08 | $318.28 | $4,013.33 | 12.61x | 19.1% | 2.9% |
| **5** | 362 | $412.58 - $913.69 | $665.77 | $4,090.41 | 6.14x | 9.9% | 4.1% |
| **6** | 375 | $915.93 - $1,461.49 | $1,137.14 | $8,184.84 | 7.20x | 11.5% | 9.3% |
| **7** | 378 | $1,461.56 - $2,744.96 | $2,068.48 | $9,835.12 | 4.76x | 5.6% | 12.4% |
| **8** | 373 | $2,749.80 - $4,140.29 | $3,466.76 | $11,978.64 | 3.46x | 2.4% | 15.0% |
| **9** | 375 | $4,143.65 - $6,772.45 | $5,307.46 | $15,538.82 | 2.93x | 1.6% | 19.5% |
| **10** | 376 | $6,774.51 - $23,962.79 | $10,396.39 | $24,974.08 | 2.40x | 1.6% | 31.4% |
| **Total / Overall** | **3,755** | **$25.81 - $23,962.79** | **$2,384.13** | **$8,764.62** | **3.68x** | **13.4%** | **10.3%** |

#### Reconciliation Summary (Observable XGBoost Model):
- **Test Sample Size:** $3,755$ (exact decile count sum = $3,755$)
- **Overall Observed Mean:** **$\$8,764.62$** $\implies$ Count-weighted decile observed mean: **$\$8,764.62$** ($\Delta = \$0.0000$)
- **Overall Predicted XGBoost Observable Mean:** **$\$2,384.13$** $\implies$ Count-weighted decile predicted mean: **$\$2,384.13$** ($\Delta = \$0.0000$)
- **Status:** **STRICTLY RECONCILED (< 0.05)**

---

## 5. Input Availability Parity, Runtime Mapping & Clinical NLP Audit

### 5.1. Artifact Inventory and Declared Targets
Every model serialized in the HealthScore runtime has been audited for input requirements, declared targets, and feature counts:

| Serialized Model Artifact | Target Definition | Target Threshold | Features | Exact Input Generation Path for Inference | Parity Status |
|:---|:---|:---:|:---:|:---|:---:|
| [`risk_model.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/risk_model.pkl) | Relative expenditure ranking (log scale) | — | 11 | Derived from `age`, `gender`, `diseaseInput`. No unobserved fields. | **Input Availability Parity; Semantic Validation Pending** |
| [`risk_model_observable.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_observable.pkl) | Benchmark observable regressor | — | 11 | Same as primary model. No unobserved fields. | **Input Availability Parity; Semantic Validation Pending** |
| [`risk_model_tweedie_observable.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_tweedie_observable.pkl)| Direct dollar prediction (Observable Tweedie) | — | 11 | Evaluates Tweedie directly on 11 observable features. Zero SAQ dependency. | **Input Availability Parity; Semantic Validation Pending** |
| [`risk_model_classifier_observable.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_classifier_observable.pkl)| Target 2: Survey-Weighted Population P90 | $\ge \$17,827.41$ | 11 | Logistic Regression on 11 observable features. Zero SAQ dependency. | **Input Availability Parity; Semantic Validation Pending** |
| [`risk_model_classifier_observable_weighted_p90.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_classifier_observable_weighted_p90.pkl)| Target 2: Survey-Weighted Population P90 | $\ge \$17,827.41$ | 11 | Explicitly named Target 2 observable classifier (Normalized Weighted Fit). | **Input Availability Parity; Semantic Validation Pending** |
| [`risk_model_classifier_observable_unweighted_p90.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_classifier_observable_unweighted_p90.pkl)| Target 1: Unweighted Sample P90 | $\ge \$20,360.50$ | 11 | Explicitly named Target 1 observable classifier (Unweighted Fit). | **Input Availability Parity; Semantic Validation Pending** |
| [`risk_model_14feat_full.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_14feat_full.pkl)| Benchmark 14-feature regressor | — | 14 | SAQ features (`ADGENH42`, `ANYLMI23`, `DFCOG42`, `K6SUM42`) imputed via training conditional expectation lookup. | **Deployment-Imputed Benchmark** |
| [`risk_model_tweedie.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_tweedie.pkl) | Benchmark 14-feature Tweedie | — | 14 | SAQ features imputed via training conditional expectation lookup. | **Deployment-Imputed Benchmark** |
| [`risk_model_classifier.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_classifier.pkl) | Target 1: Unweighted Sample P90 | $\ge \$20,360.50$ | 14 | Benchmark 14-feature Platt XGBoost on Target 1 with imputed SAQ features. | **Deployment-Imputed Benchmark** |
| [`risk_model_classifier_weighted_p90.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_classifier_weighted_p90.pkl)| Target 2: Survey-Weighted Population P90 | $\ge \$17,827.41$ | 14 | Benchmark 14-feature Platt XGBoost on Target 2 with imputed SAQ features. | **Deployment-Imputed Benchmark** |
| [`risk_model_classifier_unweighted_p90.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_classifier_unweighted_p90.pkl)| Target 1: Unweighted Sample P90 | $\ge \$20,360.50$ | 14 | Explicitly named 14-feature Platt XGBoost on Target 1 with imputed SAQ features. | **Deployment-Imputed Benchmark** |

### 5.2. Runtime Input Mapping to MEPS Training Features
Equal feature counts do **not** establish semantic equivalence. The table below documents precisely how every runtime input maps to each MEPS training feature:

| Runtime Input | Target Feature Name | MEPS Training Construction (HC-251) | Runtime Intake Generation Path | Semantic Parity Status |
|:---|:---|:---|:---|:---|
| `age` (numeric) | `AGE23X` | Continuous person age (0–85 top-coded in MEPS) from variable `AGE23X`. | Exact numeric float value passed in intake JSON (range 0–125; ages >85 represent out-of-distribution extrapolation). | **Computational Parity (OOD >85)** |
| `gender` (string) | `Gender_Male` | Binary indicator derived from `SEX == 1` (1=Male, 0=Female). | Strict validation: requires 'male' or 'female'; missing or unparseable input rejected with ValueError (no silent default). | **Strict Direct Parity** |
| `diseaseInput` (text) | `Cardio_ACG` | Sum of 4 clinician-reported MEPS binary indicators: `HIBPDX` (hypertension) + `CHDDX` (CAD) + `MIDX` (myocardial infarction) + `STRKDX` (stroke). `ANGIDX` omitted in training pipeline line 168. Integer range: 0–4. | **Free-Text:** Regex heuristic score (range 0–2).<br>**Structured Intake:** Exact Phase 1 integer sum (range 0–4). Unmapped `angina` quarantined in metadata. | **Computational Feature Mapping Aligned; Clinical Semantic Validity Pending** |
| `diseaseInput` (text) | `Metabolic_ACG` | Sum of 2 MEPS binary flags: `DIABDX_M18` (diabetes) + `CHOLDX` (hyperlipidemia). Integer range: 0–2. | **Free-Text:** Regex heuristic score (range 0–2).<br>**Structured Intake:** Exact Phase 1 integer sum (range 0–2). Unmapped `thyroid_disorder` quarantined. | **Computational Feature Mapping Aligned; Clinical Semantic Validity Pending** |
| `diseaseInput` (text) | `Respiratory_ACG`| Sum of 3 MEPS binary flags: `ASTHDX` (asthma) + `CHBRON31` (chronic bronchitis) + `EMPHDX` (emphysema). Integer range: 0–3. | **Free-Text:** Regex heuristic score (range 0–2).<br>**Structured Intake:** Exact Phase 1 integer sum (range 0–3). | **Computational Feature Mapping Aligned; Clinical Semantic Validity Pending** |
| `diseaseInput` (text) | `Oncology_ACG` | Single MEPS binary flag `CANCERDX` (any cancer diagnosis). Range 0–1. | **Free-Text:** Regex heuristic score (range 0–1).<br>**Structured Intake:** Exact Phase 1 binary indicator (range 0–1). | **Computational Feature Mapping Aligned; Clinical Semantic Validity Pending** |
| `diseaseInput` (text) | `Musculoskeletal_ACG`| Sum of 2 MEPS binary flags: `ARTHDX` (arthritis diagnosis) + `JTPAIN31_M18` (joint pain). Integer range: 0–2. | **Free-Text:** Regex heuristic score (range 0–1).<br>**Structured Intake:** Exact Phase 1 integer sum (range 0–2). | **Computational Feature Mapping Aligned; Clinical Semantic Validity Pending** |
| `diseaseInput` (text) | `Psychiatric_ACG`| Sum of 2 MEPS binary flags: `ADDPRS42` (past-2-week depression symptoms) + `ADHDADDX` (pediatric ADHD). Integer range: 0–2. | **Free-Text:** Regex heuristic score (range 0–2).<br>**Structured Intake:** Exact Phase 1 integer sum (range 0–2). Unmapped `bipolar`, `anxiety` quarantined. | **Computational Feature Mapping Aligned; Clinical Semantic Validity Pending** |
| Derived | `Comorbidity_Count` | Count of positive clusters among the 6 chronic condition clusters ($\sum_{c=1}^6 \mathbb{I}(\text{Cluster}_c > 0)$). Range 0–6. | Identical formula applied to the 6 runtime cluster values. | **Formulaic Parity on Proxy Clusters** |
| Derived | `Multimorbidity_Penalty` | Quadratic interaction $\text{Comorbidity\_Count}^2$. Range 0–36. | Identical quadratic interaction $\text{Comorbidity\_Count}^2$. | **Formulaic Parity** |
| Derived | `Age_x_Comorbidity` | Product $\text{AGE23X} \times \text{Comorbidity\_Count}$. | Identical product $\text{age} \times \text{Comorbidity\_Count}$. | **Formulaic Parity** |
| *Imputed (14-Feat)* | `Frailty_Index` | Composite $\text{ADGENH42} + 2 \cdot \text{ANYLMI23} + 2 \cdot \text{DFCOG42}$. Range 1–9. | Imputed conditional mean by age bracket and comorbidity tier from training lookup (unless explicit questionnaire inputs provided). | **Imputed Population Expectation** |
| *Imputed (14-Feat)* | `Age_x_Frailty` | Product $\text{AGE23X} \times \text{Frailty\_Index}$. | Product of runtime age and imputed frailty index. | **Imputed Interaction** |
| *Imputed (14-Feat)* | `K6SUM42` | Kessler 6 psychological distress sum (0–24) from self-administered questionnaire. | Imputed conditional mean by age bracket and comorbidity tier from training lookup (unless explicit questionnaire input provided). | **Imputed Population Expectation** |

### 5.3. Clinical NLP Parser: Same-Cluster Negation & Missing-versus-Negative Handling
The clinical text parsing engine (`ml_model/risk_engine.py`) preserves condition-level semantics before cluster aggregation:
1. **Preservation of Same-Cluster Mixed Statements:**
   Negating one condition within a cluster does not suppress an affirmed condition in that same cluster:
   - `"no hypertension, but prior stroke"`: Hypertension is negated, but stroke is affirmed. The cardiovascular cluster resolves to `2` (not suppressed to 0).
   - `"no asthma, but COPD"`: Asthma is negated, but COPD is affirmed. The respiratory cluster resolves to `2` (not suppressed to 0).
   - `"no diabetes, but high cholesterol"`: Diabetes is negated, but hyperlipidemia is affirmed. The metabolic cluster resolves to `1`.
2. **Explicit Negation vs. Missing/Unmentioned Inputs:**
   - **Explicit Absence:** Statements like `"Healthy patient, no chronic medical conditions"` or `"denies all medical conditions"` set all 6 clusters to 0 with `input_status = "explicitly_negated_general"`.
   - **Missing / Unparseable Inputs:** Empty text `""` or non-clinical text ("patient walks in the park") sets all clusters to 0 with `input_status = "missing_or_empty"` or `"unparseable_or_unmentioned"`. All 6 clusters are marked `unmentioned`.
   - **Diagnostic Warnings:** When conditions are unmentioned, the engine flags `input_completeness_warning`: *"Absence of condition mentions in diseaseInput does not imply confirmed clinical absence. Zero comorbidity cluster scores were assigned as an uninformative numerical default for regression input, NOT a clinically confirmed healthy profile."*
   - **Strict Input Mode:** If `require_structured_inputs=True` is requested, the engine returns `{"status": "insufficient_input", "unmentioned_clusters": [...]}` rather than generating an unverified baseline.
3. **Unresolved Semantic Limitations:**
   Regex pattern matching cannot assess complex syntactic dependencies, family medical history (e.g. "mother has cancer"), temporal chronicity ("childhood asthma resolved"), or diagnostic uncertainty. Regex flags remain heuristic intake features and must not be described as clinically equivalent to MEPS physician diagnoses.

---

## 6. AHRQ Validation Roadmap (Executed & Superseded by Phase 2 Report)

> [!NOTE]
> **Status Update (October 2026):**
> The Phase 2 external and prospective validation evaluations outlined below have been **fully executed and completed**. Comprehensive results, cohort flows, and metric evaluations are documented in [`EXTERNAL_VALIDATION_REPORT.md`](EXTERNAL_VALIDATION_REPORT.md). The original roadmap descriptions are retained below for historical provenance:

1. **MEPS HC-256 (2024 Full Year Consolidated Data File):**
   - **File Type:** Annual cross-sectional consolidated file covering calendar year 2024 ($N = 18,979$).
   - **Validation Phase:** **Out-of-year contemporaneous external validation** (**Completed** in Phase 2).
   - **Empirical Findings:** The frozen 2023 Weighted P90 Classifier achieved survey-weighted ROC-AUC $0.7828$, PR-AUC $0.3229$, and Weighted Brier Skill Score $+0.1266$ (cal slope $1.0554$). Tweedie GLM tracked the rising population mean ($$9,266.75$ observed) with predicted mean $\$8,473.71$.

2. **MEPS HC-257 (2023–2024 Longitudinal Data File, Panel 28):**
   - **File Type:** Longitudinal two-year panel file tracking Panel 28 respondents across 2023 and 2024 ($N = 8,708$).
   - **Validation Phase:** **Prospective multi-year healthcare expenditure forecasting** (**Completed** in Phase 2).
   - **Empirical Findings:** Baseline 2023 predictors forecast Year 2 high-cost status with prospective ROC-AUC $0.7807$ (Adult SAQ subcohort: $0.7466$). Econometric persistence benchmark confirmed that lagged Year 1 spending (`TOTEXPY1`) achieves $R^2 = 0.1204$, outperforming static diagnosis-only Tweedie ($R^2 = 0.0652$).


---

## 7. SHAP Feature Attribution (TreeExplainer)

SHAP attributions computed via `TreeExplainer` on the 11-feature Observable XGBoost Regressor over the held-out test set represent **statistical contributions to this model's log-expenditure predictions (associative contributions)**, not clinical or causal effects.

| Rank | Feature | Mean Absolute SHAP Value | Interpretation |
|:---:|:---|:---:|:---|
| 1 | `Age_x_Comorbidity` | 0.7712 | Statistical interaction: chronic illness burden scales non-linearly with age. |
| 2 | `Comorbidity_Count` | 0.3541 | Main contribution of cumulative chronic condition count. |
| 3 | `AGE23X` | 0.2814 | Main contribution of chronological age. |
| 4 | `Gender_Male` | 0.2642 | Sex indicator contribution. |
| 5 | `Multimorbidity_Penalty` | 0.0592 | Quadratic penalty term contribution ($\text{Count}^2$). |
| 6 | `Metabolic_ACG` | 0.0475 | Contribution of diabetes/hyperlipidemia indicator. |
| 7 | `Musculoskeletal_ACG`| 0.0421 | Contribution of arthritis/joint pain indicator. |
| 8 | `Oncology_ACG` | 0.0312 | Contribution of cancer history indicator. |
| 9 | `Psychiatric_ACG` | 0.0284 | Contribution of depressive symptoms / ADHD indicator. |
| 10 | `Cardio_ACG` | 0.0241 | Contribution of hypertension/CAD/stroke indicator. |
| 11 | `Respiratory_ACG` | 0.0071 | Contribution of asthma/COPD indicator. |

> [!IMPORTANT]
> **Custom Condition-Cluster Disclaimer:**
> The six condition clusters (`Cardio_ACG`, `Metabolic_ACG`, etc.) are custom heuristic condition indicator sums built from MEPS priority condition survey flags. They were **NOT** produced using the proprietary Johns Hopkins ACG® Case-Mix System software.

---

## 8. Score Semantics & Expenditure Risk Interpretation

The inference engine outputs `relative_expenditure_score` (aliased backwards-compatibly to `health_score`):
$$\text{relative\_expenditure\_score} = 100 - \text{PercentileRank}(\hat{y}_{\text{model}}, \text{OOF\_predictions})$$

### Interpretation & Limitations:
1. **Inverse Model Expenditure Rank:** A score of 85 signifies that the model expects the individual to incur lower annual medical expenditure than approximately 85% of individuals in the training cohort, given their demographic and chronic condition profile.
2. **Not a Clinical Vitality Index:** The score does not measure physiological health, biological age, cardiovascular fitness, mental well-being, or disease remission.
3. **No Causal Interpretation:** A higher score does not guarantee lower future healthcare utilization, nor does modifying an input guarantee a causal reduction in medical costs.
4. **Cohort Specificity:** The benchmark distribution reflects the civilian noninstitutionalized U.S. population in calendar year 2023. It cannot be directly generalized to institutionalized, incarcerated, or international populations.
5. **Not an Actuarial Pricing or Underwriting Model:** Predicted dollar expenditure and relative rank do not represent actuarially certified commercial insurance premiums, risk adjustment transfer payments, underwriting adequacy, or reserve solvency computations. The model is designated strictly as an empirical dollar-scale expenditure stratification candidate for research and technical integration testing.
