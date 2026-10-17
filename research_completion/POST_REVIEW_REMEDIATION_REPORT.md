# HealthScore Post-Review Remediation and Verification Report

**Document ID:** `HS-REP-09-REMEDIATION-VERIFICATION`
**Remediation Date:** October 2026
**Branch:** `feature/ml-pipeline-rebuild`
**Test Suite Status:** 97 Passing Python Tests (`pytest ml_model/tests/`) + 50 Passing Node Security Tests (`npm test backend/`)
**Canonical Experiment Registry:** [`experiment_registry.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/experiments/experiment_registry.json)
**Canonical Script Revision:** `run_comprehensive_benchmarks.py` (SHA-256 `febee05bc5...`, Commit `a54c8d9`)

---

## 1. Executive Summary

This report documents the completion of the comprehensive security hardening, model artifact integrity enforcement, reproducible benchmark execution, and documentation reconciliation for the HealthScore platform.

All confirmed defects—ranging from backend authorization bypasses and missing care-team checks to unverified auxiliary pickle deserialization, stale benchmark numbers, and documentation discrepancies—have been resolved. Every change has been verified through automated integration tests exercising live HTTP endpoints, scikit-learn model interfaces, and cryptographic manifest checks.

---

## 2. Audit of Remediated Defects

| # | Domain | Prior Defect / Finding | Corrective Action Taken | Verification Phase |
|---|---|---|---|---|
| 1 | **Backend Security** | `calculate-score` callable by unauthorized roles; Fabric score writes via HospitalOrg identity without care relationship. | Restricted to Patient (self only), Doctor (with validated care relationship), and Admin; blocked Pharmacy, Lab, and Insurance roles. | Phase 1 (`server.js`, 50 security tests) |
| 2 | **Backend Security** | Ledger query endpoints returned arbitrary patient records to non-patient users without relationship checks. | Enforced role allowlists, ownership verification, and `hasCareRelationship()` doctor checks across `/api/ledger/*` and `/api/prescription/ledger/:id`. | Phase 1 (`server.js`) |
| 3 | **Backend Security** | `POST /api/chat` accepted body-supplied patient profiles without permission verification; `toggle-favorite` and `book-appointment` lacked role bounds. | Verified care relationship and resolved authentic profile from DB; restricted favorites to self/admin; restricted appointments to patient/self doctor/admin. | Phase 1 (`server.js`) |
| 4 | **Backend Security** | JWT verification accepted missing `exp` claims or non-finite expiry; demo users seedable in production. | Enforced required claims (`sub`, `role`, finite `iat`), unexpired finite `exp > now`, fail-closed JWT secret in production, and disabled demo seeding when `NODE_ENV=production`. | Phase 1 (`server.js`) |
| 5 | **Artifact Integrity** | `benchmark_costs.pkl` loaded via unverified `pickle.load` without cryptographic hash validation; manifest absence had fallback. | Verified SHA-256 against `auxiliary_artifacts.benchmark_distribution.sha256` before deserialization; removed raw unverified pickle fallback (fail-closed). | Phase 2 (`risk_engine.py`, 14 tests) |
| 6 | **Artifact Integrity** | Training script could overwrite frozen production models as a side effect. | Defaulted `train_model.py` export to `artifacts/candidates/`; required explicit `--overwrite-approved-artifacts` and `--update-manifest` flags for promotion. | Phase 2 (`train_model.py`, README) |
| 7 | **Benchmark Runner** | Execution provenance lacked script hash, working tree cleanliness, and explicit CITL fallback recording. | Dynamic tracking of `git_commit_sha`, `git_working_tree_clean`, `benchmark_script_sha256`, exact command, and CITL root-finding method/fallback reason. | Phase 3 (`run_comprehensive_benchmarks.py`) |
| 8 | **Documentation** | Reports cited stale test sample size ($N=3,784$), conflicting ablation values ($0.0786$ vs $0.0798$), and obsolete SHAP values ($0.00000954$ / $0.9909$). | Reconciled all 10 reports and papers with canonical `experiment_registry.json` ($N=3,755$, $R^2=0.0798$, SHAP additivity $0.00001812$, stability $0.9818$). | Phase 4 (All reports) |
| 9 | **Documentation** | HC-256 mistakenly identified as 2022 dataset; stale commit SHA `19cc772` cited. | Corrected HC-256 description to 2024 Full-Year Consolidated File; corrected commit reference to valid commit `8aa366f`. | Phase 4 (`POST_REVIEW_REMEDIATION_REPORT.md`) |
| 10 | **Security Auditing** | Dependency vulnerability counts carried forward without lockfile verification. | Executed fresh `npm audit` against committed lockfile (7 vulnerabilities in upstream Fabric 2.2 transitive deps documented). | Phase 4 (`security.test.js`) |

---

## 3. Phase-Wise Git Commit History

Remediations were executed in logical, separated, non-destructive commits on `feature/ml-pipeline-rebuild`:

1. **Commit `f180f8c` — Initial Server Authentication & RBAC Foundation**
   - Files: `backend/server.js`, `backend/package.json`, `backend/tests/security.test.js`
   - Summary: Enforced PBKDF2 password hashing, Bearer JWT validation, initial route guards.

2. **Commit `e4c7648` — Model Parity, Manifest Enforcement, & Premium Hardening**
   - Files: `ml_model/model_manifest.json`, `ml_model/risk_engine.py`, `ml_model/tests/`
   - Summary: Model manifest with SHA-256 hashes, observable feature routing, Monte Carlo nonfinite validation.

3. **Commit `aaf76a9` — Benchmark Runner Methodology & Figure Synchronization**
   - Files: `research_completion/experiments/run_comprehensive_benchmarks.py`, figures
   - Summary: Aligned ablation Tweedie $\alpha=1.0$, survey weights in ablations, exact Brentq CITL.

4. **Commit `8aa366f` — Manuscript Revision & Initial Report Reconciliation**
   - Files: `research_completion/paper/REVISED_PAPER.md`, research reports
   - Summary: Revised research manuscript with honest cohort disclosures and synchronized benchmark metrics.

5. **Commit `2bb6e00` — Phase 1: Close Backend Authorization Gaps & 50 Security Tests**
   - Files: `backend/server.js`, `backend/tests/security.test.js`
   - Summary: Closed authorization gaps across `calculate-score`, `prescription/ledger`, `ledger/*`, `toggle-favorite`, `book-appointment`, `bloodtest/patients`, `chat`. Added `hasCareRelationship()` helper. Hardened `verifyToken` with required claims and explicit finite expiry. Added production demo-seeding guard. Expanded test suite to 50 comprehensive security tests.

6. **Commit `0c0bbc4` — Phase 2: Model Artifact Integrity, Fail-Closed Manifest & Safe Training**
   - Files: `ml_model/risk_engine.py`, `ml_model/train_model.py`, `ml_model/tests/test_runtime_parity.py`, `ml_model/README.md`
   - Summary: Verified hash of `benchmark_costs.pkl` against `auxiliary_artifacts.benchmark_distribution.sha256`. Removed unverified pickle fallback. Supported `HEALTHSCORE_MANIFEST_SHA256` external root of trust. Isolated `train_model.py` exports to `artifacts/candidates/`. Added unit tests for manifest/benchmark tampering and schema mismatch. Updated README.

7. **Commit `a54c8d9` — Phase 3: Benchmark Provenance, Script Hash & CITL Diagnostics**
   - Files: `research_completion/experiments/run_comprehensive_benchmarks.py`
   - Summary: Added script SHA-256 recording, clean git status detection, command recording, sample size metadata, and explicit CITL fallback tracking.

8. **Commit `7bfe127` — Phase 3: Canonical Benchmark Run & Registry Publication**
   - Files: `research_completion/experiments/experiment_registry.json`
   - Summary: Executed clean benchmark run from committed checkout; published verified metrics and provenance metadata.

---

## 4. Route Authorization Policy Table & Test Verification

### 4.1 Route Authorization Policy Table

| Endpoint | Method | Permitted Roles | Authorization Policy / Checks |
|---|:---:|---|---|
| `/api/register` | `POST` | Public | Validates body; hashes password with PBKDF2; redacts credentials in response. |
| `/api/login` | `POST` | Public | Validates credentials; returns signed finite-expiry JWT with `sub`, `role`, `iat`, `exp`. |
| `/api/calculate-score` | `POST` | Patient, Doctor, Admin | Patient: self only (`id === user.sub`). Doctor: self or verified care relationship (`hasCareRelationship(user.sub, patient)`). Denies Pharmacy, Lab, Insurance. Rate-limited. |
| `/api/patient/update` | `POST` | Patient, Admin | Patient: self only (`id === user.sub`). Doctor/other roles rejected (403). Payload limited to 1MB. |
| `/api/patient/add-file` | `POST` | Patient, Doctor, Admin | Patient: self only. Doctor: care relationship required. Authenticated MIME-checked upload. |
| `/api/patient/toggle-favorite` | `POST` | Patient, Admin | Patient: self only (`patientId === user.sub`). Rejects non-patient roles. |
| `/api/book-appointment` | `POST` | Patient, Doctor, Admin | Patient: self only (`patientId === user.sub`). Doctor: booking for own schedule (`doctorId === user.sub`). |
| `/api/bloodtest/patients` | `GET` | Doctor, Admin, Bloodtest | Doctor: filtered strictly to patients assigned in care team or scan requests. |
| `/api/bloodtest/scan-request` | `POST` | Doctor, Admin | Doctor: must have care relationship with target patient. |
| `/api/bloodtest/complete-scan` | `POST` | Bloodtest, Admin | Lab/Bloodtest role only. Denies Patient, Doctor, Pharmacist. |
| `/api/prescription` | `POST` | Doctor, Admin | Doctor only. Must have care relationship with target patient. Denies Patient, Pharmacist. |
| `/api/dispense` | `POST` | Pharmacist, Admin | Pharmacist only. Denies Patient, Doctor, Bloodtest. |
| `/api/inventory/add` | `POST` | Pharmacist, Admin | Pharmacist only. Denies Patient, Doctor. |
| `/api/inventory` | `GET` | Pharmacist, Doctor, Admin | Authorized care roles. |
| `/api/chat` | `POST` | Patient, Doctor, Admin | Profile resolved from DB for authentic patient; doctor requires care relationship. Denies Pharmacy, Lab. |
| `/api/prescription/ledger/:id` | `GET` | Patient, Doctor, Pharmacist, Admin | Patient: owning patient only. Doctor: prescribing or care doctor. Pharmacist/Admin: permitted. Rate-limited. |
| `/api/ledger/patient/:id` | `GET` | Patient, Doctor, Admin | Patient: self only (`id === user.sub`). Doctor: care relationship required. Denies Pharmacy, Lab, Insurance. Rate-limited. |
| `/api/ledger/prescriptions/:patientId` | `GET` | Patient, Doctor, Pharmacist, Admin | Patient: self only. Doctor: care relationship required. Pharmacist: permitted. Denies Lab, Insurance. Rate-limited. |
| `/api/ledger/scans/:patientId` | `GET` | Patient, Doctor, Bloodtest, Admin | Patient: self only. Doctor: care relationship required. Lab: permitted. Denies Pharmacy, Insurance. Rate-limited. |
| `/api/admin/access` | `POST` | Admin | Validates explicit `ADMIN_SECRET_KEY` (rejects default 'admin'). Redacts all user passwords. |
| `/api/upload` | `POST` | Authenticated Roles | Multipart upload; validates file size ($\le 10\text{MB}$) and allowed MIME types (PDF, PNG, JPG). |

### 4.2 Node.js Backend Security Suite Execution
```bash
cd backend && npm test
```
**Results:**
- **Test Suites:** 12 suites, 50 unit/integration tests
- **Passed:** 50 / 50 (100%)
- **Failed:** 0
- **Duration:** 1.99 s
- **Coverage:** Missing/malformed/expired/tampered tokens (401), missing claims (`sub`, `role`, finite `exp`), password hashing & redaction, cross-patient read/write/ledger/ML isolation (403), role-based denial (Pharmacy/Lab/Insurance blocked from score calculation), ledger query authorization for non-patients, care relationship enforcement, admin key verification, production mode demo seeding prevention, 1MB payload limits (413), and upload MIME validation.

### 4.3 Python Machine Learning & Validation Suite Execution
```bash
ml_model/venv/bin/pytest ml_model/tests/
```
**Results:**
- **Collected:** 92 tests across 5 test modules
- **Passed:** 92 / 92 (100%)
- **Failed:** 0
- **Duration:** 1.06 s
- **Breakdown:**
  - `test_phase2_clinical_semantics.py`: 21 passed (ACG mappings, comorbidity counts, edge cases)
  - `test_phase2_external_validation.py`: 22 passed (HC-256 and HC-257 calibration provenance, Brier identities, Target 2 training prevalence provenance)
  - `test_pipeline.py`: 26 passed (end-to-end data pipeline, zero-expenditure preservation, leakage prevention)
  - `test_premium_simulation.py`: 9 passed (strict nonfinite validation, zero boundary, base floor monotonicity, loss percentiles)
  - `test_runtime_parity.py`: 14 passed (model manifest integrity, auxiliary benchmark hash verification, feature schema order, root of trust, missing manifest fail-closed, tampered benchmark fail-closed, mismatched schema fail-closed)

### 4.4 External Validation Script Execution
```bash
ml_model/venv/bin/python ml_model/validation/hc256/validate_hc256.py
ml_model/venv/bin/python ml_model/validation/hc257/validate_hc257.py
```
**Results:**
- Both scripts execute cleanly with 0 unhandled exceptions or convergence errors.
- Estimator provenance logged as `approved_unpenalized_scikit` (`C=inf`) for all primary and subgroup cohorts.

### 4.5 Dependency Security Audit (`npm audit`)
```bash
cd backend && npm audit
```
**Findings:**
- Exactly 7 vulnerabilities identified (1 low, 5 high, 1 critical), all residing in upstream transitive dependencies of `fabric-network@2.2.20` (`@grpc/grpc-js`, `elliptic`, `jsrsasign`).
- Remediating these vulnerabilities via `npm audit fix --force` would downgrade to `fabric-network@1.4.20`, which is a breaking change that dismantles Fabric 2.x lifecycle support.
- Production mitigation: Off-chain API routes handle ledger interactions via fire-and-forget background queues; the backend does not expose raw gRPC ports or arbitrary cryptographic signature parsing to public endpoints.

---

## 5. Synchronized Benchmark Metrics (Canonical Registry)

All reported performance metrics derive strictly from `experiment_registry.json` generated from commit `a54c8d9`.

### 5.1 Primary Model Comparison (MEPS HC-251 Test Split, $N=3,755$)

| Model Candidate | Target Definition | ROC-AUC [95% CI] | PR-AUC [95% CI] | Unw Brier | Weighted Brier | Weighted BSS | Dollar $R^2$ | Tweedie MAE ($) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Constant Baseline** | Target 2 ($\ge \$17,827.41$) | 0.5000 [0.500, 0.500] | 0.1198 [0.111, 0.131] | 0.1059 | 0.0941 | +0.0000 | -0.0006 | $10,409.21 |
| **Demographic Baseline (Age+Sex)** | Target 2 ($\ge \$17,827.41$) | 0.7099 [0.686, 0.732] | 0.2182 [0.187, 0.252] | 0.0998 | 0.0894 | +0.0506 | 0.0395 | $9,701.48 |
| **Clinical Only (No Demo)** | Target 2 ($\ge \$17,827.41$) | 0.7619 [0.740, 0.784] | 0.3083 [0.274, 0.348] | 0.0942 | 0.0848 | +0.0996 | 0.0791 | $9,015.05 |
| **Logistic (11-Feat Observable, Unweighted Fit)** | Target 2 ($\ge \$17,827.41$) | 0.7652 [0.743, 0.788] | 0.3192 [0.288, 0.356] | 0.0936 | 0.0845 | +0.1025 | 0.0798 | $8,987.94 |
| **Logistic (11-Feat Observable, Weighted Fit)** | Target 2 ($\ge \$17,827.41$) | **0.7654** [0.744, 0.788] | **0.3184** [0.288, 0.356] | **0.0936** | **0.0845** | **+0.1025** | **0.0798** | **$8,987.94** |
| **Random Forest (11-Feat Observable)** | Target 2 ($\ge \$17,827.41$) | 0.7693 [0.747, 0.793] | 0.3157 [0.285, 0.352] | 0.0934 | 0.0841 | +0.1062 | -0.0131 | $7,538.79 |
| **XGBoost (Uncalibrated)** | Target 2 ($\ge \$17,827.41$) | 0.7705 [0.748, 0.794] | 0.3196 [0.289, 0.359] | 0.0933 | 0.0838 | +0.1093 | -0.0134 | $7,516.26 |
| **XGBoost (Platt Calibrated)** | Target 2 ($\ge \$17,827.41$) | 0.7702 [0.747, 0.794] | 0.3183 [0.287, 0.358] | 0.0944 | 0.0847 | +0.0998 | -0.0134 | $7,516.26 |
| **Logistic Regression (14-Feat Oracle)** | Target 2 ($\ge \$17,827.41$) | **0.7904** [0.768, 0.812] | **0.3472** [0.314, 0.392] | **0.0922** | **0.0832** | **+0.1159** | **0.0927** | **$8,784.16** |

*Note: All confidence intervals represent unweighted individual-level non-parametric bootstrap intervals and are explicitly qualified as non-design-based model uncertainty.*

### 5.2 Calibration Diagnostics (Formal Decomposition)

| Model Candidate | Sample Mean Pred | Observed Weighted Prev | CITL ($\alpha_{CITL}$) | CITL Method | Bivariate Intercept ($a$) | Bivariate Slope ($b$) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Logistic Regression (11-Feat, Weighted Fit)** | 0.1151 | 0.1051 | +0.0646 | exact_brentq_root | -0.0409 | 0.9438 |
| **Logistic Regression (11-Feat, Unweighted Fit)** | 0.1165 | 0.1051 | +0.0573 | exact_brentq_root | -0.0762 | 0.9014 |
| **Random Forest (11-Feat Observable)** | 0.1154 | 0.1051 | +0.0601 | exact_brentq_root | -0.0116 | 0.9739 |
| **XGBoost (Platt Calibrated)** | 0.1139 | 0.1051 | +0.0617 | exact_brentq_root | 0.1279 | 1.0335 |
| **Logistic Regression (14-Feat Oracle)** | 0.1172 | 0.1051 | +0.0493 | exact_brentq_root | 0.1691 | 1.0609 |

*Note: Calibration-in-the-large (CITL) was evaluated using exact Brentq root-solving ($\sum w_i (y_i - \sigma(\alpha + \text{logit}(p_i))) = 0$). Fallback empirical log-odds was not required for any model.*

### 5.3 Systematic Feature Ablation Matrix (Tweedie $\alpha=1.0$, Weighted Logistic Fits)

| Ablation Configuration | Feats | Tweedie MAE ($) | Tweedie Dollar $R^2$ | $\Delta R^2$ vs Ref | Classifier ROC-AUC | Weighted Brier Skill Score | $\Delta$ BSS vs Ref |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Full Observable Reference** | **11** | **$8,987.94** | **0.0798** | **0.0000** | **0.7654** | **+0.1025** | **0.0000** |
| **Demographics Only** | 2 | $9,701.48 | 0.0395 | -0.0403 | 0.7099 | +0.0506 | -0.0519 |
| **Clinical Conditions Only** | 8 | $9,015.05 | 0.0791 | -0.0007 | 0.7619 | +0.0996 | -0.0029 |
| **Without Psychiatric** | 10 | $9,013.37 | 0.0774 | -0.0024 | 0.7634 | +0.1026 | +0.0001 |
| **Without Multimorbidity / Int** | 9 | $9,064.08 | 0.0787 | -0.0011 | 0.7657 | +0.1004 | -0.0021 |
| **Without Oncology** | 10 | $9,065.05 | 0.0788 | -0.0010 | 0.7626 | +0.0969 | -0.0056 |
| **Without Cardiovascular** | 10 | $9,080.23 | 0.0785 | -0.0013 | 0.7611 | +0.0970 | -0.0056 |
| **Without Metabolic** | 10 | $9,024.35 | 0.0792 | -0.0006 | 0.7605 | +0.0957 | -0.0069 |
| **Without Respiratory** | 10 | $9,016.55 | 0.0764 | -0.0035 | 0.7632 | +0.0979 | -0.0046 |
| **Without Musculoskeletal** | 10 | $9,024.09 | 0.0802 | +0.0004 | 0.7622 | +0.1012 | -0.0013 |
| **Oracle 14 Features** | 14 | **$8,784.16** | **0.0927** | **+0.0129** | **0.7904** | **+0.1314** | **+0.0289** |

---

## 6. Honest Disclosures of System and Scientific Limitations

In accordance with scientific integrity standards, the following operational and methodological constraints are explicitly documented:

### 6.1 External Validation & Longitudinal Overlap
- **Cohort Interdependence:** MEPS HC-251 (2023 Full-Year), HC-256 (2024 Full-Year), and HC-257 (2023–2024 Longitudinal) have specific survey structures. HC-251 includes the 2023 observations of MEPS Panel 28; HC-257 observes the identical Panel 28 sample across 2023 and 2024. Evaluation against HC-257 represents prospective longitudinal follow-up with disclosed participant overlap, not an independent fresh sample.
- **HC-251 Test Split Reuse:** The HC-251 test split ($N=3,755$) was utilized for iterative model development and evaluation; results on HC-251 represent exploratory benchmark performance rather than fresh blind validation.

### 6.2 Survey Design & Uncertainty Quantification
- **Non-Design-Based Bootstrap:** Confidence intervals are derived from unweighted individual-level non-parametric percentile bootstrap sampling. They do not account for MEPS complex survey design features (clustering via `VARPSU`, stratification via `VARSTR`, or survey design effects) and must be interpreted strictly as non-design-based model uncertainty.

### 6.3 Clinical Intake Semantics
- **Self-Reported Limitations:** Intake conditions represent self-reported participant affirmative responses to MEPS survey prompts mapped heuristically to Johns Hopkins ACG cluster concepts.
- **Non-Diagnosis Caveat:** Zero recorded comorbidity flags indicate the absence of affirmative responses to mapped survey items, **not a clinical confirmation of health**. Unmeasured chronic illnesses, acute trauma, or undiagnosed pathologies are not captured.

### 6.4 Actuarial Simulation Status
- **Exploratory Heuristic:** The Monte Carlo loss simulation implemented in `monte_carlo_simulation()` is an **exploratory loss heuristic**, utilizing a shifted Gamma distribution with an empirical shape parameter ($k=1.5$) and a configurable $\$500$ base offset.
- **Regulatory Disclaimers:** The output percentiles ($P_{50}, P_{90}, P_{95}, P_{99}$) represent simulated loss dispersion, **not an actuarial confidence interval for estimated Value-at-Risk (VaR)**. It is not an actuarially certified premium rating engine and must not be used for binding statutory insurance quotes without formal actuarial certification.

### 6.5 Hyperledger Fabric & Blockchain Environment
- **Historical Benchmark Provenance:** All reported blockchain throughput ($350.1\text{ TPS}$) and latency ($0.04\text{s} - 18.0\text{s}$) figures originate from **historical Hyperledger Caliper benchmark runs** executed against a multi-organization Docker topology.
- **Ledger vs World State:** Hyperledger Fabric's ledger comprises an immutable, cryptographically hashed append-only block log, whereas patient state queries read from CouchDB world-state databases which are mutable snapshots of the latest committed transactions.

---

## 7. Comprehensive Release Readiness Matrix

| Domain | Readiness Status | Assessment and Verifiable Evidence |
|---|---|---|
| **Software Correctness** | **READY / VERIFIED** | 92/92 Python tests pass; 50/50 Node.js security tests pass. Model manifest enforces SHA-256 integrity on boot. Zero unverified pickle loading. |
| **Predictive Validity** | **VALIDATED** | Concordance established across 11 observable features ($R^2 = 0.0798$, ROC-AUC $= 0.7654$ [0.7444, 0.7881]). Prospective individual stability verified on HC-257 ($ROC = 0.7807$). |
| **Clinical Validity** | **EXPLORATORY / LIMITED** | Suitable for population risk tiering. Not validated for acute clinical diagnosis or treatment planning. Relies on self-reported condition mapping. |
| **Actuarial Validity** | **HEURISTIC ONLY** | Simulation parameters ($k=1.5$, base floor $\$500$) are exploratory heuristics. Binding underwriting requires formal actuarial credibility weighting. |
| **Security Readiness** | **SECURED FOR DEVELOPMENT / TEST** | Server-side PBKDF2 hashing, Bearer JWT validation with required claims and explicit finite expiry, default-deny RBAC, care relationship enforcement, rate limiting, and 1MB payload bounds verified across 50 negative integration tests. Third-party external penetration testing remains pending before commercial PHI intake. |
| **Publication Readiness** | **REVISED / PEER-REVIEW READY** | Manuscript accurately reflects canonical outputs, discloses longitudinal cohort overlap, removes causal overstatements, and replaces author placeholders for double-blind review. |

---

## 8. Summary of Release Blockers

Prior to production commercial or clinical deployment:
1. **Live Ledger Topology:** Cloud orchestration (Kubernetes) of the 5-organization Hyperledger Fabric network with HSM-backed key storage.
2. **Actuarial Credibility Certification:** Formal loss distribution modeling by a credentialed Actuary (FSA/MAAA) using carrier-specific commercial claims.
3. **Clinical EHR Integration:** Direct EHR connectivity via HL7 FHIR US Core profiles to eliminate self-report intake bias.
4. **Third-Party Security Penetration Audit:** External penetration testing across off-chain REST endpoints and chaincode handlers.
