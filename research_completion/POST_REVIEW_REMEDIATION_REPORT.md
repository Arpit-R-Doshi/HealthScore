# HealthScore — Post-Review Remediation & Research-Production Parity Report

**Date:** October 17, 2026  
**Branch:** `feature/ml-pipeline-rebuild`  
**Repository:** `HealthScore`  
**Status:** Verification Complete — Production Parity & Security Remediated  

---

## 1. Executive Summary

This report documents the remediation of critical architectural, security, and research-production parity defects in the **HealthScore** platform. Operating strictly on the `feature/ml-pipeline-rebuild` branch without altering frozen model weights or destructive Git history, the system has been reconciled so that:

1. **Backend API security** enforces real server-side authentication (PBKDF2-SHA512 password hashing, signed HMAC-SHA256 JWT tokens), default-deny role-based authorization (RBAC), strict cross-patient data isolation, and comprehensive upload/payload limits.
2. **Production model routing** matches the research-approved 11-feature observable model artifacts verified via an explicit machine-readable manifest (`model_manifest.json`) with cryptographic SHA-256 integrity checks, eliminating synthetic SAQ imputation at inference time.
3. **Premium simulation semantics** enforce fail-closed input validation (rejecting nonfinite, negative, NaN, or unbounded inputs), deterministic seed support, and explicit qualification of P5/P95 outputs as exploratory simulated loss percentiles rather than actuarial confidence intervals.
4. **Experiment runner & benchmark methodology** separates candidate-model cross-validation from frozen-artifact evaluation, eliminates duplicate model definitions, applies consistent survey weighting and Tweedie hyperparameters ($\alpha=1.0$), implements exact root-finding Calibration-In-The-Large (CITL), and dynamically captures system provenance.
5. **Data provenance & documentation** reconcile historical checksum discrepancies to the authentic AHRQ MEPS HC-251 dataset hash (`1de0133d0d5a4eeef1f08b60931e0d2669de1507007fd8fabdb84e1c0d15ffb5`), disclose participant overlap between HC-251 and HC-257 (Panel 28), remove unsupported causal claims, and distinguish Hyperledger Fabric's immutable append-only ledger from CouchDB's mutable world state.

All 85 Python ML unit, regression, and runtime parity tests and all 24 Node.js API security tests pass with zero failures.

---

## 2. Confirmed Problems and Implemented Remediations

| # | Domain | Confirmed Problem | Implemented Fix | Phase & Commit |
|---|---|---|---|---|
| 1 | **Security** | Default `ADMIN_KEY \|\| 'admin'` fallback permitted silent startup with a known default credential. | Removed default string fallback; requires explicit non-empty environment variable, failing closed (HTTP 403) if undefined or default. | Phase 1 (`f180f8c`) |
| 2 | **Security** | Hardcoded demo accounts automatically seeded on production server initialization with plaintext passwords. | Removed automatic demo initialization from production boot; added PBKDF2-SHA512 (100,000 iterations, 32-byte salt) hashing; passwords never stored or returned in responses. | Phase 1 (`f180f8c`) |
| 3 | **Security** | Role and identity inferred from unverified client payload fields; no cross-patient authorization checks. | Implemented HMAC-SHA256 Bearer tokens with 24h expiration, `authenticateToken` middleware, default-deny RBAC (`requireRole`), and cross-patient isolation. | Phase 1 (`f180f8c`) |
| 4 | **Security** | Unbounded request bodies, unrestricted file upload types, and missing rate limits on auth routes. | Added 1MB JSON body limit, sliding-window rate limiting (100 req/15min on auth), and Multer 5MB file upload limit with MIME-type validation and cleanup. | Phase 1 (`f180f8c`) |
| 5 | **Parity** | Runtime inference engine defaulted to 14-feature models requiring unobserved SAQ imputation instead of research-approved 11-feature observable models. | Updated `REG_MODEL_PATH`, `TWEEDIE_MODEL_PATH`, and `CLS_MODEL_PATH` to approved 11-feature observable artifacts; created `model_manifest.json` with SHA-256 hashes and schema validation. | Phase 2 (`e4c7648`) |
| 6 | **Actuarial** | `monte_carlo_simulation` silently masked nonfinite, negative, or NaN costs into positive premiums and mislabeled simulated loss percentiles as a "confidence interval". | Added strict input validation raising `ValueError` on None, NaN, Inf, or negative costs; renamed structure to `simulated_loss_percentiles` and documented $500 base offset as exploratory heuristic. | Phase 3 (`e4c7648`) |
| 7 | **Runner** | Duplicate 11-feature logistic regression candidates in registry; unweighted logistic model presented as ablation of weighted frozen artifact; Tweedie $\alpha$ mismatch. | Removed duplicate entry; separated weighted vs unweighted fits; aligned Tweedie $\alpha=1.0$ across ablations; passed survey weights during ablation training. | Phase 4 (`aaf76a9`) |
| 8 | **Calibration** | Calibration-In-The-Large (CITL) conflated with the intercept of a bivariate logistic slope model. | Implemented formal CITL via Brent's root-finding with fixed slope $\beta=1.0$ and offset; reported bivariate slope and intercept separately. | Phase 4 (`aaf76a9`) |
| 9 | **Provenance** | Audit report declared HC-251 checksum `30198e3b...` while actual file hash was `1de0133d...`; metadata contained hardcoded software versions. | Verified authentic AHRQ release hash on disk (`1de0133d...`); reconciled all audit reports; updated benchmark runner to generate metadata dynamically. | Phase 5 (`aaf76a9`) |
| 10 | **Manuscript** | Manuscript described HC-251, HC-256, and HC-257 as three fully independent cohorts without disclosing Panel 28 longitudinal overlap. | Updated `REVISED_PAPER.md` to disclose Panel 28 overlap between HC-251 and HC-257; characterized prospective validation as cross-year individual stability. | Phase 7 (Current) |

