# PHASE 0 — Initial Research, Implementation & Paper Audit

**Project:** HealthScore — CRC Paper Evidence Enhancement, Threshold Analysis & Controlled Revision
**Repository Branch:** `feature/ml-pipeline-rebuild` (`master` untouched at `944fb0d73dc964eeec702e77b13668baeead0d85`)
**Audited Manuscript Foundations:**
1. Original IEEE-format manuscript: [`old paper.pdf`](../../old%20paper.pdf) (*"HealthScore: Unified Health Scoring, Prescription and Blockchain Based Healthcare Solution"*, authored by Arpit Doshi, Dhruv Gandhi, Harshkumar Padhiyar, Hetam Patel, Stevina Correia, Monali Sankhe, and Monika Mangla, Department of Information Technology, Dwarkadas J. Sanghvi College of Engineering, Mumbai, India).
2. Existing repository research manuscript: [`research_completion/paper/REVISED_PAPER.md`](../paper/REVISED_PAPER.md) and [`research_completion/latex_submission/main.tex`](../latex_submission/main.tex).

---

## 1. Existing Paper Structure and Central Research Contribution

### 1.1 Structure of Original Manuscript (`old paper.pdf`) vs. Repository Revised Manuscript (`main.tex`)
- **`old paper.pdf` (7 pages, IEEE 2-column format):**
  - **Title:** *HealthScore: Unified Health Scoring, Prescription and Blockchain Based Healthcare Solution*
  - **Authors:** Arpit Doshi\*, Dhruv Gandhi\*, Harshkumar Padhiyar\*, Hetam Patel\*, Stevina Correia†, Monali Sankhe†, and Monika Mangla† (\*Department of Information Technology; †Department of Information Technology (Professor), Dwarkadas J. Sanghvi College of Engineering, Mumbai, India).
  - **Sections:** Abstract & Index Terms; I. Introduction; II. Related Works; III. Methodology (A. Process Flow and Blockchain Infrastructure, B. Dataset Description and Variable Inclusion, C. Engineering Frailty and Multimorbidity, D. Machine Learning Architecture); IV. Results and Findings (A. Multimorbidity and Feature Correlation Analysis, B. Actuarial Machine Learning Results, C. Explainable AI (SHAP) and Platform Outputs, D. Blockchain Performance and Scalability (Hyperledger Caliper)); V. Conclusion and Future Scope; References ([1]–[12]).
- **`research_completion/latex_submission/main.tex` (26 pages, Springer LNCS format):**
  - Retains the core 3-pillar HealthScore architecture (Hyperledger Fabric 5-organization permissioned consortium + MEPS ACG-inspired chronic-disease risk scoring + parametric Gamma Value-at-Risk premium simulation), while replacing unverified/inflated claims from `old paper.pdf` with reproducible multi-cohort MEPS evaluations (`HC-251`, `HC-256`, `HC-257`), 17-scenario feature ablations, 9-model classifier benchmarks, 60-scenario VaR sensitivity grids, and multi-run Caliper benchmarks.
  - However, `main.tex` had anonymized the authors (`Anonymous Author(s)`) and evaluated the primary classification model only at a single probability threshold ($\hat{p} \ge 0.10$, plus a brief prose note on top-10% ranked decile selection), leaving the low precision ($23.18\%$) at $\hat{p} \ge 0.10$ vulnerable to reviewer criticism regarding false positives, operating threshold choice, and potential overfitting.

### 1.2 Central Research Contribution
HealthScore investigates an integrated healthcare risk-scoring and multi-organization workflow architecture that:
1. Anchors auditable clinical milestones (`createPatientRecord`, `updateHealthScore`, `createPrescription`, `dispensePrescription`, `requestScan`, `completeScan`) onto a 5-organization Hyperledger Fabric permissioned ledger with Membership Service Provider (MSP) role-based access control, while keeping heavy ML inference and raw clinical records off-chain.
2. Evaluates a parsimonious, intake-observable 11-feature chronic-condition risk model (6 ACG-inspired condition clusters, comorbidity count, quadratic multimorbidity penalty, age-by-comorbidity interaction, age, and sex) across three official AHRQ MEPS releases for both top-decile high-expenditure classification and direct dollar expenditure regression.
3. Formulates a parameterized Gamma Value-at-Risk loss simulation ($X_\alpha = B + (1+\alpha)G$) verified against closed-form analytical quantiles.

---

## 2. Audit of Existing Experimental Methodology & Data Splitting Pipeline

