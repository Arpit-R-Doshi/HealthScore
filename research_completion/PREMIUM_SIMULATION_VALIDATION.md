# HealthScore Premium & Loss Simulation Validation Report

**Document ID:** `HS-REP-04-PREMIUM-VALIDATION`
**Evaluation Date:** October 2026 (Audited & Parameterized Edition)
**Auditor:** Autonomous Actuarial-Engineering Reviewer & Senior Healthcare Systems Architect
**Implementation Source:** [`ml_model/risk_engine.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/risk_engine.py)
**Test Suite:** [`ml_model/tests/test_premium_simulation.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/tests/test_premium_simulation.py) (14/14 Passing Tests)
**Sensitivity Analysis Script:** [`research_completion/experiments/run_premium_sensitivity.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/experiments/run_premium_sensitivity.py)
**Machine-Readable Results:** [`research_completion/reports/premium_sensitivity_results.json`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/reports/premium_sensitivity_results.json)
**Visualization:** [`fig6_premium_sensitivity.png`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/figures/fig6_premium_sensitivity.png)

---

## 1. Executive Summary

HealthScore incorporates an off-chain risk engine that converts machine learning predictions into expected healthcare costs and simulated insurance premium estimates. This report validates the mathematical correctness, software invariants, edge-case robustness, and actuarial scoping boundaries of the premium simulation module.

### Core Finding
The premium simulation functions as a transparent, parameterized Value-at-Risk (VaR) demonstration heuristic. It demonstrates software-level correctness, monotonic scaling, deterministic reproducibility, and closed-form calibration against theoretical Gamma quantiles within **$0.7\%$**. However, it does **not** constitute an actuarially certified commercial insurance rating model.

---

## 2. Mathematical Specification

The premium module implements a Monte Carlo parametric loss simulation based on a shifted two-parameter Gamma loss distribution scaled by an explicit, dimensionless risk-loading parameter:

$$X_\alpha = B + (1 + \alpha) G$$

where:
- $\hat{y}$: Model-predicted expected annual healthcare expenditure (derived from the 11-feature Observable Tweedie GLM in USD).
- $B \ge 0$: Configurable base expenditure floor (defaulting to $\$500.00$, representing baseline administrative and preventive overhead).
- $G \sim \text{Gamma}(k = 1.5, \theta = \frac{\hat{y}}{1.5})$: Simulated loss component, parameterized so that $\mathbb{E}[G] = k\theta = \hat{y}$.
- $\alpha \ge 0$: Dimensionless **risk-loading parameter** (default $\alpha = 0.0$). When $\alpha = 0$, $X_0 = B + G$ reproduces the un-loaded baseline simulation exactly. For $\alpha > 0$, the simulated loss is scaled by $(1 + \alpha)$, representing a conservative risk-loaded pricing scenario.
- $N = 5,000$ (default) or $N = 20,000$ (sensitivity analysis): Number of independent pseudo-random synthetic loss draws.
- $\text{Premium} = \text{Percentile}_{95}(X_\alpha)$: 95th-percentile Value-at-Risk of the simulated loss distribution.
- $\text{Loss Percentiles} = [P_5, P_{50}, P_{90}, P_{95}, P_{99}]$.

---

## 3. Implementation Corrections & Hardening

During this hardening pass, the implementation in `risk_engine.py` was enhanced:

1. **Explicit Risk-Loading Parameter ($\alpha$):**
   Added `pricing_alpha=0.0` to `monte_carlo_simulation()` and `calculate_risk()`. When $\alpha=0$, previous behavior is strictly preserved bit-for-bit.
2. **Deterministic Random Seed Support:**
   Added an optional `seed` parameter. When provided, an independent `np.random.default_rng(seed)` generator is used, ensuring exact bit-level determinism down to the cent across calls.
3. **Fail-Closed Input Validation:**
   Rejects `None`, `NaN`, infinite, negative, or non-numeric inputs for `predicted_mean_cost`, `base_cost`, and `pricing_alpha` with explicit `ValueError` exceptions.
4. **Rich Percentile Hierarchy:**
   Returns full simulated percentiles ($P_5 \le P_{50} \le P_{90} \le P_{95} \le P_{99}$), base cost, pricing alpha, and explicit non-actuarial disclaimers via `return_details=True`.
5. **Subprocess and API Propagation:**
   Wired `base_cost` and `pricing_alpha` through `ml_model/run_engine.py` and Node.js backend.

---

## 4. Automated Invariant & Scenario Test Suite

Fourteen automated invariant tests are verified in [`test_premium_simulation.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/tests/test_premium_simulation.py):

