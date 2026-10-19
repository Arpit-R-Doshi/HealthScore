# HealthScore Manuscript Final QA Checklist

**Document ID:** `HS-QA-FINAL-CHECKLIST`
**Evaluation Date:** October 2026
**Repository Branch:** `feature/ml-pipeline-rebuild`
**Manuscript Target:** [`research_completion/paper/REVISED_PAPER.md`](paper/REVISED_PAPER.md) (Version 3.1)
**Reconciliation Log:** [`research_completion/ORIGINAL_VS_REVISED_PAPER.md`](ORIGINAL_VS_REVISED_PAPER.md)

---

## 1. Scope & Thematic Integrity

- [x] **Preserved Central Theme:** Evaluates Hyperledger Fabric performance for healthcare workflows, supported by ACG-inspired risk scoring and an exploratory premium simulation.
- [x] **Primary vs. Supporting Contributions:** Primary focus is empirical blockchain throughput, latency, saturation dynamics, and ledger-to-application boundaries; ML feature ablations and premium simulation are explicitly positioned as supporting contributions.
- [x] **No Project Redesign:** Experiments, registry artifacts, and benchmark measurements from approved live runs are preserved without refitting models or rerunning testbeds.

---

## 2. Unsupported or Overstated Claims Audit

| Manuscript Section | Original / Risk Claim | Final Reconciled Status (Version 3.1) | Verified |
| :--- | :--- | :--- | :---: |
| **Abstract & Conclusion** | "production-grade scalability" | Replaced with measured protocol-level performance under evaluated single-host testbed conditions ($200$ TPS sub-$100$ms, $350$–$516$ TPS stress saturation, $500$ TPS read). | ✅ |
| **Abstract & Intro** | "eliminating centralized single points of failure" | Replaced with distributed multi-party verification; explicitly disclosed that resilience under actual peer, orderer, storage, or network crashes was not tested via fault injection. | ✅ |
| **Entire Paper** | "production healthcare traffic" | Replaced with representative synthetic benchmark transaction workloads (`createPatientRecord`, `updateHealthScore`, `createPrescription`, `requestScan`). | ✅ |
| **Section 3 & 8** | "proven superior privacy" | Comparative privacy evaluation against encrypted databases explicitly disclaimed as outside study scope; data-management partitioning described only as implemented. | ✅ |
| **Section 3** | "drug-abuse prevention" | Described as an auditable multiparty prescription workflow; clinical prevention claims removed. | ✅ |
| **Section 7 & 9** | "actuarial pricing / commercial insurance rating" | Explicitly disclaimed; parameterized Value-at-Risk demonstration ($X_\alpha = B + (1+\alpha)G$) without commercial underwriting adequacy or reserve solvency claims. | ✅ |
| **Section 6 & 10** | "dominant predictive gain" | Replaced with exact empirical ablation findings: ACG-inspired clusters provide the primary predictive improvement over demographics ($\Delta R^2 = +0.0376$, $\Delta \text{BSS} = +0.0499$). | ✅ |
| **Throughout** | "Johns Hopkins ACG" | Consistently labeled as heuristic "ACG-inspired condition clusters" rather than the official proprietary grouper. | ✅ |

---

## 3. Machine Learning Reporting & Artifact Alignment

- [x] **Chosen Classifier:** 11-Feature Observable Logistic Regression (Weighted Fit, serialized artifact `risk_model_classifier_observable_weighted_p90.pkl` with normalized person weights `normalized_person_weights`).
- [x] **Target Definition & Rationale:** High-expenditure survey-weighted P90 ($TOTEXP23 \ge \$17,827.41$). Rationale documented: Pareto distribution of healthcare costs (top 10% consume ~65–70% of resources); arbitrary 15% threshold rejected.
- [x] **Class Prevalence & Baselines:**
  - Training weighted prevalence: $9.99\%$ ($0.099888$).
  - Test weighted prevalence: $10.51\%$ ($0.105134$).
  - Test unweighted prevalence: $11.98\%$ ($0.119840$, $450$ individuals).
  - Constant baseline weighted Brier score: $0.0941$.
  - Constant baseline unweighted Brier score: $0.1059$.