---

## 3. Phase-Wise Git Commit History

The remediations were executed in focused, logical, non-destructive commits on `feature/ml-pipeline-rebuild`:

1. **Commit `f180f8c` — Phase 1: Backend Security Remediation & Test Suite**
   - Files: `backend/package.json`, `backend/package-lock.json`, `backend/server.js`, `backend/tests/security.test.js`
   - Summary: Enforced server-side authentication, PBKDF2 password hashing, Bearer JWT validation, default-deny RBAC, cross-patient data isolation, rate limiting, and 24 passing Node.js security tests.

2. **Commit `e4c7648` — Phases 2 & 3: Model Parity, Manifest Enforcement, & Premium Hardening**
   - Files: `.gitignore`, `ml_model/model_manifest.json`, `ml_model/risk_engine.py`, `ml_model/tests/test_runtime_parity.py`, `ml_model/tests/test_premium_simulation.py`, `ml_model/tests/test_pipeline.py`
   - Summary: Created machine-readable model manifest with SHA-256 checksums and feature schemas; routed runtime engine to 11-feature observable artifacts; hardened Monte Carlo simulation with strict nonfinite validation and loss percentile naming; added 7 runtime parity tests.

3. **Commit `aaf76a9` — Phases 4, 5, 6: Benchmark Runner Methodology & Figure Synchronization**
   - Files: `research_completion/experiments/run_comprehensive_benchmarks.py`, `research_completion/experiments/experiment_registry.json`, `research_completion/figures/fig1_roc_pr_curves.png`, `research_completion/figures/fig2_calibration_deciles.png`, `research_completion/figures/fig4_feature_ablations.png`
   - Summary: Aligned ablation Tweedie $\alpha=1.0$, passed survey weights in ablations, implemented exact Brent's root-finding CITL, separated cross-validation from frozen evaluation, dynamically recorded provenance metadata, and regenerated publication figures.

4. **Commit `19cc772` — Phases 7, 8, 9: Manuscript Revision, Report Reconciliation, & Post-Review Report**
   - Files: `research_completion/paper/REVISED_PAPER.md`, `research_completion/FINAL_INDEPENDENT_VERIFICATION.md`, `research_completion/FINAL_REPRODUCTION_GUIDE.md`, `research_completion/ORIGINAL_VS_REVISED_PAPER.md`, `research_completion/PIPELINE_AUDIT_REPORT.md`, `research_completion/SECURITY_REPRODUCIBILITY_FAIRNESS_REPORT.md`, `research_completion/POST_REVIEW_REMEDIATION_REPORT.md`
   - Summary: Revised research manuscript with honest cohort disclosures, portable citations, CouchDB vs ledger clarification, synchronized benchmark metrics, and published final remediation report.

