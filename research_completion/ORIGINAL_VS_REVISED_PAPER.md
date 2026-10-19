# HealthScore Manuscript Comparison: Original Working Claims vs. Revised Paper

**Document ID:** `HS-REP-08-ORIGINAL-VS-REVISED`
**Date:** October 2026
**Auditor / Methodologist:** Senior Healthcare Systems Reviewer
**Original Reference:** Historical Project Reports & Working Claims
**Revised Document:** [`paper/REVISED_PAPER.md`](paper/REVISED_PAPER.md)
**Supporting Evidence Artifact:** [`experiments/experiment_registry.json`](experiments/experiment_registry.json)

---

## 1. Executive Summary & Original Manuscript Discovery Blocker

> [!IMPORTANT]
> **Discovery Finding & Comparison Scope:**
> An exhaustive audit across all Git commits (`git log --all`), branches, working trees, and parent directories confirmed that **no pre-existing standalone research manuscript file** (such as a `.tex`, `.docx`, or pre-existing `paper.md`) existed in the HealthScore repository prior to this research completion effort. The original repository at commit `944fb0d` referenced an intended academic paper in its benchmark configuration (`caliper-benchmark/benchmark.yaml`), and intermediate project reports (`MODEL_EXPERIMENT_REPORT.md`, `CLINICAL_SEMANTIC_VALIDATION_REPORT.md`, `EXTERNAL_VALIDATION_REPORT.md`, `ACTUARIAL_SCOPE_GAP_ASSESSMENT.md`, `README.md`) recorded early preliminary working claims.
>
> Therefore:
> - We do **not** claim to have performed a direct manuscript-to-manuscript text diff against a pre-existing authentic paper.
> - The manuscript in [`paper/REVISED_PAPER.md`](paper/REVISED_PAPER.md) represents the **initial complete, evidence-backed academic research manuscript draft** authored for the project.
> - This reconciliation document compares the new manuscript draft against **historical project markdown reports, preliminary engineering claims, and pre-audit working draft metrics**.
> - A direct original-manuscript comparison remains blocked by the absence of any prior manuscript file in the repository.

Every material modification is categorized by type (Numerical, Methodological, Conceptual, or Actuarial Scoping) and cross-referenced with empirical test outputs.

---

## 2. Consolidated Summary of Material Changes

