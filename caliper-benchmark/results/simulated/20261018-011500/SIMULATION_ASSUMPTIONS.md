# Hyperledger Fabric Performance Simulation: Model Assumptions & Calibration Report

**Document ID:** `HS-SIM-01-FABRIC-QUEUEING-ASSUMPTIONS`  
**Execution Timestamp:** October 18, 2026 (Run `20261018-011500`)  
**Methodology:** Discrete-Event & Fluid-Queueing Hybrid Model with Log-Normal Service Jitter  
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
> 1. **Historical Empirical Caliper Baseline** (`caliper-benchmark/report.html`, commit `944fb0d`): 8 rounds, 24,500 real transactions.
> 2. **New Live Empirical Caliper Run** (`caliper-benchmark/results/live/20261018-010200/`): 11 rounds, 31,500 real transactions on an isolated 5-org network.
> 3. **Synthetic Queueing Projections** (`caliper-benchmark/results/simulated/20261018-011500/`): Mathematical simulation across 100 seeds.

---

## 2. Mathematical Formulation & Structural Assumptions

The performance model distinguishes between two fundamentally different transaction paths in Hyperledger Fabric v2.4+:

### 2.1. Consensus-Backed Write Path (Execute-Order-Validate)

For write operations (`createPatientRecord`, `updateHealthScore`, `createPrescription`, `requestScan`):
Transactions require three phases:
1. **Endorsement Phase:** Client submits proposal to endorsing peers; peers execute chaincode in parallel against their world state without committing.
2. **Ordering Phase:** Client sends signed endorsements to the Raft ordering service (`orderer.healthscore.com`). The orderer establishes total order and batches transactions into blocks based on two criteria:
   - `BatchTimeout` ($T_{\text{timeout}} = 2.0$s)
   - `MaxMessageCount` ($B_{\max} = 10$ transactions per block)
3. **Validation & Commit Phase:** Peers receive blocks, validate endorsement signatures and MVCC read-write sets, and commit valid state mutations to GoLevelDB/CouchDB.

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
    Orderer arrival rate exceeds consensus commitment capacity. Unprocessed transactions accumulate in memory buffers without dropping (assuming infinite buffer capacity):
    $$\gamma(\lambda) = \mu_w$$
    For a test of nominal duration $T_{\text{nom}} = \frac{N}{\lambda}$, the queue length at time $t$ grows as $(\lambda - \mu_w)t$. The time-averaged queueing latency is:
    $$\bar{W}_q = \frac{(\lambda - \mu_w) \cdot T_{\text{nom}}}{2 \cdot \mu_w}$$
    Total average latency expands linearly with queue buildup:
    $$W_{\text{sat}}(\lambda) = L_0 + \bar{W}_q$$

### 2.2. Local Read-Only Query Path

For read operations (`getPatientRecord`):
Transactions bypass the Raft ordering service entirely. The client submits a proposal to the local peer; the peer evaluates the chaincode query locally against its committed database and returns the result in a single gRPC round trip.
- Read capacity $\mu_r \approx 1,200.0$ QPS.
- Query latency is bounded by local serialization ($L_r \approx 0.001$–$0.005$s).
- Throughput is linear up to tested query limits ($500$ TPS).

---

## 3. Parameter Calibration & Residual Analysis

The simulator parameters were calibrated using the historical empirical Caliper baseline (commit `944fb0d`) and live benchmark observations:
- Calibrated Write Capacity $\mu_w$: **$350.1$ TPS**
- Calibrated Read Capacity $\mu_r$: **$1,200.0$ QPS**
- Base Write Network Latency: **$0.035$s**
- Base Read Network Latency: **$0.002$s**

### Calibration Residual Comparison Table:

| Benchmark Operation | Configured Offered Load (TPS) | Historical Measured Throughput (TPS) | Simulated Median Throughput (TPS) | Calibration Residual (TPS) | Historical Measured Avg Latency (s) | Simulated Median Avg Latency (s) | Latency Residual (s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **createPatientRecord** | 50 TPS | 49.8 | **50.0** | +0.2 (+0.4%) | 0.04 | **0.05** | +0.01 |
| **createPatientRecord** | 100 TPS | 99.9 | **100.0** | +0.1 (+0.1%) | 0.05 | **0.05** | 0.00 |
| **createPatientRecord** | 200 TPS | 199.9 | **200.0** | +0.1 (+0.05%) | 0.06 | **0.05** | -0.01 |
| **createPatientRecord (Knee)** | 350 TPS | — (Expanded) | **349.9** | — | — | **0.07** | — |
| **createPatientRecord (Stress)** | 1,000 TPS | 350.1 | **350.2** | +0.1 (+0.03%) | 7.92 | **7.84** | -0.08 (-1.0%) |
| **getPatientRecord** | 100 TPS | — (Expanded) | **100.0** | — | — | **0.002** | — |
| **getPatientRecord** | 250 TPS | — (Expanded) | **250.0** | — | — | **0.002** | — |
| **getPatientRecord** | 500 TPS | 500.3 | **500.0** | -0.3 (-0.06%) | 0.00 | **0.002** | +0.002 |

*Residual Summary:* Across all historical calibration points, the simulation models achieved throughput within $\pm 0.4\%$ and average latency within $\pm 0.08$ seconds of historical Caliper observations.

---

## 4. Key Simulation Limitations & Modeling Boundaries

1. **Infinite Queue Buffer Assumption:** The simulator assumes that peer and orderer memory buffers never drop transactions during over-saturation. In physical hardware, extreme queue buildup eventually leads to gRPC stream termination (`DEADLINE_EXCEEDED` or `RESOURCE_EXHAUSTED`).
2. **Zero Failures as a Modeling Assumption:** The simulated zero-failure rate reflects the ideal queueing assumption, NOT an empirical finding.
3. **Single-Node Orderer Contention:** The model reflects a single active Raft leader node. It does not model cross-datacenter Raft leader election failures or network partitions.
4. **Calibration vs. Validation:** Because the simulator was calibrated directly on the available historical points, residual closeness confirms goodness-of-fit, NOT independent validation on unobserved network topologies.
