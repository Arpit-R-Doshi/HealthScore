"""
Generate publication-quality figures for HealthScore LaTeX submission.
Outputs both vector PDF and >=600 DPI PNG assets into research_completion/latex_submission/figures/.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_FIG_DIR = os.path.join(REPO_ROOT, "research_completion", "latex_submission", "figures")
SRC_FIG_DIR = os.path.join(REPO_ROOT, "research_completion", "figures")
REGISTRY_PATH = os.path.join(REPO_ROOT, "research_completion", "experiments", "experiment_registry.json")

os.makedirs(OUT_FIG_DIR, exist_ok=True)

with open(REGISTRY_PATH, 'r') as f:
    registry = json.load(f)

# -----------------------------------------------------------------------------
# Figure 5: Blockchain Benchmarks (Write Consensus vs Read Queries)
# -----------------------------------------------------------------------------
print("Generating Figure 5 (Blockchain Benchmarks)...")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=600)

hist_write_send = [50.5, 100.5, 200.5, 963.6]
hist_write_tps = [50.3, 100.2, 199.9, 350.1]
hist_write_lat = [0.10, 0.06, 0.04, 18.00]

live_write_send = [50.5, 100.5, 200.5, 350.6, 615.7]
live_write_tps = [50.4, 100.3, 200.2, 349.9, 515.8]
live_write_lat = [0.09, 0.05, 0.03, 0.03, 6.98]

stress_write_send = [742.70]
stress_write_tps = [485.27]
stress_write_lat = [5.36]

all_read_send = [100.5, 250.5, 500.4, 500.4, 500.6]
all_read_tps = [100.4, 250.4, 500.3, 500.3, 500.6]
all_read_lat = [0.01, 0.00, 0.00, 0.00, 0.01]

# Panel A
ax1.plot(hist_write_send[:3], hist_write_tps[:3], 'o-', color='#1f77b4', lw=2.2,
         label="Historical Writes: Linear Regime (< 200 TPS)")
ax1.plot(hist_write_send[2:], hist_write_tps[2:], 's--', color='#d62728', lw=2.2,
         label="Historical Writes: 350.1 TPS Knee (963.6 send)")
ax1.plot(live_write_send, live_write_tps, '^-', color='#2ca02c', lw=2.2,
         label="Live Isolated Writes (5 Workers: 515.8 TPS at 615.7 send)")
ax1.scatter(stress_write_send, stress_write_tps, color='#9467bd', s=80, marker='D', edgecolors='black',
            zorder=6, label="Corrected Stress Writes (8 Workers: 485.27 ± 14.60 TPS)")
ax1.plot(all_read_send[:3], all_read_tps[:3], 'v-.', color='#ff7f0e', lw=2.2,
         label="Read Queries: Linear Scaling (500.3 TPS, No Raft)")
ax1.plot([0, 1000], [0, 1000], 'k:', alpha=0.4, label="Ideal 1:1 Scaling Reference")

ax1.set_xlabel("Actual Caliper Send Rate (TPS)", fontsize=11, fontweight='semibold')
ax1.set_ylabel("Committed Throughput (TPS)", fontsize=11, fontweight='semibold')
ax1.set_title("A. Committed Throughput vs. Actual Send Rate", fontsize=12, fontweight='bold')
ax1.set_xlim(0, 1050)
ax1.set_ylim(0, 600)
ax1.legend(loc='upper left', fontsize=8.2, frameon=True)
ax1.grid(True, linestyle='--', alpha=0.5)

# Panel B
ax2.plot(hist_write_tps[:3], hist_write_lat[:3], 'o-', color='#1f77b4', lw=2.2,
         label="Historical Writes: Sub-100ms Baseline")
ax2.plot(hist_write_tps[2:], hist_write_lat[2:], 's--', color='#d62728', lw=2.2,
         label="Historical Writes: 18.00s Queueing at 350.1 TPS")
ax2.plot(live_write_tps, live_write_lat, '^-', color='#2ca02c', lw=2.2,
         label="Live Isolated Writes (5 Workers: 6.98s at Saturation)")
ax2.scatter(stress_write_tps, stress_write_lat, color='#9467bd', s=80, marker='D', edgecolors='black',
            zorder=6, label="Corrected Stress Writes (8 Workers: 5.18–5.60s Avg)")
ax2.scatter(all_read_tps, [0.00, 0.01, 0.00, 0.00, 0.01], color='#ff7f0e', s=100, marker='*', edgecolors='black',
            zorder=7, label=r"Read Queries: $\leq$ 0.01s Displayed Avg (Max 0.04–0.13s)")

ax2.set_xlabel("Committed Throughput (TPS)", fontsize=11, fontweight='semibold')
ax2.set_ylabel("Average Confirmation Latency (seconds)", fontsize=11, fontweight='semibold')
ax2.set_title("B. Confirmation Latency vs. Committed Throughput", fontsize=12, fontweight='bold')
ax2.set_xlim(0, 560)
ax2.set_ylim(-0.5, 20.0)
ax2.legend(loc='upper left', fontsize=8.2, frameon=True)
ax2.grid(True, linestyle='--', alpha=0.5)

ax2.annotate('Historical Queueing:\n18.00s Avg (350.1 TPS)', xy=(350.1, 18.00), xytext=(220, 17.0),
             arrowprops=dict(facecolor='#d62728', shrink=0.08, width=1, headwidth=5),
             fontsize=8, fontweight='bold', color='#d62728')
ax2.annotate('Read Queries:\n$\\leq$ 0.01s Displayed Avg\n(No Raft Ordering)', xy=(500.6, 0.01), xytext=(380, 2.5),
             arrowprops=dict(facecolor='#ff7f0e', shrink=0.08, width=1, headwidth=5),
             fontsize=8, fontweight='bold', color='#d35400')

fig.suptitle(
    "Hyperledger Fabric Performance Profiles: Write Consensus vs. Local State Queries\n"
    "(5-Org Topology, Raft Consensus, CouchDB State; Caliper Two-Decimal Latency Precision Noted)",
    fontsize=12, fontweight='bold'
)
plt.tight_layout()
fig5_pdf = os.path.join(OUT_FIG_DIR, "fig5_blockchain_benchmarks.pdf")
fig5_png = os.path.join(OUT_FIG_DIR, "fig5_blockchain_benchmarks.png")
fig.savefig(fig5_pdf, bbox_inches='tight')
fig.savefig(fig5_png, dpi=600, bbox_inches='tight')
plt.close()
print("✓ Saved fig5_blockchain_benchmarks (.pdf and .png)")

# -----------------------------------------------------------------------------
# Figure 5b: Caliper Simulation Projection
# -----------------------------------------------------------------------------
print("Generating Figure 5b (Caliper Simulation Projection)...")
sim_results_path = os.path.join(REPO_ROOT, "caliper-benchmark", "results", "simulated", "20261018-011500", "simulation_results.json")
with open(sim_results_path, "r") as f:
    sim_data = json.load(f)

# Authoritative recorded createPatientRecord simulation scenarios
cpr_sim = [r for r in sim_data["results"] if r.get("target_function") == "createPatientRecord"]
cpr_sim = sorted(cpr_sim, key=lambda x: x["offered_tps"])

sim_offered = np.array([r["offered_tps"] for r in cpr_sim])
sim_med_tps = np.array([r["simulated_throughput"]["median_tps"] for r in cpr_sim])
sim_p5_tps = np.array([r["simulated_throughput"]["p5_tps"] for r in cpr_sim])
sim_p95_tps = np.array([r["simulated_throughput"]["p95_tps"] for r in cpr_sim])

sim_med_lat = np.array([r["simulated_avg_latency"]["median_sec"] for r in cpr_sim])
sim_p5_lat = np.array([r["simulated_avg_latency"]["p5_sec"] for r in cpr_sim])
sim_p95_lat = np.array([r["simulated_avg_latency"]["p95_sec"] for r in cpr_sim])

# Empirical Caliper benchmark observations plotted consistently at configured target loads
hist_target_tps = np.array([50, 100, 200, 1000])
hist_tps = np.array([50.3, 100.2, 199.9, 350.1])
hist_lat = np.array([0.10, 0.06, 0.04, 18.00])

# Compute asymmetric error bars: [median - p5, p95 - median]
yerr_tps = np.array([sim_med_tps - sim_p5_tps, sim_p95_tps - sim_med_tps])
yerr_lat = np.array([sim_med_lat - sim_p5_lat, sim_p95_lat - sim_med_lat])

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=600)
bbox_props = lambda color: dict(boxstyle="round,pad=0.25", facecolor="white", alpha=0.92, edgecolor=color, lw=0.6)

# Panel A: Throughput
ax1.errorbar(sim_offered, sim_med_tps, yerr=yerr_tps, fmt="s", markersize=8,
             color="#1f78b4", markerfacecolor="#a6cee3", markeredgecolor="#1f78b4",
             markeredgewidth=1.8, capsize=5, capthick=1.5, elinewidth=1.8,
             linestyle="None", zorder=4,
             label="Simulated Median & P5–P95 Range (Fluid Model)")
ax1.scatter(hist_target_tps, hist_tps, color="#d73027", s=75, marker="o", zorder=5,
            label="Historical Caliper Benchmark (Commit 944fb0d)")
ax1.scatter([1000], [515.8], color="#1b9e77", s=90, marker="^", zorder=6,
            label="Live Rerun Stress (5 Workers)")
ax1.scatter([1000], [485.27], color="#7570b3", s=85, marker="D", zorder=6,
            label="Corrected Stress Rerun (8 Workers)")
ax1.plot([0, 600], [0, 600], color="gray", linestyle=":", lw=1.2, label="Ideal 1:1 Scaling Reference")

ax1.annotate("Live Rerun Stress:\n515.8 TPS (Send: 615.7)", xy=(1000, 515.8), xytext=(650, 520),
             arrowprops=dict(facecolor="#1b9e77", shrink=0.08, width=1, headwidth=5),
             fontsize=8.5, fontweight="bold", color="#1b9e77", bbox=bbox_props("#1b9e77"))
ax1.annotate("Corrected Stress:\n485.3 TPS (Send: 742.7)", xy=(1000, 485.27), xytext=(680, 430),
             arrowprops=dict(facecolor="#7570b3", shrink=0.08, width=1, headwidth=5),
             fontsize=8.5, fontweight="bold", color="#7570b3", bbox=bbox_props("#7570b3"))
ax1.annotate("Historical Saturation:\n350.1 TPS (Send: 963.6)", xy=(1000, 350.1), xytext=(680, 270),
             arrowprops=dict(facecolor="#d73027", shrink=0.08, width=1, headwidth=5),
             fontsize=8.5, fontweight="bold", color="#d73027", bbox=bbox_props("#d73027"))

ax1.set_title("(A) Committed Throughput vs. Configured Target Load", fontsize=12, fontweight="bold")
ax1.set_xlabel("Configured Offered Load / Target Rate (TPS)", fontsize=11)
ax1.set_ylabel("Committed Throughput (TPS)", fontsize=11)
ax1.set_xlim(-20, 1100)
ax1.set_ylim(0, 600)
ax1.legend(loc="upper left", fontsize=8.5, frameon=True)
ax1.grid(True, linestyle="--", alpha=0.5)

# Panel B: Latency
ax2.errorbar(sim_offered, sim_med_lat, yerr=yerr_lat, fmt="s", markersize=8,
             color="#1f78b4", markerfacecolor="#a6cee3", markeredgecolor="#1f78b4",
             markeredgewidth=1.8, capsize=5, capthick=1.5, elinewidth=1.8,
             linestyle="None", zorder=4,
             label="Simulated Median & P5–P95 Range (Fluid Model)")
ax2.scatter(hist_target_tps, hist_lat, color="#d73027", s=75, marker="o", zorder=5,
            label="Historical Caliper Latency (Commit 944fb0d)")
ax2.scatter([1000], [6.98], color="#1b9e77", s=90, marker="^", zorder=6,
            label="Live Rerun Stress (5 Workers)")
ax2.scatter([1000], [5.36], color="#7570b3", s=85, marker="D", zorder=6,
            label="Corrected Stress Rerun (8 Workers)")

ax2.annotate("Historical Backlog Drain:\n18.00s Avg (Send: 963.6)", xy=(1000, 18.00), xytext=(650, 17.5),
             arrowprops=dict(facecolor="#d73027", shrink=0.08, width=1, headwidth=5),
             fontsize=8.5, fontweight="bold", color="#d73027", bbox=bbox_props("#d73027"))
ax2.annotate("Simulated Median:\n9.27s (P5: 8.23s, P95: 10.35s)", xy=(1000, 9.268), xytext=(630, 11.8),
             arrowprops=dict(facecolor="#4575b4", shrink=0.08, width=1, headwidth=5),
             fontsize=8.5, fontweight="bold", color="#2b5c9e", bbox=bbox_props("#4575b4"))
ax2.annotate("Live Rerun Stress:\n6.98s (Send: 615.7)", xy=(1000, 6.98), xytext=(690, 4.8),
             arrowprops=dict(facecolor="#1b9e77", shrink=0.08, width=1, headwidth=5),
             fontsize=8.5, fontweight="bold", color="#1b9e77", bbox=bbox_props("#1b9e77"))
ax2.annotate("Corrected Stress:\n5.36s (Send: 742.7)", xy=(1000, 5.36), xytext=(690, 1.2),
             arrowprops=dict(facecolor="#7570b3", shrink=0.08, width=1, headwidth=5),
             fontsize=8.5, fontweight="bold", color="#7570b3", bbox=bbox_props("#7570b3"))

ax2.set_title("(B) Confirmation Latency vs. Configured Target Load", fontsize=12, fontweight="bold")
ax2.set_xlabel("Configured Offered Load / Target Rate (TPS)", fontsize=11)
ax2.set_ylabel("Average Confirmation Latency (seconds)", fontsize=11)
ax2.set_xlim(-20, 1100)
ax2.set_ylim(-0.5, 21.0)
ax2.legend(loc="upper left", fontsize=8.2, frameon=True)
ax2.grid(True, linestyle="--", alpha=0.5)

plt.tight_layout()
fig5b_pdf = os.path.join(OUT_FIG_DIR, "fig5b_caliper_simulation_projection.pdf")
fig5b_png = os.path.join(OUT_FIG_DIR, "fig5b_caliper_simulation_projection.png")
fig.savefig(fig5b_pdf, bbox_inches='tight')
fig.savefig(fig5b_png, dpi=600, bbox_inches='tight')
plt.close()
print("✓ Saved fig5b_caliper_simulation_projection (.pdf and .png)")

# -----------------------------------------------------------------------------
# Figure 3: SHAP Feature Importance
# -----------------------------------------------------------------------------
print("Generating Figure 3 (SHAP Feature Importance)...")
shap_rankings = registry["shap_summary"]["feature_importance"]
feats_plot = [x["feature"] for x in shap_rankings][::-1]
vals_plot = [x["mean_abs_shap_log_scale"] for x in shap_rankings][::-1]

fig, ax = plt.subplots(figsize=(10, 6), dpi=600)
colors = ['#1f77b4' if 'ACG' in f else '#ff7f0e' if 'Age' in f or 'Gender' in f else '#2ca02c' for f in feats_plot]
ax.barh(feats_plot, vals_plot, color=colors, alpha=0.85, edgecolor='black', lw=0.5)
ax.set_xlabel("Mean |SHAP Value| (Impact on Model Log Expenditure)", fontsize=11)
ax.set_title("SHAP TreeExplainer Global Feature Importance (11 Observable Features)", fontsize=12, fontweight='bold')
ax.grid(True, alpha=0.3)

p1 = mpatches.Patch(color='#ff7f0e', label='Demographics & Age Interactions')
p2 = mpatches.Patch(color='#1f77b4', label='Clinical ACG Condition Clusters')
p3 = mpatches.Patch(color='#2ca02c', label='Comorbidity Composites')
ax.legend(handles=[p1, p2, p3], loc='lower right', fontsize=9)

plt.tight_layout()
fig3_pdf = os.path.join(OUT_FIG_DIR, "fig3_shap_importance.pdf")
fig3_png = os.path.join(OUT_FIG_DIR, "fig3_shap_importance.png")
fig.savefig(fig3_pdf, bbox_inches='tight')
fig.savefig(fig3_png, dpi=600, bbox_inches='tight')
plt.close()
print("✓ Saved fig3_shap_importance (.pdf and .png)")

# -----------------------------------------------------------------------------
# Figure 4: Feature Ablation Comparison
# -----------------------------------------------------------------------------
print("Generating Figure 4 (Feature Ablation Comparison)...")
ablations = registry["feature_ablations"]
abl_labels = [x["ablation_label"] for x in ablations][::-1]
abl_r2 = [x["regression_r2"] for x in ablations][::-1]
abl_bss = [x["classification_bss_weighted"] for x in ablations][::-1]

fig, ax = plt.subplots(figsize=(12, 7.5), dpi=600)
y_pos = np.arange(len(abl_labels))
height = 0.38
ax.barh(y_pos - height/2, abl_r2, height, label='Expenditure Dollar R²', color='#1f77b4', alpha=0.85)
ax.barh(y_pos + height/2, abl_bss, height, label='Classifier Weighted BSS', color='#ff7f0e', alpha=0.85)
ax.set_yticks(y_pos)
ax.set_yticklabels(abl_labels, fontsize=8.5)
ax.set_xlabel("Metric Score (Higher is Better)", fontsize=11)
ax.set_title("Systematic Feature Ablation Impact Across Regression and Classification\n(Isolating Demographics, Clinical Clusters, Multimorbidity Composites, and Leave-One-Out Terms)", fontsize=12, fontweight='bold')
ax.axvline(0, color='black', lw=0.8, ls='--')
ax.legend(loc='lower right', fontsize=9.5)
ax.grid(True, alpha=0.3)

plt.tight_layout()
fig4_pdf = os.path.join(OUT_FIG_DIR, "fig4_feature_ablations.pdf")
fig4_png = os.path.join(OUT_FIG_DIR, "fig4_feature_ablations.png")
fig.savefig(fig4_pdf, bbox_inches='tight')
fig.savefig(fig4_png, dpi=600, bbox_inches='tight')
plt.close()
print("✓ Saved fig4_feature_ablations (.pdf and .png)")

# -----------------------------------------------------------------------------
# Figure 6: Premium Sensitivity
# -----------------------------------------------------------------------------
print("Generating Figure 6 (Premium Sensitivity)...")
from scipy.stats import gamma

cost_levels = [1500.0, 5000.0, 15000.0]
cost_labels = ["Low Risk ($1,500)", "Moderate Risk ($5,000)", "High Risk ($15,000)"]
base_costs = [0.0, 250.0, 500.0, 1000.0]
alphas = [0.0, 0.10, 0.25, 0.50, 1.00]
shape_k = 1.5

fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), sharey=False, dpi=600)
colors = {0.0: '#1f77b4', 250.0: '#ff7f0e', 500.0: '#2ca02c', 1000.0: '#d62728'}
markers = {0.0: 'o', 250.0: 's', 500.0: '^', 1000.0: 'D'}

for idx, (cost_mean, cost_label) in enumerate(zip(cost_levels, cost_labels)):
    ax = axes[idx]
    scale_theta = cost_mean / shape_k
    np.random.seed(42)
    G_samples = np.random.gamma(shape=shape_k, scale=scale_theta, size=20000)

    for b in base_costs:
        premiums = []
        ana_premiums = []
        for a in alphas:
            X_alpha = b + (1.0 + a) * G_samples
            sim_p95 = np.percentile(X_alpha, 95)
            ana_p95 = b + (1.0 + a) * gamma.ppf(0.95, a=shape_k, scale=scale_theta)
            premiums.append(sim_p95)
            ana_premiums.append(ana_p95)

        ax.plot(alphas, premiums, marker=markers[b], color=colors[b], linewidth=2.0, label=f"Base B = ${int(b)}")
        ax.plot(alphas, ana_premiums, linestyle='--', color=colors[b], alpha=0.5, linewidth=1.2)

    ax.set_title(f"Expected Spending: {cost_label}", fontsize=12, fontweight='bold', pad=10)
    ax.set_xlabel(r"Risk-Loading Parameter ($\alpha$)", fontsize=11)
    ax.set_ylabel("Target Premium / P95 Loss ($ USD)", fontsize=11)
    ax.grid(True, linestyle=':', alpha=0.6)
    if idx == 0:
        ax.legend(frameon=True, fontsize=9.5, loc='upper left')

plt.suptitle(
    r"HealthScore Premium Simulation Sensitivity: Impact of Base Floor $B$ and Risk Loading $\alpha$ on P95 Loss" + "\n" +
    r"Solid lines = Monte Carlo Simulated P95 ($N=20,000$); Dashed lines = Analytical Gamma Quantiles",
    fontsize=12, fontweight='bold', y=1.03
)
plt.tight_layout()
fig6_pdf = os.path.join(OUT_FIG_DIR, "fig6_premium_sensitivity.pdf")
fig6_png = os.path.join(OUT_FIG_DIR, "fig6_premium_sensitivity.png")
fig.savefig(fig6_pdf, bbox_inches='tight')
fig.savefig(fig6_png, dpi=600, bbox_inches='tight')
plt.close()
print("✓ Saved fig6_premium_sensitivity (.pdf and .png)")

# -----------------------------------------------------------------------------
# Figure 1 & Figure 2: High-Resolution Raster-Backed PDF Wrappers & 600 DPI PNGs
# -----------------------------------------------------------------------------
print("Processing Figure 1 & Figure 2...")
for fname in ["fig1_roc_pr_curves", "fig2_calibration_deciles"]:
    src_png = os.path.join(SRC_FIG_DIR, f"{fname}.png")
    dst_png = os.path.join(OUT_FIG_DIR, f"{fname}.png")
    dst_pdf = os.path.join(OUT_FIG_DIR, f"{fname}.pdf")

    img = Image.open(src_png)
    # The source is 3900x1500 pixels. At 4.8 inches LNCS text width, that is 812.5 DPI.
    img.save(dst_png, dpi=(600, 600))
    img.save(dst_pdf, "PDF", resolution=600.0)
    print(f"✓ Saved {fname} (.pdf and .png with {img.size[0]}x{img.size[1]} px, effective {img.size[0]/4.8:.1f} DPI at 4.8 in width)")

print("\nAll 7 publication figures successfully generated in research_completion/latex_submission/figures/!")
