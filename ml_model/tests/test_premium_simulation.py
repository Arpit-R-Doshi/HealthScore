import os
import sys
import math
import pytest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from risk_engine import monte_carlo_simulation, calculate_risk


class TestPremiumSimulationInvariants:
    """Verifies invariant business and mathematical rules for the premium simulation."""

    def test_non_negativity_and_base_floor(self):
        """Premiums and simulated percentiles must always be strictly positive and >= base floor ($500)."""
        test_costs = [0, -100, 50, 500, 2500, 10000, 50000]
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

    def test_extreme_and_invalid_inputs(self):
        """Robust handling of negative, zero, None, string, NaN, and extreme values."""
        # None input
        prem_none, _, _ = monte_carlo_simulation(None, seed=42)
        assert prem_none >= 500.0

        # NaN input
        prem_nan, _, _ = monte_carlo_simulation(float('nan'), seed=42)
        assert prem_nan >= 500.0

        # Negative input
        prem_neg, _, _ = monte_carlo_simulation(-9999.0, seed=42)
        assert prem_neg >= 500.0

        # Extreme high input (should not overflow)
        prem_large, p5_large, p95_large = monte_carlo_simulation(10_000_000.0, seed=42)
        assert not math.isnan(prem_large)
        assert not math.isinf(prem_large)
        assert prem_large > 10_000_000.0

    def test_loading_and_risk_margin(self):
        """Target premium (VaR 0.95) must include positive risk margin above expected cost."""
        costs = [2000.0, 5000.0, 12000.0, 20000.0]
        for c in costs:
            prem, p5, p95 = monte_carlo_simulation(c, seed=42)
            assert prem > c, f"Premium ({prem}) does not exceed expected cost ({c})"

    def test_engine_integration_and_disclaimers(self):
        """Integrated risk assessment returns properly structured premium and semantic qualifications."""
        patient_data = {
            "age": 55,
            "gender": "male",
            "diseaseInput": "hypertension and type 2 diabetes"
        }
        res = calculate_risk(patient_data)
        assert "premium" in res
        assert "confidence_interval" in res
        assert "p5" in res["confidence_interval"]
        assert "p95" in res["confidence_interval"]
        assert res["premium"] >= 500.0
        assert res["confidence_interval"]["p5"] <= res["confidence_interval"]["p95"]
        assert "score_semantics" in res
        assert "dollar_prediction_qualification" in res["score_semantics"]
