# HealthScore MEPS HC-257 Cohort & Survey Weight Audit

**Document Version:** 2.0  
**Audit Date:** October 2026  
**Auditor:** Antigravity Autonomous Research Agent  
**Repository Branch:** `feature/ml-pipeline-rebuild`  
**Dataset Reference:** AHRQ MEPS HC-257 (2023–2024 Panel 28 Longitudinal Data File)  

---

## 1. Executive Summary & Weighting Decision

This audit establishes the definitive cohort derivation, attrition accounting, and survey-weight methodology for the prospective healthcare expenditure forecasting evaluation conducted in Stage D.

### Definitive Methodological Decisions
1. **Primary Analysis (AHRQ-Consistent SAQ Estimand):** The frozen Phase 1 model incorporates `ADDPRS2` (Round 2 Self-Administered Questionnaire depression screener) as an active predictor in `Psychiatric_ACG`. Per official AHRQ documentation, any analysis incorporating SAQ variables must use **`LSAQWT`** (Longitudinal SAQ Weight) to adjust for questionnaire nonresponse among eligible adults. The **Adult SAQ Sub-Cohort ($N = 5,630$)** weighted by `LSAQWT` is therefore designated as the **Primary Longitudinal Estimand**.
2. **Secondary Sensitivity Analysis (Full-Population Screening Heuristic):** The full continuous cohort of two-year respondents ($N = 8,708$) weighted by **`LONGWT`** is retained strictly as a **secondary screening sensitivity analysis**. In this full-cohort analysis, inapplicable/missing SAQ responses for pediatric cases ($< 18$, $N=2,374$) and adult non-respondents are treated as zero scores, with pediatric psychiatric risk captured solely through `ADHDADY1`.
3. **Cohort Size Reconciliation ($5,643 \to 5,630$):** Exactly $5,643$ rows in the raw file have positive `LSAQWT`. Of these, $10$ individuals died or attrited in Year 2 (`YEARIND == 2`) and $3$ were Year 2 entrants with no baseline Year 1 data (`YEARIND == 3`). Among the two-year eligible prospective panel (`YEARIND == 1`, $N=8,708$), exactly **$5,630$** individuals have valid positive `LSAQWT` and observed Year 2 expenditures.
4. **Variance Estimation Limitations (`VARSTR` & `VARPSU`):** Survey weights (`LSAQWT`, `LONGWT`) ensure that point estimates represent design-adjusted population expectations. However, standard variance formulas, naive standard errors, and unweighted bootstrap intervals do not account for multi-stage clustering across Primary Sampling Units (`VARPSU`) and strata (`VARSTR`), and must not be interpreted as complex survey-design inferences.

---

## 2. AHRQ Documentation & Variable Specifications

Forensic analysis of the official Stata programming statements (`h257stu.txt`) and codebook identifies the following structural survey variables:

### 2.1. Year Indicator (`YEARIND`)
- **AHRQ Definition:** Identifies whether an individual was eligible and in-scope for data collection across the two panel years.
- **Coding Semantics:**
  - `1 = In-Scope Both Years (Two-Year Person)`: $N = 8,709$
  - `2 = In-Scope in Year 1 Only (Died, institutionalized, or attrited during 2024)`: $N = 106$
  - `3 = In-Scope in Year 2 Only (Newborn or out-of-scope entrant during 2024; no baseline Y1 data)`: $N = 57$
  - Total File Records: $8,709 + 106 + 57 = 8,872$
- **Note on Retention:** Among individuals present at baseline in 2023 ($8,709 + 106 = 8,815$), two-year retention in-scope is $8,709 / 8,815 = 98.80\%$. Describing $8,708 / 8,872 = 98.15\%$ as "follow-up completion" is mathematically inaccurate because the denominator includes 57 Year 2 entrants who were never part of the baseline cohort.

### 2.2. All Five Rounds Indicator (`ALL5RDS`)
- **AHRQ Definition:** Identifies respondents who remained in-scope and had data collected across all 5 distinct longitudinal interview rounds.
- **Distribution:**
  - `1 = Data Collected All 5 Rounds`: $N = 8,389$ ($95.17\%$ of baseline respondents)
  - `0 = Not in All 5 Rounds`: $N = 483$

