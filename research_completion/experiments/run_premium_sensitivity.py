#!/usr/bin/env python3
"""
HealthScore — Systematic Premium & Loss Simulation Sensitivity Analysis
Evaluates the parametric Value-at-Risk (VaR) simulation across:
  - Base-cost floors: B in {0, 250, 500, 1000} USD
  - Risk-loading alpha: alpha in {0.0, 0.10, 0.25, 0.50, 1.00}
  - Expected expenditure levels: {1500 (low), 5000 (moderate), 15000 (high)} USD
  - Common random numbers (CRN) with fixed seed for controlled variance reduction
  - Analytical Gamma quantile validation and numerical approximation error tracking
"""

import os
import sys
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import gamma

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../ml_model'))
from risk_engine import monte_carlo_simulation

BASE_COSTS = [0.0, 250.0, 500.0, 1000.0]
ALPHAS = [0.0, 0.10, 0.25, 0.50, 1.00]
EXPENDITURE_LEVELS = [
    {"label": "Low ($1,500)", "cost": 1500.0},
    {"label": "Moderate ($5,000)", "cost": 5000.0},
    {"label": "High ($15,000)", "cost": 15000.0}
]
N_SIMULATIONS = 20000
FIXED_SEED = 42

def run_sensitivity_grid():
    results = []
    summary_table = []

    print("=" * 80)
    print("HealthScore Premium Simulation & Risk-Loading Sensitivity Analysis")
    print(f"Configurations: {len(BASE_COSTS)} base costs x {len(ALPHAS)} alphas x {len(EXPENDITURE_LEVELS)} cost levels = {len(BASE_COSTS) * len(ALPHAS) * len(EXPENDITURE_LEVELS)} scenarios")
    print(f"Simulations per scenario: N = {N_SIMULATIONS:,} (Seed = {FIXED_SEED})")
    print("=" * 80)

    shape = 1.5

    for exp in EXPENDITURE_LEVELS:
        cost = exp["cost"]
        cost_label = exp["label"]
        scale = cost / shape

        for b in BASE_COSTS:
            # Baseline premium at alpha=0 for uplift calculation
            sim_base = monte_carlo_simulation(
                cost,
                n_simulations=N_SIMULATIONS,
                seed=FIXED_SEED,
                base_cost=b,
                pricing_alpha=0.0,
                return_details=True
            )
            prem_baseline = sim_base["target_premium"]

            for a in ALPHAS:
                sim = monte_carlo_simulation(
                    cost,
                    n_simulations=N_SIMULATIONS,
                    seed=FIXED_SEED,
                    base_cost=b,
                    pricing_alpha=a,
                    return_details=True
                )

                # Analytical Gamma quantiles
                # X_alpha = B + (1 + alpha) * G
                ana_p5 = b + (1.0 + a) * gamma.ppf(0.05, a=shape, scale=scale)
                ana_p50 = b + (1.0 + a) * gamma.ppf(0.50, a=shape, scale=scale)
                ana_p90 = b + (1.0 + a) * gamma.ppf(0.90, a=shape, scale=scale)
                ana_p95 = b + (1.0 + a) * gamma.ppf(0.95, a=shape, scale=scale)
                ana_p99 = b + (1.0 + a) * gamma.ppf(0.99, a=shape, scale=scale)

                p95_sim = sim["p95"]
                p95_error_usd = round(p95_sim - ana_p95, 2)
                p95_error_pct = round(abs(p95_sim - ana_p95) / ana_p95 * 100, 3)

                uplift_usd = round(p95_sim - prem_baseline, 2)
                uplift_pct = round((uplift_usd / prem_baseline * 100) if prem_baseline > 0 else 0.0, 2)

                entry = {
                    "expected_expenditure": cost,
                    "expenditure_tier": cost_label,
                    "base_cost": b,
                    "pricing_alpha": a,
                    "simulated_p5": sim["p5"],
                    "simulated_p50": sim["p50"],
                    "simulated_p90": sim["p90"],
                    "simulated_p95_target_premium": p95_sim,
                    "simulated_p99": sim["p99"],
                    "analytical_p95": round(ana_p95, 2),
                    "analytical_p95_error_usd": p95_error_usd,
                    "analytical_p95_error_pct": p95_error_pct,
                    "premium_uplift_usd": uplift_usd,
                    "premium_uplift_pct": uplift_pct,
                    "loss_ratio_on_expected": round(cost / p95_sim, 4) if p95_sim > 0 else None
                }
                results.append(entry)

    # Save machine-readable JSON
    out_dir = os.path.join(os.path.dirname(__file__), '../reports')
    os.makedirs(out_dir, exist_ok=True)
    out_json = os.path.join(out_dir, 'premium_sensitivity_results.json')
    with open(out_json, 'w') as f:
        json.dump({
            "metadata": {
                "experiment": "Parametric Value-at-Risk Simulation Sensitivity Analysis",
                "loss_distribution": "Shifted Gamma (shape=1.5, scale=y_hat/1.5)",
                "formula": "X_alpha = B + (1 + alpha) * G",
                "n_simulations": N_SIMULATIONS,
                "seed": FIXED_SEED,
                "design": "Common Random Numbers (CRN) across alpha and base_cost grid",
                "disclaimer": "Exploratory parametric loss simulation heuristic, NOT an actuarially certified insurance quote."
            },
            "scenarios": results
        }, f, indent=2)
    print(f"Saved sensitivity results to: {out_json}")

    # Generate Figures
    generate_figures(results)

    return results