---

## 4. Test Verification and Commands

All suites were executed locally in the verified workspace environment.

### 4.1 Node.js Backend Security Suite
```bash
cd backend && npm test
```
**Results:**
- **Test Suites:** 8 suites, 24 unit/integration tests
- **Passed:** 24 / 24 (100%)
- **Failed:** 0
- **Duration:** 247 ms
- **Key Tests:** Missing/malformed/expired/tampered tokens (401), password hashing & redaction, cross-patient read/write/ledger/ML isolation (403), role-based denial (doctor vs pharmacist vs patient), admin key enforcement, 1MB payload limits (413), upload MIME & size validation.

### 4.2 Python Machine Learning & Validation Suite
```bash
ml_model/venv/bin/pytest ml_model/tests/
```
**Results:**
- **Collected:** 85 tests across 5 test modules
- **Passed:** 85 / 85 (100%)
- **Failed:** 0
- **Duration:** 1.52 s
- **Breakdown:**
  - `test_phase2_clinical_semantics.py`: 21 passed (ACG mappings, comorbidity counts, edge cases)
  - `test_phase2_external_validation.py`: 22 passed (HC-256 and HC-257 calibration provenance, Brier identities, Target 2 training prevalence provenance)
  - `test_pipeline.py`: 26 passed (end-to-end data pipeline, top-coding, imputation tracking)
  - `test_premium_simulation.py`: 9 passed (strict nonfinite validation, zero boundary, base floor monotonicity, loss percentile structures)
  - `test_runtime_parity.py`: 7 passed (model manifest integrity, SHA-256 verification, feature ordering, fail-closed on corrupt/missing models)

### 4.3 External Validation Scripts
```bash
python3 ml_model/validation/hc256/validate_hc256.py
python3 ml_model/validation/hc257/validate_hc257.py
```
**Results:**
- Both scripts execute cleanly with 0 unhandled exceptions or convergence errors.
- Estimator provenance explicitly logged as `approved_unpenalized_scikit` (`C=inf`) for all primary and subgroup cohorts.

---

## 5. Regenerated Metrics and Synchronization

All reported performance metrics and figures derive from the canonical benchmark runner (`run_comprehensive_benchmarks.py`) and registry (`experiment_registry.json`).

### 5.1 Primary Model Comparison (HC-251 Test Split, $N=3,784$)

| Model Candidate | Target Definition | ROC-AUC (Unwtd) | PR-AUC (Unwtd) | Brier Score (Unwtd) | Brier Skill Score (Wtd) | Dollar $R^2$ | MAE ($) |
|---|---|---|---|---|---|---|---|
| **Constant Prevalence Baseline** | Target 2 ($\ge \$17,827.41$) | 0.5000 | 0.1147 | 0.1016 | 0.0000 | -0.0016 | 6,346.73 |
| **Demographic Baseline (Age+Sex)** | Target 2 ($\ge \$17,827.41$) | 0.6976 | 0.2238 | 0.0945 | 0.0739 | 0.0210 | 6,104.28 |
| **Random Forest (11-Feat Observable)** | Target 2 ($\ge \$17,827.41$) | 0.7712 | 0.3340 | 0.0883 | 0.1347 | 0.0542 | 5,591.24 |
| **Logistic Regression (11-Feat, Weighted Fit)** | Target 2 ($\ge \$17,827.41$) | 0.7766 | 0.3540 | 0.0864 | 0.1537 | 0.0798 | 5,482.11 |
| **Logistic Regression (11-Feat, Unweighted Fit)**| Target 2 ($\ge \$17,827.41$) | 0.7766 | 0.3540 | 0.0858 | 0.1592 | 0.0798 | 5,482.11 |
| **XGBoost (Platt Calibrated)** | Target 2 ($\ge \$17,827.41$) | 0.7774 | 0.3556 | 0.0867 | 0.1507 | 0.0583 | 5,562.90 |
| **Logistic Regression (14-Feat Oracle)** | Target 2 ($\ge \$17,827.41$) | 0.7844 | 0.3664 | 0.0854 | 0.1636 | 0.0821 | 5,411.80 |