### 2.3. SAQ Timing & Round 2 Depressive Symptoms (`ADDPRS2`)
- **Timing:** Administered in Round 2 (the final interview of Year 1 / 2023). It assesses depressive symptoms over the preceding 2 weeks using the PHQ-2 screener (codes 0=None, 1=Few days, 2=Half days, 3=Nearly every day; -1=Inapplicable, -15=Cannot be computed).
- **Target Population:** Administered strictly to non-institutionalized adults aged $\ge 18$. Children under 18 are coded as `-1 Inapplicable` and binarized as 0, while their psychiatric comorbidity is captured via pediatric ADHD (`ADHDADY1`).

### 2.4. Longitudinal Weights: `LSAQWT` vs. `LONGWT`
- **`LSAQWT` (Longitudinal SAQ Weight - Panel 28):**
  - Designed specifically for longitudinal analyses where the primary analytic sample incorporates SAQ variables.
  - Positive for $N = 5,643$ in raw file; positive for **$N = 5,630$** among two-year eligible panel persons. Zero for $N = 3,078$ two-year respondents (children and adult non-respondents).
- **`LONGWT` (Longitudinal Analysis Weight - Panel 28):**
  - Calibrated for general population totals across all ages (positive for all 8,872 records).
  - Used for the full-population screening sensitivity analysis.

---

## 3. Cohort Flow Reconciliation

The exact row-count reconciliation is documented below:

```
[ Total Raw Records in MEPS HC-257 ] = 8,872
        │
        ├── Less YEARIND == 2 (Died / Out-of-Scope in Year 2): -106
        ├── Less YEARIND == 3 (Newborn / Entrant in Year 2):   -57
        ▼
[ In-Scope Two-Year Population (YEARIND == 1) ] = 8,709
        │
        ├── Less Inapplicable Baseline Age (AGEY1X == -1): -1
        ▼
[ Eligible Two-Year Prospective Panel Cohort ] = 8,708 (98.79% of baseline respondents)
        │
        ├── Primary AHRQ-Consistent Track: Adult SAQ Respondents (LSAQWT > 0): N = 5,630
        │     └── (File LSAQWT > 0 count of 5,643 less 10 YEARIND==2 and 3 YEARIND==3)
        │
        └── Secondary Sensitivity Track: Full-Population Screening Cohort (LONGWT): N = 8,708
              ├── Adults with LSAQWT > 0: N = 5,630
              ├── Adult SAQ Non-Respondents / Inapplicable: N = 704
              └── Pediatric Respondents (Age < 18 at baseline): N = 2,374
```

---

## 4. Weight Selection, Estimand Alignment & Preprocessing Operations

### 4.1. SAQ Subcohorts & Preprocessing Mechanics
- **Primary Estimand (Track 1): Positive-LSAQWT Adult SAQ Subcohort ($N=5,630$, `LSAQWT`)**
  - Follows official AHRQ guidance requiring `LSAQWT` when SAQ items (`ADDPRS2`) are present in longitudinal models.
  - **Formal Estimand Definition:** The prospective predictive performance of the frozen pipeline in the longitudinal adult SAQ population under the operational model's declared missingness mapping (mapping unobserved/inapplicable Round 2 `ADDPRS2` codes `-1` and `-15` to $0$, i.e., asymptomatic), weighted by `LSAQWT`. It is not claimed to be a fully observed baseline depression cohort.
  - **Important Clarification:** Positive `LSAQWT` alone does **NOT** imply an observed Round 2 `ADDPRS2` response. Among the 5,630 respondents with `LSAQWT > 0`:
    * `SAQRDS24 == 1` (SAQ administered in both Round 2 and Round 4): **$4,337$ respondents**.
    * `SAQRDS24 == 0` (SAQ administered in Round 4 only; Round 2 unobserved): **$1,293$ respondents**.
  - **Round 2 Baseline Depression Screener (`ADDPRS2`):**
    * `ADDPRS2 = -1` (Inapplicable at Round 2): **$1,294$ cases** ($1,293$ where `SAQRDS24 = 0` + $1$ respondent ineligible at Round 2).
    * `ADDPRS2 = -15` (Cannot be computed / item non-response): **$128$ cases**.
    * Valid, non-negative responses (`ADDPRS2 >= 0`): **$4,208$ respondents**.
  - **Frozen Preprocessing Operation:** The frozen Phase 1 pipeline binarizes `ADDPRS2` via `apply(lambda x: 1 if x in [1, 2, 3] else 0)`. Thus, values 1, 2, and 3 map to 1 (symptomatic), while 0 and all unobserved negative codes (`-1` inapplicable and `-15` missing) map to 0 (asymptomatic). The primary analysis evaluates this operational frozen model rule in the weighted target population.