| Research Domain | Original Working Draft Claim | Revised Paper (Version 3.1) Finding | Nature of Change | Supporting Artifact / Reason |
| :--- | :--- | :--- | :--- | :--- |
| **Expenditure Regression** | Claimed XGBoost accurately predicts dollar healthcare costs. | Disclosed that log-transformed XGBoost underpredicts dollar mean by $72.8\%$ ($Mean Predicted = \$2,384.13$ vs $\$8,764.62$ observed; $R^2 = -0.0134$). Tweedie GLM identified as true direct dollar regression model ($R^2 = 0.0798$). | **Methodological & Numerical** | [`MODEL_COMPARISON_REPORT.md`](MODEL_COMPARISON_REPORT.md); Retransformation bias in log-OLS/trees. |
| **Prospective Persistence** | Claimed HealthScore outperforms standard risk benchmarks. | Disclosed that a simple lagged Year 1 spending baseline achieves $R^2 = 0.1204$, outperforming static diagnosis-only Tweedie ($R^2 = 0.0652$). | **Methodological** | Stage D evaluation on MEPS HC-257; econometrics persistence principle. |
| **Survey Weighting & Baselines** | Single unweighted prevalence used for all Brier baselines. | Reconciled Target 1 ($P_{90}=\$20,360.50$, Prev $0.1000$) and Target 2 ($P_{90,\text{wtd}}=\$17,827.41$, Weighted Prev $0.0999$, Unw Prev $0.1156$). | **Mathematical / Statistical** | [`PIPELINE_AUDIT_REPORT.md`](PIPELINE_AUDIT_REPORT.md); Reconciled Brier identities. |
| **Classifier Decision Metrics** | Loosely labelled top-decile performance. | Explicitly distinguishes predicted-probability threshold ($\hat{p} \ge 0.10$, Recall $0.7733$, Precision $0.2318$) from a top-10%-ranked cohort cutoff. Disclosed absence of decision-curve analysis (DCA). | **Reporting & Metrics** | [`run_comprehensive_benchmarks.py`](experiments/run_comprehensive_benchmarks.py); Audited metric definitions. |
| **Comorbidity Benchmarks** | Implied clinical index superiority. | Clarified that MEPS public files lack granular ICD-10-CM codes required for Charlson or Elixhauser indices; direct comparison is recorded as a data-driven limitation. | **Clinical Semantics** | AHRQ MEPS de-identification mandates; no claims of clinical index superiority. |
| **Premium Calculation** | Described as an actuarially validated insurance premium engine. | Reclassified as an exploratory parametric Value-at-Risk (VaR) technical demonstration heuristic; commercial pricing explicitly disclaimed. | **Actuarial / Regulatory** | [`PREMIUM_SIMULATION_VALIDATION.md`](PREMIUM_SIMULATION_VALIDATION.md); Absence of claims, MLR loadings. |
| **Clinical Classification** | Custom condition clusters described as "ACG classification system". | Clarified as heuristic survey aggregations inspired by ACG concepts; clinical semantic validity explicitly pending physician review. | **Clinical Semantics** | [`CLINICAL_SEMANTIC_VALIDATION_REPORT.md`](CLINICAL_SEMANTIC_VALIDATION_REPORT.md); Absence of mentions treated as uninformative default, not confirmed health. |
| **Blockchain Scaling & Accounting** | Unlimited throughput scalability claimed without accounting bounds. | Separated allocation shortfall (20 proposals) from transaction failures (0 reported failures among 25,480 submitted vs. 25,500 configured in 8-worker runs; $100\%$ submitted success rate, $99.92\%$ proposal completion). Disclosed single-host virtualized testbed and absence of fault-injection testing. | **Empirical Benchmark** | [`BLOCKCHAIN_BENCHMARK_REPORT.md`](BLOCKCHAIN_BENCHMARK_REPORT.md); Caliper manifests and verifiers. |
| **Subgroup Fairness** | Universal high performance claimed across all cohorts. | Disclosed that classifier discrimination collapses in pediatric ($<18$) and healthy cohorts (ROC $0.40$ – $0.49$); seniors well-calibrated ($1.01\text{x}$). | **Algorithmic Fairness** | [`SECURITY_REPRODUCIBILITY_FAIRNESS_REPORT.md`](SECURITY_REPRODUCIBILITY_FAIRNESS_REPORT.md). |
| **SHAP Explainability** | Reused legacy 14-feature explanations on uncalibrated models. | Recomputed SHAP TreeExplainer attributions on approved 11-feature model; numerical additivity (error $< 2 \times 10^{-5}$) and subsample stability ($\rho = 0.9818$) proven. | **Explainability Audit** | [`SHAP_VALIDATION_REPORT.md`](SHAP_VALIDATION_REPORT.md). |

---

## 3. Section-by-Section Manuscript Comparison

### 3.1. Abstract & Introduction
- **Original Working Claims:** Focused broadly on blockchain in healthcare, claiming "production-grade scalability", elimination of single points of failure, and high accuracy in cost forecasting without qualification.
- **Revised Manuscript (Version 3.1):** Formulates specific empirical research questions: ordinal high-cost discrimination vs. nominal dollar forecasting vs. blockchain consensus throughput. Clearly distinguishes between rank-order risk indexing and direct dollar estimation, disclosing the $6–8\%$ variance ceiling for static diagnosis flags. Discloses participant overlap between HC-251 and HC-257. Discloses that fault-tolerance resilience under actual peer, orderer, storage, or network crashes was not evaluated via fault-injection testing. Replaces "production-grade scalability" with precise measured performance on the evaluated single-host testbed.

### 3.2. Data & Cohorts
- **Original Working Claims:** Described only the 2023 development set (HC-251); external validation mentioned only as planned future work.
- **Revised Manuscript:** Integrates three complete AHRQ datasets: HC-251 (2023, $N=18,771$), HC-256 (2024, $N=18,979$), and HC-257 (Panel 28 Longitudinal, $N=8,708$). Documents data provenance via SHA-256 hashes, zero-expenditure retention ($13.8\% – 14.1\%$), and longitudinal SAQ weighting protocols (`LSAQWT`). Reconciles verified HC-251 SHA-256 hash (`1de0133d0d5a4eeef1f08b60931e0d2669de1507007fd8fabdb84e1c0d15ffb5`).

### 3.3. Clinical Feature Engineering
- **Original Working Claims:** Described custom 6-cluster sums as "ACG grouper categories". Unobservable survey variables (`ADDPRS42`, `K6SUM42`) were treated as interchangeable between training and runtime.
- **Revised Manuscript:** Formulates **Input Availability Parity**. Restricts primary deployment models to 11 directly observable intake variables. Reclassifies clusters as heuristic survey-variable proxies inspired by ACG concepts. Documents the parsimony omission of Angina (`ANGIDX`) and proves runtime age top-coding parity at 85. Notes that absence of granular ICD-10-CM codes in public MEPS files precludes computing Charlson or Elixhauser comorbidity indices.