### 5.2 Calibration Diagnostics (Formal Decomposition)

| Model Candidate | Sample Mean Pred | Observed Prev | CITL ($\alpha_{CITL}$) | Bivariate Intercept ($a$) | Bivariate Slope ($b$) |
|---|---|---|---|---|---|
| **Logistic Regression (11-Feat, Weighted Fit)** | 0.0999 | 0.1147 | -0.1582 | -0.1714 | 0.9835 |
| **XGBoost (Platt Calibrated)** | 0.1084 | 0.1147 | -0.0631 | -0.1554 | 0.9128 |
| **Logistic Regression (14-Feat Oracle)** | 0.0999 | 0.1147 | -0.1581 | -0.1691 | 0.9852 |

*Note: CITL was computed using Brent's root-finding with offset ($\text{logit}(p) + \alpha$) fixing the slope strictly to 1.0, resolving the prior conflation with the bivariate calibration model.*

### 5.3 Systematic Feature Ablation Matrix (Tweedie $\alpha=1.0$, Weighted Logistic Fits)

| Ablation Configuration | Features | Tweedie Dollar $R^2$ | $\Delta R^2$ vs Full | Classifier Weighted BSS | $\Delta$ BSS vs Full |
|---|---|---|---|---|---|
| **Full 11-Feature Observable Model** | 11 | **0.0798** | — | **0.1537** | — |
| **Exclude ACG Condition Count** | 10 | 0.0612 | -0.0186 | 0.1284 | -0.0253 |
| **Exclude Age Interaction Terms** | 8 | 0.0714 | -0.0084 | 0.1421 | -0.0116 |
| **Demographics Only (Age, Sex)** | 2 | 0.0210 | -0.0588 | 0.0739 | -0.0798 |
| **Clinical Flags Only (8 Conditions)** | 8 | 0.0541 | -0.0257 | 0.1102 | -0.0435 |
| **Leave-One-Out: Exclude Diabetes** | 10 | 0.0762 | -0.0036 | 0.1492 | -0.0045 |
| **Leave-One-Out: Exclude Hypertension** | 10 | 0.0745 | -0.0053 | 0.1468 | -0.0069 |
| **Leave-One-Out: Exclude Heart Disease** | 10 | 0.0751 | -0.0047 | 0.1481 | -0.0056 |
| **Leave-One-Out: Exclude Cancer** | 10 | 0.0778 | -0.0020 | 0.1518 | -0.0019 |
| **Leave-One-Out: Exclude Asthma** | 10 | 0.0789 | -0.0009 | 0.1528 | -0.0009 |
| **Leave-One-Out: Exclude Joint Pain** | 10 | 0.0781 | -0.0017 | 0.1521 | -0.0016 |

---

## 6. Honest Disclosures of System and Scientific Limitations

In accordance with research integrity requirements, the following operational and methodological constraints remain active:

### 6.1 External Validation & Longitudinal Overlap
- **Cohort Interdependence:** The evaluation cohorts HC-251 (2023 Full-Year), HC-256 (2022 Full-Year), and HC-257 (2023–2024 Longitudinal) are **not fully independent populations**. Specifically, HC-251 includes the 2023 observations of MEPS Panel 28, while HC-257 observes the identical Panel 28 sample across 2023 and 2024.
- **Evaluation Scope:** HC-257 constitutes a **prospective within-individual longitudinal stability test**, evaluating whether baseline 2023 conditions predict 2024 expenditure exceedance. It does not evaluate independent population-level generalization.

### 6.2 Survey Design & Uncertainty Quantification
- **Independent Split vs Complex Design:** Primary ML training, cross-validation, and non-parametric bootstrap intervals treat observations as exchangeable sample draws. Complex MEPS survey design features—stratification (`VARSTR`) and primary sampling units (`VARPSU`)—are incorporated into weighted prevalence and summary statistics, but non-linear tree ensembles do not utilize full Taylor-series linearization or balanced repeated replications (BRR/Fay).
- **Subgroup Precision:** Subgroup analyses (e.g., specific age and gender intersections) reflect unweighted sample counts. Subgroups with $N < 100$ exhibit wider sampling variance and must be interpreted as exploratory.

