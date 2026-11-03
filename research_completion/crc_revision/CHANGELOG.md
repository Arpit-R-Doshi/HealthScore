# Controlled Revision Change Log (`CHANGELOG.md`)

**Project:** HealthScore — CRC Paper Evidence Enhancement & Controlled Revision
**Branch:** `feature/ml-pipeline-rebuild`
**Original Baseline Manuscript:** `/Users/arpitdoshi/Desktop/ipd/HealthScore/old paper.pdf`
**Revised CRC Deliverables:** [`REVISED_CRC_PAPER.md`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/REVISED_CRC_PAPER.md), [`latex/main.tex`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/latex/main.tex), and [`latex/final_crc_paper.pdf`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/latex/final_crc_paper.pdf)

---

## Summary of Controlled Revision Philosophy

In accordance with the CRC controlled revision protocol, this revision **preserves the original paper's research identity, two-stage ML + permissioned Hyperledger Fabric + dynamic actuarial pricing architecture, section organization, and exact 7-author block**, while incorporating rigorous probability threshold sensitivity evidence (`Phase 1`), resolving reviewer criticisms (`Phase 2`), correcting unsupported or circular claims (`Phase 3 & 4`), and rendering all figures at **$600\text{ DPI}$** (`> 500 DPI` requirement).

---

## Section-by-Section Summary of Substantive Changes

### 1. Title & Author Block
- **Preserved Exact Original Author Identity:** Retained the exact 7 authors and affiliations from `old paper.pdf`:
  - `Arpit Doshi*, Dhruv Gandhi*, Harshkumar Padhiyar*, Hetam Patel*, Stevina Correia†, Monali Sankhe† and Monika Mangla†`
  - `*Department of Information Technology, Dwarkadas J. Sanghvi College of Engineering, Mumbai, India`
  - `†Department of Information Technology (Professor), Dwarkadas J. Sanghvi College of Engineering, Mumbai, India`
- **Refined Title:** Updated from *"HealthScore: A Blockchain-Integrated Dynamic Healthcare Pricing Model"* to *"HealthScore: A Blockchain-Anchored Healthcare Risk Stratification and Actuarial Pricing Framework"* to accurately reflect the off-chain ML + on-chain SHA-256 provenance architecture and two-stage clinical risk stratification pipeline.

### 2. Abstract
- **Added Multi-Cohort MEPS Provenance:** Specified all three AHRQ MEPS releases evaluated: `HC-251` (2023 Full-Year Consolidated, $N=18,771$), `HC-256` (2024 Full-Year Consolidated, $N=18,979$, explicitly isolating the strictly unseen 2024 Panel 29 cohort of $N=10,037$), and `HC-257` (Panel 28 Two-Year Longitudinal file, $N=8,708$).
- **Added Phase 1 Threshold Sensitivity Results:** Reported the leak-free 5-fold Out-of-Fold (OOF) validated probability threshold sweep across $\tau \in [0.05, 0.90]$, contrasting the reference screening cutoff ($\tau = 0.10$: Balanced Accuracy $= 0.7122$, Recall $= 77.33\%$, Precision $= 23.18\%$ [$1.93\times$ base rate, achieving $77.3\%$ of the $29.98\%$ oracle volume ceiling]) against the validation F1-optimal triage cutoff ($\tau = 0.20$: Precision $= 30.49\%$ [$2.54\times$ enrichment; $33.91\%$ on unseen 2024 Panel 29], Recall $= 46.89\%$, F1 $= 0.3695$, false positives reduced by $58.3\%$) and the targeted case-management cutoff ($\tau = 0.30$: Precision $= 40.00\%$ [$3.34\times$ enrichment], Specificity $= 94.83\%$, false positives reduced by $85.2\%$).
- **Replaced Circular Regression & Overclaimed Latency Numbers:** Replaced the circular $R^2 = 0.7538$ and unsupported `0.85 ms` blockchain latency from `old paper.pdf` with the verified intake-observable Tweedie GLM performance ($R^2 = 0.1257$, $\text{MAE} = \$6,462$; longitudinal lagged $R^2 = 0.2581$, $\text{ROC-AUC} = 0.8407$), verified Caliper throughput/latency ($586.5\text{ TPS}$ at $6.0\text{ ms}$ for reads; $181.6\text{--}315.4\text{ TPS}$ for writes), and empirical bootstrap $\text{VaR}_{99}$ / $\text{TVaR}_{99}$ solvency simulation.

### 3. Section I (Introduction) & Section II (Related Work)
- **Explicitly Formulated Three Core Domain Problems:** (1) Simultaneous-year target-proxy circularity in MEPS expenditure prediction, (2) rigid single-threshold classification under $\sim 10\%$ class imbalance, and (3) opaque risk scoring vs. privacy-preserving off-chain ML / on-chain blockchain provenance.
- **Expanded Related Work:** Added peer-reviewed foundations on exponential dispersion Tweedie GLMs (Tweedie 1984, Jørgensen 1987), Precision–Recall evaluation under class imbalance (Saito & Rehmsmeier 2015, Davis & Goadrich 2006), paired DeLong ROC comparison (DeLong et al. 1988), and permissioned healthcare blockchains (Androulaki et al. 2018, Azaria et al. 2016, Kuo et al. 2017).

