# Phase 1 Technical Report: Classification Probability Threshold Sensitivity & Diagnostic Analysis

**Project:** HealthScore — CRC Paper Evidence Enhancement & Controlled Revision
**Branch:** `feature/ml-pipeline-rebuild`
**Model Audited:** `ml_model/artifacts/risk_model_classifier_observable_weighted_p90.pkl` (`SHA-256: 3632f820b2ed9dd0ca5dc33aa86e5d52c921c764dfde6db9db6ac6c06401db36`)
**Reproducible Experiment Script:** [`experiments/run_threshold_sensitivity_analysis.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/experiments/run_threshold_sensitivity_analysis.py)
**Machine-Readable Registry:** [`results/threshold_analysis_complete_registry.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/results/threshold_analysis_complete_registry.json)

---

## 1. Executive Summary & Verification of Baseline Reference Metrics

In the HealthScore two-stage predictive pipeline, Stage 1 is a survey-weighted $L_2$-regularized logistic regression classifier (`C=1.0`, `lbfgs`) trained on 11 intake-observable demographic, socioeconomic, self-rated health, and chronic comorbidity features from the 2023 Medical Expenditure Panel Survey (`MEPS HC-251`, $N=18,771$ adults aged $\ge 18$; $80\%$ train $N=15,016$, $20\%$ held-out test $N=3,755$). The binary target (`Target 2`) identifies patients exceeding the survey-weighted 90th percentile of annual healthcare expenditure ($\text{TOTEXP23} \ge \$17,827.41$, computed exclusively on the training split using `PERWT23F` weights).

Before conducting the threshold sensitivity sweep, we verified all baseline metrics reported for the reference probability threshold ($\tau = 0.10$) directly against the frozen serving artifact on the held-out test set ($N=3,755$):

| Baseline Metric (`HC-251` Held-Out Test, $N=3,755$) | Reported Value | Verified Exact Value (Unweighted) | Verified Exact Value (Survey-Weighted `PERWT23F`) | Verification Status |
| :--- | :---: | :---: | :---: | :---: |
| **Positive Class Cutoff ($\text{P90}_{\text{wtd}}$)** | $\$17,827.41$ | $\$17,827.41$ | $\$17,827.41$ | **Exact Match** |
| **Cohort Positive Prevalence ($\pi$)** | $11.98\%$ ($450/3,755$) | $11.984\%$ ($450/3,755$) | $10.506\%$ (US Adult Pop.) | **Exact Match** |
| **ROC-AUC (Threshold-Independent)** | $0.7654$ | $0.7654$ $[0.7444, 0.7881]$ | $0.7707$ | **Exact Match** |
| **PR-AUC (Threshold-Independent)** | $0.3184$ | $0.3184$ $[0.2876, 0.3556]$ | $0.2966$ | **Exact Match** |
| **Brier Score** | $0.0936$ (Unw) / $0.0845$ (Wtd) | $0.0936$ | $0.0845$ | **Exact Match** |
| **Brier Skill Score (BSS vs. Null)** | $+0.1025$ (Wtd) | $+0.1123$ (Null $= 0.1055$) | $+0.1025$ (Null $= 0.0941$) | **Exact Match** |
| **Precision (PPV) at $\tau = 0.10$** | $23.18\%$ | $23.18\%$ ($348 / 1,501$) | $22.54\%$ | **Exact Match** |
| **Recall (Sensitivity) at $\tau = 0.10$** | $77.33\%$ | $77.33\%$ ($348 / 450$) | $71.93\%$ | **Exact Match** |
| **F1-Score at $\tau = 0.10$** | $0.3567$ | $0.3567$ | $0.3433$ | **Exact Match** |
| **Specificity (TNR) at $\tau = 0.10$** | $65.11\%$ | $65.11\%$ ($2,152 / 3,305$) | $70.98\%$ | **Exact Match** |
| **Balanced Accuracy at $\tau = 0.10$** | $0.7122$ | $0.7122$ | $0.7145$ | **Exact Match** |
| **Prevalence Enrichment Ratio at $\tau = 0.10$** | $1.93\times$ | $1.9346\times$ ($23.18\% / 11.98\%$) | $2.1456\times$ ($22.54\% / 10.51\%$) | **Exact Match** |

---

## 2. Experimental Methodology & Leak-Free Threshold Selection Protocol

### 2.1 Fixed-Model Isolation Principle
To isolate the effect of the classification decision boundary $\tau$ from model retraining variance, **no model retraining was performed across thresholds for test or external evaluation**. The frozen serving classifier (`risk_model_classifier_observable_weighted_p90.pkl`) outputs continuous predicted probabilities $\hat{p}_i = P(y_i = 1 \mid \mathbf{x}_i) \in (0, 1)$, and binary predictions are generated purely via $\hat{y}_i(\tau) = \mathbb{I}(\hat{p}_i \ge \tau)$ across:
- **Primary Threshold Grid:** $\tau \in \{0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90\}$
- **Intermediate Diagnostic Thresholds:** $\tau \in \{0.05, 0.15, 0.25\}$ (plus a fine-grid sweep $\tau \in [0.05, 0.75]$ in steps of $0.01$ on Out-of-Fold validation).

