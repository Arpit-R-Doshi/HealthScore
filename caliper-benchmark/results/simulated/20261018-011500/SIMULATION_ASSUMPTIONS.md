# Hyperledger Fabric Performance Simulation: Model Assumptions & Calibration Report

**Document ID:** `HS-SIM-01-FABRIC-QUEUEING-ASSUMPTIONS`
**Execution Timestamp:** October 18, 2026 (Run `20261018-011500`)
**Methodology:** Stochastic Fluid-Queueing Performance Model with Log-Normal Raft Consensus Jitter
**Number of PRNG Seeds:** 100 Seeds per scenario (Seed base: 42)
**Output Files:**
- Machine-Readable JSON: [`simulation_results.json`](simulation_results.json)
- Summary CSV: [`simulation_results.csv`](simulation_results.csv)
- Comparative Figure: [`research_completion/figures/fig5b_caliper_simulation_projection.png`](../../../research_completion/figures/fig5b_caliper_simulation_projection.png)

---

## 1. Important Provenance & Scientific Disclaimers

> [!CAUTION]
> **SYNTHETIC SIMULATION ESTIMATES ONLY:**
> The figures and tables produced in this directory are the result of a mathematical queueing model. They are **synthetic estimates**, NOT empirical measurements of physical network hardware or live transaction execution.
> Under no circumstances should simulation outputs be described as "observed transactions," "empirical Caliper results," or "measured blockchain throughput."
>
> The project maintains three mutually exclusive evidence classes:
> 1. **Class 1: Historical Empirical Caliper Baseline** (`caliper-benchmark/report.html`, commit `944fb0d`): 8 rounds, 24,500 real transactions.
> 2. **Class 2: New Live Empirical Caliper Run** (`caliper-benchmark/results/live/20261018-010200/`): 11 rounds, 31,500 real transactions on an isolated 5-org network.
> 3. **Class 3: Synthetic Queueing Projections** (`caliper-benchmark/results/simulated/20261018-011500/`): Mathematical simulation across 100 seeds.

---

## 2. Mathematical Formulation & Structural Assumptions

The performance model distinguishes between two fundamentally different transaction paths in Hyperledger Fabric v2.4+:

### 2.1. Consensus-Backed Write Path (Execute-Order-Validate)

For write operations (`createPatientRecord`, `updateHealthScore`, `createPrescription`, `requestScan`):
Transactions require three phases:
1. **Endorsement Phase:** Client submits proposal to endorsing peers; peers execute chaincode in parallel against their world state without committing.
2. **Ordering Phase:** Client sends signed endorsements to the Raft ordering service (`orderer.healthscore.com`). The orderer establishes total order and batches transactions into blocks based on two criteria configured in `healthscore-network/configtx/configtx.yaml`:
   - `BatchTimeout` ($T_{\text{timeout}} = 2.0$s)
   - `MaxMessageCount` ($B_{\max} = 10$ transactions per block)
3. **Validation & Commit Phase:** Peers receive blocks, validate endorsement signatures and MVCC read-write sets, and commit valid state mutations to CouchDB.

#### Equations:
- **Block-Cutting Delay:**
  $$D_{\text{block}}(\lambda) = \frac{1}{2} \cdot \min\left(T_{\text{timeout}}, \frac{B_{\max}}{\max(1, \lambda)}\right)$$
- **Base Confirmation Latency:**
  $$L_0 \sim (D_{\text{endorse}} + D_{\text{block}}(\lambda) + D_{\text{commit}}) \cdot \text{Lognormal}(0, \sigma=0.08)$$
- **Operating Regimes:**
  - **Linear Operating Regime ($\lambda \le \mu_w$):**
    Committed throughput tracks offered rate linearly:
    $$\gamma(\lambda) \approx \lambda$$
    Mean confirmation latency exhibits minor queueing near capacity:
    $$W(\lambda) = L_0 + \left(\frac{\rho}{1 - \rho}\right) \cdot \frac{0.1}{\mu_w}, \quad \rho = \min(0.98, \lambda / \mu_w)$$
  - **Saturation Queueing Regime ($\lambda > \mu_w$):**
    Orderer arrival rate exceeds consensus commitment capacity. Unprocessed transactions accumulate in memory buffers without dropping (assuming unbounded buffer capacity):
    $$\gamma(\lambda) = \mu_w$$
    For a test of nominal duration $T_{\text{nom}} = \frac{N}{\lambda}$, the queue length at time $t$ grows as $(\lambda - \mu_w)t$. The time-averaged queueing latency strictly over the submission duration is:
    $$\bar{W}_q = \frac{(\lambda - \mu_w) \cdot T_{\text{nom}}}{2 \cdot \mu_w}$$
    Total average latency expands linearly with queue buildup:
    $$W_{\text{sat}}(\lambda) = L_0 + \bar{W}_q$$

### 2.2. Local Read-Only Query Path

