# HealthScore Actuarial Scope & Solvency Assessment (Phase 2 — Stage E)

**Document Version:** 1.0  
**Evaluation Date:** October 2026  
**Evaluation Scope:** Technical Audit of Monte Carlo Simulation, Value-at-Risk Heuristics, Premium Terminology, and Solvency Modeling Gaps  
**Repository Branch:** `feature/ml-pipeline-rebuild`  
**Compliance Standard:** Actuarial Modeling and Governance Disclosure  

---

## Executive Summary & Regulatory Boundary

> [!CAUTION]
> **ACTUARIAL DISCLAIMER & CRITICAL BOUNDARY DECLARATION:**
> HealthScore's current codebase does **NOT** constitute an actuarial pricing engine, an insurance underwriting system, or a solvency capital model.
> 
> The outputs labeled `premium`, `confidence_interval`, and `monte_carlo_simulation` in `ml_model/risk_engine.py` are **exploratory parametric simulation heuristics** designed for technical demonstration. They must **never** be used to price commercial insurance policies, determine capital adequacy, underwrite individual applicants, or establish statutory reserves.
> 
> Statistical expenditure predictions derived from the Medical Expenditure Panel Survey (MEPS) cannot validate insurance premium rates or financial solvency. Commercial insurance pricing requires plan-specific claims data, formal benefit design adjustments, expense loadings, risk margins, regulatory rate filings, and sign-off by a credentialed actuary (MAAA / FSA / FCAS).

---

## 1. Technical Audit of the Current Simulation Engine

The table below provides a forensic audit of the implementation in `ml_model/risk_engine.py` (`monte_carlo_simulation` and `calculate_risk`):

```python
def monte_carlo_simulation(predicted_mean_cost, n_simulations=5000):
    if predicted_mean_cost <= 0:
        predicted_mean_cost = 500.0

    shape = 1.5
    scale = predicted_mean_cost / shape
    losses = np.random.gamma(shape, scale, n_simulations)
    target_premium = round(float(np.percentile(losses, 95)), 2)
    p5 = round(float(np.percentile(losses, 5)), 2)
    p95 = round(float(np.percentile(losses, 95)), 2)
    return target_premium, p5, p95
```

### Forensic Breakdown of Simulation Quantities

| Quantity / Parameter | Value in Code | Technical Derivation | Actuarial Status | Gap & Flaw Analysis |
| :--- | :--- | :--- | :--- | :--- |
| **Input Mean ($\mu$)** | `predicted_mean_cost` | Model-derived point estimate from Tweedie GLM or $\text{expm1}(\text{XGBoost})$. | **Model-Derived** | Represents individual annual gross expected spend; ignores benefit design and cost-sharing. |
| **Distribution Family** | Gamma($k, \theta$) | Parametric assumption via `np.random.gamma`. | **Assumed** | Real medical claims exhibit extreme heavy tails (often Pareto, Generalized Beta 2, or zero-inflated two-part lognormal). |
| **Shape Parameter ($k$)** | `1.5` | Hardcoded constant across all profiles. | **Hardcoded / Arbitrary** | Implies a fixed coefficient of variation $\text{CV} = 1/\sqrt{1.5} \approx 0.816$. In reality, spend variance varies by age, health, and disease chronicity. |
| **Sample Size ($N$)** | `5,000` | Pseudo-random Monte Carlo draws. | **Assumed** | Draws represent individual variation, not aggregate portfolio risk or parameter uncertainty. |
| **`target_premium`** | 95th Percentile ($P_{95}$) | `np.percentile(losses, 95)` | **HEURISTIC MISNOMER** | **Fatal Actuarial Flaw:** Pricing an individual policy at the 95th percentile of an individual's parametric loss distribution conflates single-life tail volatility with pooled commercial pricing. In commercial insurance, pure premium is determined from portfolio-level expected loss plus risk/expense loadings, not by charging each policyholder their individual 95th percentile tail draw. |
| **Expense Loading ($e$)** | Zero ($0.0\%$) | Omitted from simulation. | **Missing** | Ignores general administrative expenses, commissions, premium taxes, and claims adjustment expenses (ALAE/ULAE) (typically 12–20% of premium). |
| **Risk Margin / Profit ($\pi$)** | Zero ($0.0\%$) | Omitted from simulation. | **Missing** | Ignores cost of capital, surplus preservation, and underwriting risk margins. |
| **Benefit Structure** | Gross Total Spend | Omitted from simulation. | **Missing** | Assumes 100% coverage with zero deductible, zero coinsurance, zero copays, and no out-of-pocket maximum. |
| **Portfolio Exposure** | Individual Draw | Single-life simulation. | **Missing** | Insurance solvency depends on aggregate portfolio loss distributions across thousands of pooled lives, not single-life Monte Carlo. |

---

## 2. Structural Distinctions: ML Prediction vs Actuarial Science

HealthScore's scientific documentation must maintain a rigorous distinction between four separate modeling tiers:

```
[ Tier 1: Individual Expenditure Prediction ]  <-- CURRENT ML PIPELINE (Tweedie GLM / XGBoost)
        │
        ▼
[ Tier 2: Aggregate Loss Modeling ]            <-- MISSING (Compound Poisson / Collective Risk)
        │
        ▼
[ Tier 3: Commercial Insurance Pricing ]       <-- MISSING (Benefit Design, Expenses, ACA Rating)
        │
        ▼
[ Tier 4: Capital Solvency & Reserves ]        <-- MISSING (RBC, Solvency II, TVaR, Stress Testing)
```

