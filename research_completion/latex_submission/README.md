# HealthScore Research Manuscript — LaTeX Project Submission

This directory contains the complete, publication-ready LaTeX project for the HealthScore research paper:

> **Evaluating High-Throughput Permissioned Blockchain for Healthcare Workflows: Fabric Performance with ACG-Inspired Risk Scoring and Premium Simulation**

Target publication format: **Springer Lecture Notes in Computer Science (LNCS)**.

---

## 1. Directory Structure

```text
research_completion/latex_submission/
├── main.tex                            # Authoritative LaTeX manuscript source
├── references.bib                      # Verified BibTeX bibliography
├── llncs.cls                           # Official Springer LNCS document class
├── splncs04.bst                        # Official Springer LNCS BibTeX style
├── generate_submission_figures.py      # Automated publication figure generator
├── figures/                            # High-resolution PDF and >=600 DPI PNG assets
│   ├── fig1_roc_pr_curves.pdf          # ROC and PR curves (Raster-backed PDF, 812.5 effective DPI)
│   ├── fig1_roc_pr_curves.png          # ROC and PR curves (600 DPI, 3900x1500 px)
│   ├── fig2_calibration_deciles.pdf    # Calibration & decile stratification (Raster-backed PDF, 812.5 effective DPI)
│   ├── fig2_calibration_deciles.png    # Calibration & decile stratification (600 DPI, 3900x1500 px)
│   ├── fig3_shap_importance.pdf        # Global SHAP feature importance (True Vector PDF)
│   ├── fig3_shap_importance.png        # Global SHAP feature importance (600 DPI, 5940x3540 px)
│   ├── fig4_feature_ablations.pdf      # Systematic feature ablations (True Vector PDF)
│   ├── fig4_feature_ablations.png      # Systematic feature ablations (600 DPI, 7447x4440 px)
│   ├── fig5_blockchain_benchmarks.pdf  # Fabric throughput/latency profiles (True Vector PDF)
│   ├── fig5_blockchain_benchmarks.png  # Fabric throughput/latency profiles (600 DPI, 8340x3264 px)
│   ├── fig5b_caliper_simulation_projection.pdf # Caliper queueing simulation vs empirical (True Vector PDF)
│   ├── fig5b_caliper_simulation_projection.png # Caliper queueing simulation vs empirical (600 DPI, 8340x3240 px)
│   ├── fig6_premium_sensitivity.pdf    # Value-at-Risk premium sensitivity (True Vector PDF)
│   └── fig6_premium_sensitivity.png    # Value-at-Risk premium sensitivity (600 DPI, 9540x3243 px)
├── README.md                           # This documentation and verification manifest
└── final_paper.pdf                     # Successfully compiled camera-ready PDF
```

---

## 2. Compilation Instructions

### Using Tectonic (Recommended)
The project compiles out-of-the-box using the self-contained Tectonic compiler:
```bash
cd research_completion/latex_submission
tectonic main.tex
cp main.pdf final_paper.pdf
```

### Using Standard TeX Live / XeLaTeX
If using a standard TeX Live distribution:
```bash
cd research_completion/latex_submission
xelatex main.tex
bibtex main
xelatex main.tex
xelatex main.tex
cp main.pdf final_paper.pdf
```

Required LaTeX packages: `graphicx`, `amsmath`, `amssymb`, `amsfonts`, `booktabs`, `tabularx`, `url`, `color`, `hyperref`, `microtype`, `array`.

---

## 3. Figure Quality and Resolution Verification (>500 DPI Requirement)

Data figures are provided in both print PDF (`.pdf`) and verified companion high-resolution PNG (`.png`) formats:
- **True Resolution-Independent Vector Plots (Figures 3, 4, 5, 5b, 6):** Generated programmatically via Matplotlib as native vector PDF graphics with smooth scalable bezier curves and fonts, paired with 600+ DPI PNG fallbacks.
- **High-Resolution Raster-Backed PDFs (Figures 1 and 2):** Created by embedding verified high-resolution source bitmap artwork ($3900 \times 1500$ pixels) within standard PDF containers. At the full Springer LNCS text column placement width of 4.80 inches (122 mm), the effective print resolution is **812.5 DPI** ($3900\text{ px} / 4.8\text{ in} = 812.5\text{ DPI}$), substantially exceeding the $\ge 500$ DPI publication requirement. These are explicitly documented as raster-backed PDFs rather than resolution-independent vector graphics.