### 2.2 Leak-Free Validation Strategy (5-Fold Out-of-Fold Validation)
Because `split_data()` in [`ml_model/data_pipeline.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/data_pipeline.py) partitions `MEPS HC-251` ($N=18,771$) into an $80\%$ training set ($N=15,016$) and a $20\%$ held-out test set ($N=3,755$) without a separate validation split, selecting an operating threshold on the held-out test set would constitute test leakage. Instead, we implemented **5-Fold Out-of-Fold (OOF) cross-validation strictly within the training split ($N=15,016$)** using identical model hyperparameters (`LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, random_state=42)`) and normalized survey weights (`w_train_norm`):
1. **Stratified 5-Fold OOF Validation (`StratifiedKFold`, $N=15,016$):** Preserves the exact training positive class ratio across folds (OOF ROC-AUC $= 0.7795$, OOF PR-AUC $= 0.3260$).
2. **Household-Clustered 5-Fold OOF Validation (`GroupKFold` by dwelling unit `DUID`, $N=15,016$):** Places all members of the same household (`DUID`) into the same validation fold to audit whether shared household socioeconomic status inflates performance (Household OOF ROC-AUC $= 0.7785$, PR-AUC $= 0.3252$ — virtually identical to stratified OOF, $\Delta\text{ROC-AUC} = -0.0010$).

All threshold optima (maximum Balanced Accuracy, maximum F1-score, and Precision–Recall breakeven) are selected exclusively on the **5-Fold OOF validation predictions ($N=15,016$)** and subsequently evaluated on:
- **`HC-251` Held-Out Test Set ($N=3,755$)**
- **`HC-256` 2024 Panel 29 Unseen External Cohort ($N=10,037$)** — the newly enrolled 2024 MEPS panel that has **zero person (`DUPERSID`) and zero household (`DUID`) overlap** with `HC-251`.

### 2.3 Unweighted vs. Survey-Weighted Evaluation
In `MEPS HC-251`, low-income and minority subpopulations are oversampled by design, and older chronically ill individuals have slightly higher sample representation prior to `PERWT23F` weighting. Consequently, the $\$17,827.41$ cutoff (defined at the **survey-weighted** 90th percentile of training expenditure) corresponds to:
- **Unweighted Sample Prevalence:** $11.99\%$ ($1,800 / 15,016$) in Train and $11.98\%$ ($450 / 3,755$) in Test.
- **Survey-Weighted Population Prevalence:** $9.88\%$ in Train and $10.51\%$ in Test.

Because confusion matrix counts ($\text{TP}, \text{FP}, \text{TN}, \text{FN}$ and patient volumes) represent discrete sample patients, we report exact unweighted sample counts alongside both **unweighted** and **survey-weighted** rates in all tables and CSV artifacts.

---

## 3. Comprehensive Threshold Comparison Results

### 3.1 Leak-Free 5-Fold Stratified OOF Validation ($N=15,016$, Actual High-Cost $P=1,800$, Unweighted Prev $= 11.99\%$, Weighted Prev $= 9.88\%$)
Full CSV: [`results/threshold_comparison_validation_oof.csv`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/results/threshold_comparison_validation_oof.csv)

| Threshold ($\tau$) | Grid Type | TP | FP | TN | FN | Flagged ($N$ / Unw %) | Unw Precision (%) | Unw Recall (%) | Unw F1-Score | Unw Specificity (%) | Unw NPV (%) | Unw Bal. Acc. | Unw Enrich. Ratio | Oracle Max Prec. at Vol. (%) | Wtd Precision (%) | Wtd Recall (%) | Wtd F1-Score | Wtd Bal. Acc. |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.05** | Interm. | 1,622 | 7,498 | 5,718 | 178 | 9,120 (60.74%) | 17.79% | 90.11% | 0.2971 | 43.27% | 96.98% | 0.6669 | $1.48\times$ | 19.74% | 15.65% | 87.34% | 0.2655 | 0.6790 |
| **0.10** | **Primary (Ref)** | **1,389** | **4,527** | **8,689** | **411** | **5,916 (39.40%)** | **23.48%** | **77.17%** | **0.3600** | **65.75%** | **95.48%** | **0.7146** | **$1.96\times$** | **30.43%** | **21.64%** | **71.50%** | **0.3322** | **0.7158** |
| **0.15** | Interm. | 1,148 | 2,980 | 10,236 | 652 | 4,128 (27.49%) | 27.81% | 63.78% | 0.3873 | 77.45% | 94.01% | 0.7061 | $2.32\times$ | 43.60% | 26.27% | 57.62% | 0.3609 | 0.6995 |
| **0.20** | **Primary (F1-Opt)** | **894** | **1,955** | **11,261** | **906** | **2,849 (18.97%)** | **31.38%** | **49.67%** | **0.3846** | **85.21%** | **92.55%** | **0.6744** | **$2.62\times$** | **63.18%** | **29.96%** | **43.57%** | **0.3551** | **0.6620** |
| **0.25** | Interm. | 665 | 1,196 | 12,020 | 1,135 | 1,861 (12.39%) | 35.73% | 36.94% | 0.3633 | 90.95% | 91.37% | 0.6395 | $2.98\times$ | 96.72% | 34.47% | 30.89% | 0.3258 | 0.6223 |
| **0.30** | Primary | 457 | 692 | 12,524 | 1,343 | 1,149 (7.65%) | 39.77% | 25.39% | 0.3099 | 94.76% | 90.31% | 0.6008 | $3.32\times$ | 100.00% | 39.32% | 21.13% | 0.2749 | 0.5878 |
| **0.40** | Primary | 213 | 246 | 12,970 | 1,587 | 459 (3.06%) | 46.41% | 11.83% | 0.1886 | 98.14% | 89.10% | 0.5499 | $3.87\times$ | 100.00% | 46.46% | 9.57% | 0.1587 | 0.5418 |
| **0.50** | Primary | 82 | 76 | 13,140 | 1,718 | 158 (1.05%) | 51.90% | 4.56% | 0.0838 | 99.43% | 88.44% | 0.5199 | $4.33\times$ | 100.00% | 55.66% | 3.74% | 0.0700 | 0.5171 |
| **0.60** | Primary | 29 | 17 | 13,199 | 1,771 | 46 (0.31%) | 63.04% | 1.61% | 0.0314 | 99.87% | 88.17% | 0.5074 | $5.26\times$ | 100.00% | 68.78% | 1.24% | 0.0243 | 0.5059 |
| **0.70** | Primary | 4 | 2 | 13,214 | 1,796 | 6 (0.04%) | 66.67% | 0.22% | 0.0044 | 99.98% | 88.03% | 0.5010 | $5.56\times$ | 100.00% | 69.39% | 0.16% | 0.0031 | 0.5008 |
| **0.80** | Primary | 0 | 1 | 13,215 | 1,800 | 1 (0.01%) | 0.00% | 0.00% | 0.0000 | 99.99% | 88.01% | 0.5000 | $0.00\times$ | 100.00% | 0.00% | 0.00% | 0.0000 | 0.5000 |
| **0.90** | Primary | 0 | 0 | 13,216 | 1,800 | 0 (0.00%) | 0.00% | 0.00% | 0.0000 | 100.00% | 88.01% | 0.5000 | $0.00\times$ | 0.00% | 0.00% | 0.00% | 0.0000 | 0.5000 |

---

### 3.2 `HC-251` Held-Out Test Set ($N=3,755$, Actual High-Cost $P=450$, Unweighted Prev $= 11.98\%$, Weighted Prev $= 10.51\%$)
Full CSV: [`results/threshold_comparison_test.csv`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/results/threshold_comparison_test.csv)

| Threshold ($\tau$) | Grid Type | TP | FP | TN | FN | Flagged ($N$ / Unw %) | Unw Precision (%) | Unw Recall (%) | Unw F1-Score | Unw Specificity (%) | Unw NPV (%) | Unw Bal. Acc. | Unw Enrich. Ratio | Oracle Max Prec. at Vol. (%) | Wtd Precision (%) | Wtd Recall (%) | Wtd F1-Score | Wtd Bal. Acc. |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.05** | Interm. | 401 | 1,880 | 1,425 | 49 | 2,281 (60.75%) | 17.58% | 89.11% | 0.2936 | 43.12% | 96.68% | 0.6611 | $1.47\times$ | 19.73% | 16.58% | 85.40% | 0.2777 | 0.6749 |
| **0.10** | **Primary (Ref)** | **348** | **1,153** | **2,152** | **102** | **1,501 (39.97%)** | **23.18%** | **77.33%** | **0.3567** | **65.11%** | **95.47%** | **0.7122** | **$1.93\times$** | **29.98%** | **22.54%** | **71.93%** | **0.3433** | **0.7145** |
| **0.15** | Interm. | 281 | 771 | 2,534 | 169 | 1,052 (28.02%) | 26.71% | 62.44% | 0.3742 | 76.67% | 93.75% | 0.6956 | $2.23\times$ | 42.78% | 26.78% | 56.08% | 0.3625 | 0.6904 |
| **0.20** | **Primary (F1-Opt)** | **211** | **481** | **2,824** | **239** | **692 (18.43%)** | **30.49%** | **46.89%** | **0.3695** | **85.45%** | **92.20%** | **0.6617** | **$2.54\times$** | **65.03%** | **30.73%** | **41.52%** | **0.3532** | **0.6527** |
| **0.25** | Interm. | 154 | 286 | 3,019 | 296 | 440 (11.72%) | 35.00% | 34.22% | 0.3461 | 91.35% | 91.07% | 0.6278 | $2.92\times$ | 100.00% | 34.62% | 29.10% | 0.3162 | 0.6132 |
| **0.30** | Primary | 114 | 171 | 3,134 | 336 | 285 (7.59%) | 40.00% | 25.33% | 0.3102 | 94.83% | 90.31% | 0.6008 | $3.34\times$ | 100.00% | 39.21% | 21.40% | 0.2769 | 0.5875 |
| **0.40** | Primary | 46 | 58 | 3,247 | 404 | 104 (2.77%) | 44.23% | 10.22% | 0.1661 | 98.25% | 88.93% | 0.5423 | $3.69\times$ | 100.00% | 42.19% | 7.90% | 0.1331 | 0.5331 |
| **0.50** | Primary | 15 | 21 | 3,284 | 435 | 36 (0.96%) | 41.67% | 3.33% | 0.0617 | 99.36% | 88.30% | 0.5135 | $3.48\times$ | 100.00% | 38.67% | 2.61% | 0.0489 | 0.5106 |
| **0.60** | Primary | 6 | 1 | 3,304 | 444 | 7 (0.19%) | 85.71% | 1.33% | 0.0263 | 99.97% | 88.15% | 0.5065 | $7.15\times$ | 100.00% | 80.17% | 1.11% | 0.0218 | 0.5054 |
| **0.70** | Primary | 2 | 0 | 3,305 | 448 | 2 (0.05%) | 100.00% | 0.44% | 0.0088 | 100.00% | 88.06% | 0.5022 | $8.34\times$ | 100.00% | 100.00% | 0.45% | 0.0089 | 0.5022 |
| **0.80** | Primary | 1 | 0 | 3,305 | 449 | 1 (0.03%) | 100.00% | 0.22% | 0.0044 | 100.00% | 88.04% | 0.5011 | $8.34\times$ | 100.00% | 100.00% | 0.23% | 0.0045 | 0.5011 |
| **0.90** | Primary | 0 | 0 | 3,305 | 450 | 0 (0.00%) | 0.00% | 0.00% | 0.0000 | 100.00% | 88.02% | 0.5000 | $0.00\times$ | 0.00% | 0.00% | 0.00% | 0.0000 | 0.5000 |

---

### 3.3 External Unseen Cohort Verification: `HC-256` 2024 Panel 29 ($N=10,037$, Zero Overlap with `HC-251`, Actual High-Cost $P=1,254$, Unweighted Prev $= 12.49\%$, Weighted Prev $= 11.24\%$)
Full CSV: [`results/threshold_comparison_external_hc256_panel29.csv`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/results/threshold_comparison_external_hc256_panel29.csv)

| Threshold ($\tau$) | TP | FP | TN | FN | Flagged ($N$ / Unw %) | Unw Precision (%) | Unw Recall (%) | Unw F1-Score | Unw Specificity (%) | Unw Bal. Acc. | Wtd Precision (%) | Wtd Recall (%) | Wtd F1-Score | Wtd Bal. Acc. |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.05** | 1,123 | 4,768 | 4,015 | 131 | 5,891 (58.69%) | 19.06% | 89.55% | 0.3143 | 45.71% | 0.6763 | 17.85% | 86.26% | 0.2958 | 0.6800 |
| **0.10** | **973** | **2,934** | **5,849** | **281** | **3,907 (38.93%)** | **24.90%** | **77.59%** | **0.3771** | **66.59%** | **0.7209** | **24.20%** | **72.42%** | **0.3627** | **0.7186** |
| **0.15** | 812 | 1,924 | 6,859 | 442 | 2,736 (27.26%) | 29.68% | 64.75% | 0.4070 | 78.10% | 0.7142 | 29.02% | 58.31% | 0.3875 | 0.7011 |
| **0.20** | **629** | **1,226** | **7,557** | **625** | **1,855 (18.48%)** | **33.91%** | **50.16%** | **0.4046** | **86.04%** | **0.6810** | **33.76%** | **44.62%** | **0.3844** | **0.6677** |
| **0.25** | 485 | 757 | 8,026 | 769 | 1,242 (12.37%) | 39.05% | 38.68% | 0.3886 | 91.38% | 0.6503 | 38.68% | 33.24% | 0.3575 | 0.6329 |
| **0.30** | 341 | 443 | 8,340 | 913 | 784 (7.81%) | 43.49% | 27.19% | 0.3346 | 94.96% | 0.6107 | 43.11% | 23.09% | 0.3007 | 0.5961 |
| **0.40** | 162 | 150 | 8,633 | 1,092 | 312 (3.11%) | 51.92% | 12.92% | 0.2069 | 98.29% | 0.5561 | 51.63% | 10.60% | 0.1759 | 0.5467 |
| **0.50** | 62 | 47 | 8,736 | 1,192 | 109 (1.09%) | 56.88% | 4.94% | 0.0910 | 99.46% | 0.5220 | 56.86% | 3.74% | 0.0702 | 0.5169 |
| **0.60** | 17 | 9 | 8,774 | 1,237 | 26 (0.26%) | 65.38% | 1.36% | 0.0266 | 99.90% | 0.5063 | 61.18% | 1.07% | 0.0211 | 0.5049 |
| **0.70** | 6 | 3 | 8,780 | 1,248 | 9 (0.09%) | 66.67% | 0.48% | 0.0095 | 99.97% | 0.5022 | 64.91% | 0.35% | 0.0070 | 0.5016 |
| **0.80** | 0 | 0 | 8,783 | 1,254 | 0 (0.00%) | 0.00% | 0.00% | 0.0000 | 100.00% | 0.5000 | 0.00% | 0.00% | 0.0000 | 0.5000 |
| **0.90** | 0 | 0 | 8,783 | 1,254 | 0 (0.00%) | 0.00% | 0.00% | 0.0000 | 100.00% | 0.5000 | 0.00% | 0.00% | 0.0000 | 0.5000 |

---

## 4. Visual Diagnostic Evidence ($\ge 600$ DPI Figures)

All five diagnostic figures were generated directly from the machine-readable threshold registry at $600\text{ DPI}$ (`.png`) and vector `.pdf`:

1. **[`fig_t1_precision_recall_f1_vs_threshold.pdf`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/figures/fig_t1_precision_recall_f1_vs_threshold.pdf):** Plots Precision, Recall, and Specificity (Panel A) alongside F1-Score and Balanced Accuracy (Panel B) across $\tau \in [0.05, 0.90]$ for both 5-Fold OOF Validation ($N=15,016$) and the Held-Out Test Set ($N=3,755$). Demonstrates that $\tau = 0.10$ maximizes Balanced Accuracy ($0.7146$ Val / $0.7122$ Test), whereas $\tau = 0.20$ maximizes F1 on the primary grid ($0.3846$ Val / $0.3695$ Test, with fine-grid peak at $\tau = 0.15\text{--}0.17$).
2. **[`fig_t2_precision_recall_tradeoff.pdf`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/figures/fig_t2_precision_recall_tradeoff.pdf):** Plots the continuous Precision–Recall curve overlaid with discrete threshold operating points (Panel A) and compares observed precision against the **Theoretical Oracle Ceiling at Flagged Volume** $\min(P, \text{Flagged}(\tau)) / \text{Flagged}(\tau)$ (Panel B).
3. **[`fig_t3_fp_fn_and_flagged_volume.pdf`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/figures/fig_t3_fp_fn_and_flagged_volume.pdf):** Plots absolute False Positives ($\text{FP}$), False Negatives ($\text{FN}$), and True Positives ($\text{TP}$) across thresholds (Panel A) and the unweighted vs. survey-weighted percentage of patients flagged as high-expenditure (Panel B).
4. **[`fig_t4_confusion_matrices_comparison.pdf`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/figures/fig_t4_confusion_matrices_comparison.pdf):** Side-by-side confusion matrices on the held-out test set ($N=3,755$) at $\tau = 0.10$ (High-Sensitivity Screening), $\tau = 0.20$ (Validation Primary-Grid F1-Optimal Triage), $\tau = 0.30$ (Targeted Intensive Care Management), and $\tau = 0.50$ (Naive Default Cutoff).
5. **[`fig_t5_calibration_and_overfitting_audit.pdf`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/figures/fig_t5_calibration_and_overfitting_audit.pdf):** Shows the patient count distribution and observed vs. predicted event rates across probability bins on the test set (Panel A) alongside the 7-cohort cross-split and cross-release generalization audit (Panel B).

---

## 5. Six-Factor Root-Cause Investigation: Why Precision is $23.18\%$ at $\tau = 0.10$

To determine why the reference model yields $23.18\%$ precision at $\tau = 0.10$, we systematically evaluated all six candidate hypotheses specified in the study protocol.

### Factor 1: Threshold Sensitivity & Volume-Ceiling Mathematics (**Primary Direct Cause**)
Setting $\tau = 0.10$ equates the classification cutoff to the approximate population base rate ($\sim 10\%$). Because the logistic regression model outputs calibrated probabilities centered around the population prevalence, $39.97\%$ of the test cohort ($1,501 / 3,755$ patients) have a predicted probability $\hat{p}_i \ge 0.10$.
- However, the entire test set contains only $P = 450$ true high-expenditure patients ($11.98\%$).
- Therefore, **even a hypothetical perfect oracle classifier ($100\%$ recall, $\text{ROC-AUC} = 1.00$) that flags $1,501$ patients is mathematically bounded by:**
  $$\text{Precision}_{\text{oracle}}(\text{Flagged} = 1,501) = \frac{\min(450, 1,501)}{1,501} = \frac{450}{1,501} = 29.98\%$$
- At $\tau = 0.10$, our model captures $348$ of those $450$ patients, achieving $348 / 1,501 = 23.18\%$ precision — which is **$77.33\%$ of the theoretical maximum precision mathematically achievable when flagging $40\%$ of the cohort**.
- When $\tau$ is increased to $\tau = 0.20$, the flagged volume drops from $39.97\%$ ($1,501$ patients) to $18.43\%$ ($692$ patients), **eliminating $672$ false positives (a $58.28\%$ reduction in $\text{FP}$, from $1,153$ to $481$)** and raising precision to **$30.49\%$ ($2.54\times$ base rate)**. At $\tau = 0.30$, flagged volume drops to $7.59\%$ ($285$ patients), **cutting false positives by $85.17\%$ (to $171$)** and raising precision to **$40.00\%$ ($3.34\times$ base rate)**.

### Factor 2: Class Imbalance & Base-Rate Conditioning (**Structural Contributing Factor**)
High-expenditure healthcare utilization is inherently right-skewed and rare by definition ($\ge \text{P90}_{\text{wtd}} = \$17,827.41$, so $\pi = 10.51\%$ weighted / $11.98\%$ unweighted). By Bayes' rule:
$$\text{Precision}(\tau) = \frac{\text{Recall}(\tau) \cdot \pi}{\text{Recall}(\tau) \cdot \pi + \text{FPR}(\tau) \cdot (1 - \pi)} = \frac{1}{1 + \frac{1-\pi}{\pi} \cdot \frac{\text{FPR}(\tau)}{\text{Recall}(\tau)}}$$
Because the negative-to-positive class odds ratio is $\frac{1-\pi}{\pi} = \frac{3,305}{450} = 7.344$ (unweighted) or $\frac{0.8949}{0.1051} = 8.518$ (survey-weighted), every $1\%$ increase in false positive rate ($\text{FPR}$) generates $7.34\times$ as many false positives as a $1\%$ increase in recall generates true positives. At $\tau = 0.10$, achieving $77.33\%$ recall requires accepting an $\text{FPR}$ of $34.89\%$ ($\text{Specificity} = 65.11\%$), which directly yields $\text{Precision} = \frac{0.7733 \times 0.11984}{0.7733 \times 0.11984 + 0.3489 \times 0.88016} = 23.18\%$.

### Factor 3: Model Discrimination Ceiling (**Moderate Contributing Factor**)
The 11-feature Observable Logistic Regression model achieves a threshold-independent test ROC-AUC of $0.7654$ ($95\%$ bootstrap CI: $[0.7444, 0.7881]$) and PR-AUC of $0.3184$ ($2.66\times$ the $0.1198$ random baseline). While this represents substantial discriminative signal for survey-based clinical screening, positive and negative class probability distributions overlap across intermediate comorbidity profiles. Importantly, our nine-model benchmark confirms that **nonlinear models trained on the exact same 11 observable features do not overcome this ceiling**:
- **Observable Logistic Regression (Serving):** ROC-AUC $= 0.7654$, PR-AUC $= 0.3184$, Weighted BSS $= +0.1025$
- **Observable Tuned XGBoost Classifier:** ROC-AUC $= 0.7662$ ($p > 0.78$ vs. Logistic via paired DeLong test), PR-AUC $= 0.3119$, Weighted BSS $= +0.0977$

Even expanding to all 17 candidate demographics, insurance, and comorbidity features (Ab-09) yields ROC-AUC $= 0.7689$ ($\Delta = +0.0035$). Thus, the discrimination ceiling is a property of intake-observable survey variables rather than linear model misspecification.

### Factor 4: Probability Calibration & Score Distribution Concentration (**Explains Intermediate-Threshold Behavior & High-Cutoff Collapse**)
Auditing predicted probability bins on the held-out test set ($N=3,755$, [`results/threshold_analysis_complete_registry.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/crc_revision/results/threshold_analysis_complete_registry.json)) reveals that **the model's probabilities are well-calibrated across the entire risk spectrum**, with an overall test Brier score of $0.0936$ (Weighted Brier $= 0.0845$, Weighted BSS $= +0.1025$):

