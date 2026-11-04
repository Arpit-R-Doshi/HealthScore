# Phase 1 Technical Report: Classification Probability Threshold Sensitivity & Diagnostic Analysis

**Project:** HealthScore — CRC Paper Evidence Enhancement & Controlled Revision
**Branch:** `feature/ml-pipeline-rebuild`
**Model Audited:** `ml_model/artifacts/risk_model_classifier_observable_weighted_p90.pkl` (`SHA-256: 3632f8201136a2740c3d5a564bbdbb29bc8511db51709fb42c1f8e271bf28c2a`)
**Reproducible Experiment Script:** [`experiments/run_threshold_sensitivity_analysis.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/experiments/run_threshold_sensitivity_analysis.py)
**Machine-Readable Registry:** [`results/threshold_analysis_complete_registry.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/results/threshold_analysis_complete_registry.json)

---

## 1. Executive Summary & Verification of Baseline Reference Metrics

In the HealthScore machine learning pipeline, the approved serving classifier is an 11-feature Observable Logistic Regression (Weighted Fit, `LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, random_state=42)`) trained on the 11 intake-observable demographic and ACG-inspired chronic-condition features from the 2023 Medical Expenditure Panel Survey (`MEPS HC-251`, $N=18,771$ eligible individuals; $80\%$ training split $N=15,016$, $20\%$ held-out test split $N=3,755$). The binary target (`Target 2`) identifies individuals exceeding the survey-weighted 90th percentile of annual healthcare expenditure ($\text{TOTEXP23} \ge \$17,827.41$, computed strictly on the training split using `PERWT23F` weights).

Before conducting the threshold sensitivity sweep, we verified all baseline metrics reported for the reference probability threshold ($\tau = 0.10$) directly against the frozen serving artifact on the held-out test partition ($N=3,755$):

| Baseline Metric (`HC-251` Held-Out Test, $N=3,755$) | Reported Value | Verified Exact Value (Unweighted) | Verified Exact Value (Survey-Weighted `PERWT23F`) | Verification Status |
| :--- | :---: | :---: | :---: | :---: |
| **Positive Class Cutoff ($\text{P90}_{\text{wtd}}$)** | $\$17,827.41$ | $\$17,827.41$ | $\$17,827.41$ | **Exact Match** |
| **Cohort Positive Prevalence ($\pi$)** | $11.98\%$ ($450/3,755$) | $11.9840\%$ ($450/3,755$) | $10.5134\%$ | **Exact Match** |
| **ROC-AUC (Threshold-Independent)** | $0.7654$ | $0.7654$ $[0.7444, 0.7881]$ | $0.7509$ | **Exact Match** |
| **PR-AUC (Threshold-Independent)** | $0.3184$ | $0.3184$ $[0.2876, 0.3556]$ | $0.2966$ | **Exact Match** |
| **Brier Score** | $0.0936$ (Unw) / $0.0845$ (Wtd) | $0.0936$ | $0.0845$ | **Exact Match** |
| **Brier Skill Score (BSS vs. Null)** | $+0.1025$ (Wtd) | $+0.1160$ (Null $= 0.1059$) | $+0.1025$ (Null $= 0.0941$) | **Exact Match** |
| **Precision (PPV) at $\tau = 0.10$** | $23.18\%$ | $23.18\%$ ($348 / 1,501$) | $22.54\%$ | **Exact Match** |
| **Recall (Sensitivity) at $\tau = 0.10$** | $77.33\%$ | $77.33\%$ ($348 / 450$) | $71.93\%$ | **Exact Match** |
| **F1-Score at $\tau = 0.10$** | $0.3567$ | $0.3567$ | $0.3433$ | **Exact Match** |
| **Specificity (TNR) at $\tau = 0.10$** | $65.11\%$ | $65.11\%$ ($2,152 / 3,305$) | $70.96\%$ | **Exact Match** |
| **Balanced Accuracy at $\tau = 0.10$** | $0.7122$ | $0.7122$ | $0.7145$ | **Exact Match** |
| **Prevalence Enrichment Ratio at $\tau = 0.10$** | $1.93\times$ | $1.9346\times$ ($23.18\% / 11.98\%$) | $2.14\times$ ($22.54\% / 10.51\%$) | **Exact Match** |

---

## 2. Experimental Methodology & Leak-Free Threshold Selection Protocol

### 2.1 Fixed-Model Isolation Principle
To isolate the effect of the classification decision boundary $\tau$ from model retraining variance, **no model retraining was performed across thresholds for test or external evaluation**. The frozen serving classifier (`risk_model_classifier_observable_weighted_p90.pkl`) outputs continuous predicted probabilities $\hat{p}_i = P(y_i = 1 \mid \mathbf{x}_i) \in (0, 1)$, and binary predictions are generated purely via $\hat{y}_i(\tau) = \mathbb{I}(\hat{p}_i \ge \tau)$ across:
- **Primary Threshold Grid:** $\tau \in \{0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90\}$
- **Intermediate Diagnostic Thresholds:** $\tau \in \{0.05, 0.15, 0.25\}$

