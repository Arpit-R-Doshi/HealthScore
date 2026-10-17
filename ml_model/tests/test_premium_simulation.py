import os
import sys
import math
import subprocess
import json
import pytest
import numpy as np
from scipy.stats import gamma

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from risk_engine import monte_carlo_simulation, calculate_risk


class TestPremiumSimulationInvariants:
    """Verifies invariant business and mathematical rules for the premium simulation."""

    def test_non_negativity_and_base_floor(self):
        """Premiums and simulated percentiles must always be strictly positive and >= base floor ($500)."""
        test_costs = [0.0, 50.0, 500.0, 2500.0, 10000.0, 50000.0]
        for cost in test_costs:
            prem, p5, p95 = monte_carlo_simulation(cost, seed=42)
            assert prem >= 500.0, f"Premium {prem} below base floor for cost {cost}"
            assert p5 >= 500.0, f"P5 {p5} below base floor for cost {cost}"
            assert p95 >= 500.0, f"P95 {p95} below base floor for cost {cost}"

    def test_percentile_ordering_and_equality(self):
        """P5 <= P95 and target premium equals the 95th percentile Value-at-Risk."""
        for cost in [1000.0, 5000.0, 15000.0, 30000.0]:
            prem, p5, p95 = monte_carlo_simulation(cost, seed=42)
            assert p5 <= p95, f"P5 ({p5}) exceeded P95 ({p95})"
            assert prem == p95, f"Target premium ({prem}) does not match P95 ({p95})"

    def test_full_percentile_hierarchy_and_details(self):
        """P5 <= P50 <= P90 <= P95 <= P99 across all loss scenarios."""
        for cost in [2000.0, 8000.0, 25000.0]:
            details = monte_carlo_simulation(cost, seed=42, return_details=True)
            p5 = details["p5"]
            p50 = details["p50"]
            p90 = details["p90"]
            p95 = details["p95"]
            p99 = details["p99"]
            assert p5 <= p50 <= p90 <= p95 <= p99, f"Hierarchy violated: {p5} <= {p50} <= {p90} <= {p95} <= {p99}"
            assert details["target_premium"] == p95
            assert details["base_cost"] == 500.0
            assert details["pricing_alpha"] == 0.0

    def test_determinism_with_fixed_seed(self):
        """Identical inputs and seed must produce identical outputs down to the cent."""
        cost = 8764.62
        run1 = monte_carlo_simulation(cost, seed=123)
        run2 = monte_carlo_simulation(cost, seed=123)
        assert run1 == run2, f"Runs with identical seed produced different results: {run1} vs {run2}"

    def test_monotonicity_under_fixed_seed(self):
        """Higher expected expenditure must produce monotonically increasing target premiums."""
        costs = [500.0, 1500.0, 4000.0, 8000.0, 15000.0, 25000.0]
        premiums = [monte_carlo_simulation(c, seed=999)[0] for c in costs]
        for i in range(len(premiums) - 1):
            assert premiums[i] <= premiums[i + 1], (
                f"Monotonicity violated: cost {costs[i]} gave premium {premiums[i]}, "
                f"but cost {costs[i+1]} gave {premiums[i+1]}"
            )

    def test_pricing_alpha_default_compatibility(self):
        """alpha=0 must reproduce exact default baseline outputs bit-for-bit down to the cent."""
        test_expenditures = [1200.0, 5400.0, 14250.0]
        for cost in test_expenditures:
            prem_default, p5_def, p95_def = monte_carlo_simulation(cost, seed=42)
            prem_alpha0, p5_a0, p95_a0 = monte_carlo_simulation(cost, seed=42, pricing_alpha=0.0)
            assert prem_default == prem_alpha0, f"Mismatch at cost {cost}: default {prem_default} vs alpha=0 {prem_alpha0}"
            assert p5_def == p5_a0
            assert p95_def == p95_a0

    def test_pricing_alpha_monotonicity_under_common_random_numbers(self):
        """Increasing risk-loading alpha >= 0 must strictly non-decrease simulated premium and percentiles."""
        cost = 7500.0
        alphas = [0.0, 0.10, 0.25, 0.50, 1.00]
        results = [monte_carlo_simulation(cost, seed=777, pricing_alpha=a, return_details=True) for a in alphas]

        for i in range(len(results) - 1):
            a_cur, a_next = alphas[i], alphas[i + 1]
            p_cur, p_next = results[i]["target_premium"], results[i + 1]["target_premium"]
            assert p_cur <= p_next, f"Premium decreased with higher alpha: alpha={a_cur} -> {p_cur}, alpha={a_next} -> {p_next}"
            assert results[i]["p50"] <= results[i + 1]["p50"]
            assert results[i]["p95"] <= results[i + 1]["p95"]
            assert results[i]["p99"] <= results[i + 1]["p99"]

    def test_analytical_gamma_quantile_agreement(self):
        """Monte Carlo quantiles with N=50,000 must agree with analytical Gamma distribution quantiles within 2.5%."""
        predicted_cost = 6000.0
        base_cost = 500.0
        pricing_alpha = 0.20
        n_sim = 50000

        details = monte_carlo_simulation(
            predicted_cost,
            n_simulations=n_sim,
            seed=42,
            base_cost=base_cost,
            pricing_alpha=pricing_alpha,
            return_details=True
        )

        shape = 1.5
        scale = predicted_cost / shape
        # Analytical quantile of X_alpha = B + (1 + alpha) * G
        # Since (1 + alpha) * G is Gamma(shape, (1 + alpha) * scale)
        for q, key in [(0.50, "p50"), (0.90, "p90"), (0.95, "p95")]:
            analytical_q = base_cost + (1.0 + pricing_alpha) * gamma.ppf(q, a=shape, scale=scale)
            simulated_q = details[key]
            rel_err = abs(simulated_q - analytical_q) / analytical_q
            assert rel_err < 0.025, f"Quantile {key} relative error {rel_err:.4f} exceeded 2.5% (sim={simulated_q}, ana={analytical_q:.2f})"

    def test_explicit_validation_of_invalid_inputs(self):
        """Fails closed with ValueError on None, NaN, Inf, negative, non-numeric, or invalid parameters."""
        # None input
        with pytest.raises(ValueError, match="cannot be None"):
            monte_carlo_simulation(None, seed=42)

        # NaN input
        with pytest.raises(ValueError, match="finite non-negative"):
            monte_carlo_simulation(float('nan'), seed=42)

        # Negative input
        with pytest.raises(ValueError, match="finite non-negative"):
            monte_carlo_simulation(-9999.0, seed=42)

        # Infinite input
        with pytest.raises(ValueError, match="finite non-negative"):
            monte_carlo_simulation(float('inf'), seed=42)

        # Non-numeric string input
        with pytest.raises(ValueError, match="convertible to float"):
            monte_carlo_simulation("invalid_string", seed=42)

        # Invalid n_simulations (<= 0 or non-int)
        with pytest.raises(ValueError, match="positive integer"):
            monte_carlo_simulation(5000.0, n_simulations=0)
        with pytest.raises(ValueError, match="positive integer"):
            monte_carlo_simulation(5000.0, n_simulations=-100)
        with pytest.raises(ValueError, match="positive integer"):
            monte_carlo_simulation(5000.0, n_simulations=10.5)

        # Invalid base_cost (< 0 or non-finite)
        with pytest.raises(ValueError, match="finite non-negative"):
            monte_carlo_simulation(5000.0, base_cost=-50.0)
        with pytest.raises(ValueError, match="finite non-negative"):
            monte_carlo_simulation(5000.0, base_cost=float('nan'))

        # Invalid pricing_alpha (< 0 or non-finite)
        with pytest.raises(ValueError, match="finite non-negative"):
            monte_carlo_simulation(5000.0, pricing_alpha=-0.5)
        with pytest.raises(ValueError, match="finite non-negative"):
            monte_carlo_simulation(5000.0, pricing_alpha=float('nan'))
        with pytest.raises(ValueError, match="finite non-negative"):
            monte_carlo_simulation(5000.0, pricing_alpha=float('inf'))
        with pytest.raises(ValueError, match="finite non-negative"):
            monte_carlo_simulation(5000.0, pricing_alpha="high_risk")

    def test_boundary_zero_and_extreme_high_inputs(self):
        """Boundary zero cost returns base_cost exactly; extreme high values do not overflow."""
        prem_zero, p5_zero, p95_zero = monte_carlo_simulation(0.0, seed=42, base_cost=500.0, pricing_alpha=0.5)
        assert prem_zero == 500.0
        assert p5_zero == 500.0
        assert p95_zero == 500.0

        prem_large, p5_large, p95_large = monte_carlo_simulation(10_000_000.0, seed=42, pricing_alpha=0.25)
        assert not math.isnan(prem_large)
        assert not math.isinf(prem_large)
        assert prem_large > 10_000_000.0

    def test_loading_and_risk_margin(self):
        """Target premium (VaR 0.95) must include positive risk margin above expected cost."""
        costs = [2000.0, 5000.0, 12000.0, 20000.0]
        for c in costs:
            prem, p5, p95 = monte_carlo_simulation(c, seed=42)
            assert prem > c, f"Premium ({prem}) does not exceed expected cost ({c})"

    def test_configurable_base_cost_scenario(self):
        """Allows sensitivity testing with custom base floors (e.g. $0 or $250)."""
        cost = 5000.0
        prem_default, _, _ = monte_carlo_simulation(cost, seed=42, base_cost=500.0)
        prem_zero, _, _ = monte_carlo_simulation(cost, seed=42, base_cost=0.0)
        prem_250, _, _ = monte_carlo_simulation(cost, seed=42, base_cost=250.0)
        assert prem_zero < prem_250 < prem_default, "Custom base_cost did not scale premium monotonically"

    def test_engine_integration_and_disclaimers(self):
        """Integrated risk assessment returns properly structured premium, loss percentiles, and semantic qualifications."""
        patient_data = {
            "age": 55,
            "gender": "male",
            "diseaseInput": "hypertension and type 2 diabetes",
            "base_cost": 750.0,
            "pricing_alpha": 0.15
        }
        res = calculate_risk(patient_data)
        assert "premium" in res
        assert "simulated_loss_percentiles" in res
        assert "p5" in res["simulated_loss_percentiles"]
        assert "p50" in res["simulated_loss_percentiles"]
        assert "p90" in res["simulated_loss_percentiles"]
        assert "p95" in res["simulated_loss_percentiles"]
        assert "p99" in res["simulated_loss_percentiles"]
        assert res["simulated_loss_percentiles"]["base_cost"] == 750.0
        assert res["simulated_loss_percentiles"]["pricing_alpha"] == 0.15
        assert "formula" in res["simulated_loss_percentiles"]
        assert res["premium"] >= 750.0
        assert res["simulated_loss_percentiles"]["p5"] <= res["simulated_loss_percentiles"]["p95"]
        assert "score_semantics" in res
        assert "dollar_prediction_qualification" in res["score_semantics"]

    def test_subprocess_run_engine_with_pricing_parameters(self):
        """run_engine.py subprocess correctly propagates base_cost and pricing_alpha in JSON."""
        python_bin = sys.executable
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "run_engine.py")

        payload = {
            "age": 45,
            "gender": "female",
            "diseaseInput": "asthma",
            "base_cost": 250.0,
            "pricing_alpha": 0.25
        }

        proc = subprocess.run([python_bin, script_path, json.dumps(payload)], capture_output=True, text=True, check=True)
        out = json.loads(proc.stdout)

        assert "premium" in out
        assert "pricing_parameters" in out
        assert out["pricing_parameters"]["base_cost"] == 250.0
        assert out["pricing_parameters"]["pricing_alpha"] == 0.25
        assert out["simulated_loss_percentiles"]["base_cost"] == 250.0
        assert out["simulated_loss_percentiles"]["pricing_alpha"] == 0.25
