# HealthScore Premium & Loss Simulation Validation Report

**Document ID:** `HS-REP-04-PREMIUM-VALIDATION`
**Evaluation Date:** October 2026
**Auditor:** Autonomous Actuarial-Engineering Reviewer & Senior Healthcare Systems Architect
**Implementation Source:** [`ml_model/risk_engine.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/risk_engine.py)
**Test Suite:** [`ml_model/tests/test_premium_simulation.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/tests/test_premium_simulation.py) (8/8 Passing Tests)

---

## 1. Executive Summary

HealthScore incorporates an off-chain risk engine that converts machine learning predictions into expected healthcare costs and simulated insurance premium estimates. This report validates the mathematical correctness, software invariants, edge-case robustness, and actuarial scoping boundaries of the premium simulation module.

### Core Finding
The premium simulation functions as an exploratory parametric Value-at-Risk (VaR) demonstration heuristic. It demonstrates software-level correctness and deterministic invariance across all tested scenarios. However, it does **not** constitute an actuarially certified commercial insurance rating model.

---

## 2. Mathematical Specification

The premium module implements a Monte Carlo parametric loss simulation based on a shifted two-parameter Gamma distribution:

$$X \sim \text{Gamma}(k = 1.5, \theta = \frac{\hat{C}}{1.5}) + B$$

Where:
- $\hat{C}$: Model-predicted expected annual healthcare expenditure (derived from the 11-feature Observable Tweedie GLM in USD).
- $k = 1.5$: Fixed Gamma shape parameter reflecting moderate positive skewness in individual healthcare claims.
- $\theta = \frac{\hat{C}}{k}$: Scale parameter matching the expected loss mean ($\mathbb{E}[\text{Gamma}] = k\theta = \hat{C}$).
- $B = \$500.00$: Configurable base expenditure floor (defaulting to $\$500.00$, originating as an arbitrary administrative scalar in prototype commit `af6a322`).
- $N = 5,000$: Number of independent pseudo-random synthetic loss draws.
- $\text{Premium} = \text{VaR}_{0.95}(X)$: 95th-percentile Value-at-Risk of the simulated annual loss distribution.
- $\text{Confidence Interval} = [\text{VaR}_{0.05}(X), \text{VaR}_{0.95}(X)]$.

---

## 3. Implementation Corrections & Hardening

During Phase 3 engineering, the original implementation in `risk_engine.py` was enhanced to resolve potential edge-case failures:

1. **Deterministic Random Seed Support:**
   Added an optional `seed` parameter (`monte_carlo_simulation(predicted_mean_cost, n_simulations=5000, seed=None, base_cost=500.0)`). When provided, an independent `np.random.default_rng(seed)` generator is used, ensuring exact bit-level determinism down to the cent across calls.
2. **Robust Boundary & Missing Input Guards:**
   Implemented explicit type-casting and boundary checks:
   - If `predicted_mean_cost` is `None`, `NaN`, non-numeric, or $\le 0$, it is safely clamped to the baseline floor (`base_cost`, default $\$500.00$).
   - Extreme outlier values are capped at $\$10,000,000.00$ to prevent numerical overflow in floating-point Gamma samplers.
3. **Configurable Base Cost Scenario Parameter:**
   Rather than hard-coding an unalterable rule, `base_cost` is an explicit keyword argument (default `500.0`), allowing empirical sensitivity analysis (e.g. testing $\$0$, $\$250$, or $\$500$).
4. **Strict Non-Negativity Invariant:**
   Enforced floor bounding via `np.maximum(base_cost, gamma_draws + base_cost)`, guaranteeing that simulated draws and final premiums never evaluate below the specified base floor.

---

## 4. Automated Invariant & Scenario Test Suite

Eight automated invariant tests were implemented in [`test_premium_simulation.py`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/ml_model/tests/test_premium_simulation.py):

| Test Case Name | Invariant Tested | Verified Behavior | Status |
| :--- | :--- | :--- | :---: |
| `test_non_negativity_and_base_floor` | Non-negativity & Floor | Premium and percentiles strictly $\ge \$500.00$ for all costs $\le \$0$ to $\$50,000$. | **PASSED** |
| `test_percentile_ordering_and_equality` | Quantile Monotonicity | $P_5 \le P_{95}$ strictly holds; target premium strictly equals $P_{95}$. | **PASSED** |
| `test_determinism_with_fixed_seed` | Replicability | Identical inputs and seed produce identical outputs down to $\$0.01$. | **PASSED** |
| `test_monotonicity_under_fixed_seed` | Stochastic Dominance | Increasing expected costs ($\$500 \to \$25,000$) produce monotonically non-decreasing premiums. | **PASSED** |
| `test_extreme_and_invalid_inputs` | Edge Robustness | Graceful handling of `None`, `NaN`, $-9999.0$, and $\$10,000,000.0$ without unhandled exceptions. | **PASSED** |
| `test_loading_and_risk_margin` | Risk Margin Coverage | Target premium exceeds expected mean cost ($\text{VaR}_{0.95} > \hat{C}$), providing reserve margin. | **PASSED** |
| `test_configurable_base_cost_scenario` | Parameter Sensitivity | Monotonic scaling with custom base floors ($\$0 < \$250 < \$500$). | **PASSED** |
| `test_engine_integration_and_disclaimers` | System Integration | Integrated `calculate_risk` returns structured premium, CI, and explicit disclaimer qualifications. | **PASSED** |

---

## 5. Actuarial Limitations & Scoping Gap Assessment

While the software implementation is mathematically sound and robust, it must **not** be presented as a production insurance rating system. The following structural gaps are explicitly disclosed:

1. **Absence of Credible Claims & Expense Data:**
   The simulation uses MEPS survey-reported total expenditures. It does not incorporate real payer claims data, negotiated provider fee schedules, out-of-pocket plan designs (deductibles, copays, coinsurance, out-of-pocket maximums), or geographic rating factors.
2. **Missing Administrative Expense Loadings:**
   Commercial insurance pricing requires explicit expense loadings (underwriting overhead, claims administration, taxes, regulatory fees) compliant with statutory Medical Loss Ratio (MLR) thresholds (e.g. ACA 80/20 rule). The current model uses a static $\$500$ heuristic offset.
3. **Lack of Risk Adjustment Corridors:**
   Under statutory health insurance regulation (e.g. ACA Section 1343), plans participate in statewide risk-adjustment transfer pools that redistribute funds from healthier-than-average to sicker-than-average risk pools. The current model does not simulate market-wide risk equalization.
4. **Solvency & Capital Reserve Certification:**
   Regulatory capital adequacy (NAIC Risk-Based Capital) requires multi-year stochastic surplus modeling under catastrophic stress scenarios. HealthScore's single-period VaR heuristic does not model insurance carrier capital solvency.

### Regulatory Classification
**Status:** **EXPLORATORY TECHNICAL DEMONSTRATION ONLY.**
Current HealthScore outputs represent epidemiological cost estimations and technical proof-of-concept heuristics. They must **not** be used for insurance underwriting, rate filing, commercial pricing, or reserve certification without formal review by a credentialed Fellow of the Society of Actuaries (FSA / MAAA).