Every raster asset exceeds the $\ge 500$ DPI publication requirement:

| Figure File | Asset / Format Type | Pixel Dimensions | File DPI | Text Width on LNCS Page | Effective Print DPI |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `fig1_roc_pr_curves` | Raster-backed PDF + PNG | $3900 \times 1500$ px | 600.0 DPI | 4.80 in (122 mm) | **812.5 DPI** |
| `fig2_calibration_deciles` | Raster-backed PDF + PNG | $3900 \times 1500$ px | 600.0 DPI | 4.80 in (122 mm) | **812.5 DPI** |
| `fig3_shap_importance` | True Vector PDF + PNG | $5940 \times 3540$ px | 600.0 DPI | 4.22 in (107 mm) | **1407.6 DPI** |
| `fig4_feature_ablations` | True Vector PDF + PNG | $7447 \times 4440$ px | 600.0 DPI | 4.80 in (122 mm) | **1551.5 DPI** |
| `fig5_blockchain_benchmarks` | True Vector PDF + PNG | $8340 \times 3264$ px | 600.0 DPI | 4.80 in (122 mm) | **1737.5 DPI** |
| `fig5b_caliper_simulation_projection` | True Vector PDF + PNG | $8340 \times 3240$ px | 600.0 DPI | 4.80 in (122 mm) | **1737.5 DPI** |
| `fig6_premium_sensitivity` | True Vector PDF + PNG | $9540 \times 3243$ px | 600.0 DPI | 4.80 in (122 mm) | **1987.5 DPI** |

### Automated Figure Regeneration
To regenerate all figures from source data and registries:
```bash
../../ml_model/venv/bin/python generate_submission_figures.py
```

---

## 4. Exclusion of Old Architecture Diagram

As explicitly required by the project specifications:
- The ASCII/raster architecture diagram from the old paper is **completely excluded** from `main.tex`, the figure directory, and the compiled `final_paper.pdf`.
- Section 3 documents the hybrid off-chain/on-chain transaction lifecycle and Membership Service Provider authorization policies textually and via Table 1 (RBAC authorization policy matrix) without referencing or embedding the old diagram.

---

## 5. Scientific Integrity and Metric Reconciliation

All canonical metrics reported in `final_paper.pdf` strictly match the authoritative manuscript (`REVISED_PAPER.md`) and the underlying benchmark registries (`experiment_registry.json`):

1. **Classification Comparison (Table 6):** Complete 9-model comparison preserved, including:
   - Approved serving candidate: 11-feature Observable Logistic Regression (Weighted Fit, `risk_model_classifier_observable_weighted_p90.pkl`) with ROC-AUC $0.7654$ [95% CI: $0.7444, 0.7881$], PR-AUC $0.3184$ [95% CI: $0.2876, 0.3556$], unweighted Brier $0.0936$, weighted Brier $0.0845$, weighted BSS $+0.1025$, CITL $+0.0646$, and calibration slope $0.9438$.
   - Weighting ablation: 11-feature Observable Logistic Regression (Unweighted Fit) with ROC-AUC $0.7652$, PR-AUC $0.3192$, unweighted Brier $0.0936$, weighted Brier $0.0845$, weighted BSS $+0.1025$, CITL $+0.0570$, and calibration slope $0.9008$.
   - Full baseline and ensemble comparisons: Constant baseline ($0.5000 / 0.1198 / 0.1059 / 0.0941 / +0.0000$), Demographic baseline ($0.7099 / 0.2182 / 0.0996 / 0.0893 / +0.0506$), Random Forest ($0.7693 / 0.3157 / 0.0935 / 0.0841 / +0.1062$), Uncalibrated XGBoost ($0.7705 / 0.3196 / 0.0932 / 0.0838 / +0.1093$), Platt-Calibrated XGBoost ($0.7702 / 0.3183 / 0.0944 / 0.0847 / +0.0998$), and 14-feature Oracle ($0.7904 / 0.3472 / 0.0922 / 0.0832 / +0.1159$).