### 4. Section III (Methodology & System Architecture)
- **Zero-Expenditure Retention (`N = 18,771` vs. `N = 16,106`):** Documented why retaining all $2,665$ zero-expenditure adults ($14.20\%$) in `MEPS HC-251` prevents upward selection bias.
- **Multi-Release & Household (`DUID`) Overlap Disclosure:** Documented the exact rotating panel structure of `MEPS HC-256` (Panel 28 overlap of $8,775$ individuals with `HC-251` vs. 100% unseen Panel 29 of $N=10,037$) and the household dwelling unit (`DUID`) sharing across `HC-251` splits, introducing both Stratified 5-Fold OOF and Household-Grouped (`GroupKFold` by `DUID`) 5-Fold OOF validation.
- **Survey-Weighted 90th Percentile Target Construction:** Explained how `PERWT23F` survey weighting on the training split ($N=15,016$) defines the $\$17,827.41$ high-cost threshold (vs. $\$19,927.30$ unweighted P90) and why unweighted sample prevalence is $11.98\%$ ($450/3,755$) while survey-weighted US population prevalence is $10.51\%$.
- **Off-Chain ML Inference vs. On-Chain Go Chaincode Provenance:** Clarified that ML inference runs off-chain in Python while SHA-256 cryptographic commitments and deterministic premium rebate transitions execute on-chain in Hyperledger Fabric v2.5 Go chaincode.

### 5. Section IV-A (Comprehensive Nine-Model Benchmark)
- **Added Complete 9-Model Table (`Table II`):** Reported all 3 Stage-1 classifiers, 6 Stage-2 regressors, and the prospective lagged utilization models on `HC-257` ($N=8,708$) with $1,000$-iteration bootstrap $95\%$ CIs and explicit paired statistical test disclosures (DeLong test for ROC-AUC, paired bootstrap for PR-AUC/Brier, Wilcoxon signed-rank test on absolute errors for MAE).

### 6. Section IV-B (NEW: Classification Probability Threshold Sensitivity Analysis & Root-Cause Investigation)
- **Added Full 12-Threshold Evaluation Table (`Table III`) & 5 New $600\text{ DPI}$ Figures (`Figures T1–T5`):**
  - Evaluated $\tau \in \{0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90\}$ on 5-Fold OOF Validation ($N=15,016$), `HC-251` Held-Out Test ($N=3,755$), and Unseen 2024 Panel 29 ($N=10,037$).
  - Added mathematical derivation and visual plot (`Figure T2-B`) of the **Theoretical Oracle Precision Ceiling at Flagged Volume** ($\frac{450}{1,501} = 29.98\%$ at $\tau = 0.10$).
  - Added the **Six-Factor Root-Cause Investigation** covering: (1) Threshold sensitivity & volume ceiling, (2) Class imbalance & Bayes base-rate odds ($7.34:1$), (3) Model discrimination ceiling (`Logistic 0.7654` vs. `XGBoost 0.7662`), (4) Probability calibration & $[0.10, 0.20)$ bin concentration, (5) 7-cohort overfitting refutation (`Figure T5-B`), and (6) Intake-observable feature granularity & acute vs. chronic expenditure variance.
  - Formulated the **Three-Tier Operational Threshold Framework** ($\tau = 0.10$ for broad screening, $\tau = 0.20$ for F1-optimal care-management triage, $\tau = 0.30$ for high-specificity targeted intervention).

### 7. Section IV-C, IV-D, IV-E & Section V (Ablations, Blockchain, Actuarial Simulation & Limitations)
- **17 Feature Ablations (`Figure 4`):** Documented `Ab-01` through `Ab-17`.
- **Hyperledger Fabric v2.5 Benchmarks (`Table IV`, `Figure 5`, `Figure 5b`):** Reported historical empirical baseline, live 5-worker rerun, and corrected 8-worker stress run alongside discrete synthetic fluid-queueing sensitivity bounds (`P5–P95` across 100 seeds at `50, 100, 200, 350, 1000` TPS), explicitly distinguishing synthetic model percentiles from empirical measurements.
- **Empirical Bootstrap Actuarial Simulation (`Table V`, `Figure 6`):** Replaced unconditional "zero insolvency proof" language with $10,000$-iteration Monte Carlo bootstrap $\text{VaR}_{99}$ and $\text{TVaR}_{99}$ estimates and quantified the $\$1.032\text{M}$ tail-risk underestimation of naive parametric Gamma approximations.