Inspection of [`ml_model/data_pipeline.py`](../../ml_model/data_pipeline.py), [`ml_model/train_model.py`](../../ml_model/train_model.py), [`research_completion/experiments/run_comprehensive_benchmarks.py`](../experiments/run_comprehensive_benchmarks.py), [`ml_model/validation/hc256/validate_hc256.py`](../../ml_model/validation/hc256/validate_hc256.py), and [`ml_model/validation/hc257/validate_hc257.py`](../../ml_model/validation/hc257/validate_hc257.py) establishes the following verified implementation facts:

1. **Development Dataset (`MEPS HC-251`, 2023 Full-Year Consolidated File):**
   - Raw records: $18,919$. Removing $148$ ineligible rows with `AGE23X < 0` yields **$N = 18,771$ eligible individuals** ($100\%$ retained, including $2,598$ zero-expenditure records [$13.84\%$]).
2. **Train/Test Split Implementation (`split_data()`):**
   - Uses `sklearn.model_selection.train_test_split(..., test_size=0.20, random_state=42)`, producing:
     - **Training Split (`X_train`):** $N = 15,016$ ($80.0\%$)
     - **Held-Out Test Split (`X_test`):** $N = 3,755$ ($20.0\%$)
   - **Absence of Dedicated Validation Split:** The existing pipeline does **not** create a separate standalone validation split; `X_test` ($N=3,755$) was used across iterative benchmark evaluations. Therefore, for threshold selection in Phase 1, we must **not** select thresholds on `X_test`; instead, we implement **5-fold Out-of-Fold (OOF) cross-validation strictly within the training split ($N=15,016$)** to compare thresholds and select operating points before evaluating on the untouched test split ($N=3,755$).
3. **Forensic Audit of Participant (`DUPERSID`) and Household (`DUID`) Overlap:**
   - **Within HC-251 (`N = 18,771`):** All $18,771$ rows have unique person identifiers (`DUPERSID`), so person-level overlap between `X_train` and `X_test` is **strictly zero ($0$)**. However, because MEPS samples households ($8,851$ unique Dwelling Units `DUID`) and `train_test_split` performs row-level random splitting without grouping by `DUID`, **$2,198$ households are shared between `X_train` and `X_test`**, meaning **$2,711$ of the $3,755$ test respondents ($72.20\%$)** belong to a household that also has at least one member in `X_train`. We therefore evaluate both standard Stratified 5-Fold OOF and **Household-Grouped (`GroupKFold` by `DUID`) 5-Fold OOF** in Phase 1.
   - **Across MEPS Releases (`HC-251` vs. `HC-256` vs. `HC-257`):** MEPS uses an overlapping two-year rotating panel design:
     - `HC-251` (2023, $N=18,771$) comprises **Panel 27** ($N=8,365$, Year 2) and **Panel 28** ($N=10,406$, Year 1).
     - `HC-256` (2024, $N=18,979$) comprises **Panel 28** ($N=8,942$, Year 2) and **Panel 29** ($N=10,037$, Year 1).
     - `HC-257` (2023–2024 Longitudinal, $N=8,708$) comprises **Panel 28** ($N=8,708$).
     - **Critical Finding:** While the existing revised paper disclosed the overlap between `HC-251` and `HC-257`, it inaccurately referred to `HC-256` ($N=18,979$) as an "independent 2024 population." In fact, **$8,775$ of the $18,979$ respondents in `HC-256` ($46.24\%$)** are Panel 28 carryovers who also appeared in `HC-251` ($7,030$ in `X_train`, $1,745$ in `X_test`). Only **`HC-256` Panel 29 ($N = 10,037$)** is $100\%$ disjoint from `HC-251` ($0$ shared `DUPERSID`s and $0$ shared `DUID`s). We explicitly separate `HC-256` Full ($N=18,979$), `HC-256` Panel 28 ($N=8,942$), and **`HC-256` Panel 29 Unseen ($N=10,037$)** in our Phase 1 experiments and revised paper!

---

## 3. Verification of Existing Model Selection & Baseline Metrics