### 2.2 Leak-Free Validation Strategy (5-Fold Out-of-Fold Validation)
Because `split_data()` in [`ml_model/data_pipeline.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/data_pipeline.py) partitions `MEPS HC-251` ($N=18,771$) into an $80\%$ training set ($N=15,016$, $P=1,736$) and a $20\%$ held-out test set ($N=3,755$, $P=450$) without a separate validation split, selecting an operating threshold on the held-out test set would constitute test leakage. Instead, we implemented **5-Fold Out-of-Fold (OOF) cross-validation strictly within the training split ($N=15,016$)** using identical model hyperparameters (`LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, random_state=42)`) and normalized survey weights (`w_train_norm`):
1. **Stratified 5-Fold OOF Validation (`StratifiedKFold`, $N=15,016$):** Preserves the exact training positive class ratio across folds (OOF Unweighted ROC-AUC $= 0.7795$, Weighted ROC-AUC $= 0.7674$, Unweighted PR-AUC $= 0.3260$).
2. **Household-Clustered 5-Fold OOF Validation (`GroupKFold` by dwelling unit `DUID`, $N=15,016$):** Places all members of the same household (`DUID`) into the same validation fold to audit whether shared household membership inflates performance (Household OOF Unweighted ROC-AUC $= 0.7785$, Weighted ROC-AUC $= 0.7660$, Unweighted PR-AUC $= 0.3247$ — virtually identical to stratified OOF, $\Delta\text{ROC-AUC} = -0.0010$).

All threshold optima (maximum Balanced Accuracy, maximum F1-score, and high-specificity targeted triage) are selected exclusively on the **5-Fold OOF validation predictions ($N=15,016$)** and subsequently evaluated on:
- **`HC-251` Held-Out Test Set ($N=3,755$, $P=450$)**
- **`HC-256` 2024 Panel 29 Unseen External Cohort ($N=10,037$, $P=1,258$)** — the newly enrolled 2024 MEPS panel that has **zero person (`DUPERSID`) and zero household (`DUID`) overlap** with `HC-251`.

---

## 3. Comprehensive Threshold Comparison Results

### 3.1 Leak-Free 5-Fold Stratified OOF Validation ($N=15,016$, Actual High-Cost $P=1,736$, Unweighted Prev $= 11.56\%$, Weighted Prev $= 9.99\%$)
Full CSV: [`results/threshold_comparison_validation_oof.csv`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/results/threshold_comparison_validation_oof.csv)

| Threshold ($\tau$) | Grid Type | TP | FP | TN | FN | Flagged ($N$ / Unw %) | Unw Precision (%) | Unw Recall (%) | Unw F1-Score | Unw Specificity (%) | Unw NPV (%) | Unw Bal. Acc. | Unw Enrich. Ratio | Oracle Max Prec. at Vol. (%) | Wtd Precision (%) | Wtd Recall (%) | Wtd F1-Score | Wtd Bal. Acc. |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.05** | Interm. | 1,561 | 7,432 | 5,848 | 175 | 8,993 (59.89%) | 17.36% | 89.92% | 0.2910 | 44.04% | 97.09% | 0.6698 | $1.50\times$ | 19.30% | 15.62% | 86.04% | 0.2644 | 0.6723 |
| **0.10** | **Primary (Ref)** | **1,342** | **4,550** | **8,730** | **394** | **5,892 (39.24%)** | **22.78%** | **77.30%** | **0.3519** | **65.74%** | **95.68%** | **0.7152** | **$1.97\times$** | **29.46%** | **21.51%** | **70.60%** | **0.3297** | **0.7101** |
| **0.15** | Interm. | 1,095 | 2,938 | 10,342 | 641 | 4,033 (26.86%) | 27.15% | 63.08% | 0.3796 | 77.88% | 94.16% | 0.7048 | $2.35\times$ | 43.04% | 25.94% | 55.11% | 0.3528 | 0.6883 |
| **0.20** | **Primary (F1-Opt)** | **872** | **1,916** | **11,364** | **864** | **2,788 (18.57%)** | **31.28%** | **50.23%** | **0.3855** | **85.57%** | **92.93%** | **0.6790** | **$2.71\times$** | **62.27%** | **30.24%** | **43.01%** | **0.3551** | **0.6600** |
| **0.25** | Interm. | 670 | 1,175 | 12,105 | 1,066 | 1,845 (12.29%) | 36.31% | 38.59% | 0.3742 | 91.15% | 91.91% | 0.6487 | $3.14\times$ | 94.09% | 35.19% | 32.17% | 0.3361 | 0.6280 |
| **0.30** | **Primary (Targeted)** | **464** | **704** | **12,576** | **1,272** | **1,168 (7.78%)** | **39.73%** | **26.73%** | **0.3196** | **94.70%** | **90.81%** | **0.6071** | **$3.44\times$** | **100.00%** | **38.37%** | **22.27%** | **0.2818** | **0.5915** |
| **0.40** | Primary | 208 | 236 | 13,044 | 1,528 | 444 (2.96%) | 46.85% | 11.98% | 0.1908 | 98.22% | 89.51% | 0.5510 | $4.05\times$ | 100.00% | 46.04% | 10.04% | 0.1648 | 0.5437 |
| **0.50** | Primary | 81 | 76 | 13,204 | 1,655 | 157 (1.05%) | 51.59% | 4.67% | 0.0856 | 99.43% | 88.86% | 0.5205 | $4.46\times$ | 100.00% | 49.86% | 4.00% | 0.0740 | 0.5177 |
| **0.60** | Primary | 33 | 19 | 13,261 | 1,703 | 52 (0.35%) | 63.46% | 1.90% | 0.0369 | 99.86% | 88.62% | 0.5088 | $5.49\times$ | 100.00% | 58.44% | 1.57% | 0.0306 | 0.5072 |
| **0.70** | Primary | 6 | 3 | 13,277 | 1,730 | 9 (0.06%) | 66.67% | 0.35% | 0.0069 | 99.98% | 88.47% | 0.5016 | $5.77\times$ | 100.00% | 66.63% | 0.32% | 0.0064 | 0.5015 |
| **0.80** | Primary | 1 | 1 | 13,279 | 1,735 | 2 (0.01%) | 50.00% | 0.06% | 0.0012 | 99.99% | 88.44% | 0.5003 | $4.32\times$ | 100.00% | 44.99% | 0.07% | 0.0014 | 0.5003 |
| **0.90** | Primary | 0 | 0 | 13,280 | 1,736 | 0 (0.00%) | 0.00% | 0.00% | 0.0000 | 100.00% | 88.44% | 0.5000 | $0.00\times$ | — | 0.00% | 0.00% | 0.0000 | 0.5000 |

---

### 3.2 `HC-251` Held-Out Test Set ($N=3,755$, Actual High-Cost $P=450$, Unweighted Prev $= 11.98\%$, Weighted Prev $= 10.51\%$)
Full CSV: [`results/threshold_comparison_test.csv`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/results/threshold_comparison_test.csv)

| Threshold ($\tau$) | Grid Type | TP | FP | TN | FN | Flagged ($N$ / Unw %) | Unw Precision (%) | Unw Recall (%) | Unw F1-Score | Unw Specificity (%) | Unw NPV (%) | Unw Bal. Acc. | Unw Enrich. Ratio | Oracle Max Prec. at Vol. (%) | Wtd Precision (%) | Wtd Recall (%) | Wtd F1-Score | Wtd Bal. Acc. |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.05** | Interm. | 401 | 1,879 | 1,426 | 49 | 2,280 (60.72%) | 17.59% | 89.11% | 0.2938 | 43.15% | 96.68% | 0.6613 | $1.47\times$ | 19.74% | 15.98% | 83.59% | 0.2682 | 0.6597 |
| **0.10** | **Primary (Ref)** | **348** | **1,153** | **2,152** | **102** | **1,501 (39.97%)** | **23.18%** | **77.33%** | **0.3567** | **65.11%** | **95.47%** | **0.7122** | **$1.93\times$** | **29.98%** | **22.54%** | **71.93%** | **0.3433** | **0.7145** |
| **0.15** | Interm. | 281 | 771 | 2,534 | 169 | 1,052 (28.02%) | 26.71% | 62.44% | **0.3742** | 76.67% | 93.75% | 0.6956 | $2.23\times$ | 42.78% | 26.09% | 54.32% | **0.3525** | 0.6812 |
| **0.20** | **Primary (F1-Opt)** | **211** | **481** | **2,824** | **239** | **692 (18.43%)** | **30.49%** | **46.89%** | **0.3695** | **85.45%** | **92.20%** | **0.6617** | **$2.54\times$** | **65.03%** | **30.73%** | **40.23%** | **0.3485** | **0.6479** |
| **0.25** | Interm. | 154 | 286 | 3,019 | 296 | 440 (11.72%) | 35.00% | 34.22% | 0.3461 | 91.35% | 91.07% | 0.6278 | $2.92\times$ | 100.00% | 35.04% | 29.25% | 0.3188 | 0.6144 |
| **0.30** | **Primary (Targeted)** | **114** | **171** | **3,134** | **336** | **285 (7.59%)** | **40.00%** | **25.33%** | **0.3102** | **94.83%** | **90.32%** | **0.6008** | **$3.34\times$** | **100.00%** | **40.10%** | **21.72%** | **0.2818** | **0.5895** |
| **0.40** | Primary | 46 | 58 | 3,247 | 404 | 104 (2.77%) | 44.23% | 10.22% | 0.1661 | 98.25% | 88.93% | 0.5423 | $3.69\times$ | 100.00% | 43.25% | 8.33% | 0.1397 | 0.5352 |
| **0.50** | Primary | 15 | 21 | 3,284 | 435 | 36 (0.96%) | 41.67% | 3.33% | 0.0617 | 99.36% | 88.30% | 0.5135 | $3.48\times$ | 100.00% | 37.12% | 2.52% | 0.0472 | 0.5101 |
| **0.60** | Primary | 6 | 1 | 3,304 | 444 | 7 (0.19%) | 85.71% | 1.33% | 0.0263 | 99.97% | 88.15% | 0.5065 | $7.15\times$ | 100.00% | 82.19% | 0.84% | 0.0166 | 0.5041 |
| **0.70** | Primary | 2 | 0 | 3,305 | 448 | 2 (0.05%) | 100.00% | 0.44% | 0.0088 | 100.00% | 88.06% | 0.5022 | $8.34\times$ | 100.00% | 100.00% | 0.39% | 0.0078 | 0.5020 |
| **0.80** | Primary | 1 | 0 | 3,305 | 449 | 1 (0.03%) | 100.00% | 0.22% | 0.0044 | 100.00% | 88.04% | 0.5011 | $8.34\times$ | 100.00% | 100.00% | 0.24% | 0.0048 | 0.5012 |
| **0.90** | Primary | 0 | 0 | 3,305 | 450 | 0 (0.00%) | 0.00% | 0.00% | 0.0000 | 100.00% | 88.02% | 0.5000 | $0.00\times$ | — | 0.00% | 0.00% | 0.0000 | 0.5000 |

---

### 3.3 External Unseen Cohort Verification: `HC-256` 2024 Panel 29 ($N=10,037$, Zero Overlap with `HC-251`, Actual High-Cost $P=1,258$, Unweighted Prev $= 12.53\%$, Weighted Prev $= 10.97\%$)
Full CSV: [`results/threshold_comparison_external_hc256_panel29.csv`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/results/threshold_comparison_external_hc256_panel29.csv)

| Threshold ($\tau$) | TP | FP | TN | FN | Flagged ($N$ / Unw %) | Unw Precision (%) | Unw Recall (%) | Unw F1-Score | Unw Specificity (%) | Unw Bal. Acc. | Wtd Precision (%) | Wtd Recall (%) | Wtd F1-Score | Wtd Bal. Acc. |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.05** | 1,145 | 5,112 | 3,667 | 113 | 6,257 (62.34%) | 18.30% | 91.02% | 0.3047 | 41.77% | 0.6639 | 16.86% | 88.38% | 0.2831 | 0.6734 |
| **0.10** | **987** | **3,163** | **5,616** | **271** | **4,150 (41.35%)** | **23.78%** | **78.46%** | **0.3650** | **63.97%** | **0.7121** | **22.88%** | **73.06%** | **0.3485** | **0.7137** |
| **0.15** | 832 | 2,072 | 6,707 | 426 | 2,904 (28.93%) | 28.65% | 66.14% | 0.3998 | 76.40% | 0.7127 | 28.15% | 59.73% | 0.3826 | 0.7047 |
| **0.20** | **659** | **1,357** | **7,422** | **599** | **2,016 (20.09%)** | **32.69%** | **52.38%** | **0.4026** | **84.54%** | **0.6846** | **32.32%** | **45.59%** | **0.3783** | **0.6692** |
| **0.25** | 511 | 842 | 7,937 | 747 | 1,353 (13.48%) | 37.77% | 40.62% | 0.3914 | 90.41% | 0.6551 | 37.10% | 34.32% | 0.3566 | 0.6358 |
| **0.30** | **381** | **520** | **8,259** | **877** | **901 (8.98%)** | **42.29%** | **30.29%** | **0.3529** | **94.08%** | **0.6218** | **41.66%** | **25.25%** | **0.3144** | **0.6045** |
| **0.40** | 183 | 202 | 8,577 | 1,075 | 385 (3.84%) | 47.53% | 14.55% | 0.2228 | 97.70% | 0.5612 | 46.09% | 11.42% | 0.1830 | 0.5489 |
| **0.50** | 72 | 63 | 8,716 | 1,186 | 135 (1.35%) | 53.33% | 5.72% | 0.1034 | 99.28% | 0.5250 | 52.50% | 4.68% | 0.0859 | 0.5208 |
| **0.60** | 26 | 15 | 8,764 | 1,232 | 41 (0.41%) | 63.41% | 2.07% | 0.0400 | 99.83% | 0.5095 | 65.31% | 1.71% | 0.0333 | 0.5080 |
| **0.70** | 5 | 0 | 8,779 | 1,253 | 5 (0.05%) | 100.00% | 0.40% | 0.0079 | 100.00% | 0.5020 | 100.00% | 0.37% | 0.0073 | 0.5018 |
| **0.80** | 1 | 0 | 8,779 | 1,257 | 1 (0.01%) | 100.00% | 0.08% | 0.0016 | 100.00% | 0.5004 | 100.00% | 0.05% | 0.0009 | 0.5002 |
| **0.90** | 0 | 0 | 8,779 | 1,258 | 0 (0.00%) | 0.00% | 0.00% | 0.0000 | 100.00% | 0.5000 | 0.00% | 0.00% | 0.0000 | 0.5000 |

---

## 4. Visual Diagnostic Evidence ($\ge 600$ DPI Figures)

All five diagnostic figures were generated directly from the machine-readable threshold registry at $600\text{ DPI}$ (`.png`) and vector `.pdf`:

1. **[`fig_t1_precision_recall_f1_vs_threshold.pdf`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/figures/fig_t1_precision_recall_f1_vs_threshold.pdf):** Plots Precision, Recall, and Specificity (Panel A) alongside F1-Score and Balanced Accuracy (Panel B) across $\tau \in [0.05, 0.90]$ for both 5-Fold OOF Validation ($N=15,016$) and the Held-Out Test Set ($N=3,755$). Demonstrates that $\tau = 0.10$ maximizes Balanced Accuracy ($0.7152$ Val / $0.7122$ Test), whereas $\tau = 0.20$ maximizes F1 on the primary grid ($0.3855$ Val / $0.3695$ Test, with fine-grid $\tau = 0.15$ achieving Test F1 $= 0.3742$).
2. **[`fig_t2_precision_recall_tradeoff.pdf`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/figures/fig_t2_precision_recall_tradeoff.pdf):** Plots the continuous Precision–Recall curve overlaid with discrete threshold operating points (Panel A) and compares observed precision against the **Theoretical Oracle Ceiling at Flagged Volume** $\min(P, \text{Flagged}(\tau)) / \text{Flagged}(\tau)$ (Panel B).
3. **[`fig_t3_fp_fn_and_flagged_volume.pdf`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/figures/fig_t3_fp_fn_and_flagged_volume.pdf):** Plots absolute False Positives ($\text{FP}$), False Negatives ($\text{FN}$), and True Positives ($\text{TP}$) across thresholds (Panel A) and the unweighted vs. survey-weighted percentage of patients flagged as high-expenditure (Panel B).
4. **[`fig_t4_confusion_matrices_comparison.pdf`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/figures/fig_t4_confusion_matrices_comparison.pdf):** Side-by-side confusion matrices on the held-out test set ($N=3,755$) at $\tau = 0.10$ (High-Sensitivity Screening), $\tau = 0.20$ (Validation Primary-Grid F1-Optimal Triage), $\tau = 0.30$ (Targeted Intensive Case Management), and $\tau = 0.50$ (Naive Default Cutoff).
5. **[`fig_t5_calibration_and_overfitting_audit.pdf`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/figures/fig_t5_calibration_and_overfitting_audit.pdf):** Shows the patient count distribution and observed vs. predicted event rates across probability bins on the test set (Panel A) alongside the multi-cohort cross-split and cross-release generalization audit (Panel B).

---

## 5. Six-Factor Root-Cause Investigation: Why Precision is $23.18\%$ at $\tau = 0.10$

To determine why the reference model yields $23.18\%$ precision at $\tau = 0.10$, we systematically evaluated all six candidate hypotheses specified in the study protocol.

### Factor 1: Threshold Sensitivity & Volume-Ceiling Mathematics (**Primary Direct Cause**)
Setting $\tau = 0.10$ equates the classification cutoff to the approximate population base rate ($\sim 10\%$). Because the logistic regression model outputs calibrated probabilities centered around the population prevalence, $39.97\%$ of the test cohort ($1,501 / 3,755$ patients; $33.54\%$ weighted) have a predicted probability $\hat{p}_i \ge 0.10$.
- However, the entire test set contains only $P = 450$ true high-expenditure patients ($11.98\%$).
- Therefore, **even a hypothetical perfect oracle classifier ($100\%$ recall, $\text{ROC-AUC} = 1.00$) that flags $1,501$ patients is mathematically bounded by:**
  $$\text{Precision}_{\text{oracle}}(\text{Flagged} = 1,501) = \frac{\min(450, 1,501)}{1,501} = \frac{450}{1,501} = 29.98\%$$
- Whenever $\text{Flagged}(\tau) \ge P$, the ratio of observed precision to this oracle volume ceiling is algebraically identical to recall:
  $$\frac{\text{Precision}(\tau)}{\text{Precision}_{\text{oracle}}(\tau)} = \frac{\text{TP} / \text{Flagged}(\tau)}{P / \text{Flagged}(\tau)} = \frac{\text{TP}}{P} = \text{Recall}(\tau) = \frac{348}{450} = 77.33\%$$
  Thus, at $\tau = 0.10$, the observed precision of $23.18\%$ remains below the $29.98\%$ theoretical upper bound imposed by the flagged cohort volume (where the ratio $23.18\% / 29.98\% = 348 / 450 = 77.33\%$ equals model recall rather than independent evidence against overfitting).
- When $\tau$ is increased to $\tau = 0.20$, the flagged volume drops from $39.97\%$ ($1,501$ patients) to $18.43\%$ ($692$ patients), **eliminating $672$ false positives (a $58.28\%$ reduction in $\text{FP}$, from $1,153$ to $481$)** and raising precision to **$30.49\%$ ($2.54\times$ base rate; $32.69\%$ on disjoint 2024 Panel 29)**. At $\tau = 0.30$, flagged volume drops to $7.59\%$ ($285$ patients), **cutting false positives by $85.17\%$ (to $171$)** and raising precision to **$40.00\%$ ($3.34\times$ base rate; $42.29\%$ on Panel 29)**.

### Factor 2: Class Imbalance & Base-Rate Conditioning (**Structural Contributing Factor**)
High-expenditure healthcare utilization is inherently right-skewed and rare by definition ($\ge \text{P90}_{\text{wtd}} = \$17,827.41$, so $\pi = 10.51\%$ weighted / $11.98\%$ unweighted). By Bayes' rule:
$$\text{Precision}(\tau) = \frac{\text{Recall}(\tau) \cdot \pi}{\text{Recall}(\tau) \cdot \pi + \text{FPR}(\tau) \cdot (1 - \pi)} = \frac{1}{1 + \frac{1-\pi}{\pi} \cdot \frac{\text{FPR}(\tau)}{\text{Recall}(\tau)}}$$
Because the negative-to-positive class odds ratio is $\frac{1-\pi}{\pi} = \frac{3,305}{450} = 7.344$ (unweighted) or $\frac{0.8949}{0.1051} = 8.518$ (survey-weighted), every $1\%$ increase in false positive rate ($\text{FPR}$) generates $7.34\times$ as many false positives as a $1\%$ increase in recall generates true positives. At $\tau = 0.10$, achieving $77.33\%$ recall requires accepting an $\text{FPR}$ of $34.89\%$ ($\text{Specificity} = 65.11\%$), which directly yields $\text{Precision} = \frac{0.7733 \times 0.11984}{0.7733 \times 0.11984 + 0.3489 \times 0.88016} = 23.18\%$.

### Factor 3: Model Discrimination Ceiling (**Moderate Contributing Factor**)
The 11-feature Observable Logistic Regression model achieves a threshold-independent test ROC-AUC of $0.7654$ ($95\%$ bootstrap CI: $[0.7444, 0.7881]$) and PR-AUC of $0.3184$ ($2.66\times$ the $0.1198$ random baseline). Importantly, our nine-model benchmark confirms that **nonlinear models trained on the exact same 11 observable features yield virtually identical precision at $\tau = 0.10$**:
- **Observable Logistic Regression (Weighted Fit, Serving):** ROC-AUC $= 0.7654$, PR-AUC $= 0.3184$, Weighted BSS $= +0.1025$, Prec@0.10 $= 23.18\%$, Rec@0.10 $= 77.33\%$
- **Random Forest (11-Feat Observable):** ROC-AUC $= 0.7693$, PR-AUC $= 0.3157$, Weighted BSS $= +0.1062$, Prec@0.10 $= 23.42\%$, Rec@0.10 $= 75.56\%$
- **XGBoost (Uncalibrated, 11-Feat Observable):** ROC-AUC $= 0.7705$, PR-AUC $= 0.3196$, Weighted BSS $= +0.1093$, Prec@0.10 $= 22.62\%$, Rec@0.10 $= 80.22\%$

Thus, the discrimination boundary reflects the intrinsic information content of the 11 intake-observable survey variables rather than linear model misspecification.

### Factor 4: Probability Calibration & Score Distribution Concentration (**Explains Intermediate-Threshold Behavior & High-Cutoff Collapse**)
Auditing predicted probability bins on the held-out test set ($N=3,755$, [`results/threshold_analysis_complete_registry.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/results/threshold_analysis_complete_registry.json)) reveals that **the model's probabilities are well-calibrated across the entire risk spectrum**, with an overall test unweighted Brier score of $0.0936$ (Weighted Brier $= 0.0845$, Weighted BSS $= +0.1025$, slope $b = 0.9438$, $\text{CITL} = +0.0646$):