For read operations (`getPatientRecord`):
Transactions bypass the Raft ordering service entirely. The client submits a proposal to the local peer; the peer evaluates the chaincode query locally against its committed database and returns the result in a single gRPC round trip.
- Read capacity $\mu_r \approx 1,200.0$ QPS.
- Query latency is bounded by local serialization ($L_r \approx 0.001$–$0.005$s).
- Displayed latency in Caliper is rounded to 2 decimal places ($0.00$s).

---

## 3. Parameter Calibration & Residual Analysis

The simulator parameters were calibrated strictly using the historical empirical Caliper baseline (commit `944fb0d`):
- Calibrated Write Capacity $\mu_w$: **$350.1$ TPS**
- Calibrated Read Capacity $\mu_r$: **$1,200.0$ QPS**
- Base Write Network Latency: **$0.035$s**
- Base Read Network Latency: **$0.002$s**

### Calibration Residual Comparison Table (Historical Baseline vs. Simulation):

| Benchmark Operation | Configured Offered Load (TPS) | Historical Measured Throughput (TPS) | Simulated Median Throughput (TPS) | Throughput Residual (TPS) | Historical Measured Avg Latency (s) | Simulated Median Avg Latency (s) | Latency Residual (s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **createPatientRecord** | 50 TPS | 50.3 | **49.99** | -0.31 (-0.6%) | 0.10 | **0.133** | +0.033s |
| **createPatientRecord** | 100 TPS | 100.2 | **99.98** | -0.22 (-0.2%) | 0.06 | **0.084** | +0.024s |
| **createPatientRecord** | 200 TPS | 199.9 | **199.96** | +0.06 (+0.03%) | 0.04 | **0.060** | +0.020s |
| **createPatientRecord (Knee)** | 350 TPS | — (Expanded) | **349.40** | — | — | **0.065** | — |
| **createPatientRecord (Stress)** | 1,000 TPS | 350.1 | **351.53** | +1.43 (+0.41%) | 18.00 | **9.268** | **-8.732s (-48.5%)** |
| **getPatientRecord** | 100 TPS | — (Expanded) | **100.00** | — | — | **0.002** | — |
| **getPatientRecord** | 250 TPS | — (Expanded) | **250.00** | — | — | **0.002** | — |
| **getPatientRecord** | 500 TPS | 500.3 | **500.00** | -0.30 (-0.06%) | 0.00 (2-dec) | **0.002** | +0.002s |

### Critical Residual & Model Limitation Analysis:
1. **Linear Regime Throughput Agreement:** For offered loads below saturation ($50$ to $200$ TPS), the simulated throughput matches historical observations within $\pm 0.6\%$, with latencies within $+0.033$s.
2. **Stress Latency Discrepancy (-8.73s Residual):**
   The historical stress round observed an average confirmation latency of **$18.00$ seconds** (max $21.14$s) under $963.6$ TPS send rate. The fluid queueing model computes a mean latency of **$9.268$ seconds** during the nominal $10$-second submission window ($T_{\text{submit}} = 10,000 / 1,000 = 10$s).
   This large residual occurs because the fluid model calculates queue delay strictly during the transaction arrival interval. In physical Fabric execution, however, the Raft ordering service and peer validation pipelines experience persistent downstream backpressure: draining the accumulated $10,000$-transaction backlog required $28.56$ seconds of physical ledger processing time, extending lingering queue wait times far beyond the nominal submission phase. The fluid model does not capture lingering post-submission pipeline drain dynamics.
3. **Out-of-Calibration Empirical Observation (Live Rerun):**
   The live empirical rerun (`20261018-010200`) executed on a modern isolated container testbed observed an achieved write throughput of **$515.8$ TPS** (at $615.7$ TPS send rate) with **$6.98$ seconds** average latency.
   The simulation model ($\mu_w = 350.1$ TPS) does NOT predict $515.8$ TPS because it was strictly calibrated to the historical baseline ($350.1$ TPS). The live rerun represents an independent, out-of-calibration empirical observation reflecting different container I/O performance and client send rate bounds.

---

## 4. Key Simulation Limitations & Modeling Boundaries

1. **Stochastic Fluid Approximation:** The model evaluates continuous fluid queues with seeded log-normal consensus jitter rather than discrete event-by-event packet simulation. It must not be cited as a discrete-event simulator.
2. **Unbounded Queue Buffer Assumption:** The simulator assumes zero packet drops and infinite buffer capacity. In physical deployments, extreme queue buildup triggers gRPC timeouts (`DEADLINE_EXCEEDED`). Zero transaction failure in the simulation is an assumption, not an empirical observation.
3. **Sensitivity Envelope vs. Empirical Confidence Intervals:** The reported P5–P95 ranges reflect model sensitivity to PRNG jitter across 100 synthetic seeds. They do NOT represent empirical confidence intervals from repeated hardware trials.
4. **Calibration vs. Validation:** Parameter calibration on historical points proves mathematical convergence, NOT independent validation of unobserved blockchain configurations.
