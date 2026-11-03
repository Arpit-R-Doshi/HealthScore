# Phase 6: Final Research & Submission Readiness Audit (`FINAL_RESEARCH_AUDIT.md`)

**Project:** HealthScore — CRC Paper Evidence Enhancement, Threshold Analysis & Controlled Revision
**Branch:** `feature/ml-pipeline-rebuild` (`master` untouched)
**Deliverables Directory:** [`research_completion/crc_revision/`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision)

---

## 1. Why Was Precision Low ($23.18\%$) at Threshold $\tau = 0.10$?

Our six-factor empirical diagnostic investigation ([`THRESHOLD_SENSITIVITY_REPORT.md`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/THRESHOLD_SENSITIVITY_REPORT.md)) establishes that the $23.18\%$ precision at $\tau = 0.10$ is **not** caused by model overfitting or probability miscalibration, but by four interacting mathematical and domain mechanisms:
1. **Theoretical Volume-Ceiling Bound (Primary Direct Cause):** Setting $\tau = 0.10$ flags $39.97\%$ of the held-out test cohort ($1,501 / 3,755$ patients). Because only $P = 450$ true high-expenditure patients ($\ge \$17,827.41$) exist in the entire test cohort ($11.98\%$), **even a hypothetical perfect oracle classifier ($\text{ROC-AUC} = 1.00$, $100\%$ recall) that flags $1,501$ patients is mathematically bounded by $\text{Precision}_{\text{oracle}} = 450 / 1,501 = 29.98\%$**. Capturing $348$ true positives at $\tau = 0.10$ yields $348 / 1,501 = 23.18\%$ precision, which is **$77.33\%$ of the theoretical maximum precision possible at a $40\%$ screening volume**.
2. **Class Imbalance & Bayes Base-Rate Conditioning:** With an unweighted positive prevalence of $\pi = 11.984\%$ ($10.506\%$ survey-weighted), non-high-cost individuals outnumber high-cost individuals by $7.344 : 1$ ($8.518 : 1$ weighted). Operating at $77.33\%$ recall and $65.11\%$ specificity ($\text{FPR} = 34.89\%$) inevitably produces $3,305 \times 0.3489 = 1,153$ false positives.
3. **Well-Calibrated Intermediate Probability Concentration:** More than half ($53.9\%$, $809 / 1,501$) of all patients flagged at $\tau = 0.10$ reside in the $[0.10, 0.20)$ probability band, where the model's mean predicted risk is $14.5\%$ and the actual observed event rate is $16.9\%$ ($137 / 809$). Because the model is well-calibrated (`Weighted BSS = +0.1025`, `Unweighted Brier = 0.0936`), assigning binary `1` to patients whose true event probability is $\sim 15\%$ converts the remaining $\sim 85\%$ into false positives.
4. **Overfitting Conclusively Refuted & Feature Granularity Ceiling Quantified:** Across 7 internal and external evaluation splits—including 5-Fold Stratified OOF (`ROC-AUC = 0.7795`), 5-Fold Household (`DUID`) OOF (`ROC-AUC = 0.7785`), and the **100% unseen 2024 `HC-256` Panel 29 cohort ($N=10,037$, `ROC-AUC = 0.7824`, `PR-AUC = 0.3506`)**—generalization is rock-solid. The remaining discrimination ceiling (`0.7654` Logistic vs. `0.7662` Tuned XGBoost, DeLong $p > 0.78$) reflects the absence of concurrent utilization proxies (`IPNGTD`, `ERTOT`, `OBTOTV`, `RXTOT`) and clinical lab severity biomarkers during cold-start intake.

---

## 2. How Does Performance Change Across Thresholds $\tau = 0.10$ to $0.90$?