| Predicted Probability Bin | Test Patients ($N$) | % of Test Cohort | Observed High-Cost ($N$) | Mean Predicted Prob ($\bar{\hat{p}}$) | Observed Unw. Event Rate (%) | Observed Survey-Wtd Event Rate (%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$[0.00, 0.05)$** | $1,475$ | $39.28\%$ | $49$ | $3.16\%$ | $3.32\%$ | $3.83\%$ |
| **$[0.05, 0.10)$** | $779$ | $20.75\%$ | $53$ | $7.25\%$ | $6.80\%$ | $5.71\%$ |
| **$[0.10, 0.15)$** | $449$ | $11.96\%$ | $67$ | $12.35\%$ | $14.92\%$ | $15.88\%$ |
| **$[0.15, 0.20)$** | $360$ | $9.59\%$ | $70$ | $17.35\%$ | $19.44\%$ | $18.23\%$ |
| **$[0.20, 0.25)$** | $252$ | $6.71\%$ | $57$ | $22.28\%$ | $22.62\%$ | $23.15\%$ |
| **$[0.25, 0.30)$** | $155$ | $4.13\%$ | $40$ | $27.33\%$ | $25.81\%$ | $25.69\%$ |
| **$[0.30, 0.40)$** | $181$ | $4.82\%$ | $68$ | $34.37\%$ | $37.57\%$ | $38.36\%$ |
| **$[0.40, 0.50)$** | $68$ | $1.81\%$ | $31$ | $44.27\%$ | $45.59\%$ | $46.59\%$ |
| **$[0.50, 0.60)$** | $29$ | $0.77\%$ | $9$ | $54.28\%$ | $31.03\%$ | $29.14\%$ |
| **$[0.60, 0.70)$** | $5$ | $0.13\%$ | $4$ | $63.44\%$ | $80.00\%$ | $71.00\%$ |
| **$[0.70, 0.80)$** | $1$ | $0.03\%$ | $1$ | $70.30\%$ | $100.00\%$ | $100.00\%$ |
| **$[0.80, 0.90)$** | $1$ | $0.03\%$ | $1$ | $80.08\%$ | $100.00\%$ | $100.00\%$ |
| **$[0.90, 1.00]$** | $0$ | $0.00\%$ | $0$ | — | — | — |

Two critical insights emerge from this calibration audit:
1. **Why precision is $23.18\%$ at $\tau = 0.10$:** More than half of all patients flagged at $\tau = 0.10$ ($809$ out of $1,501$ flagged patients, or $53.90\%$) reside in the $[0.10, 0.20)$ probability band, where the model correctly predicts a $12.35\%\text{--}17.35\%$ risk and the actual observed high-cost rate is $14.92\%\text{--}19.44\%$ ($137 / 809 = 16.93\%$). Because the model is well-calibrated, patients in this moderate-risk band only experience high costs $\sim 17\%$ of the time; classifying all of them as binary positive (`1`) inevitably generates $672$ false positives within that band alone.
2. **Why high thresholds ($\tau \ge 0.50$) suffer severe recall collapse:** Because predicted probabilities are well-calibrated and bounded by $\max(\hat{p}_{\text{test}}) = 0.8008$ ($\text{P90} = 0.2640$, $\text{P99} = 0.4981$), only $36$ test patients ($0.96\%$) have $\hat{p}_i \ge 0.50$, and $0$ patients have $\hat{p}_i \ge 0.90$. Thus, a naive $\tau = 0.50$ cutoff misses $96.67\%$ of high-expenditure patients ($\text{Recall} = 3.33\%$, $\text{FN} = 435$).

### Factor 5: Cross-Split and Multi-Release Generalization Comparison (**No Evidence of Substantial Generalization Collapse**)
To evaluate whether generalization degradation contributed to the precision behavior on the internal holdout test set, we compared threshold-independent and threshold-specific performance across **all eight internal and external cohorts/partitions**:

| Evaluation Split / Cohort | Sample Size ($N$) | Positives ($P$, Unw %) | Overlap with `HC-251` | Unw / Wtd ROC-AUC | Unw PR-AUC | Unw / Wtd Brier | Wtd BSS | $\tau=0.10$ Prec / Rec / F1 | $\tau=0.20$ Prec / Rec / F1 | $\tau=0.30$ Prec / Rec / F1 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. `HC-251` Train (In-Sample)** | $15,016$ | $1,736$ ($11.56\%$) | $100\%$ Train | $0.7815 / 0.7699$ | $0.3306$ | $0.0893 / 0.0798$ | $+0.1126$ | $22.77\% / 77.30\% / 0.3518$ | $31.69\% / 50.81\% / 0.3903$ | $39.90\% / 26.84\% / 0.3209$ |
| **2. `HC-251` 5-Fold Stratified OOF** | $15,016$ | $1,736$ ($11.56\%$) | $0\%$ In-Fold | $0.7795 / 0.7674$ | $0.3260$ | $0.0896 / 0.0801$ | $+0.1087$ | $22.78\% / 77.30\% / 0.3519$ | $31.28\% / 50.23\% / 0.3855$ | $39.73\% / 26.73\% / 0.3196$ |
| **3. `HC-251` 5-Fold Household (`DUID`) OOF** | $15,016$ | $1,736$ ($11.56\%$) | $0\%$ `DUID` In-Fold | $0.7785 / 0.7660$ | $0.3247$ | $0.0897 / 0.0802$ | $+0.1079$ | $22.84\% / 77.36\% / 0.3527$ | $31.11\% / 49.94\% / 0.3834$ | $39.78\% / 26.73\% / 0.3197$ |
| **4. `HC-251` Internal Holdout Test Set** | **$3,755$** | **$450$ ($11.98\%$)** | **$0\%$ `DUPERSID` ($72.2\%$ `DUID`)** | **$0.7654 / 0.7509$** | **$0.3184$** | **$0.0936 / 0.0845$** | **$+0.1025$** | **$23.18\% / 77.33\% / 0.3567$** | **$30.49\% / 46.89\% / 0.3695$** | **$40.00\% / 25.33\% / 0.3102$** |
| **5. `HC-256` 2024 Full Consolidated** | $18,979$ | $2,414$ ($12.72\%$) | $46.24\%$ Panel 28 | $0.7852 / 0.7828$ | $0.3522$ | $0.0962 / 0.0859$ | $+0.1266$ | $24.44\% / 78.79\% / 0.3731$ | $33.41\% / 52.90\% / 0.4095$ | $42.68\% / 30.82\% / 0.3580$ |
| **6. `HC-256` 2024 Panel 28 Carryover** | $8,942$ | $1,156$ ($12.93\%$) | $98.13\%$ Panel 28 | $0.7884 / 0.7852$ | $0.3557$ | $0.0974 / 0.0863$ | $+0.1297$ | $25.19\% / 79.15\% / 0.3822$ | $34.21\% / 53.46\% / 0.4172$ | $43.09\% / 31.40\% / 0.3633$ |
| **7. `HC-256` 2024 Panel 29 Disjoint** | **$10,037$** | **$1,258$ ($12.53\%$)** | **$0\%$ (`DUPERSID` & `DUID`)** | **$0.7824 / 0.7812$** | **$0.3506$** | **$0.0951 / 0.0856$** | **$+0.1242$** | **$23.78\% / 78.46\% / 0.3650$** | **$32.69\% / 52.38\% / 0.4026$** | **$42.29\% / 30.29\% / 0.3529$** |
| **8. `HC-257` Panel 28 Prospective Year-2** | $8,708$ | $1,157$ ($13.29\%$) | $100\%$ Panel 28 | $0.7824 / 0.7807$ | $0.3543$ | $0.1001 / 0.0874$ | $+0.1263$ | $25.63\% / 79.00\% / 0.3870$ | $34.72\% / 53.33\% / 0.4206$ | $43.76\% / 31.37\% / 0.3654$ |

**Conclusion on Generalization:** The difference between in-sample training (`0.7815`) and 5-Fold Stratified OOF (`0.7795`) is $\Delta = -0.0020$, and on the strictly disjoint 2024 Panel 29 cohort ($N=10,037$, zero person or household overlap with `HC-251`), ROC-AUC (`0.7824`), PR-AUC (`0.3506`), Weighted BSS (`+0.1242`), and Precision (`23.78%` at $\tau=0.10$, `32.69%` at $\tau=0.20$, `42.29%` at $\tau=0.30$) are consistent with or exceed the 2023 internal holdout metrics. Similar discrimination across stratified and household-grouped OOF validation and the disjoint HC-256 Panel 29 cohort provides no evidence of a substantial generalization collapse under the evaluated protocols; however, it does not establish the absence of overfitting.

### Factor 6: Feature Granularity Limitations & Aleatoric Healthcare Cost Variance (**Fundamental Domain Ceiling**)
Analyzing the 11 intake-observable features across comorbidity strata on `HC-251` Test ($N=3,755$) reveals two structural domain constraints:

| Comorbidity Stratum (`Comorbidity_Count`) | Test Respondents ($N$ / % of Test) | Observed High-Cost Cases ($N$ / % of All $450$ High-Cost) | Observed Stratum High-Cost Prevalence (%) | Mean Predicted Probability ($\bar{\hat{p}}$) | Mean Observed Annual Expenditure (USD) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **0 Comorbidities** | $1,358$ ($36.17\%$) | $46$ (**$10.22\%$**) | $3.39\%$ | $3.13\%$ | $\$2,851.17$ |
| **1 Comorbidity** | $827$ ($22.02\%$) | $60$ ($13.33\%$) | $7.26\%$ | $6.99\%$ | $\$6,052.22$ |
| **2 Comorbidities** | $673$ ($17.92\%$) | $91$ ($20.22\%$) | $13.52\%$ | $13.61\%$ | $\$9,882.55$ |
| **3+ Comorbidities** | $897$ ($23.89\%$) | $253$ (**$56.22\%$**) | **$28.21\%$** | **$26.79\%$** | $\$19,379.17$ |

1. **Unpredicted Acute Catastrophic Shocks among Zero-Comorbidity Individuals:** Exactly $1,358 / 3,755$ test respondents ($36.17\%$) have **zero diagnosed chronic comorbidity clusters** (`Comorbidity_Count == 0`). Yet $46$ of these healthy-appearing individuals ($3.39\%$ of the stratum, representing **$10.22\%$ of all $450$ high-cost cases**) incur $\ge \$17,827.41$ due to stochastic acute events (e.g., trauma, emergency surgery, appendicitis, or obstetric hospitalizations).
2. **Episodic Realization of High Costs among Severely Multimorbid Patients:** Conversely, among the $897$ test respondents ($23.89\%$) with $\ge 3$ chronic comorbidity clusters (`Comorbidity_Count >= 3`), $253$ ($28.21\%$) exceed $\$17,827.41$ in calendar year 2023, while the remaining $644$ ($71.79\%$) are managed via stable outpatient pharmacotherapy without requiring an acute inpatient hospitalization during that 12-month window.

---

## 6. Explicit Answers to Phase 1 Research Questions & Operating Threshold Recommendations

### Q1. Does increasing the threshold meaningfully improve precision?
**Yes.** Increasing $\tau$ from $0.10$ to $0.20$ increases test precision from **$23.18\%$ to $30.49\%$** ($+7.31$ percentage points, a $+31.5\%$ relative gain, lifting enrichment from $1.93\times$ to $2.54\times$ the baseline rate) and cuts false positives by **$58.28\%$** (from $1,153$ to $481$). Increasing $\tau$ to $0.30$ further increases test precision to **$40.00\%$** ($+16.82$ percentage points over baseline, $3.34\times$ enrichment) and cuts false positives by **$85.17\%$** (from $1,153$ to $171$). On the unseen 2024 Panel 29 cohort ($N=10,037$), precision similarly rises from $23.78\%$ ($\tau=0.10$) to $32.69\%$ ($\tau=0.20$) and $42.29\%$ ($\tau=0.30$).

### Q2. At what threshold does recall drop too sharply for high-expenditure patient screening?
- Between $\tau = 0.10$ and $\tau = 0.15$, recall declines moderately from $77.33\%$ to $62.44\%$ while Test F1 improves from $0.3567$ to $0.3742$.
- At **$\tau = 0.20$**, the model still captures roughly half of all high-cost patients ($\text{Recall} = 46.89\%$ on Test, $50.23\%$ on OOF Validation, $52.38\%$ on 2024 Panel 29) while maintaining $85.45\%$ specificity.
- **Beyond $\tau = 0.30$ ($\text{Recall} = 25.33\%$ Test, $30.29\%$ Panel 29), recall collapses rapidly:** at $\tau = 0.40$, recall falls to $10.22\%$ ($404 / 450$ high-cost patients missed), and at $\tau = 0.50$, recall falls to $3.33\%$ ($435 / 450$ missed). Therefore, **$\tau > 0.30$ is unsuitable for general population screening**, and **$\tau \ge 0.50$ causes catastrophic false-negative failure**.

### Q3. Which threshold gives the best F1-score?
- **On the Primary Threshold Grid ($\{0.10, 0.20, \dots, 0.90\}$):** Selected strictly on 5-Fold OOF Validation ($N=15,016$), **$\tau = 0.20$ maximizes both unweighted F1 ($0.3855$ vs. $0.3519$ at $\tau=0.10$) and survey-weighted F1 ($0.3551$ vs. $0.3297$ at $\tau=0.10$)**. On the held-out test set ($N=3,755$), $\tau = 0.20$ achieves a higher unweighted F1 ($0.3695$ vs. $0.3567$) and higher survey-weighted F1 ($0.3485$ vs. $0.3433$) than $\tau = 0.10$, as well as on unseen 2024 Panel 29 ($\text{F1} = 0.4026$ at $\tau=0.20$ vs. $0.3650$ at $\tau=0.10$).
- **Including Intermediate Diagnostic Cutoffs ($\{0.05, 0.15, 0.25\}$):** On OOF Validation, $\tau = 0.20$ ($\text{F1} = 0.3855$) remains the global peak, while on the held-out test set, intermediate $\tau = 0.15$ achieves the highest test F1 of **$0.3742$** ($\text{Weighted F1} = 0.3525$, $\text{Precision} = 26.71\%$, $\text{Recall} = 62.44\%$).

### Q4. Which threshold gives the best statistical trade-off?
Because decision-curve analysis (DCA), clinical utility weights, and intervention trials were not conducted, **no single static cutoff can be claimed as clinically optimal**. Instead, our empirical findings summarize three **statistical operating points** using the same calibrated probability output $\hat{p}_i$:

| Statistical Operating Point | Threshold ($\tau$) | Validation Selection Criterion | Internal Holdout Performance ($N=3,755$) | 2024 Disjoint Panel 29 ($N=10,037$) | Statistical Trade-Off Summary |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **1. High-Sensitivity Operating Point** | **$\tau = 0.10$** *(Original Reference)* | **Max Balanced Accuracy** ($\text{Val} = 0.7152$) | Prec: **$23.18\%$** ($1.93\times$)<br>Rec: **$77.33\%$** \| F1: **$0.3567$**<br>BalAcc: **$0.7122$** \| Flag: **$39.97\%$** | Prec: **$23.78\%$** ($1.90\times$)<br>Rec: **$78.46\%$** \| F1: **$0.3650$**<br>BalAcc: **$0.7121$** \| Flag: **$41.35\%$** | Maximizes Balanced Accuracy and sensitivity ($77.33\%$ recall), at the cost of flagging $39.97\%$ of the cohort ($29.98\%$ oracle volume ceiling). |
| **2. Primary-Grid F1-Optimal Operating Point** | **$\tau = 0.20$** *(or $\tau = 0.15$ fine-grid)* | **Max Primary-Grid F1-Score** ($\text{Val F1} = 0.3855$, $\text{Wtd F1} = 0.3551$) | Prec: **$30.49\%$** ($2.54\times$)<br>Rec: **$46.89\%$** \| F1: **$0.3695$**<br>Spec: **$85.45\%$** \| Flag: **$18.43\%$**<br>*(Cuts FP by $58.28\%$)* | Prec: **$32.69\%$** ($2.61\times$)<br>Rec: **$52.38\%$** \| F1: **$0.4026$**<br>Spec: **$84.54\%$** \| Flag: **$20.09\%$** | Maximizes F1 on the primary grid and cuts false positives by $58.28\%$ ($1,153 \to 481$) while retaining $\sim 47\%\text{--}52\%$ recall (does not by itself establish clinical usefulness). |
| **3. Higher-Specificity Operating Point** | **$\tau = 0.30$** | **High Specificity ($\ge 94.5\%$) & $\ge 3.3\times$ Enrichment** | Prec: **$40.00\%$** ($3.34\times$)<br>Rec: **$25.33\%$** \| F1: **$0.3102$**<br>Spec: **$94.83\%$** \| Flag: **$7.59\%$**<br>*(Cuts FP by $85.17\%$)* | Prec: **$42.29\%$** ($3.37\times$)<br>Rec: **$30.29\%$** \| F1: **$0.3529$**<br>Spec: **$94.08\%$** \| Flag: **$8.98\%$** | Restricts flagged volume to the top $\sim 7.6\%\text{--}9.0\%$ of predicted probabilities, achieving $40\%+$ precision and $94.8\%$ specificity while cutting false positives by $85.17\%$. |

### Q5. Should $\tau = 0.10$ be retained, replaced, or presented alongside an alternative operating point?
**$\tau = 0.10$ should be retained as the high-sensitivity operating point (maximizing Balanced Accuracy at $0.7122$) and presented alongside $\tau = 0.20$ (the validation-selected primary-grid F1-optimal operating point, $30.49\%$ holdout / $32.69\%$ Panel 29 precision, $46.89\%$ holdout / $52.38\%$ Panel 29 recall) and $\tau = 0.30$ (the higher-specificity operating point, $40.00\%$ holdout / $42.29\%$ Panel 29 precision, $94.83\%$ specificity) as statistical operating points.**
