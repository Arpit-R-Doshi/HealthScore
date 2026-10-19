#!/usr/bin/env python3
"""
Generate Publication Figure 5:
Hyperledger Fabric Performance Profiles: Write Consensus vs Local State Queries
Reconciles:
1. Historical Empirical Baseline (commit 944fb0d, 8 rounds, 24,500 txs)
2. Live Isolated Caliper Rerun (Run 20261018-010200, 5 workers, 11 rounds, 31,500 txs)
3. Corrected Stress & Saturation Rerun (Run 20261018-230500, 8 workers, 7 rounds, 25,480 measured txs + 400 pre-seeding setup writes)

Fixes:
- Horizontal-axis semantics: Consistently plots actual Caliper send rate across all series.
- Latency precision: Eliminates hardcoded 0.001s constants; accurately plots Caliper-measured
  displayed values (0.00s and 0.01s) with display precision annotations (<=0.01s displayed avg,
  max 0.04-0.13s).
"""

import os
import matplotlib.pyplot as plt
import numpy as np

# Styling configuration
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), dpi=300)

# =============================================================================
# 1. EMPIRICAL BENCHMARK DATA (VERIFIED FROM SOURCE ARTIFACTS)
# =============================================================================

# Historical Baseline (commit 944fb0d, 5-org Raft network)
# Writes: createPatientRecord at target 50, 100, 200, 1000 TPS
hist_write_send = [50.5, 100.5, 200.5, 963.6]
hist_write_tps = [50.3, 100.2, 199.9, 350.1]
hist_write_lat = [0.10, 0.06, 0.04, 18.00]

# Historical Read Query: getPatientRecord at target 500 TPS
# Caliper report displays 0.00s avg latency (two-decimal display limit, max 0.04s)
hist_read_send = [500.4]
hist_read_tps = [500.3]
hist_read_lat = [0.00]

# Live Isolated Rerun (Run 20261018-010200, 5 workers)
# Writes: createPatientRecord at target 50, 100, 200, 350, 1000 TPS
live_write_send = [50.5, 100.5, 200.5, 350.6, 615.7]
live_write_tps = [50.4, 100.3, 200.2, 349.9, 515.8]
live_write_lat = [0.09, 0.05, 0.03, 0.03, 6.98]

# Live Isolated Reads: getPatientRecord at target 100, 250, 500 TPS
# Displayed avg latencies: 0.01s, 0.00s, 0.00s (max 0.04s - 0.13s)
live_read_send = [100.4, 250.4, 500.3]
live_read_tps = [100.4, 250.4, 500.3]
live_read_lat = [0.01, 0.00, 0.00]

# Corrected Live Stress Run (Run 20261018-230500, 8 workers)
# Write rounds: target 350, 500, 750, 1000 (rep1, rep2, rep3) TPS
stress_write_send = [351.8, 500.7, 631.0, 729.1, 688.0, 811.0]
stress_write_tps = [249.4, 351.9, 467.0, 470.6, 499.8, 485.4]
stress_write_lat = [0.56, 1.55, 3.57, 5.29, 5.18, 5.60]

# Corrected Live Stress Read: getPatientRecord at target 500 TPS
# Send rate 501.4 TPS, Throughput 500.6 TPS, Avg Latency 0.01s, Max 0.09s
stress_read_send = [501.4]
stress_read_tps = [500.6]
stress_read_lat = [0.01]

# =============================================================================
# PANEL A: COMMITTED THROUGHPUT VS ACTUAL SEND RATE
# =============================================================================

# Reference 1:1 scaling
ax1.plot([0, 1000], [0, 1000], 'k:', alpha=0.45, label="Ideal 1:1 Scaling Reference")

# Historical Baseline
ax1.plot(hist_write_send[:3], hist_write_tps[:3], 'o-', color='#1f77b4', lw=2.0, ms=7,
         label="Historical Writes: Linear Regime (< 200 TPS)")
ax1.plot(hist_write_send[2:], hist_write_tps[2:], 's--', color='#d62728', lw=2.0, ms=8,
         label="Historical Writes: 350.1 TPS Knee (963.6 send)")

# Live Isolated Rerun (5 Workers)
ax1.plot(live_write_send, live_write_tps, '^-', color='#2ca02c', lw=2.0, ms=8,
         label="Live Isolated Writes (5 Workers, 515.8 TPS Peak)")