- **Sensitivity Analysis (Track 2): Valid Baseline SAQ Complete-Case Sensitivity ($N=4,208$, `LSAQWT`)**
  - Audits the estimand restricted strictly to individuals with an observed, non-negative baseline depression score (`ADDPRS2 >= 0`), evaluating model performance in the absence of survey-wave non-response imputation.
- **Secondary Sensitivity Analysis (Track 3): Full-Population Screening Cohort ($N=8,708$, `LONGWT`)**
  - Pragmatic deployment simulation evaluating the model as a universal population screening tool with zero-fill conventions for pediatric ($<18$) and adult non-respondents.

---

## 5. Authoritative Empirical Results: Primary SAQ vs. Full-Population Sensitivity

All metrics below are drawn directly and programmatically from [`metrics_hc257.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/validation/hc257/metrics_hc257.json):

| Estimand & Cohort | Sample Size ($N$) | Survey Weight | Eval Prev (Unw / Wtd) | Observed Y2 Mean | Predicted Mean | MAE | $R^2$ | P90 Classifier ROC-AUC | Classifier Model Brier | Classifier Baseline Brier | Classifier Brier Skill Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Primary: Positive-LSAQWT Adult SAQ (Wtd)** | **5,630** | `LSAQWT` | **0.1422** (Wtd) | **$9,866.56** | **$8,679.50** | **$9,679.67** | **0.0728** | **0.7466** | **0.10874** | **0.12373** | **+0.1212** |
| Positive-LSAQWT Adult SAQ (Unweighted) | 5,630 | None | 0.1677 (Unw) | $11,659.94 | $10,293.86 | $11,095.08 | 0.0644 | 0.7444 | 0.12416 | 0.14227 | +0.1273 |
| **Sensitivity: Valid Baseline SAQ Complete-Case (Wtd)** | **4,208** | `LSAQWT` | **0.1546** (Wtd) | **$10,621.24** | **$9,398.51** | **$10,090.88** | **0.0717** | **0.7420** | **0.11680** | **0.13366** | **+0.1261** |
| Valid Baseline SAQ Complete-Case (Unweighted) | 4,208 | None | 0.1808 (Unw) | $12,424.13 | $10,967.08 | $11,511.04 | 0.0606 | 0.7359 | 0.13223 | 0.15240 | +0.1323 |
| **Sensitivity: Full Pop Screening (Wtd)** | **8,708** | `LONGWT` | **0.1125** (Wtd) | **$8,434.02** | **$7,319.12** | **$8,573.07** | **0.0559** | **0.7807** | **0.08737** | **0.09999** | **+0.1263** |
| Sensitivity: Full Pop Screening (Unweighted) | 8,708 | None | 0.1158 (Unw) | $9,687.75 | $8,585.17 | $9,631.83 | 0.0652 | 0.7732 | 0.09120 | 0.10260 | +0.1112 |

### Methodological Insights & Cross-Cohort Comparison
1. **SAQ Sub-Cohort Spending:** In the adult SAQ sub-cohort ($N=5,630$), `LSAQWT`-weighted observed mean expenditure is $\$9,866.56$, compared to $\$8,434.02$ in the `LONGWT`-weighted full population. This difference reflects the exclusion of low-expenditure pediatric respondents ($N=2,374$, mean spending $\$3,288$).
2. **Predictive Performance:** Tweedie regression achieves an $R^2$ of **0.0728** in the primary adult SAQ cohort (`LSAQWT`), compared to **0.0559** in the full population (`LONGWT`). The classifier achieves an ROC-AUC of **0.7466** and a Brier Skill Score of **+0.1212** in the primary adult cohort.
3. **Complex Survey Variance Limitations:** Standard errors and confidence intervals cannot be inferred from standard regression or unweighted bootstrap calculations due to unmodeled clustering in `VARPSU` and `VARSTR`.
4. **Scope & Outstanding Governance Validations:** Clinical semantic validity remains strictly pending independent adjudicated reference annotations; design-based complex-survey variance and actuarial pricing/solvency validation remain explicitly outstanding.

---

## 6. Audit Verdict

- **Cohort Flow Reconciliation:** **100% RECONCILED (8,872 $\to$ 8,709 $\to$ 8,708; Adult SAQ 5,643 file $\to$ 5,630 two-year).**
- **Weighting Methodology:** **AUDITED, PRIMARY/SENSITIVITY ESTIMANDS FORMALLY SEPARATED AND AHRQ-COMPLIANT.**
- **Status:** **COMPLETED.**