### 3.4. Expenditure Regression
- **Original Working Claims:** Highlighted XGBoost MAE ($\approx \$7,516$) as proof of cost prediction accuracy, obscuring that predicted mean was $\$2,384$ against an observed $\$8,765$ (a negative dollar $R^2$).
- **Revised Manuscript:** Discloses the mathematical divergence between log-scale median optimization and dollar-scale mean estimation. Promotes the 11-feature Tweedie GLM ($p=1.5, \alpha=1.0$) as the sole valid dollar regressor ($R^2 = 0.0798$, predicted mean $\$8,177.92$). Plainly reports that the lagged Year 1 spending baseline achieves $R^2 = 0.1204$, outperforming the diagnosis-only model.

### 3.5. High-Cost Classification & Metrics Reporting
- **Original Working Claims:** Mixed unweighted and weighted target thresholds inconsistently; used unweighted prevalence for weighted Brier baselines; loosely labelled top-decile metrics.
- **Revised Manuscript:** Strictly reconciles target definitions. Target 1 ($P_{90} = \$20,360.50$, prevalence $0.1000$) and Target 2 ($P_{90,\text{wtd}} = \$17,827.41$, weighted prevalence $0.0999$, unweighted prevalence $0.1156$). Reports target-matched Brier Skill Scores ($+0.1025$ in 2023, $+0.1266$ in 2024 cross-section, $+0.1263$ in prospective panel) with unpenalized logistic calibration diagnostics ($\beta \approx 0.90 – 1.06$) and formal calibration-in-the-large. Explicitly explains that practical metrics (Precision $0.2318$, Recall $0.7733$, F1 $0.3566$) are evaluated at a **predicted-probability decision threshold of $\hat{p} \ge 0.10$**, distinguishing this from selecting a top-10%-ranked cohort cutoff. Discloses that decision-curve analysis (DCA) was not performed.

### 3.6. Premium Simulation & Actuarial Scope
- **Original Working Claims:** Claimed to calculate accurate insurance premiums and provide underwriting risk ratings.
- **Revised Manuscript:** Explicitly disclaims actuarial pricing, underwriting adequacy, and reserve solvency. Reclassifies the Monte Carlo simulation as an exploratory technical demonstration heuristic ($X_\alpha = B + (1+\alpha)G$). Implements strict input validation, nonfinite error handling, and loss percentile naming, with empirical simulations calibrating within $0.7\%$ of analytical Gamma quantiles.

### 3.7. Blockchain Performance & Accounting Hardening
- **Original Working Claims:** Reported high TPS without workload specifications, test duration, or failure analysis. Conflated allocation shortfalls with transaction failures.
- **Revised Manuscript:** Details exact Caliper benchmark parameters across $24,500$ transactions in 8 rounds (historical baseline) and subsequent live reruns. Reports linear regime up to $200$ TPS ($0.03$–$0.06$s latency), historical saturation knee at $350.1$ TPS, 5-worker live rerun at $515.8$ TPS, and corrected 8-worker repetitions sustaining $485.27 \pm 14.60$ TPS under $1,000$ TPS stress load. Separates allocation shortfall (20 proposals due to worker integer division) from transaction failures (zero reported failures among submitted transactions; $100\%$ submitted success rate, $99.92\%$ proposal completion). Discloses single-identity client submission under `HospitalOrgAdmin` on a single-host virtualized bridge network without multi-host physical latency. Clarifies that ledger block storage is immutable while CouchDB provides mutable latest world-state caching.

### 3.8. Algorithmic Fairness & Limitations
- **Original Working Claims:** Absent from the original draft.
- **Revised Manuscript:** Evaluates distinct subgroups across Age, Sex, and Comorbidity tiers. Discloses poor pediatric/healthy discrimination ($0.40$ – $0.49$) and excellent senior calibration ($1.01\text{x}$). Discusses ACA regulatory constraints against pre-existing condition rating and summarizes all 11 core limitations in Section 9.

---

## 4. Verification Check & Final Integrity Verdict

All numerical values, tables, and figures in the Revised Paper have been cross-checked against:
1. `ml_model/tests/` (97 passing Python tests).
2. `backend/tests/` (50 passing Node.js security tests).
3. `research_completion/experiments/experiment_registry.json`.
4. `ml_model/validation/hc256/metrics_hc256.json`.
5. `ml_model/validation/hc257/metrics_hc257.json`.
6. `caliper-benchmark/report.html` (historical baseline).

**Integrity Verdict:** **VERIFIED — Zero unverified claims, zero duplicate candidate models, canonical provenance reconciled.**