Holding the fitted classifier (`risk_model_classifier_observable_weighted_p90.pkl`) strictly fixed ([`threshold_comparison_test.csv`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/results/threshold_comparison_test.csv)):
- **$\tau = 0.05$ (Intermediate Ultra-Wide Screening):** Flags $60.75\%$ ($2,281$); Precision $= 17.58\%$ ($1.47\times$), Recall $= 89.11\%$, F1 $= 0.2936$, Specificity $= 43.12\%$, Balanced Accuracy $= 0.6611$ ($1,880\text{ FP}, 49\text{ FN}$).
- **$\tau = 0.10$ (Reference High-Sensitivity Screening):** Flags $39.97\%$ ($1,501$); Precision $= 23.18\%$ ($1.93\times$; Weighted $22.54\%$), Recall $= 77.33\%$ (Weighted $71.93\%$), F1 $= 0.3567$ (Weighted $0.3433$), Specificity $= 65.11\%$, **Balanced Accuracy $= 0.7122$ (Maximum)** ($1,153\text{ FP}, 102\text{ FN}$).
- **$\tau = 0.15$ (Fine-Grid F1 Peak):** Flags $28.02\%$ ($1,052$); Precision $= 26.71\%$ ($2.23\times$), Recall $= 62.44\%$, **Unweighted F1 $= 0.3742$ (Weighted F1 $= 0.3625$)**, Specificity $= 76.67\%$, Balanced Accuracy $= 0.6956$ ($771\text{ FP}, 169\text{ FN}$).
- **$\tau = 0.20$ (Validation Primary-Grid F1-Optimal Triage):** Flags $18.43\%$ ($692$); **Precision $= 30.49\%$ ($2.54\times$; Weighted $30.73\%$)**, Recall $= 46.89\%$, **F1 $= 0.3695$ (Primary-Grid Peak; Val F1 $= 0.3846$)**, Specificity $= 85.45\%$, Balanced Accuracy $= 0.6617$ ($481\text{ FP}$ — **a $58.28\%$ reduction in false positives** vs. $\tau=0.10$, $239\text{ FN}$). On unseen 2024 Panel 29 ($N=10,037$), $\tau=0.20$ achieves $33.91\%$ precision, $50.16\%$ recall, and $0.4046$ F1.
- **$\tau = 0.25$ (Precision–Recall Breakeven):** Flags $11.72\%$ ($440$); Precision $= 35.00\%$ ($2.92\times$), Recall $= 34.22\%$, F1 $= 0.3461$, Specificity $= 91.35\%$ ($286\text{ FP} \approx 296\text{ FN}$).
- **$\tau = 0.30$ (Targeted Intensive Case Management):** Flags $7.59\%$ ($285$); **Precision $= 40.00\%$ ($3.34\times$; $43.49\%$ on 2024 Panel 29)**, Recall $= 25.33\%$, F1 $= 0.3102$, **Specificity $= 94.83\%$** ($171\text{ FP}$ — **an $85.17\%$ reduction in false positives**, $336\text{ FN}$).
- **$\tau = 0.40$:** Flags $2.77\%$ ($104$); Precision $= 44.23\%$ ($3.69\times$), Recall $= 10.22\%$, F1 $= 0.1661$, Specificity $= 98.25\%$ ($58\text{ FP}, 404\text{ FN}$).
- **$\tau = 0.50$ to $0.90$ (High-Cutoff Recall Collapse):** Because calibrated probabilities are bounded by $\max(\hat{p}_{\text{test}}) = 0.8008$, $\tau = 0.50$ flags only $36$ patients ($0.96\%$, Recall $= 3.33\%$, F1 $= 0.0617$), $\tau = 0.60$ flags $7$ (Recall $= 1.33\%$), $\tau = 0.70$ flags $2$ (Recall $= 0.44\%$), $\tau = 0.80$ flags $1$ (Recall $= 0.22\%$), and $\tau = 0.90$ flags $0$ patients (Recall $= 0.00\%$).

---

## 3. What Is the Best Threshold (or Set of Operating Thresholds) and Why?

Selected strictly on leak-free **5-Fold Out-of-Fold (OOF) validation ($N=15,016$)**, we recommend presenting a **three-tier operational decision framework** rather than a single static cutoff:
1. **Tier 1 ($\tau = 0.10$ — Broad Preventive Screening / Max Balanced Accuracy $= 0.7122$):** Retain as the high-sensitivity baseline ($77.33\%$ recall, $23.18\%$ precision, $1.93\times$ enrichment) for low-cost digital outreach and actuarial tail monitoring.
2. **Tier 2 ($\tau = 0.20$ — Care-Management Triage / Validation Primary-Grid F1-Optimal):** Present as the primary balanced operating point ($30.49\%$ test precision [$2.54\times$ enrichment], $46.89\%$ recall, $85.45\%$ specificity, $0.3695$ F1, cutting false positives by $58.3\%$; with $\tau = 0.15$ noted as the fine-grid F1 peak at $0.3742$).
3. **Tier 3 ($\tau = 0.30$ — High-Specificity Intensive Intervention):** Present for capacity-constrained nurse case management ($40.00\%$ precision [$3.34\times$ enrichment], $94.83\%$ specificity, $25.33\%$ recall, flagging the top $7.59\%$ of patients and cutting false positives by $85.2\%$).

---

## 4. Which Reviewer Concerns Were Fully Resolved by Experiments?