We verified the frozen serving classifier (`ml_model/artifacts/risk_model_classifier_observable_weighted_p90.pkl`, SHA-256: `3632f8201136a2740c3d5a564bbdbb29bc8511db51709fb42c1f8e271bf28c2a`) against `X_test` ($N=3,755$):
- **Architecture:** `LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, random_state=42)` fit on the 11 observable features (`OBSERVABLE_FEATURE_COLS`) with normalized survey person weights (`w_train_norm`).
- **Target Definition (Target 2):** Survey-weighted 90th percentile of training expenditure ($\text{TOTEXP23} \ge \$17,827.41$, computed strictly on `y_train_raw` with `w_train`).
- **Prevalence:** Training weighted prevalence = $9.99\%$ ($0.099888$), Training unweighted prevalence = $11.56\%$ ($1,736 / 15,016$); Test weighted prevalence = $10.51\%$ ($0.105134$), Test unweighted prevalence = $11.98\%$ ($450 / 3,755$).
- **Verified Baseline Metrics on Held-Out Test Set ($N=3,755$) at $\tau = 0.10$:**
  - **ROC-AUC:** `0.7654` (exact: `0.765400`, 95% CI: `[0.7444, 0.7881]`) — **Matches reported value exactly.**
  - **PR-AUC:** `0.3184` (exact: `0.318389`, 95% CI: `[0.2876, 0.3556]`) — **Matches reported value exactly.**
  - **Precision (Unweighted at $\tau = 0.10$):** `23.18%` (`0.231845`, $348 / 1,501$) — **Matches reported value exactly.**
  - **Recall (Unweighted at $\tau = 0.10$):** `77.33%` (`0.773333`, $348 / 450$) — **Matches reported value exactly.**
  - **F1-Score (Unweighted at $\tau = 0.10$):** `0.3567` (`0.356740`) — **Matches reported value exactly.**
  - **Weighted Brier Skill Score (Wtd BSS):** `+0.1025` (Weighted Brier `0.0845` vs. baseline `0.0941`; Unweighted Brier `0.0936` vs. baseline `0.1059`, Unweighted BSS `+0.1123`) — **Matches reported value exactly.**

---

## 4. Current Limitations and Unsupported Claims Identified

1. **Legacy Claims in `old paper.pdf` (Removed or Qualified in Revised Work):**
   - Claimed $R^2 = 0.256$ for XGBoost regression and $83.7\%$ accuracy / $0.778$ ROC-AUC on a 15% high-risk cutoff using 14 features that included unobservable Self-Administered Questionnaire (SAQ) variables (`ADGENH42`, `ANYLMI23`, `DFCOG42`, `K6SUM42`), violating deployment input availability parity and masking log-retransformation dollar bias (where $\exp(\hat{y})-1$ underpredicts mean dollars by $72.8\%$, yielding dollar $R^2 = -0.0134$).
   - Claimed custom 6-condition sums were official "Johns Hopkins Adjusted Clinical Groups (ACG)" and "Expanded Diagnosis Clusters (EDC)".
   - Claimed the Monte Carlo Gamma simulation established "actuarial validity" and "financial solvency".
   - Claimed 0 failed transactions in Caliper proved "absolute crash fault tolerance" without fault-injection testing.
2. **Remaining Weaknesses in Existing `REVISED_PAPER.md` / `main.tex` to Correct in This Revision:**
   - **Author Attribution:** `main.tex` replaced the 7 authors from `old paper.pdf` with `Anonymous Author(s)`. Must restore all 7 authors and their Dwarkadas J. Sanghvi College of Engineering affiliations in exact format.
   - **Single-Threshold Evaluation ($\tau = 0.10$):** Only $\tau = 0.10$ was systematically tabulated, yielding $23.18\%$ precision ($1,153$ false positives out of $1,501$ flagged patients in `X_test`) without a systematic probability-threshold sensitivity analysis across $\tau \in [0.05, 0.90]$.
   - **Lack of Explicit Overfitting vs. Class-Imbalance/Threshold Decomposition:** Did not present side-by-side Training vs. 5-Fold OOF Validation vs. Household-Grouped OOF vs. Test vs. External Cohort classification metrics (ROC-AUC, PR-AUC, Log Loss, Brier) to prove empirically that the $23.18\%$ precision at $\tau = 0.10$ is driven by operating-threshold selection and base prevalence ($11.98\%$), **not** model overfitting.
   - **Inaccurate Independence Claim for `HC-256`:** Described `HC-256` ($N=18,979$) as an "independent 2024 population" without disclosing that $46.24\%$ ($8,775 / 18,979$) are Panel 28 respondents shared with `HC-251`, and without isolating the truly disjoint **Panel 29 ($N=10,037$)** cohort.
   - **Unclustered Household Split Disclosure:** Did not disclose that `train_test_split` in `HC-251` splits at the individual (`DUPERSID`) level rather than the household (`DUID`) level ($72.20\%$ of test rows share a `DUID` with training rows).

---

## 5. Reviewer Comments Mapped to Paper Sections & Required Evidence

