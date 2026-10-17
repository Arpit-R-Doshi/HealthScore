# HealthScore Phase 2: Clinical Semantic Validation & External Generalization Plan

**Document Version:** 1.0 (Pre-Experimental Protocol & Specification)  
**Date:** October 2026  
**Auditor / Healthcare Data Scientist:** Senior Healthcare Data Scientist & Research-Methodology Reviewer  
**Branch:** `feature/ml-pipeline-rebuild`  
**Repository:** [https://github.com/Arpit-R-Doshi/HealthScore](https://github.com/Arpit-R-Doshi/HealthScore)  

---

## 1. Executive Overview & Mission

Phase 1 established a hardened, leak-free, reproducible training and inference pipeline evaluated on MEPS HC-251 (2023 Full Year Consolidated File, $N=18,771$ eligible records; $N_{\text{train}}=15,016, N_{\text{test}}=3,755$). It reconciled data drops (retaining 2,611 zero-spenders), fixed mental health coding (`ADDPRS42`), eliminated in-sample benchmark optimism via 5-fold cross-validation, aligned variance conventions, and qualified Tweedie decile stratification without overclaiming full calibration.

The objective of **Phase 2** is to move beyond development-time exploratory benchmarks and evaluate:
1. **Clinical Semantic Validity:** Whether runtime free-text and structured inputs faithfully capture the clinical features on which models were trained.
2. **Contemporaneous Cross-Year External Generalization (MEPS HC-256):** Whether frozen 2023 models generalize across calendar years to an independent 2024 cross-sectional cohort.
3. **Prospective Longitudinal Forecasting (MEPS HC-257):** Whether 2023 baseline clinical predictors can forecast future 2024 healthcare expenditures across time, without temporal leakage.
4. **Actuarial Scope & Solvency Boundaries:** Disentangle technical simulation heuristics from formal actuarial underwriting, commercial insurance pricing, and capital solvency.

> [!CRITICAL]
> **Validation Protocol Notice:**  
> All primary Phase 2 evaluations are conducted against **frozen Phase 1 models**. Models will **NOT** be refitted, retrained, or fine-tuned on 2024 data to optimize reported metrics. Pre-declared thresholds and evaluation criteria are established herein prior to scoring.

---

## 2. Frozen Baseline Artifacts & Provenance

The frozen Phase 1 artifacts serve as the immutable evaluation baseline. Their identities, sizes, and SHA-256 checksums are recorded below:

| Model / Artifact File | Size (Bytes) | SHA-256 Checksum | Frozen Training Specification |
| :--- | :---: | :--- | :--- |
| [`risk_model.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/risk_model.pkl) | 1,252,943 | `2ba4331510d688b1a21e67156bb5aab547c12e8c1ee109a851591b126a7d9c72` | 11-feature Observable XGBoost Regressor ($\ln(1+y)$ objective, ordinal ranking) |
| [`risk_model_tweedie_observable.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_tweedie_observable.pkl) | 1,234 | `a7f185db46316c6ac5f9051f0d5e0e24c7e80f3bd1f7777cd26cd0e1b42fcbd8` | 11-feature Observable Tweedie GLM ($p=1.5$, log link, un-logged dollar prediction) |
| [`risk_model_classifier_observable_weighted_p90.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_classifier_observable_weighted_p90.pkl) | 1,087 | `3632f8201136a2740c3d5a564bbdbb29bc8511db51709fb42c1f8e271bf28c2a` | 11-feature Observable Logistic Regression (Normalized survey-weighted fit, Target 2) |
| [`risk_model_classifier_observable_unweighted_p90.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/risk_model_classifier_observable_unweighted_p90.pkl) | 1,087 | `cc266ae52414169c3c93b97a8ee147cba5eb62b0e0feff583c85a4e133a880fb` | 11-feature Observable Logistic Regression (Unweighted fit, Target 1) |
| [`benchmark_costs.pkl`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/benchmark_costs.pkl) | 242,743 | `03537b28f71a1bea2a94322fee85c9c4e9734acc618894335b9f22196d09b820` | 5-fold cross-validated out-of-fold cost percentiles ($N=15,016$) |
| [`training_metadata.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/training_metadata.json) | 7,611 | `f9f43ccfabd0de3c3b7702e2acc589f0f4c9803d885bf14937f94214dc985ca6` | Frozen P90 thresholds: Target 1 = $\$20,360.50$, Target 2 = $\$17,827.41$ |
| [`feature_schema.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/feature_schema.json) | 6,006 | `2a8a5b6b5d127e809ee992f39c64d533762d2b51d1d89436678b142ac36f5fea` | 11-feature observable schema & runtime variable mapping definitions |
| [`evaluation_metrics.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/artifacts/evaluation_metrics.json) | 40,546 | `fa2e70c5e9524abe5472666f637905fd0a6021b051822b51d2e7e73ebfb08b9c` | Phase 1 baseline evaluation metrics on held-out 2023 test partition |

---

## 3. Methodological Distinctions: Five Separate Analytical Domains

To ensure scientific rigor and prevent methodological conflation, Phase 2 strictly separates five distinct analytical domains:

```
+----------------------------------------------------------------------------------------------------+
|                                    PHASE 2 VALIDATION DOMAINS                                      |
+------------------------------------+----------------------------------+----------------------------+
| 1. Cross-Sectional 2023 Benchmark  | 2. External Cross-Year (HC-256)   | 3. Prospective Forecasting |
|    (Exploratory Held-Out Test Set) |    (CY 2024 Cross-Section)       |    (HC-257 Panel 28)       |
|    - 2023 features -> 2023 spend   |    - 2024 features -> 2024 spend |    - 2023 features -> 2024 |
|    - Repeatedly accessed           |    - Unaccessed test cohort      |    - True temporal delay   |
|    - Exploratory benchmark         |    - Cross-sectional stability   |    - Predictive causality  |
+------------------------------------+----------------------------------+----------------------------+
| 4. Clinical Semantic Validity                                         | 5. Actuarial Pricing Scope |
|    - Runtime text / structured input -> MEPS clinical concepts        |    - Micro-level simulation|
|    - Negation, family history, chronicity, uncertainty                |    - Solvency, risk margins|
|    - Heuristic proxy vs diagnostic truth                              |    - Non-pricing technical |
+-----------------------------------------------------------------------+----------------------------+
```

1. **Cross-Sectional 2023 Internal Evaluation:** Evaluated contemporaneous associations within calendar year 2023. Because the held-out test split ($N=3,755$) was repeatedly evaluated during development, it is explicitly classified as an *exploratory held-out benchmark*, not a pristine confirmatory validation.
2. **External Cross-Year Validation (MEPS HC-256):** Evaluates whether models trained on 2023 cross-sectional data retain predictive validity on an entirely separate, unaccessed cross-sectional cohort in calendar year 2024. Predictors and expenditures are both measured in 2024.
3. **Prospective Healthcare Expenditure Forecasting (MEPS HC-257):** Evaluates true temporal risk forecasting. Baseline predictors are restricted strictly to Year 1 (2023), and the outcome is Year 2 (2024) total medical expenditure. This measures genuine forward-looking risk prediction rather than contemporaneous association.
4. **Clinical Semantic Validity:** Evaluates whether free-text regex parsing and structured patient intake accurately mirror MEPS clinician-confirmed priority condition diagnoses. Unit tests verify syntactic parsing rules, but do not establish clinical validity.
5. **Actuarial Scope & Solvency Boundaries:** Discloses that empirical expenditure percentiles and parametric loss draws represent research simulations. They do not constitute certified insurance pricing, premium setting, underwriting adequacy, or reserve solvency.

---

## 4. Pre-Declared Hypotheses & Success Criteria

Prior to scoring 2024 datasets, the following pre-experimental hypotheses and quantitative acceptance criteria are declared:

### Hypothesis 1: Cross-Year Generalization on HC-256 (2024 Cross-Sectional)
- **Null Hypothesis ($H_{0,1}$):** Frozen 2023 models will collapse on 2024 data ($R^2 \le 0$ or calibration slope $\beta < 0.5$).
- **Alternative Hypothesis ($H_{1,1}$):** Frozen 11-feature Observable Tweedie GLM will maintain positive dollar $R^2 > 0.05$ on HC-256, with observed-to-predicted aggregate ratio within $0.85 \le \frac{\text{Obs}}{\text{Pred}} \le 1.20$.
- **Classifier Hypothesis ($H_{1,1\text{b}}$):** Frozen Target 2 Observable Logistic Classifier will maintain positive Survey-Weighted Brier Skill Score ($\text{Wtd BSS} > 0$) against the 2024 uninformative baseline.

### Hypothesis 2: Prospective Forecasting Degradation on HC-257 (Panel 28 Longitudinal)
- **Null Hypothesis ($H_{0,2}$):** Baseline 2023 features forecast 2024 expenditures with equal or higher $R^2$ than contemporaneous models.
- **Alternative Hypothesis ($H_{1,2}$):** True prospective forecasting will exhibit marked performance degradation relative to contemporaneous models (anticipated $R^2$ drop of $\ge 30\%$, Dollar RMSE increase $\ge 10\%$) due to incident acute conditions, regression to the mean in high spenders, and 12-month temporal latency.

### Hypothesis 3: Clinical NLP Semantic Failure on Complex Syntax
- **Hypothesis ($H_{1,3}$):** Regex-based keyword matching will achieve high sensitivity ($>90\%$) on direct affirmative statements, but will exhibit significant error rates ($>20\%$ false positive rate) when challenged with family medical history, temporal resolution (cured/historical conditions), diagnostic uncertainty, and non-standard syntax.

---

## 5. Input Variables, Target Formulations & Missing Data Policy

### 5.1. Variable Mapping: HC-251 (2023) to HC-256 (2024) and HC-257 (Panel 28)

| Feature Role | 2023 Source (HC-251) | 2024 Cross-Sectional (HC-256) | Longitudinal Baseline (HC-257 Panel 28) | Harmonization Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Age** | `AGE23X` | `AGE24X` | `AGE23X` (Year 1 Age) | Identity mapping; filter `AGE >= 0` |
| **Sex** | `SEX` | `SEX` | `SEX` | Binary indicator (`1` if Male, else `0`) |
| **Cardiovascular** | `HIBPDX`, `CHDDX`, `MIDX`, `STRKDX` | `HIBPDX`, `CHDDX`, `MIDX`, `STRKDX` | Year 1 Priority DX flags (`ANGIDX` omitted) | Sum of 4 binary flags: `HIBPDX + CHDDX + MIDX + STRKDX` (Range 0–4) |
| **Metabolic** | `DIABDX_M18`, `CHOLDX` | `DIABDX_M18`, `CHOLDX` | Year 1 Priority DX flags | Sum of 2 binary flags: `DIABDX_M18 + CHOLDX` (Range 0–2) |
| **Respiratory** | `ASTHDX`, `CHBRON31`, `EMPHDX` | `ASTHDX`, `CHBRON31`, `EMPHDX` | Year 1 Priority DX flags | Sum of 3 binary flags: `ASTHDX + EMPHDX + CHBRON31` (Range 0–3) |
| **Oncology** | `CANCERDX` | `CANCERDX` | Year 1 Priority DX flag | Binary flag: `CANCERDX` (0 or 1) |
| **Musculoskeletal** | `ARTHDX`, `JTPAIN31_M18` | `ARTHDX`, `JTPAIN31_M18` | Year 1 Priority DX flags | Sum of 2 binary flags: `ARTHDX + JTPAIN31_M18` (Range 0–2) |
| **Psychiatric** | `ADDPRS42`, `ADHDADDX` | `ADDPRS42`, `ADHDADDX` | Year 1 Priority DX flags | Sum of 2 binary flags: `ADDPRS42 + ADHDADDX` (Range 0–2) |
| **Sampling Weight** | `PERWT23F` | `PERWT24F` | `LONGWT` (Longitudinal 2-Year Weight) | Normalized to mean=1.0 for ML evaluation |
| **Variance Strata** | `VARSTR` | `VARSTR` | `VARSTR` | Complex survey design stratification |
| **Variance PSU** | `VARPSU` | `VARPSU` | `VARPSU` | Complex survey design cluster indicator |
| **Target: Expenditure** | `TOTEXP23` | `TOTEXP24` | `TOTEXP24` (Year 2 Expenditure) | Continuous positive dollar expenditure |

### 5.2. Locked Target Thresholds
All classification evaluations on HC-256 and HC-257 will be evaluated primarily against the **frozen Phase 1 training thresholds**:
- **Target 1 (Unweighted Sample P90):** $\text{Expenditure} \ge \mathbf{\$20,360.50}$
- **Target 2 (Survey-Weighted Population P90):** $\text{Expenditure} \ge \mathbf{\$17,827.41}$

*Secondary Descriptive Note:* Year-specific sample percentiles on 2024 data will be computed solely for descriptive comparison, but will not replace the primary frozen evaluation.

### 5.3. Missing Data & Skip Pattern Policy
- Special MEPS negative values (`-1 INAPPLICABLE`, `-7 REFUSED`, `-8 DON'T KNOW`, `-9 NOT ASCERTAINED`):
  - Inapplicable codes for age-restricted items (e.g. `HIBPDX` for children under 18) are mapped strictly to `0` (absence of documented condition), reflecting standard survey skip patterns.
  - Refused or unascertined condition flags ($<0.05\%$ of records) are treated as unconfirmed (`0`) and audited for missingness frequency.
  - Records with invalid age (`AGE < 0`) are excluded from the eligible analysis cohort.

---

## 6. Evaluation Metrics & Statistical Protocol

### Regressor Evaluation Metrics
1. **Mean Absolute Error (MAE):** Unweighted and survey-weighted dollar error.
2. **Root Mean Squared Error (RMSE):** Unweighted and survey-weighted dollar error.
3. **Coefficient of Determination ($R^2$):** Evaluated strictly against population variance ($\text{ddof}=0$):
   $$R^2 = 1 - \frac{\sum w_i (y_i - \hat{y}_i)^2}{\sum w_i (y_i - \bar{y}_{\text{pop}})^2}$$
4. **Decile Stratification & Calibration Ratios:** Binned by model predicted deciles; reporting mean observed, mean predicted, count, and observed-to-predicted ratio ($\frac{\text{Obs}}{\text{Pred}}$).

### Classifier Evaluation Metrics
1. **Brier Score:** $\frac{1}{N} \sum (p_i - y_i)^2$ (unweighted and survey-weighted).
2. **Brier Skill Score (BSS):** Relative improvement over the target-specific constant baseline prevalence predictor:
   $$\text{BSS} = 1 - \frac{\text{Brier}_{\text{model}}}{\text{Brier}_{\text{baseline}}}$$
3. **Area Under ROC Curve (ROC-AUC) & Precision-Recall Curve (PR-AUC)**.
4. **Calibration Intercept ($\alpha$) and Calibration Slope ($\beta$)** via logistic calibration regression $\text{logit}(y) = \alpha + \beta \cdot \text{logit}(\hat{p})$.

---

## 7. Execution Roadmap & Phase 2 Deliverables

1. **Stage B Deliverable:** `CLINICAL_SEMANTIC_VALIDATION_REPORT.md`
   - Complete 14-feature lineage table.
   - Structured intake pathway implementation and unit tests.
   - Adversarial challenge set execution (syntactic, family history, temporal, negation).
   - Independent clinical chart adjudication protocol and gold-standard schema.
2. **Stage C & D Deliverable:** `EXTERNAL_VALIDATION_REPORT.md`
   - Data provenance, download URLs, and SHA-256 hashes for HC-256 and HC-257.
   - HC-256 out-of-year cross-sectional evaluation results.
   - HC-257 prospective longitudinal forecasting evaluation results.
   - Subgroup analyses and temporal drift evaluation.
3. **Stage E Deliverable:** `ACTUARIAL_SCOPE_GAP_ASSESSMENT.md`
   - Audit of current Monte Carlo loss simulation.
   - Disentangling technical demonstration simulations from formal actuarial pricing.
   - Commercial insurance data requirements and regulatory solvency boundaries.

---

## 8. Definition of Done & Scientific Integrity

Phase 2 deliverables will present **measured empirical evidence as observed**, without suppressing disappointing findings. If clinical chart review datasets or external survey files are unavailable or restricted by environment boundaries, they will be reported transparently as **Blocked** or **Not Yet Validated**. No synthetic benchmarks will be presented as genuine clinical validation.