def generate_figures(results):
    fig_dir = os.path.join(os.path.dirname(__file__), '../figures')
    os.makedirs(fig_dir, exist_ok=True)
    fig_path = os.path.join(fig_dir, 'fig6_premium_sensitivity.png')

    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), sharey=False)

    colors = {0.0: '#1f77b4', 250.0: '#2ca02c', 500.0: '#ff7f0e', 1000.0: '#d62728'}
    markers = {0.0: 'o', 250.0: 's', 500.0: '^', 1000.0: 'D'}

    for idx, exp in enumerate(EXPENDITURE_LEVELS):
        ax = axes[idx]
        cost = exp["cost"]
        cost_label = exp["label"]

        tier_results = [r for r in results if r["expected_expenditure"] == cost]

        for b in BASE_COSTS:
            b_results = [r for r in tier_results if r["base_cost"] == b]
            alphas = [r["pricing_alpha"] for r in b_results]
            premiums = [r["simulated_p95_target_premium"] for r in b_results]
            ana_premiums = [r["analytical_p95"] for r in b_results]

            ax.plot(alphas, premiums, marker=markers[b], color=colors[b], linewidth=2.0, label=f"Base B = ${int(b)}")
            ax.plot(alphas, ana_premiums, linestyle='--', color=colors[b], alpha=0.5, linewidth=1.2)

        ax.set_title(f"Expected Spending: {cost_label}", fontsize=13, fontweight='bold', pad=10)
        ax.set_xlabel(r"Risk-Loading Parameter ($\alpha$)", fontsize=11)
        ax.set_ylabel("Target Premium / P95 Loss ($ USD)", fontsize=11)
        ax.grid(True, linestyle=':', alpha=0.6)
        if idx == 0:
            ax.legend(frameon=True, fontsize=10, loc='upper left')

    plt.suptitle(
        r"HealthScore Premium Simulation Sensitivity: Impact of Base Floor $B$ and Risk Loading $\alpha$ on P95 Loss" + "\n" +
        r"Solid lines = Monte Carlo Simulated P95 ($N=20,000$); Dashed lines = Analytical Gamma Quantiles",
        fontsize=13, fontweight='bold', y=1.03
    )
    plt.tight_layout()
    plt.savefig(fig_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved publication sensitivity figure to: {fig_path}")

if __name__ == '__main__':
    run_sensitivity_grid()