| Predicted Probability Bin | Test Patients ($N$) | % of Test Cohort | Observed High-Cost ($N$) | Mean Predicted Prob ($\bar{\hat{p}}$) | Observed Unw. Event Rate (%) | Observed Survey-Wtd Event Rate (%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$[0.00, 0.05)$** | $1,474$ | $39.25\%$ | $49$ | $3.15\%$ | $3.32\%$ | $3.38\%$ |
| **$[0.05, 0.10)$** | $780$ | $20.77\%$ | $53$ | $7.08\%$ | $6.79\%$ | $6.74\%$ |
| **$[0.10, 0.15)$** | $449$ | $11.96\%$ | $67$ | $12.23\%$ | $14.92\%$ | $14.07\%$ |
| **$[0.15, 0.20)$** | $360$ | $9.59\%$ | $70$ | $17.44\%$ | $19.44\%$ | $17.90\%$ |
| **$[0.20, 0.25)$** | $252$ | $6.71\%$ | $57$ | $22.34\%$ | $22.62\%$ | $24.16\%$ |
| **$[0.25, 0.30)$** | $155$ | $4.13\%$ | $40$ | $27.43\%$ | $25.81\%$ | $23.22\%$ |
| **$[0.30, 0.40)$** | $181$ | $4.82\%$ | $68$ | $34.47\%$ | $37.57\%$ | $37.24\%$ |
| **$[0.40, 0.50)$** | $68$ | $1.81\%$ | $31$ | $44.27\%$ | $45.59\%$ | $44.50\%$ |
| **$[0.50, 0.60)$** | $29$ | $0.77\%$ | $9$ | $54.37\%$ | $31.03\%$ | $28.76\%$ |
| **$[0.60, 0.70)$** | $5$ | $0.13\%$ | $4$ | $63.48\%$ | $80.00\%$ | $73.01\%$ |
| **$[0.70, 0.80)$** | $1$ | $0.03\%$ | $1$ | $70.35\%$ | $100.00\%$ | $100.00\%$ |
| **$[0.80, 0.90)$** | $1$ | $0.03\%$ | $1$ | $80.08\%$ | $100.00\%$ | $100.00\%$ |
| **$[0.90, 1.00]$** | $0$ | $0.00\%$ | $0$ | — | — | — |

Two critical insights emerge from this calibration audit:
1. **Why precision is $23.18\%$ at $\tau = 0.10$:** More than half of all patients flagged at $\tau = 0.10$ ($809$ out of $1,501$ flagged patients, or $53.9\%$) reside in the $[0.10, 0.20)$ probability band, where the model correctly predicts a $12.2\%\text{--}17.4\%$ risk and the actual observed high-cost rate is $14.9\%\text{--}19.4\%$. Because the model is well-calibrated, patients with a $15\%$ predicted probability only experience high costs $\sim 15\%$ of the time; classifying all of them as binary positive (`1`) inevitably generates $\sim 85\%$ false positives within that band.
2. **Why high thresholds ($\tau \ge 0.50$) suffer severe recall collapse:** Because predicted probabilities are well-calibrated and bounded by $\max(\hat{p}_{\text{test}}) = 0.8008$ ($\text{P99 of } \hat{p}_{\text{test}} = 0.4981$), only $36$ test patients ($0.96\%$) have $\hat{p}_i \ge 0.50$, and $0$ patients have $\hat{p}_i \ge 0.90$. Thus, a naive $\tau = 0.50$ cutoff misses $96.67\%$ of high-expenditure patients ($\text{Recall} = 3.33\%$, $\text{FN} = 435$).

### Factor 5: Overfitting vs. Generalization Audit (**Conclusively Refuted**)
To test whether overfitting contributed to the precision behavior on the test set, we compared threshold-independent and threshold-specific performance across **seven internal and external cohorts** (`N = 15,016` to `N = 18,979`):

| Evaluation Split / Cohort | Sample Size ($N$) | Overlap with `HC-251` Train | Unw. ROC-AUC | Wtd. ROC-AUC | Unw. PR-AUC | Unw. Brier | Wtd. BSS | Precision at $\tau=0.10$ | Recall at $\tau=0.10$ | Precision at $\tau=0.20$ | Recall at $\tau=0.20$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`HC-251` Train (In-Sample)** | $15,016$ | $100\%$ | $0.7815$ | $0.7885$ | $0.3310$ | $0.0894$ | $+0.1055$ | $23.56\%$ | $77.44\%$ | $31.69\%$ | $49.94\%$ |
| **`HC-251` 5-Fold Stratified OOF** | $15,016$ | $0\%$ (Out-of-Fold) | $0.7795$ | $0.7863$ | $0.3260$ | $0.0897$ | $+0.1021$ | $23.48\%$ | $77.17\%$ | $31.38\%$ | $49.67\%$ |
| **`HC-251` 5-Fold Household (`DUID`) OOF** | $15,016$ | $0\%$ Person & HH | $0.7785$ | $0.7852$ | $0.3252$ | $0.0899$ | $+0.1008$ | $23.47\%$ | $77.06\%$ | $31.42\%$ | $49.72\%$ |
| **`HC-251` Held-Out Test Set** | $3,755$ | $0\%$ Person ($72.2\%$ HH) | $0.7654$ | $0.7707$ | $0.3184$ | $0.0936$ | $+0.1025$ | $23.18\%$ | $77.33\%$ | $30.49\%$ | $46.89\%$ |
| **`HC-256` 2024 Panel 29 (100% Unseen)** | $10,037$ | **$0\%$ Person & $0\%$ HH** | **$0.7824$** | **$0.7812$** | **$0.3506$** | **$0.0947$** | **$+0.1180$** | **$24.90\%$** | **$77.59\%$** | **$33.91\%$** | **$50.16\%$** |
| **`HC-256` 2024 Full Cross-Sectional** | $18,979$ | $46.2\%$ (Panel 28) | $0.7852$ | $0.7848$ | $0.3522$ | $0.0964$ | $+0.1235$ | $25.55\%$ | $78.02\%$ | $34.72\%$ | $50.85\%$ |
| **`HC-257` Panel 28 Prospective Year-2** | $8,708$ | Longitudinal Panel 28 | $0.7732$ | $0.7807$ | $0.3536$ | $0.1003$ | $+0.1149$ | $26.35\%$ | $76.29\%$ | $35.09\%$ | $48.72\%$ |

**Conclusion on Overfitting:** The generalization gap between in-sample training (`0.7815`) and 5-Fold Stratified OOF (`0.7795`) is only $\Delta = -0.0020$, and on the completely unseen 2024 Panel 29 cohort ($N=10,037$, zero person or household overlap), ROC-AUC (`0.7824`), PR-AUC (`0.3506`), and Precision (`24.90%` at $\tau=0.10$, `33.91%` at $\tau=0.20$) **exceed** the in-sample 2023 training metrics. Thus, **overfitting is conclusively ruled out**.

### Factor 6: Feature Granularity Limitations & Aleatoric Healthcare Cost Variance (**Fundamental Domain Ceiling**)
By design, the deployed serving classifier excludes retrospective healthcare utilization variables (inpatient nights `IPNGTD23`, emergency department visits `ERTOT23`, outpatient visits `OBTOTV23`, and prescription fills `RXTOT23`) to prevent simultaneous-year target leakage (`Target- Proxy Circularity`) and enable cold-start onboarding for new insurance applicants. Analyzing the 11 intake-observable features on `HC-251` Test ($N=3,755$) reveals two structural domain constraints:
1. **Unpredicted Acute Catastrophic Shocks among Zero-Comorbidity Individuals:** Exactly $1,358 / 3,755$ test adults ($36.17\%$) have **zero diagnosed chronic comorbidity clusters** (`Comorbidity_Count == 0`). Yet $46$ of these healthy-appearing individuals ($3.39\%$ of the subgroup, representing **$10.22\%$ of all $450$ high-cost cases**) incur $\ge \$17,827.41$ in annual medical expenditures due to stochastic acute events (e.g., motor vehicle trauma, appendicitis/acute surgical emergencies, complicated childbirth, or newly diagnosed malignancies). No intake questionnaire can predict stochastic trauma or acute emergencies at high precision.
2. **Episodic Realization of High Costs among Severely Multimorbid Patients:** Conversely, among the $734$ test patients with $\ge 3$ chronic comorbidity clusters (`Comorbidity_Count >= 3`), only $207$ ($28.20\%$) exceed $\$17,827.41$ in calendar year 2023, while the remaining $527$ ($71.80\%$) are stably managed via low-cost generic pharmacotherapy and routine office visits without requiring inpatient hospitalization during that specific 12-month window. Because MEPS binary comorbidity indicators (`HIBPDX`, `DIABDX_M18`, etc.) lack clinical severity staging (e.g., HbA1c, eGFR, ejection fraction, prior 12-month hospitalization count), the conditional probability $P(Y=1 \mid \mathbf{X}_{\text{observable}})$ for most multimorbid profiles legitimately lies in the $20\%\text{--}45\%$ range rather than approaching $100\%$.

---

## 6. Explicit Answers to Phase 1 Research Questions & Operating Threshold Recommendations

### Q1. Does increasing the threshold meaningfully improve precision?
**Yes.** Increasing $\tau$ from $0.10$ to $0.20$ increases test precision from **$23.18\%$ to $30.49\%$** ($+7.31$ percentage points, a $+31.5\%$ relative gain, lifting enrichment from $1.93\times$ to $2.54\times$ the baseline rate) and cuts false positives by **$58.28\%$** (from $1,153$ to $481$). Increasing $\tau$ to $0.30$ further increases test precision to **$40.00\%$** ($+16.82$ percentage points over baseline, $3.34\times$ enrichment) and cuts false positives by **$85.17\%$** (from $1,153$ to $171$). On the unseen 2024 Panel 29 cohort ($N=10,037$), precision similarly rises from $24.90\%$ ($\tau=0.10$) to $33.91\%$ ($\tau=0.20$) and $43.49\%$ ($\tau=0.30$).

### Q2. At what threshold does recall drop too sharply for high-expenditure patient screening?
- Between $\tau = 0.10$ and $\tau = 0.15$, recall declines moderately from $77.33\%$ to $62.44\%$ while F1 improves from $0.3567$ to $0.3742$.
- At **$\tau = 0.20$**, the model still captures nearly half of all high-cost patients ($\text{Recall} = 46.89\%$ on Test, $49.67\%$ on OOF Validation, $50.16\%$ on 2024 Panel 29) while maintaining $85.45\%$ specificity.
- **Beyond $\tau = 0.30$ ($\text{Recall} = 25.33\%$), recall collapses rapidly:** at $\tau = 0.40$, recall falls to $10.22\%$ ($404 / 450$ high-cost patients missed), and at $\tau = 0.50$, recall falls to $3.33\%$ ($435 / 450$ missed). Therefore, **$\tau > 0.30$ is unsuitable for general population screening**, and **$\tau \ge 0.50$ causes catastrophic false-negative failure**.

### Q3. Which threshold gives the best F1-score?
- **On the Primary Threshold Grid ($\{0.10, 0.20, \dots, 0.90\}$):** Selected strictly on 5-Fold OOF Validation ($N=15,016$), **$\tau = 0.20$ maximizes both unweighted F1 ($0.3846$ vs. $0.3600$ at $\tau=0.10$) and survey-weighted F1 ($0.3551$ vs. $0.3322$ at $\tau=0.10$)**. On the held-out test set ($N=3,755$), $\tau = 0.20$ achieves a higher unweighted F1 ($0.3695$ vs. $0.3567$) and higher survey-weighted F1 ($0.3532$ vs. $0.3433$) than $\tau = 0.10$, as well as on unseen 2024 Panel 29 ($\text{F1} = 0.4046$ at $\tau=0.20$ vs. $0.3771$ at $\tau=0.10$).
- **On the Fine Diagnostic Grid ($0.01$ increments on OOF Validation):** Unweighted OOF validation F1 peaks across a flat plateau between **$\tau = 0.15$ ($\text{Val F1} = 0.3873$, $\text{Test F1} = 0.3742$, $\text{Panel 29 F1} = 0.4070$)** and **$\tau = 0.17$ ($\text{Val F1} = 0.3910$, $\text{Test F1} = 0.3729$)**, while survey-weighted OOF validation F1 peaks at **$\tau = 0.17$ ($\text{Val Wtd F1} = 0.3656$, $\text{Test Wtd F1} = 0.3667$)**.

### Q4. Which threshold gives the best practical healthcare trade-off?
Because healthcare risk stratification serves distinct operational workflows with different per-patient intervention budgets and false-negative costs, **no single static cutoff is optimal for all clinical deployments**. Instead, our empirical findings support a **three-tier operational decision framework** using the same calibrated probability output $\hat{p}_i$:

| Operational Tier | Recommended Threshold ($\tau$) | Validation Selection Criterion | Held-Out Test Performance ($N=3,755$) | 2024 Unseen Panel 29 ($N=10,037$) | Target Healthcare Use Case |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **Tier 1: Broad Preventive Screening** | **$\tau = 0.10$** *(Original Reference)* | **Max Balanced Accuracy** ($\text{Val} = 0.7146$) | Prec: **$23.18\%$** ($1.93\times$)<br>Rec: **$77.33\%$** \| F1: **$0.3567$**<br>BalAcc: **$0.7122$** \| Flag: **$39.97\%$** | Prec: **$24.90\%$** ($1.99\times$)<br>Rec: **$77.59\%$** \| F1: **$0.3771$**<br>BalAcc: **$0.7209$** \| Flag: **$38.93\%$** | Low-cost automated outreach, wellness reminders, and actuarial tail-risk pool identification where missing a catastrophic case ($\text{FN}$) is much costlier than a false alarm. |
| **Tier 2: Balanced Care-Management Triage** | **$\tau = 0.20$** *(or $\tau = 0.15$ fine-grid)* | **Max Primary-Grid F1-Score** ($\text{Val F1} = 0.3846$, $\text{Wtd F1} = 0.3551$) | Prec: **$30.49\%$** ($2.54\times$)<br>Rec: **$46.89\%$** \| F1: **$0.3695$**<br>Spec: **$85.45\%$** \| Flag: **$18.43\%$**<br>*(Cuts FP by $58.3\%$)* | Prec: **$33.91\%$** ($2.71\times$)<br>Rec: **$50.16\%$** \| F1: **$0.4046$**<br>Spec: **$86.04\%$** \| Flag: **$18.48\%$** | Nurse-led telephone triage, chronic disease medication therapy management (MTM), and moderate-cost preventive care coordination. |
| **Tier 3: High-Specificity Intensive Intervention** | **$\tau = 0.30$** | **High Specificity ($\ge 94.5\%$) & $\ge 3.3\times$ Enrichment** | Prec: **$40.00\%$** ($3.34\times$)<br>Rec: **$25.33\%$** \| F1: **$0.3102$**<br>Spec: **$94.83\%$** \| Flag: **$7.59\%$**<br>*(Cuts FP by $85.2\%$)* | Prec: **$43.49\%$** ($3.48\times$)<br>Rec: **$27.19\%$** \| F1: **$0.3346$**<br>Spec: **$94.96\%$** \| Flag: **$7.81\%$** | Capacity-constrained multidisciplinary case management, home-health visits, and intensive social-work navigation restricted to the top $\sim 7.5\%$ highest-risk enrollees. |

### Q5. Should $\tau = 0.10$ be retained, replaced, or presented alongside an alternative operating point?
**$\tau = 0.10$ should be retained as the high-sensitivity screening baseline (which maximizes Balanced Accuracy at $0.7122$) and presented alongside $\tau = 0.20$ (the validation-selected primary-grid F1-optimal triage cutoff, $30.49\%$ precision, $46.89\%$ recall) and $\tau = 0.30$ (high-specificity targeted intervention, $40.00\%$ precision, $94.83\%$ specificity) within a multi-tier operational framework.** Presenting the full threshold sensitivity curve ($\tau \in [0.05, 0.90]$) resolves reviewer concerns regarding the $23.18\%$ precision at $\tau = 0.10$, proves that the low precision at $\tau = 0.10$ is a deliberate high-sensitivity operating choice bounded by the $29.98\%$ volume ceiling rather than model failure or overfitting, and empowers healthcare administrators to select the exact decision threshold matching their clinical intervention capacity.