| Test Case Name | Invariant Tested | Verified Behavior | Status |
| :--- | :--- | :--- | :---: |
| `test_non_negativity_and_base_floor` | Non-negativity & Floor | Premium and percentiles strictly $\ge \$500.00$ for all costs $\le \$0$ to $\$50,000$. | **PASSED** |
| `test_percentile_ordering_and_equality` | Quantile Monotonicity | $P_5 \le P_{95}$ strictly holds; target premium strictly equals $P_{95}$. | **PASSED** |
| `test_full_percentile_hierarchy_and_details` | Percentile Hierarchy | $P_5 \le P_{50} \le P_{90} \le P_{95} \le P_{99}$ holds across all cost tiers. | **PASSED** |
| `test_determinism_with_fixed_seed` | Replicability | Identical inputs and seed produce identical outputs down to $\$0.01$. | **PASSED** |
| `test_monotonicity_under_fixed_seed` | Stochastic Dominance | Increasing expected costs ($\$500 \to \$25,000$) produce monotonically non-decreasing premiums. | **PASSED** |
| `test_pricing_alpha_default_compatibility` | Backward Compatibility | $\alpha=0$ reproduces default simulation outputs bit-for-bit across all expenditure levels. | **PASSED** |
| `test_pricing_alpha_monotonicity_under_crn` | Loading Monotonicity | Increasing $\alpha \in [0.0, 1.0]$ strictly non-decreases simulated premium and quantiles. | **PASSED** |
| `test_analytical_gamma_quantile_agreement` | Theoretical Calibration | Monte Carlo simulated quantiles agree with analytical Gamma PPF within $2.5\%$ ($N=50,000$). | **PASSED** |
| `test_explicit_validation_of_invalid_inputs` | Fail-Closed Guards | Rejects `None`, `NaN`, negative, non-numeric, or invalid parameters with `ValueError`. | **PASSED** |
| `test_boundary_zero_and_extreme_high_inputs`| Boundary Invariance | Boundary zero expenditure returns $B$; extreme high values do not overflow. | **PASSED** |
| `test_loading_and_risk_margin` | Risk Margin Coverage | Target premium exceeds expected mean cost ($\text{VaR}_{0.95} > \hat{C}$), providing reserve margin. | **PASSED** |
| `test_configurable_base_cost_scenario` | Parameter Sensitivity | Monotonic scaling with custom base floors ($\$0 < \$250 < \$500$). | **PASSED** |
| `test_engine_integration_and_disclaimers` | System Integration | Integrated `calculate_risk` returns structured premium, loss percentiles, and disclaimer metadata. | **PASSED** |
| `test_subprocess_run_engine_with_pricing_params`| Subprocess IPC | `run_engine.py` correctly parses and returns custom `base_cost` and `pricing_alpha` in JSON. | **PASSED** |

---

## 5. Systematic Sensitivity Analysis Across 60 Scenarios

Executed via [`run_premium_sensitivity.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/experiments/run_premium_sensitivity.py) across 4 base floors ($B \in \{0, 250, 500, 1000\}$), 5 risk loadings ($\alpha \in \{0, 0.10, 0.25, 0.50, 1.00\}$), and 3 expenditure levels ($\$1,500, \$5,000, \$15,000$) using Common Random Numbers ($N = 20,000$, Seed $= 42$):

| Expected Cost $\hat{y}$ | Base Floor $B$ | Risk-Loading $\alpha$ | Simulated P95 ($) | Analytical Gamma P95 ($) | Rel Error (%) | Premium Uplift ($) | Uplift (%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Moderate ($5,000) | $500.00 | 0.00 | **$13,616.94** | $13,524.55 | 0.683% | $0.00 | 0.00% |
| Moderate ($5,000) | $500.00 | 0.10 | **$14,928.63** | $14,827.00 | 0.685% | +$1,311.69 | +9.63% |
| Moderate ($5,000) | $500.00 | 0.25 | **$16,896.17** | $16,780.68 | 0.688% | +$3,279.23 | +24.08% |
| Moderate ($5,000) | $500.00 | 0.50 | **$20,175.41** | $20,036.82 | 0.692% | +$6,558.47 | +48.16% |
| Moderate ($5,000) | $500.00 | 1.00 | **$26,733.88** | $26,549.09 | 0.696% | +$13,116.94 | +96.33% |

*Analytical Calibration:* Across all 60 scenarios, Monte Carlo simulation aligns with the theoretical quantile $Q_{X_\alpha}(0.95) = B + (1+\alpha)\text{Gamma}^{-1}(0.95; 1.5, \hat{y}/1.5)$ within **$0.68\%$ to $0.71\%$**.

---

## 6. Actuarial Limitations & Scoping Disclosure

While mathematically verified, HealthScore outputs must **never** be presented as an actuarially certified commercial insurance rating system:
1. **Absence of Real Claims & Benefit Design:** Predictions rely on MEPS survey totals rather than insurer claims with deductibles, copayments, coinsurance, and out-of-pocket maximums.
2. **No Statutory Expense Loadings:** Commercial rate filings require compliance with the ACA Medical Loss Ratio (80/20 rule), administrative overhead allowances, and state premium taxes.
3. **No Risk Corridors or Transfers:** Does not simulate statewide risk adjustment transfer pools (ACA Section 1343).
4. **No Solvency Modeling:** Single-period Value-at-Risk does not model multi-year carrier capital solvency (NAIC Risk-Based Capital).

**Classification:** Strictly an **exploratory loss simulation heuristic** for technical demonstration.