| Reviewer Comment / Criticism Area | Relevant Paper Section(s) | Validity Assessment | Required Experimental Evidence / Action |
| :--- | :--- | :--- | :--- |
| **RC-1: Low Precision ($23.18\%$) at $\tau=0.10$ & High False Positives ($1,153$ FP)** — Is there a better threshold trade-off across $0.10, 0.20, \dots, 0.90$? | Abstract, Methodology (Threshold Selection), Results & Discussion (Classification Performance) | **Valid & Critical.** Flagging $39.97\%$ of the cohort at $\tau=0.10$ yields $\sim 3.3$ false positives per true positive. | Execute full threshold sensitivity analysis ($\tau \in \{0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90\}$) on frozen model; report Precision, Recall, F1, Specificity, NPV, Balanced Accuracy, FPR, FNR, Confusion Matrices, and Flagged counts (unweighted & survey-weighted). |
| **RC-2: Potential Overfitting vs. Imbalance / Calibration / Feature Ceiling** — Why is precision low? Is the classifier overfitting? | Methodology, Results & Discussion (Diagnostic Root-Cause Analysis) | **Valid question; overfitting hypothesis is refuted by evidence.** | Compare Train vs. 5-Fold OOF vs. Household-Grouped OOF vs. Test vs. External 2024 Panel 29 (ROC-AUC $0.7815 \to 0.7795 \to 0.7785 \to 0.7654 \to 0.7824$). Prove mathematically and empirically that low precision at $\tau=0.10$ stems from setting $\tau$ at the $10\%$ prior prevalence on a skewed outcome ($11.98\%$ base rate) and discrete 11-feature granularity ($10.22\%$ of high-cost cases have 0 chronic flags; $71.79\%$ of $3+$ comorbidity patients do not incur top-decile spend). |
| **RC-3: Threshold Selection Without Test-Set Leakage** — How is a recommended operating threshold chosen if no standalone validation split exists? | Methodology (Splitting & Validation), Results & Discussion | **Valid & Critical.** Selecting $\tau$ on `X_test` would constitute test leakage. | Use 5-Fold Out-of-Fold (OOF) cross-validation on `X_train` ($N=15,016$) to evaluate candidate thresholds and lock operating profiles ($\tau=0.10$ max Balanced Accuracy / screening; $\tau=0.20$ max validation F1 / care-management triage; $\tau=0.30$ high-specificity targeted intervention) before evaluating on `X_test` ($N=3,755$) and external cohorts. |
| **RC-4: Data Split Independence & Multi-Release Participant Overlap** — Are training, test, and external MEPS sets truly independent? | Methodology (Dataset & Splitting), Results (External Validation), Limitations | **Valid & Critical.** Unclustered household split in `HC-251` and Panel 28 overlap in `HC-256` ($46.24\%$) must be disclosed. | Audit `DUPERSID` and `DUID` overlap across `HC-251`, `HC-256`, and `HC-257`. Evaluate household-grouped `GroupKFold(groups=DUID)` OOF and isolate `HC-256` **Panel 29 ($N=10,037$, 0% overlap)** to prove genuine out-of-sample generalization. |
| **RC-5: Reconciliation of Classification ($\text{ROC-AUC}=0.7654$) vs. Dollar Regression ($R^2=0.0798$) & Lagged Baseline ($R^2=0.1204$)** | Abstract, Methodology, Results & Discussion, Limitations | **Valid & Essential.** Readers must not confuse ordinal tail discrimination with individual dollar cost accuracy. | Clearly contrast rank-order discrimination, log-scale retransformation bias (XGBoost dollar $R^2=-0.0134$), Tweedie direct dollar modeling ($R^2=0.0798$), and lagged spending persistence ($R^2=0.1204$). |
| **RC-6: Removal/Qualification of Overstated Actuarial, Clinical, Privacy & Blockchain Claims** | Abstract, Introduction, Related Work, Methodology, Results, Limitations, Conclusion | **Valid & Essential.** Claims in `old paper.pdf` overstate clinical/actuarial/fault-tolerance readiness. | Qualify ACG-inspired clusters as heuristic survey proxies; disclaim commercial underwriting/solvency for VaR simulation; separate Caliper Gateway throughput ($350\text{--}516$ write TPS) from single-worker end-to-end inference ($\approx 20\text{--}25$ req/s); disclose single-host testbed and absence of fault injection. |
| **RC-7: Author Formatting, Citations & >500 DPI Figure Standards** | Title/Author Block, Figures, Bibliography | **Valid & Required.** | Restore all 7 authors and affiliations from `old paper.pdf`; verify every citation; generate all new and existing figures at $\ge 600$ DPI. |