- [x] **Classifier Metrics & Comparison Completeness (Table 6b):**
  - All 9 canonical models present in Table 6b (Constant Baseline, Demographic Baseline, Clinical Conditions Only, Logistic 11-Feat Observable Weighted Fit, Logistic 11-Feat Observable Unweighted Fit, Random Forest 11-Feat Observable, XGBoost Uncalibrated, Platt-Calibrated XGBoost, Logistic 14-Feat Oracle).
  - Restored Random Forest (11-Feat Observable): ROC-AUC $0.7693$ [$0.7458, 0.7928$], PR-AUC $0.3157$ [$0.2823, 0.3550$], Unw Brier $0.0935$, Wtd Brier $0.0841$, Wtd BSS $+0.1062$, CITL $+0.0601$, Slope $0.9736$, Prec $0.2342$, Rec $0.7556$, F1 $0.3575$.
  - Restored XGBoost (Uncalibrated): ROC-AUC $0.7705$ [$0.7482, 0.7940$], PR-AUC $0.3196$ [$0.2853, 0.3598$], Unw Brier $0.0932$, Wtd Brier $0.0838$, Wtd BSS $+0.1093$, CITL $+0.0572$, Slope $0.9926$, Prec $0.2262$, Rec $0.8022$, F1 $0.3529$.
  - Approved Serving Candidate: Logistic 11-Feat Observable (Weighted Fit): ROC-AUC $0.7654$ [95% CI: $0.7444$, $0.7881$], PR-AUC $0.3184$ [95% CI: $0.2876$, $0.3556$], Weighted Brier $0.0845$ (Wtd BSS: $+0.1025$, $+10.25\%$), Unweighted Brier $0.0936$ (Unw BSS: $+0.1123$).
  - Calibration diagnostics: Calibration slope $b = 0.9438$, bivariate intercept $a = -0.0409$, exact Calibration-in-the-Large $\text{CITL} = +0.0646$ (exact Brent's root).
  - Selection rationale: Defensible multi-factorial balance of input availability parity, calibration quality, clinical interpretability, exact reproducibility, and operational simplicity in off-chain inference, while blockchain records auditable risk-score milestones.
  - Statistical testing disclosure: Point estimates are close and marginal 95% bootstrap confidence intervals overlap descriptively between logistic regression and tree ensembles (Random Forest / XGBoost); explicitly discloses that no formal paired statistical hypothesis test was conducted, and neither statistical significance nor non-significance is claimed.
- [x] **Explicit Metric Distinction & Unweighted Enrichment (`Precision @ 0.10`):**
  - Confirmed via inspection of `run_comprehensive_benchmarks.py` that `pred_label_10 = (prob >= 0.10).astype(int)` evaluates an unweighted **predicted-probability decision threshold of $\hat{p} \ge 0.10$**, NOT a top-10%-ranked cohort selection cutoff.
  - Practical performance: Precision = $0.2318$, Recall = $0.7733$, F1 = $0.3567$.
  - Unweighted enrichment: Evaluated strictly against the unweighted held-out test prevalence ($\bar{y}_{\text{test, unw}} = 0.119840$, $450/3,755$), yielding an unweighted enrichment of **approximately $1.93\text{x}$** ($0.231845 / 0.119840 \approx 1.934\text{x}$). Incompatible mixed-base comparisons against survey-weighted prevalences ($10.51\%$ test, $9.99\%$ train) are completely removed.
  - Clearly contrasted with a top-10% ranked-cohort selection cutoff (where precision $\approx 42\%$, recall $\le 35\%$).
- [x] **Disclosed Model Weaknesses:**
  - Direct dollar prediction: Tweedie GLM achieves $R^2 = 0.0798$ (weighted $0.0832$). Log-transformed models (XGBoost, OLS) underpredict dollar mean by $72.8\%$.
  - Econometric persistence: In longitudinal forecasting (HC-257 Panel 28), lagged Year 1 spending (`TOTEXPY1`) achieves $R^2 = 0.1204$, outperforming static diagnosis-only Tweedie ($R^2 = 0.0652$).
  - Subgroup discrimination: ROC-AUC drops to $0.7466$ on adult SAQ subcohort with functional limitations; poor discrimination in pediatric and uniformly healthy cohorts disclosed.
  - Absence of decision-curve analysis (DCA) explicitly disclosed.
  - Absence of ICD-10-CM codes in public MEPS data files preventing Charlson/Elixhauser index calculation explicitly recorded as a data-driven limitation; superiority claims avoided.
- [x] **External & Prospective Validation:**
  - HC-256 (2024 Cross-Sectional, $N=18,979$): ROC-AUC $0.7828$, PR-AUC $0.3229$, BSS $+0.1266$.
  - HC-257 (2023–2024 Panel 28 Prospective, $N=8,708$): ROC-AUC $0.7807$, PR-AUC $0.3296$, BSS $+0.1263$.
  - Participant overlap between HC-251 and HC-257 explicitly disclosed.

---

## 4. Benchmark Numbers & Provenance Reconciliation

- [x] **Historical Baseline (Class 1):** Commit `944fb0d`, 8 rounds, $24,500$ txs, SHA-256 `af935716155e10e457f593c2bd22ad55776af362c1095bd84a8a76025c856672`. Historical saturation knee at $350.1$ TPS under $1,000$ TPS load ($18.00$s avg latency).
- [x] **Live 11-Round Benchmark (Class 2):** Run `20261018-010200`, 11 rounds, $31,500$ txs, $100\%$ completion across 5 workers, $515.8$ TPS sustained at $615.7$ TPS send rate ($6.98$s latency), $500.3$ TPS read.
- [x] **8-Worker Stress Investigation Runs:**
  - Integer allocation shortfall separated from failures: $25,480$ submitted of $25,500$ configured ($20$-proposal shortfall due to $\lfloor \text{txNumber} / 8 \rfloor \times 8$).
  - Zero reported failures among submitted transactions ($0/25,480$, $0.00\%$ failure rate among submitted proposals).
  - Rate denominators explicit: submitted success rate $= 100.0\%$, configured proposal completion $\approx 99.92\%$.
  - Setup writes: 400 pre-seeding requests in corrected run ($25,880$ total requests).
  - Sustained throughput: $485.27 \pm 14.60$ TPS at $742.70 \pm 62.62$ TPS send rate ($5.36 \pm 0.22$s latency; runs: $470.6$, $499.8$, $485.4$ TPS).
- [x] **Neither $350.1$ nor $515.8$ Portrayed as Universal:** Both documented as environment-specific empirical observations under differing worker concurrency and arrival rates.
- [x] **Single-Identity Client Submission Disclosed:** All transactions submitted under `HospitalOrgAdmin`; does not simulate concurrent multi-organization client generation.
- [x] **Testbed Hardware & Environment Verifiability:** macOS (arm64, Apple Silicon), Docker 29.8.2, Caliper 0.5.0, Fabric 2.4/2.5 on virtualized bridge network. Single-host constraints and lack of physical network latency characterization disclosed.
- [x] **Bootstrap Resample Count Reconciliation:** Manuscript 95% CIs derive from $B=200$ resamples ($n\_boot=200$, seed 42) matching the benchmark registry; older training reports documenting $B=1,000$ resamples reconciled and clearly noted as initial training diagnostics.
- [x] **Stale Roadmap Notices Reconciled:** `MODEL_EXPERIMENT_REPORT.md` and `BLOCKERS_AND_DECISIONS.md` updated to mark HC-256 and HC-257 validation as completed and superseded by `EXTERNAL_VALIDATION_REPORT.md`.

---

## 5. Items Remaining Outside Project Scope (Explicit Limitations)

1. Physical multi-host, wide-area distributed network benchmarking with real cross-data-center network latency and packet loss.
2. Fault-injection testing evaluating active peer node crashes, orderer leader partition, or disk corruption resilience.
3. Decision-curve analysis (DCA) evaluating net clinical benefit across clinical decision thresholds.
4. Standardized Charlson Comorbidity Index or Elixhauser comorbidity scoring (prevented by participant de-identification in MEPS public data files).
5. Actuarial pricing certification, commercial underwriting adequacy, or statutory capital solvency modeling.
6. Comparative privacy benchmarking against encrypted relational database architectures.
7. Clinical trial or hospital-floor validation of drug-abuse prevention efficacy.

---

## 6. Verification Status Summary

| Check / Test | Command Executed | Result |
| :--- | :--- | :---: |
| **Historical Report Integrity** | `shasum -a 256 caliper-benchmark/report.html` | `af935716155e10e457f593c2bd22ad55776af362c1095bd84a8a76025c856672` (PASS) |
| **Live Artifact Verifier (11-Round)** | `python3 caliper-benchmark/verify_benchmark_artifacts.py caliper-benchmark/results/live/20261018-010200` | PASS (100% byte-for-byte reconciliation across all 11 rounds) |
| **Live Artifact Verifier (Stress)** | `python3 caliper-benchmark/verify_benchmark_artifacts.py caliper-benchmark/results/live/20261018-230500_stress_investigation` | PASS (100% byte-for-byte reconciliation across all 7 rounds, accounting verified) |
| **Caliper Test Suite** | `pytest caliper-benchmark/tests/ -v` | 23 / 23 tests PASSED |
| **Git Diff Whitespace Check** | `git diff --check` | 0 errors |

**Integrity Verdict:** **VERIFIED & RECONCILED — Manuscript Version 3.1 is aligned with empirical evidence, transparently qualified, and ready for review.**