### 1. Tier 1: Individual Expenditure Point Prediction (HealthScore Scope)
- **Mathematical Definition:** Estimating $\mathbb{E}[Y \mid X]$, the conditional expected value of gross medical expenditure for an individual with features $X$.
- **Validation Standard:** Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), calibration slope, and deviance on independent cohorts (HC-256 / HC-257).
- **Capability:** HealthScore provides an exploratory research baseline with modest explanatory power (Tweedie GLM $R^2 \approx 0.06$ on external data with observed nominal underprediction) and ordinal top-decile classification (ROC-AUC $\approx 0.78$), but exhibits substantial residual variance on dollar-scale individual expenditures.

### 2. Tier 2: Aggregate Portfolio Loss Modeling (Unaddressed)
- **Mathematical Definition:** Modeling the aggregate loss $S = \sum_{i=1}^N X_i$ of an entire insured pool, where $N$ is claim frequency and $X_i$ is severity.
- **Actuarial Standard:** Compound distributions, Panjer recursion, copula-based dependence modeling, and portfolio law of large numbers.

### 3. Tier 3: Commercial Insurance Pricing (Unaddressed)
- **Actuarial Rate Formula:**
  $$\text{Gross Premium} = \frac{\mathbb{E}[\text{Plan Claims Cost}] + \text{ALAE} + \text{Risk Margin}}{1 - (\text{Expense Ratio} + \text{Premium Tax} + \text{Target Profit Margin})}$$
- **Legal & Regulatory Constraints:** In ACA-compliant individual/small group markets, rating based on individual health conditions or comorbidity scores is **strictly prohibited by federal law** (guaranteed issue, single risk pool, 3:1 age band limit, smoking status only).

### 4. Tier 4: Capital Solvency and Statutory Reserves (Unaddressed)
- **Regulatory Framework:** NAIC Risk-Based Capital (RBC) requirements, Solvency II, and Actuarial Standards of Practice.
- **Metrics:** Tail Value-at-Risk ($\text{TVaR}_{\alpha}$), Expected Shortfall, and dynamic capital modeling to ensure surplus adequacy under 1-in-200 year insolvency shocks.

---

## 3. Data & Regulatory Requirements for Credible Insurance Pricing

If an insurance enterprise sought to transition HealthScore from an academic research model to a commercial pricing or reserve engine, the following prerequisites would be mandatory:

1. **Member-Level Commercial Claims Data:**
   - Adjudicated institutional and professional claims (UB-04 / CMS-1500), pharmacy claims (NCPDP), and lab results.
   - Distinct identification of billed charges, allowed amounts, plan-paid amounts, and member cost-sharing.
2. **Benefit Design Parameters:**
   - Plan-specific deductibles ($0 to $8,000+), coinsurance rates (e.g. 20%), tiered copayments, out-of-pocket maximums, and formulary tiers.
3. **Exposure & Incurred But Not Reported (IBNR) Reserves:**
   - Detailed member-month exposure records.
   - Actuarial completion factors (chain ladder, Bornhuetter-Ferguson) to adjust for claims lag and runout.
4. **Compliance with Actuarial Standards of Practice (ASOPs):**
   - **ASOP No. 12 (Risk Classification):** Ensures risk classifications are fair, sound, and non-discriminatory.
   - **ASOP No. 23 (Data Quality):** Audits completeness and appropriateness of data used in actuarial analysis.
   - **ASOP No. 41 (Actuarial Communications):** Mandates clear disclosure of uncertainties, limitations, and reliance on other experts.
   - **ASOP No. 56 (Modeling):** Requires model governance, sensitivity testing, and documentation of parameter choices.

---

## 4. Strategic Recommendations & Scope Boundary

To maintain absolute scientific integrity, the project team must adopt **Path 1**:

### Path 1: Retain Simulation as a Labeled Research Demonstration (Recommended)
1. **Relabel Terminology in Engine and UI:**
   - Change `premium` output to `var95_demonstration_heuristic`.
   - Update API documentation to explicitly state that `risk_score` is a predicted gross expenditure expectation, not an insurance price.
2. **Preserve Regulatory Disclaimers:**
   - Retain the explicit warnings in `calculate_risk` and `data_parity_diagnostics` confirming that MEPS spending predictions do not validate underwriting rates or solvency.
3. **Declare Project Boundary:**
   - Define HealthScore as a **health economics and clinical expenditure forecasting research platform**, deliberately excluding commercial underwriting and solvency claims.

### Path 2: Dedicated Actuarial Modeling Workstream (Future Separate Scope)
If commercial insurance pricing is pursued in a future phase, it must be chartered as a separate, independently budgeted initiative requiring:
- Integration of fully adjudicated commercial carrier claims (e.g. MarketScan, FAIR Health).
- Formal partnership with a credentialed Member of the American Academy of Actuaries (MAAA).
- Independent actuarial certification and state insurance department filing readiness.

---
*Report Author: Antigravity Autonomous Research Agent*  
*Repository: HealthScore | Branch: `feature/ml-pipeline-rebuild`*
