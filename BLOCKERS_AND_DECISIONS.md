# HealthScore: Blockers, Decisions & Methodology Audit Report (Phase 1)

**Document Version:** 5.1 (Synchronized Authoritative Run, Qualified Dollar Stratification, Candidate Integration Recommendations & Released AHRQ Roadmap)
**Date:** October 2026
**Auditor / Reviewer:** Senior Healthcare Data Scientist & Research-Methodology Reviewer
**Status:** Documented for Review — No Merges, Commits, Remote Pushes, or File Deletions

---

## 1. Overview & Verification Status

This document reconciles all empirical metrics, feature definitions, survey-weighting audits, deployed artifact schemas, and architectural decisions executed during Phase 1 for [HealthScore](file:///Users/arpitdoshi/Desktop/ipd/HealthScore).

In strict adherence to instructions:
- All changes are confined to local branch `feature/ml-pipeline-rebuild`. No commits, merges to `master`, remote pushes, or file deletions in `new/` have been performed.
- All metric tables are generated directly from [`ml_model/artifacts/evaluation_metrics.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/evaluation_metrics.json) produced by the rebuilt training harness.
- Research language has been scrubbed: unsupported claims of "clinical superiority," "calibrated premiums," "actuarial certification," and "production readiness" have been removed.

---

## 2. Reconciled Decisions & Methodological Audits

### Decision 1: Reconciled Overall Metrics, Decile Stratification & Variance Convention
- **Exact Metric Reconciliation:**
  All overall test-set metrics and decile summaries are verified to derive from the identical held-out test labels and model predictions ($N_{\text{test}} = 3,755$):
  - **Overall Observed Test Mean:** **$\$8,764.62$** (Count-weighted decile mean: **$\$8,764.62$**, $\Delta = \$0.00$)
  - **Observable Tweedie GLM Mean Prediction:** **$\$8,177.92$** (Count-weighted decile prediction: **$\$8,177.92$**, $\Delta = \$0.0022 < 0.05$)
  - **Observable XGBoost Mean Prediction:** **$\$2,384.13$** (Count-weighted decile prediction: **$\$2,384.13$**, $\Delta = \$0.00$)
  - **14-Feature Tweedie GLM Mean Prediction:** **$\$8,216.41$** (Count-weighted decile prediction: **$\$8,216.41$**, $\Delta = \$0.00$)
  - **Two-Part Model Mean Prediction:** **$\$9,781.06$** (Count-weighted decile prediction: **$\$9,781.06$**, $\Delta = \$0.00$)
  - All decile counts sum to $3,755$, and count-weighted decile means equal overall test means within a floating-point tolerance of $< 0.003$, verified via automated unit test `test_decile_reconciliation_and_count_weighted_means`.
- **Variance Convention Reconciliation:**
  - Population Variance ($\text{ddof}=0$): **$\$602,354,051.95$**.
  - Sample Variance ($\text{ddof}=1$): **$\$602,514,508.54$**.
  - Scikit-learn's `r2_score(y_true, y_pred)` evaluates $R^2 = 1 - \frac{\text{SS}_{\text{res}}}{\text{SS}_{\text{tot}}}$. Because $\text{SS}_{\text{tot}} = N \cdot \text{Var}_{\text{pop}} (\text{ddof}=0)$ and $\text{SS}_{\text{res}} = N \cdot \text{RMSE}^2$, the identity $R^2 = 1 - \frac{\text{RMSE}^2}{\text{Var}}$ strictly holds against population variance ($\text{ddof}=0$, $\$602,354,051.95$). Evaluated against sample variance ($\text{ddof}=1$), $1 - \frac{\text{RMSE}^2}{\text{Var}_{\text{sample}}}$ produces a mathematical discrepancy.
- **Tweedie Status Formulation:**
  Tweedie Compound Poisson-Gamma GLM ($p=1.5$) is documented as the **leading candidate for dollar-scale expenditure prediction**, not as a certified or fully calibrated estimator. Its group-level calibration was evaluated using its own predictions (`p_tw_obs`). While tracking upper-tail spending relatively well (Decile 10 mean predicted $\$23,846.37$ vs. observed $\$24,659.24$, ratio 1.034), observed-to-predicted ratios vary across deciles (1.766x in Decile 1 to 0.789x in Decile 4). Tweedie achieves Dollar RMSE of **$\$23,542.97$** and Dollar $R^2$ of **$0.0798$** (Observable 11-feature model); claims of full dollar calibration are not statistically justified.
- **XGBoost Status Formulation:**
  Observable XGBoost on $\ln(1+y)$ is retained strictly as an **ordinal ranking and log-cost benchmark**. It must never be described as providing calibrated expected dollar expenditure due to severe Jensen's inequality underprediction (~3.68x overall underprediction).

---

### Decision 2: Input Availability Parity Across Model Artifacts
- **Verification Rule:** Matching tensor dimensions or feature names is insufficient to claim deployment parity. Equal feature counts establish **Input Availability Parity; Semantic Validation Pending**, not semantic equivalence.
- **Artifact-Specific Parity Audits:**
  1. **Primary Regressor (`risk_model.pkl` / `risk_model_observable.pkl`):** Expects **11 observable features**. All 11 features are directly computable from patient intake (`age`, `gender`, `diseaseInput`), requiring zero unobserved synthetic imputation. **Status: Input Availability Parity; Semantic Validation Pending.**
  2. **Observable Tweedie GLM (`risk_model_tweedie_observable.pkl`):** Trained on the exact same **11 observable features** (Test MAE: $\$8,987.94$, RMSE: $\$23,542.97$, Dollar $R^2$: $0.0798$, Mean: $\$8,177.92$). Zero SAQ dependency. **Status: Input Availability Parity; Semantic Validation Pending.**
  3. **Observable Logistic Classifier (`risk_model_classifier_observable.pkl` / `risk_model_classifier_observable_weighted_p90.pkl`):** Trained on the exact same **11 observable features** (Test Brier: $0.0936$, Weighted Brier: $0.0845$, ROC-AUC: $0.7654$, PR-AUC: $0.3184$, Target 2 Weighted BSS: $+0.1025$). Zero SAQ dependency. **Status: Input Availability Parity; Semantic Validation Pending.**
  4. **14-Feature Canonical Models (`risk_model_14feat_full.pkl`, `risk_model_tweedie.pkl`, `risk_model_classifier.pkl`):** Require unobserved SAQ variables (`ADGENH42`, `ANYLMI23`, `DFCOG42`, `K6SUM42`). At inference, these are populated using empirical conditional expectations stratified by age bracket and comorbidity tier fitted strictly on training data ($N=15,016$). **Status: Documented & Validated Imputation Parity.** Conditional means are population stratification proxies, not personal health measurements.
- **Inference Engine Designation:** The 11-feature observable model suite (`risk_model.pkl`, `risk_model_tweedie_observable.pkl`, `risk_model_classifier_observable.pkl`) is designated as the primary candidate suite for integration testing because it achieves complete input availability parity with zero synthetic imputation. Every serialized artifact declares its target explicitly in `training_metadata.json`.

---

### Decision 3: Clinical NLP Disease-Parser Parity, Negation & Semantic Limitations
- **Data Generation Discrepancy:**
  MEPS diagnosis flags and frontend free-text parsing are fundamentally different input-generation processes:
  - MEPS condition flags derive from household-reported doctor diagnoses followed by medical-provider event followback and mapping to ICD-10-CM / CCSR categories.
  - The frontend parser uses regex substring matching on unstructured free-text descriptions.
- **Same-Cluster Condition Negation & Affirmation:**
  - Negating one condition within a cluster does not suppress an affirmed condition in that same cluster (e.g. `"no hypertension, but prior stroke"` preserves stroke $\implies \text{cardio}=2$; `"no asthma, but COPD"` preserves COPD $\implies \text{respiratory}=2$).
  - Statements with negative qualifiers evaluate to $0$ and never trigger positive condition flags.
- **Missing vs. Explicitly Negated Inputs:**
  - Empty text `""` or unparseable text is categorized as `unmentioned`, and the engine flags `input_completeness_warning`: absence of mentions is NOT confirmed absence of disease.
  - The inference engine supports `require_structured_inputs=True`, returning `status: "insufficient_input"` when clinical conditions are unmentioned.
- **Unresolved Semantic Limitations:**
  - Regex pattern matching cannot assess syntactic dependencies, family medical history (e.g. "mother had hypertension"), temporal chronicity ("had asthma 20 years ago"), or diagnostic uncertainty ("possible angina").
  - Regex flags are heuristic user intake features and must NOT be described as clinically equivalent to MEPS physician diagnoses.

---

### Decision 4: Reconciled Dual-Estimand Classifier Evaluation
- **Target Separation & Reconciled Baselines:**
  - **Target 1: Unweighted Sample Top Decile ($\text{TOTEXP23} \ge \$20,360.50$, Prevalence $10.28\%$):**
    - Unweighted Constant Baseline: $\hat{p} = 0.1000 \implies \text{Baseline Brier} = \mathbf{0.0922}$.
    - Observable Logistic (11-Feat): Brier = $0.0839$ ($\text{BSS} = \mathbf{+0.0906}$).
    - Deployment-Imputed Logistic (14-Feat): Brier = $0.0842$ ($\text{BSS} = \mathbf{+0.0866}$).
    - Actual MEPS Oracle Logistic (14-Feat): Brier = **$0.0810$** ($\text{BSS} = \mathbf{+0.1221}$).
    - Deployment-Imputed Platt XGBoost (14-Feat): Brier = $0.0847$ ($\text{BSS} = \mathbf{+0.0813}$).
    - Actual MEPS Oracle Platt XGBoost (14-Feat): Brier = **$0.0834$** ($\text{BSS} = \mathbf{+0.0960}$).
  - **Target 2: Survey-Weighted Population Top Decile ($\text{TOTEXP23} \ge \$17,827.41$, Prevalence $11.98\%$ unw / $10.51\%$ wtd):**
    - **Reconciled Baseline Parameters:** Training-set survey-weighted prevalence $\hat{p} = \mathbf{0.0999}$ ($0.099888$), Constant baseline prediction $\hat{p} = \mathbf{0.0999}$. Test survey-weighted outcome prevalence $\bar{y}_{\text{test, wtd}} = \mathbf{0.1051}$ ($0.105134$), Test unweighted prevalence $\bar{y}_{\text{test, unw}} = \mathbf{0.1198}$ ($0.119840$).
    - **Reconciled Baseline Brier Scores:**
      - Test Survey-Weighted Baseline Brier: $\bar{y}_{\text{test, wtd}}(1 - 2\hat{p}) + \hat{p}^2 = \mathbf{0.0941}$ ($0.094108$).
      - Test Unweighted Baseline Brier: $\bar{y}_{\text{test, unw}}(1 - 2\hat{p}) + \hat{p}^2 = \mathbf{0.1059}$ ($0.105877$).
    - **Candidate Classifier Results:**
      - *Observable Logistic Regression (11-Feat):* Unweighted Brier = $0.0936$ ($\text{Unw BSS} = \mathbf{+0.1155}$); Survey-Weighted Brier = $0.0845$ ($\text{Survey-Weighted BSS} = \mathbf{+0.1025}$).
      - *Deployment-Imputed Logistic Regression (14-Feat):* Unweighted Brier = $0.0946$ ($\text{Unw BSS} = +0.1067$); Survey-Weighted Brier = $0.0849$ ($\text{Survey-Weighted BSS} = \mathbf{+0.0978}$).
      - *Actual MEPS Oracle Logistic Regression (14-Feat):* Unweighted Brier = $0.0901$ ($\text{Unw BSS} = +0.1491$); Survey-Weighted Brier = $0.0817$ ($\text{Survey-Weighted BSS} = +0.1314$).
      - *Deployment-Imputed Platt XGBoost (14-Feat):* Unweighted Brier = $0.0946$ ($\text{Unw BSS} = +0.1062$); Survey-Weighted Brier = $0.0848$ ($\text{Survey-Weighted BSS} = \mathbf{+0.0989}$).
      - *Actual MEPS Oracle Platt XGBoost (14-Feat):* Unweighted Brier = $0.0922$ ($\text{Unw BSS} = +0.1296$); Survey-Weighted Brier = $0.0832$ ($\text{Survey-Weighted BSS} = +0.1159$).
- **Methodological Recommendation:** On the exploratory held-out test split, the 11-feature Observable Logistic Regression achieves a higher survey-weighted Brier Skill Score ($+0.1025$) than the 14-feature model under deployment imputation ($+0.0978$), demonstrating that observable demographic and clinical cluster inputs yield higher probability skill on this test partition than subjecting unobserved survey features to synthetic imputation.

---

## 3. AHRQ Validation Roadmap (Executed & Completed in Phase 2)

> [!NOTE]
> **Status Update (October 2026):**
> The Phase 2 external cross-year validation and prospective forecasting evaluations designated below have been **fully executed and completed**. Comprehensive results and provenance are documented in [`EXTERNAL_VALIDATION_REPORT.md`](EXTERNAL_VALIDATION_REPORT.md). The original roadmap descriptions are retained below for historical reference:

1. **MEPS HC-256 (2024 Full Year Consolidated Data File):**
   - **Nature:** Annual cross-sectional consolidated data file for calendar year 2024 ($N = 18,979$).
   - **Validation Phase:** **Out-of-year contemporaneous external validation** (**Completed** in Phase 2).
   - **Empirical Findings:** The frozen 2023 Weighted P90 Classifier achieved survey-weighted ROC-AUC $0.7828$, PR-AUC $0.3229$, and Weighted Brier Skill Score $+0.1266$ (cal slope $1.0554$). Tweedie GLM tracked the rising population mean ($$9,266.75$ observed) with predicted mean $\$8,473.71$.

2. **MEPS HC-257 (2023–2024 Longitudinal Data File, Panel 28):**
   - **Nature:** Two-year longitudinal panel following Panel 28 respondents across consecutive calendar years (2023 to 2024, $N = 8,708$).
   - **Validation Phase:** **True prospective healthcare expenditure forecasting** (**Completed** in Phase 2).
   - **Empirical Findings:** Baseline 2023 predictors forecast Year 2 high-cost status with prospective ROC-AUC $0.7807$ (Adult SAQ subcohort: $0.7466$). Econometric persistence benchmark confirmed that lagged Year 1 spending (`TOTEXPY1`) achieves $R^2 = 0.1204$, outperforming static diagnosis-only Tweedie ($R^2 = 0.0652$).

---

## 4. Status of Historical Defects vs. Current Implementation

| Component / Finding | Historical Defect (Pre-Audit) | Current Implementation | Status | Current Scope & Known Limitations |
|:---|:---|:---|:---:|:---|
| **Zero-Expenditure Handling** | Dropped 2,611 records ($13.91\%$) | Retained full cohort ($N=18,771$) | **Resolved** | Zero-spenders accommodated; Tweedie & 2PM benchmarked |
| **Depression Coding (`ADDPRS42`)** | `x == 1` mapped severe depression (2, 3) to 0 | `x in [1, 2, 3]` maps symptoms to 1 | **Resolved** | Captures past-2-week symptoms, not clinical MDD diagnosis |
| **In-Sample Benchmark Optimism** | Benchmark generated on in-sample training data | 5-fold cross-validated out-of-fold predictions | **Resolved** | Benchmarks reflect out-of-fold generalization |
| **Uncalibrated Classifiers** | Reweighted `scale_pos_weight=9.0` (Brier 0.177) | Natural log-loss & Platt scaling (Brier 0.081–0.083) | **Resolved** | Positive Brier skill demonstrated across both targets |
| **Target 2 Baseline Discrepancy** | Unweighted prevalence used in weighted formula | Training survey-weighted prevalence $\hat{p}=0.0999$ used | **Resolved** | Exactly reconciles weighted Brier $0.0941$ and BSS values |
| **Variance Convention Discrepancy**| Ambiguous sample vs population variance | Population Var $\$602,354,051.95$ ($\text{ddof}=0$) verified | **Resolved** | $R^2 = 1 - \text{RMSE}^2 / \text{Var}_{\text{pop}}$ identity verified |
| **Input Availability Parity & Decile Stratification**| 14-feature Tweedie used for deciles; claimed calibrated | 11-feature Observable Tweedie evaluated on its own deciles; qualified | **Resolved** | Decile counts sum to 3,755; means strictly reconciled; ratios qualified |
| **Classifier Input Parity & Declared Targets**| Only oracle 14-feature classifier reported; target undeclared | Observable, deployment-imputed, and oracle reported; targets declared | **Resolved** | Observable model ($+0.1025$ BSS) outperforms imputed model; metadata stores targets |
| **Clinical NLP Negation & Same-Cluster Handling**| "No diabetes" triggered condition flag; cluster negation suppressed stroke | Condition-level negation scoping preserves affirmed conditions | **Resolved** | Unit tests assert "no hypertension, but stroke" -> cardio=2; limitations documented |
| **AHRQ Validation Roadmap** | Erroneous reference to "HC-261" | Corrected to HC-256 (contemporaneous) & HC-257 (prospective) | **Resolved** | Both released by AHRQ; Phase 2 roadmap established |
| **Legacy `new/` Directory** | 47 MB duplicate dataset + obsolete script | Verified identical checksum; isolated from callers | **Isolated** | Awaiting formal phase sign-off; no deletion performed |

---

## 5. Architectural Recommendations for Phase 1 Sign-Off

1. **Primary Runtime Candidates for Integration Testing:**
   - **Relative Expenditure Scoring:** Designate the **11-feature Observable XGBoost Regressor** (`risk_model.pkl`) as the candidate for relative ordinal expenditure ranking, using its out-of-fold benchmark distribution for relative percentiles.
   - **Dollar-Scale Expenditure Stratification:** Designate the **11-feature Observable Tweedie Compound Poisson-Gamma GLM** (`risk_model_tweedie_observable.pkl`) as the candidate for un-logged dollar expenditure stratification and tail risk estimation (Dollar RMSE $\$23,542.97$, Dollar $R^2 = 0.0798$, Decile 10 predicted $\$23,846.37$ vs observed $\$24,659.24$; explicitly qualified against intermediate decile residual fluctuations and preserved as an expenditure stratification candidate, not an actuarial pricing model).
   - **High-Expenditure Classification:** Designate the **11-feature Observable Logistic Classifier** (`risk_model_classifier_observable.pkl` / `risk_model_classifier_observable_weighted_p90.pkl`) as the screening candidate, which achieves positive Survey-Weighted Brier Skill Score ($+0.1025$) targeting the survey-weighted population top decile ($\ge \$17,827.41$) without requiring synthetic imputation of unobserved survey features.

2. **Benchmark Artifacts:**
   - Retain the 14-feature models (`risk_model_14feat_full.pkl`, `risk_model_tweedie.pkl`, `risk_model_classifier.pkl`) and the Two-Part Model (`risk_model_twopart.pkl`) as fully documented benchmark artifacts with empirical conditional expectation imputation paths.

3. **Confirmatory Temporal Evaluation:**
   - Conduct Phase 2 out-of-year contemporaneous external validation using **MEPS HC-256** (2024 Full Year Consolidated File) and prospective longitudinal validation using **MEPS HC-257** (2023–2024 Longitudinal Panel 28 File), both released by AHRQ (neither claimed as complete until executed).