# Corrected Stress Write Repetitions (8 Workers)
ax1.scatter(stress_write_send, stress_write_tps, color='#9467bd', s=80, marker='D', edgecolors='black',
            zorder=6, label="Corrected Stress Writes (8 Workers: 470.6–499.8 TPS)")

# Read Queries (All Runs - CouchDB Local State Queries)
all_read_send = hist_read_send + live_read_send + stress_read_send
all_read_tps = hist_read_tps + live_read_tps + stress_read_tps
ax1.scatter(all_read_send, all_read_tps, color='#ff7f0e', s=100, marker='*', edgecolors='black',
            zorder=7, label="Read Queries (Local State, 100–500 TPS Linear)")

ax1.set_xlabel("Actual Caliper Send Rate (TPS)", fontsize=11, fontweight='semibold')
ax1.set_ylabel("Committed Throughput (TPS)", fontsize=11, fontweight='semibold')
ax1.set_title("A. Committed Throughput vs. Actual Send Rate", fontsize=12, fontweight='bold')
ax1.set_xlim(0, 1050)
ax1.set_ylim(0, 650)
ax1.legend(loc='lower right', fontsize=8.2, frameon=True)
ax1.grid(True, linestyle='--', alpha=0.5)

# Annotations for Panel A
ax1.annotate('Historical Knee:\n350.1 TPS', xy=(963.6, 350.1), xytext=(830, 270),
             arrowprops=dict(facecolor='#d62728', shrink=0.08, width=1, headwidth=5),
             fontsize=8, fontweight='bold', color='#d62728')
ax1.annotate('5-Worker Peak:\n515.8 TPS', xy=(615.7, 515.8), xytext=(520, 560),
             arrowprops=dict(facecolor='#2ca02c', shrink=0.08, width=1, headwidth=5),
             fontsize=8, fontweight='bold', color='#2ca02c')

# =============================================================================
# PANEL B: LATENCY VS COMMITTED THROUGHPUT
# =============================================================================

# Historical Write Latency
ax2.plot(hist_write_tps[:3], hist_write_lat[:3], 'o-', color='#1f77b4', lw=2.0, ms=7,
         label="Historical Writes: Sub-100ms (< 200 TPS)")
ax2.plot([hist_write_tps[2], hist_write_tps[3]], [hist_write_lat[2], hist_write_lat[3]], 's--', color='#d62728', lw=2.0, ms=8,
         label="Historical Saturation: 18.00s Avg Latency")

# Live Isolated Rerun Write Latency (5 Workers)
ax2.plot(live_write_tps, live_write_lat, '^-', color='#2ca02c', lw=2.0, ms=8,
         label="Live Isolated Writes (5 Workers: 6.98s at Saturation)")

# Corrected Stress Write Repetitions (8 Workers)
ax2.scatter(stress_write_tps, stress_write_lat, color='#9467bd', s=80, marker='D', edgecolors='black',
            zorder=6, label="Corrected Stress Writes (8 Workers: 5.18–5.60s Avg)")

# Read Query Latencies (Caliper Displayed Values: 0.00s and 0.01s)
ax2.scatter(all_read_tps, [0.00, 0.01, 0.00, 0.00, 0.01], color='#ff7f0e', s=100, marker='*', edgecolors='black',
            zorder=7, label="Read Queries: $\\leq$ 0.01s Displayed Avg (Max 0.04–0.13s)")

ax2.set_xlabel("Committed Throughput (TPS)", fontsize=11, fontweight='semibold')
ax2.set_ylabel("Average Confirmation Latency (seconds)", fontsize=11, fontweight='semibold')
ax2.set_title("B. Confirmation Latency vs. Committed Throughput", fontsize=12, fontweight='bold')
ax2.set_xlim(0, 560)
ax2.set_ylim(-0.5, 20.0)
ax2.legend(loc='upper left', fontsize=8.2, frameon=True)
ax2.grid(True, linestyle='--', alpha=0.5)

# Annotations for Panel B
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
output_path = os.path.join(os.path.dirname(__file__), "../figures/fig5_blockchain_benchmarks.png")
output_path = os.path.abspath(output_path)
plt.savefig(output_path, dpi=300)
plt.close()
print(f"✓ Successfully generated publication Figure 5: {output_path}")