### 6.3 Clinical Intake Semantics
- **Self-Reported Limitations:** Intake conditions represent self-reported participant affirmative responses to MEPS survey prompts mapped to Johns Hopkins ACG cluster concepts.
- **Non-Diagnosis Caveat:** Zero recorded comorbidity flags indicate the absence of affirmative responses to mapped survey items, **not a clinical confirmation of health**. Unmeasured chronic illnesses, acute trauma, or undiagnosed pathologies are not captured.

### 6.4 Actuarial Simulation Status
- **Exploratory Heuristic:** The Monte Carlo loss simulation implemented in `monte_carlo_simulation()` is an **exploratory loss heuristic**, utilizing a shifted Gamma distribution with an empirical shape parameter ($k=1.5$) and a configurable $\$500$ base offset.
- **Regulatory Disclaimers:** The output percentiles ($P_5, P_{95}$) represent simulated loss dispersion, **not an actuarial confidence interval for estimated Value-at-Risk (VaR)**. It is not an actuarially certified premium rating engine and must not be used for binding statutory insurance quotes without formal actuarial certification.

### 6.5 Hyperledger Fabric & Blockchain Environment
- **Benchmark Provenance:** All reported blockchain throughput ($350.1\text{ TPS}$) and latency ($0.04\text{s} - 18.0\text{s}$) figures originate from **historical Hyperledger Caliper benchmark runs** executed against a multi-organization Docker topology.
- **Ledger vs World State:** Hyperledger Fabric's ledger comprises an immutable, cryptographically hashed append-only block log, whereas patient state queries read from CouchDB world-state databases which are mutable snapshots of the latest committed transactions.
- **Live Deployment Blocker:** Re-execution of the live Fabric network in the local macOS development environment is currently blocked due to host Docker daemon socket permissions. The off-chain API routes handle ledger queries safely via fire-and-forget fallbacks when the ledger is offline.

---

## 7. Comprehensive Release Readiness Matrix

| Domain | Readiness Status | Assessment and Verifiable Evidence |
|---|---|---|
| **Software Correctness** | **READY / VERIFIED** | 85/85 Python unit/parity tests pass; 24/24 Node.js security tests pass. Zero warnings on benchmark generation. Model manifest enforces SHA-256 integrity on boot. |
| **Predictive Validity** | **VALIDATED** | Concordance established across 11 observable features ($R^2 = 0.0798$, ROC-AUC $= 0.7766$). Prospective individual stability verified on HC-257. |
| **Clinical Validity** | **EXPLORATORY / LIMITED** | Suitable for population risk tiering. Not validated for acute clinical diagnosis or treatment planning. Relies on self-reported condition mapping. |
| **Actuarial Validity** | **HEURISTIC ONLY** | Simulation parameters ($k=1.5$, base floor $\$500$) are exploratory heuristics. Binding underwriting requires formal actuarial credibility weighting. |
| **Security Readiness** | **INTERNALLY SECURED** | Default credentials eliminated, PBKDF2 hashing active, RBAC enforced, cross-patient access blocked, upload/payload limits enforced. Formal external penetration testing remains pending. |
| **Publication Readiness** | **REVISED / PEER-REVIEW READY** | Manuscript accurately reflects canonical outputs, discloses longitudinal cohort overlap, removes causal overstatements, and replaces author placeholders for double-blind review. |

---

## 8. Summary of Release Blockers

The following items must be resolved prior to commercial or clinical deployment:
1. **Live Ledger Integration:** Deployment of the 5-organization Hyperledger Fabric network to a Kubernetes or cloud Docker environment with provisioned TLS certificates and hardware security modules (HSM).
2. **Actuarial Certification:** Review and re-calibration of the expenditure loss models by a credentialed Actuary (FSA/MAAA) using carrier-specific claims distributions.
3. **Clinical EHR Integration:** Replacing manual self-reported intake with HL7 FHIR US Core profiles for automated extraction of ICD-10-CM diagnostic codes and lab observation values.
4. **External Security Penetration Test:** Third-party audit of the Node.js API server and Fabric smart contracts prior to handling real Protected Health Information (PHI).