2. **Corrected Precision-Enrichment Comparison:** Evaluated at predicted-probability threshold $\hat{p} \ge 0.10$, the serving model flags 1,501 individuals with precision $0.2318$ ($348 / 1,501$), representing an unweighted enrichment of approximately **$1.93\times$** ($0.231845 / 0.119840 \approx 1.934\times$) over the unweighted test prevalence ($11.98\%$, $450 / 3,755$).
3. **Paired Statistical Test Disclosures:** Marginal bootstrap confidence intervals overlap descriptively, but the manuscript explicitly states that paired hypothesis tests were not performed, and makes no claim of statistical significance or non-significance.
4. **Off-Chain / On-Chain Split:** The machine learning pipeline executes off-chain; the smart contract records auditable risk-score milestones and transaction state without recomputing model inference.
5. **Hyperledger Fabric Benchmarks:**
   - Linear regime: $199.9$--$200.2$ TPS write throughput with average confirmation latency $\le 0.06$s ($0.03$--$0.04$s median).
   - Saturation knee: $350.1$ TPS historical (commit `944fb0d`, $18.00$s avg latency); $515.8$ TPS 5-worker isolated testbed ($6.98$s avg latency); $485.27 \pm 14.60$ TPS corrected 8-worker stress repetitions ($5.36 \pm 0.22$s avg latency).
   - Read queries: $500.3$--$500.6$ TPS with $\le 0.01$s displayed average latency (two-decimal precision; max $0.04$--$0.13$s).
   - Zero reported failures among submitted transactions ($0/24,500$ historical, $0/31,500$ live 11-round, $0/25,480$ 8-worker rounds).
   - End-to-end analytical single-worker bottleneck: $\approx 20$--$25$ req/s due to Python subprocess overhead ($40$--$50$ ms).
6. **Exploratory Loss Simulation:** $X_\alpha = B + (1+\alpha)G$, verified against analytical Gamma quantiles within $0.68\%$--$0.71\%$ across 60 scenarios, with explicit disclaimers regarding commercial pricing certification.
7. **Canonical Caliper Simulation Alignment (Figure 5b):** Figure 5b dynamically loads canonical simulation outputs from `caliper-benchmark/results/simulated/20261018-011500/simulation_results.json` without fabrication of intermediate points. Canonical simulation medians, P5, and P95 (e.g., 1,000 TPS row: Median 351.53, P5 326.58, P95 379.06 TPS; Median Latency 9.268s, P5 8.2288s, P95 10.3473s) and empirical Caliper benchmark runs are plotted consistently on a unified horizontal axis (`Configured Offered Load / Target Rate (TPS)`) across both throughput and latency panels, with measured send rates (historical 963.6 TPS, live 615.7 TPS, 8-worker 742.7 TPS) explicitly annotated.
8. **Complete Bibliography Reconciliation:** All 10 entries in `references.bib` are actively cited in `main.tex` and resolve without warning:
   - Ledgers and benchmarks: `androulaki2018hyperledger`, `caliper2022`.
   - Health economics and actuarial standards: `ahrq_meps_2023`, `cms2024report`, `kronick2000improving`, `weiner1991development`, `tweedie1984index`.
   - Machine learning evaluation and interpretability: `lundberg2017unified` (SHAP TreeExplainer), `brier1950verification` (Brier score definition), `steyerberg2010assessing` (discrimination, calibration, and prediction model evaluation framework).

---

## 6. Author Confirmations and Notes

- **Double-Blind Peer Review:** Author names and institutional affiliations remain anonymized in accordance with double-blind peer review requirements.
- **No Inventions:** No synthetic claims, missing citations, or unauthorized modifications were introduced during conversion.