- **Low precision at $\tau = 0.10$ & threshold trade-off (`R1.1`, `R1.2`, `R1.4`):** Fully resolved via the 12-threshold fixed-model sweep (`0.05`–`0.90`) on 5-Fold Stratified OOF, 5-Fold Household (`DUID`) OOF, Held-Out Test, and Unseen 2024 Panel 29, plus the 6-factor diagnostic audit (`Figures T1–T5`).
- **Target-proxy circularity (`R2.1`) & zero-expenditure selection bias (`R3.1`):** Fully resolved by the 17-configuration ablation study (`Ab-01`–`Ab-17`) and 9-model benchmark (`Table II`, `Figure 4`).
- **Household (`DUID`) clustering & `HC-256` Panel 28 overlap (`R2.4`, `R2.5`):** Fully resolved by running 5-fold `GroupKFold(groups=DUID)` validation (`ROC-AUC = 0.7785`) and isolating the 100% unseen `HC-256` Panel 29 cohort ($N=10,037$, `ROC-AUC = 0.7824`).
- **Actuarial tail risk & Gamma underestimation (`R5.1`, `R5.2`):** Fully resolved via the $10,000$-iteration empirical bootstrap Monte Carlo simulation (`Table V`, `Figure 6`).

---

## 5. Which Reviewer Concerns Required Text / Methodology Clarification?

- **Unweighted ($11.98\%$) vs. Survey-Weighted ($10.51\%$) Prevalence & Enrichment Ratios (`R1.3`, `R3.2`, `R3.3`):** Clarified how `PERWT23F` defines the $\$17,827.41$ cutoff and reported both unweighted ($1.93\times$ at $\tau=0.10$, $2.54\times$ at $\tau=0.20$, $3.34\times$ at $\tau=0.30$) and survey-weighted ($2.15\times$, $2.93\times$, $3.73\times$) metrics.
- **Off-Chain ML Inference vs. On-Chain SHA-256 Provenance (`R4.1`):** Clarified throughout the manuscript that Python ML inference runs off-chain while Go smart contracts anchor cryptographic hashes and enforce premium rebate rules on-chain.
- **Synthetic Queueing Model vs. Empirical Caliper Benchmarks (`R4.2`, `R4.3`):** Clarified in `Table IV` and `Figure 5b` that P5–P95 intervals across 100 seeds describe synthetic fluid-queueing model sensitivity rather than physical network confidence intervals.

---

## 6. Which Claims Were Corrected, Qualified, or Removed?

- **Corrected:** Replaced the circular $R^2 = 0.7538$ claim from `old paper.pdf` with the leak-free intake-observable Tweedie GLM $R^2 = 0.1257$ (and longitudinal lagged $R^2 = 0.2581$, `ROC-AUC = 0.8407`), retaining the 15-feature concurrent utilization model strictly as a labeled retrospective benchmark.
- **Corrected:** Replaced imprecise descriptions of `HC-256` ($N=18,979$) as wholly disjoint with the exact rotating panel breakdown ($8,775$ Panel 28 overlap vs. $N=10,037$ strictly unseen Panel 29).
- **Qualified:** Scoped all Hyperledger Caliper throughput/latency claims to a single-host Docker deployment (`2Org2Peer` Raft + LevelDB) and framed actuarial solvency results as empirical Monte Carlo bootstrap simulations under explicit elasticity assumptions.
- **Removed:** Completely removed the unsupported `0.85 ms` blockchain latency claim and unimplemented Zero-Knowledge Proof (ZKP) claims from the main architecture (moving ZKPs strictly to Future Work).

---

## 7. What Limitations Still Remain?

1. Cold-start intake survey variables lack clinical laboratory biomarkers (e.g., HbA1c, eGFR) and cannot predict stochastic acute trauma/surgical emergencies among zero-comorbidity adults ($10.22\%$ of high-cost cases), bounding intake-observable $R^2$ at $0.1257$.
2. Empirical Hyperledger Caliper benchmarks reflect a single-host Docker test network rather than a multi-region WAN cloud deployment.
3. The actuarial Monte Carlo simulation assumes a uniform $10\%$ preventative cost reduction among compliant wellness participants rather than condition-specific clinical trial elasticities.

---

## 8. Is the Revised Paper Ready for CRC Submission?

**Yes — Ready for CRC Camera-Ready Submission.**
- All experimental scripts, CSV tables, JSON registries, Markdown reports, editable Markdown/LaTeX manuscripts, and compiled PDFs (`research_completion/crc_revision/latex/final_crc_paper.pdf`) are complete, verified, and self-consistent.
- All 7 original authors and affiliations from `old paper.pdf` are preserved and formatted properly.
- All 12 figures in `research_completion/crc_revision/figures/` are verified at **$600.0 \times 600.0\text{ DPI}$** (`> 500 DPI`) with vector `.pdf` counterparts and zero visual overlaps.
- Original files (`old paper.pdf`, `research_completion/paper/REVISED_PAPER.md`, and `master` branch) remain completely untouched.
