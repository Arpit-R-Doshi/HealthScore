# HealthScore Hyperledger Fabric Blockchain Benchmark Report

**Document ID:** `HS-REP-06-BLOCKCHAIN-BENCHMARK`
**Evaluation Date:** October 2026 (Audited, Live-Rerun & Simulation Edition)
**Benchmarking Tool:** Hyperledger Caliper v0.5.0 (`@hyperledger/caliper-cli` with `@hyperledger/fabric-gateway@1.0.1`)
**Network Architecture:** Hyperledger Fabric v2.4/v2.5 (5 Peer Organizations, Raft Ordering Service, LevelDB/CouchDB State DB)
**Historical Authoritative Artifact:** [`caliper-benchmark/report.html`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/report.html) (Commit `944fb0d`, SHA-256 `af935716155e10e457f593c2bd22ad55776af362c1095bd84a8a76025c856672`)
**New Live Empirical Benchmark:** [`caliper-benchmark/results/live/20261018-010200/`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/results/live/20261018-010200/) (11 rounds, 31,500 txs)
**Synthetic Simulation Model:** [`caliper-benchmark/results/simulated/20261018-011500/`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/results/simulated/20261018-011500/) (100 PRNG seeds)
**Visualizations:**
- Empirical Latency & Throughput: [`fig5_blockchain_benchmarks.png`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/figures/fig5_blockchain_benchmarks.png)
- Empirical vs. Simulation Comparison: [`fig5b_caliper_simulation_projection.png`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/research_completion/figures/fig5b_caliper_simulation_projection.png)

---

### 1. Classification of Benchmark Evidence

To ensure total scientific integrity, this report maintains three strictly separated evidence classes:

1. **Class 1: Historical Empirical Caliper Baseline**
   - *Artifact:* [`caliper-benchmark/report.html`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/report.html) (frozen byte-for-byte from commit `944fb0d`, SHA-256 `af935716155e10e457f593c2bd22ad55776af362c1095bd84a8a76025c856672`).
   - *Scope:* 8 test rounds, $24,500$ transactions.
    - *Findings:* Zero reported failures among submitted transactions ($0/24,500$, $0.00\%$ failure rate), linear scaling up to $200$ write TPS ($0.04$s latency), saturation knee at $350.1$ write TPS under $1,000$ TPS stress load ($18.00$s average latency), and $500.3$ read TPS ($0.00$s displayed latency, supported as $\le 0.01$s average, maximum $0.04$s; Caliper 2-decimal display limitation).
2. **Class 2: New Live Empirical Caliper Rerun (Isolated Testbed)**
   - *Artifact:* [`caliper-benchmark/results/live/20261018-010200/`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/results/live/20261018-010200/)
   - *Scope:* Complete 11 rounds, $31,500$ transactions executed on a live, isolated 5-organization Fabric deployment (`HospitalOrg`, `PatientOrg`, `PharmacyOrg`, `LabOrg`, `InsuranceOrg` + Raft `OrdererOrg`).
   - *Findings:* $31,500$ successful transactions out of $31,500$ submitted ($0.00\%$ failure rate, zero reported failures). Replicated linear write regime ($50.4$ TPS at 50 offered, $100.3$ TPS at 100 offered, $200.2$ TPS at 200 offered, $349.9$ TPS at 350 offered). Under $1,000$ TPS configured stress target, achieved $615.7$ TPS actual send rate and $515.8$ TPS committed write throughput with queueing latency expanding to $6.98$s average ($11.18$s max). Read queries scaled across 100 TPS ($100.4$ TPS, $0.01$s avg, max $0.02$s), 250 TPS ($250.4$ TPS, $0.00$s avg, max $0.01$s), and 500 TPS ($500.3$ TPS, $0.00$s avg, max $0.13$s).
3. **Class 3: Synthetic Queueing Simulation Projections**
   - *Artifact:* [`caliper-benchmark/results/simulated/20261018-011500/`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/results/simulated/20261018-011500/)
   - *Scope:* Stochastic fluid-queueing performance model with log-normal consensus jitter across 100 PRNG seeds.
   - *Findings:* Models theoretical queue accumulation and latency expansion during over-saturation. Calibrated to historical throughput baseline within $+0.4\%$ residual ($351.53$ vs $350.1$ TPS). Demonstrates analytical limitation in predicting post-submission backlog drain (-8.73s residual vs historical 18.00s empirical latency). Explicitly marked as synthetic estimates.

---

## 2. Workload Hardening & Root-Cause Remediation

During the research strengthening pass, the Caliper workload implementation ([`workload.js`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/workload.js)) was audited and hardened against five critical failure modes:

1. **Elimination of Non-Deterministic PRNG:** Replaced `Math.random()` with a deterministic 32-bit **Mulberry32 PRNG** seeded per worker and round ($S = S_0 + 7919 \cdot W_i + 997 \cdot R_i$).
2. **Fail-Closed Record Pre-seeding:** State query and update workloads verify on-chain commitment before appending to the seeded patient list; halts immediately if pre-seeding fails.
3. **Worker Collision Fix:** Fixed a critical key generation bug where a custom `runPrefix` previously suppressed worker indices; now guarantees unique prefixes `R{round}_W{worker}_TX{seq}` across all concurrent workers.
4. **Valid Schema Arguments:** Validated all chaincode signatures (`createPatientRecord` takes 6 arguments, `updateHealthScore` takes 4, `createPrescription` takes 7, `requestScan` takes 5, `getPatientRecord` takes 1).
5. **Protocol Capability Disclosure:** All Caliper submissions use the `HospitalOrgAdmin` client gateway. This benchmark represents **single-identity protocol capacity** through the hospital endorser, not concurrent submission by five contending external clients.

---

## 3. Empirical Caliper Results

### 3.1. Historical Empirical Baseline (Commit `944fb0d`, $24,500$ Transactions)

| Test Round Name | Succ Txs | Fail Txs | Send Rate (TPS) | Min Latency (s) | Max Latency (s) | Avg Latency (s) | Throughput (TPS) | Performance Regime |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `createPatientRecord-50-tps` | 500 | 0 | 50.5 | 0.03 | 0.21 | 0.10 | **50.3** | Linear / Sub-100ms |
| `createPatientRecord-100-tps` | 1,000 | 0 | 100.5 | 0.02 | 0.13 | 0.06 | **100.2** | Linear / Low Latency |
| `createPatientRecord-200-tps` | 2,000 | 0 | 200.5 | 0.02 | 0.10 | 0.04 | **199.9** | Optimal Operating Point |
| `createPatientRecord-1000-tps`| 10,000| 0 | 963.6 | 0.54 | 21.14 | 18.00 | **350.1** | **Saturation Limit (Knee)** |
| `updateHealthScore-200-tps` | 2,000 | 0 | 200.5 | 0.02 | 0.36 | 0.06 | **200.0** | Score Write Invariance |
| `createPrescription-200-tps` | 2,000 | 0 | 200.5 | 0.02 | 0.35 | 0.05 | **200.0** | Clinical Prescription Write |
| `requestScan-200-tps` | 2,000 | 0 | 200.5 | 0.02 | 0.25 | 0.04 | **200.0** | Lab Scan Order Write |
| `getPatientRecord-500-tps` | 5,000 | 0 | 500.4 | 0.00 | 0.04 | 0.00* | **500.3** | State Query (No Consensus) |

*\* Note: Average latency displayed as `0.00`s in Caliper HTML output represents two-decimal display rounding ($\le 0.01$s). Maximum observed latency was $0.04$s.*

### 3.2. New Live Empirical Caliper Run (Run `20261018-010200`, $31,500$ Transactions)

| Test Round Name | Succ Txs | Fail Txs | Send Rate (TPS) | Min Latency (s) | Max Latency (s) | Avg Latency (s) | Throughput (TPS) | Performance Regime |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `createPatientRecord-50-tps` | 500 | 0 | 50.5 | 0.02 | 0.27 | 0.09 | **50.4** | Linear / Sub-100ms |
| `createPatientRecord-100-tps` | 1,000 | 0 | 100.5 | 0.02 | 0.21 | 0.05 | **100.3** | Linear / Low Latency |
| `createPatientRecord-200-tps` | 2,000 | 0 | 200.5 | 0.01 | 0.09 | 0.03 | **200.2** | Optimal Operating Point |
| `createPatientRecord-350-tps` | 3,500 | 0 | 350.6 | 0.01 | 0.15 | 0.03 | **349.9** | Saturation Knee Boundary |
| `createPatientRecord-1000-tps`| 10,000| 0 | 615.7 | 0.12 | 11.18 | 6.98 | **515.8** | **Over-Saturation Stress** |
| `updateHealthScore-200-tps` | 2,000 | 0 | 200.5 | 0.01 | 0.06 | 0.03 | **200.1** | Score Mutation Invariance |
| `createPrescription-200-tps` | 2,000 | 0 | 200.5 | 0.02 | 0.10 | 0.03 | **200.2** | Clinical Prescription Write |
| `requestScan-200-tps` | 2,000 | 0 | 200.5 | 0.01 | 0.07 | 0.03 | **200.2** | Lab Scan Order Write |
| `getPatientRecord-100-tps` | 1,000 | 0 | 100.5 | 0.00 | 0.02 | 0.01 | **100.4** | Baseline State Query |
| `getPatientRecord-250-tps` | 2,500 | 0 | 250.5 | 0.00 | 0.01 | 0.00* | **250.4** | Intermediate State Query |
| `getPatientRecord-500-tps` | 5,000 | 0 | 500.4 | 0.00 | 0.13 | 0.00* | **500.3** | High-Rate State Query |

*\* Note: Average latencies displayed as `0.00`s in Caliper HTML output reflect two-decimal rounding ($\le 0.01$s). Maximum query latencies reached $0.01$s ($250$ TPS) and $0.13$s ($500$ TPS).*

### 3.3. Initial Controlled Stress Investigation (Run `20261018-205500_stress_investigation`, $25,480$ Submitted Transactions of $25,500$ Configured) — Preserved Historical Record & Erratum

To investigate client send-rate scaling, a controlled stress experiment was executed using **8 Caliper worker processes** across intermediate load steps (350, 500, 750 TPS) and **three independent repetitions** of the 1,000 TPS saturation condition.

Across the 7 benchmark rounds, the configuration specified a nominal target of $25,500$ configured transactions. However, because Caliper's multi-worker runner apportions round targets via integer division across $W=8$ workers ($\lfloor \text{txNumber} / W \rfloor \times W$), rounds with non-divisible targets experienced a deterministic 20-proposal allocation shortfall ($1,750 \to 1,744$; $2,500 \to 2,496$; $3,750 \to 3,744$; $5,000 \times 3 \to 15,000$; $2,500 \to 2,496$), resulting in exactly $25,480$ submitted round transactions. Zero failures were reported among submitted transactions ($0/25,480$, $0.00\%$ failure rate among submitted proposals; pre-seeding writes: 0; total requests processed: $25,480$).

> [!WARNING]
> **ERRATUM ON ROUND 7 (`getPatientRecord-500-tps`):**
> Audit of `benchmark_expanded.yaml` and `workload.js` revealed that Round 7 specified `action: getPatientRecord` instead of `targetFunction: getPatientRecord`. Because `workload.js` inspected `roundArguments.targetFunction`, it defaulted to `createPatientRecord` writes. Consequently, Round 7 executed 2,496 write transactions with consensus overhead, rather than evaluating local state queries. The reported metrics (**349.5 TPS**, **3.01s** average latency) represent write performance, **NOT** read query throughput, and are **INVALID as read evidence**. See [`ERRATUM.md`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/results/live/20261018-205500_stress_investigation/ERRATUM.md). All raw artifacts in this directory are preserved unmodified as historical execution output.

| Test Round Name | Succ Txs | Fail Txs | Send Rate (TPS) | Min Latency (s) | Max Latency (s) | Avg Latency (s) | Throughput (TPS) | Validated Operation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `createPatientRecord-350-tps` | 1,744 | 0 | **352.0** | 0.02 | 2.04 | 0.28 | **249.6** | Write Consensus |
| `createPatientRecord-500-tps` | 2,496 | 0 | **476.7** | 0.24 | 4.33 | 2.73 | **332.4** | Write Consensus |
| `createPatientRecord-750-tps` | 3,744 | 0 | **670.4** | 0.24 | 6.30 | 4.87 | **412.2** | Write Consensus |
| `createPatientRecord-1000-tps-rep1` | 5,000 | 0 | **707.9** | 0.91 | 8.75 | 6.69 | **424.3** | Write Consensus (Rep 1) |
| `createPatientRecord-1000-tps-rep2` | 5,000 | 0 | **856.3** | 0.85 | 8.43 | 6.78 | **428.8** | Write Consensus (Rep 2) |
| `createPatientRecord-1000-tps-rep3` | 5,000 | 0 | **782.5** | 0.72 | 9.81 | 7.65 | **397.3** | Write Consensus (Rep 3) |
| `getPatientRecord-500-tps` *(Misconfigured)* | 2,496 | 0 | **494.8** | 1.01 | 4.25 | 3.01 | **349.5** | *Invalid Read (Executed as Write)* |

#### Valid Write Repetition Statistics ($N=3$ Repetitions, Sample SD with $\text{ddof}=1$):
- **Actual Send Rate:** $707.9$, $856.3$, $782.5$ TPS $\implies \mathbf{782.23 \pm 74.20}$ **TPS**
- **Committed Throughput:** $424.3$, $428.8$, $397.3$ TPS $\implies \mathbf{416.80 \pm 17.04}$ **TPS**
- **Average Latency:** $6.69$, $6.78$, $7.65$ s $\implies \mathbf{7.04 \pm 0.53}$ **seconds**
- **Maximum Latency:** $8.75$, $8.43$, $9.81$ s $\implies \mathbf{9.00 \pm 0.72}$ **seconds**

---

### 3.4. Corrected Controlled Stress & Read Benchmark (Run `20261018-230500_stress_investigation`, $25,480$ Submitted Round Transactions of $25,500$ Configured)

Following the identification of the configuration defect, `workload.js` and `benchmark_stress_investigation.yaml` were updated to enforce explicit `targetFunction` arguments across all rounds and configure ledger pre-seeding (`preSeedCount: 50`) for read queries.

Across the 7 benchmark rounds, $25,500$ transactions were configured and $25,480$ transactions were submitted to the testbed due to 8-worker integer division allocation (deterministic 20-proposal allocation shortfall: $1,750 \to 1,744$; $2,500 \to 2,496$; $3,750 \to 3,744$; $5,000 \times 3 \to 15,000$; $2,500 \to 2,496$). Prior to the read round (`getPatientRecord-500-tps`), eight worker processes each successfully seeded 50 patient records ($8 \times 50 = 400$ setup write requests) to ensure state existed on the ledger. These 400 pre-seeding write requests are separate from and precede the 25,480 measured Caliper round transactions, bringing the total write and read requests processed by the Fabric network during the benchmark execution to $25,880$. Zero failures were reported among all 25,480 submitted benchmark transactions ($0/25,480$, $0.00\%$ failure rate among submitted proposals). The full stress matrix was rerun in an isolated testbed with background container resource logging:

| Test Round Name | Succ Txs | Fail Txs | Send Rate (TPS) | Min Latency (s) | Max Latency (s) | Avg Latency (s) | Throughput (TPS) | Validated Operation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `createPatientRecord-350-tps` | 1,744 | 0 | **351.8** | 0.02 | 2.04 | 0.56 | **249.4** | Write Consensus |
| `createPatientRecord-500-tps` | 2,496 | 0 | **500.7** | 0.09 | 2.89 | 1.55 | **351.9** | Write Consensus |
| `createPatientRecord-750-tps` | 3,744 | 0 | **631.0** | 0.12 | 5.13 | 3.57 | **467.0** | Write Consensus |
| `createPatientRecord-1000-tps-rep1` | 5,000 | 0 | **729.1** | 0.13 | 6.91 | 5.29 | **470.6** | Write Consensus (Rep 1) |
| `createPatientRecord-1000-tps-rep2` | 5,000 | 0 | **688.0** | 0.33 | 6.70 | 5.18 | **499.8** | Write Consensus (Rep 2) |
| `createPatientRecord-1000-tps-rep3` | 5,000 | 0 | **811.0** | 0.88 | 7.41 | 5.60 | **485.4** | Write Consensus (Rep 3) |
| `getPatientRecord-500-tps` *(Corrected)* | 2,496 | 0 | **501.4** | 0.00 | 0.09 | 0.01 | **500.6** | **Genuine Read Query** |

#### Key Empirical Findings from the Corrected Benchmark:

1. **Verified Read Query Performance:**
   With explicit `targetFunction: getPatientRecord` and verified pre-seeding ($50$ pre-seeded records per worker, $400$ setup write requests total), the read test executed genuine local CouchDB state reads against populated ledger keys. Committed throughput reached **$500.6$ TPS** under an offered send rate of **$501.4$ TPS** ($99.8\%$ scaling), with zero reported failures among submitted queries ($0/2,496$, $0.00\%$ failure rate). The displayed average confirmation latency reported by Caliper is **$0.01$ seconds** (Caliper reports latency to two decimal places; min $0.00$s), with a maximum observed latency of **$0.09$ seconds**. These measurements confirm that read queries evaluate local CouchDB state directly and bypass Raft ordering and gossip consensus; however, because Caliper displays latency to two decimal places and maximum latency reached $0.09$ seconds, these results should not be characterized as proving "sub-10ms response times" or strictly "sub-hundredth-second" average latency.

2. **Corrected 1,000 TPS Write Repetitions ($N=3$, Sample SD with $\text{ddof}=1$):**
   - **Send Rate:** $729.1$, $688.0$, $811.0$ TPS $\implies \mathbf{742.70 \pm 62.62}$ **TPS**
   - **Committed Throughput:** $470.6$, $499.8$, $485.4$ TPS $\implies \mathbf{485.27 \pm 14.60}$ **TPS**
   - **Average Confirmation Latency:** $5.29$, $5.18$, $5.60$ s $\implies \mathbf{5.36 \pm 0.22}$ **seconds**
   - **Maximum Latency:** $6.91$, $6.70$, $7.41$ s $\implies \mathbf{7.01 \pm 0.36}$ **seconds**

3. **Investigation of the Actual Send-Rate Bottleneck (Container Resource Telemetry):**
   Continuous container CPU and memory telemetry was captured throughout the run in [`resource_utilization.csv`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/results/live/20261018-230500_stress_investigation/resource_utilization.csv):
   - The Caliper runner container (`node:20-alpine`) exhibited a mean CPU utilization of **$48.87\%$** and peaked at **$375.53\%$** (saturating nearly 4 full CPU cores) while coordinating workload dispatch across its 8 worker processes.
   - The endorsing peer (`peer0.hospital.healthscore.com`) exhibited a mean CPU of **$20.97\%$** and peaked at **$155.73\%$**.
   - The Raft orderer (`orderer.healthscore.com`) exhibited a mean CPU of **$6.09\%$** and peaked at **$57.64\%$**.
   - **Scientific Assessment:** The container CPU telemetry provides evidence consistent with client-side load-generation pressure, as the Caliper runner container peaked at $375.53\%$ CPU across its 8 worker processes while coordinating dispatch, whereas peer and orderer utilizations were substantially lower. However, container telemetry does not confirm or establish the precise cause of the send-rate bottleneck; the specific causal mechanism (e.g., ECDSA cryptographic signing overhead vs. Node.js V8 single-threaded event loop scheduling vs. gRPC client connection multiplexing) remains unisolated without dedicated profiling or controlled experiments.

4. **Single-Identity Benchmark Disclosure:**
   In accordance with benchmark transparency standards: all transactions across both live Caliper runs were submitted using a single administrative identity (`HospitalOrgAdmin` from `HospitalOrgMSP`) through the Fabric Gateway. This configuration reflects consortium administrative ingestion but does not simulate concurrent transaction proposals originated from multiple independent MSP client organizations. In a multi-client deployment, client-side workload generation would be distributed across distinct physical client machines.

---

## 4. Fabric Block Formation Configuration Audit

A rigorous inspection of channel configuration files resolves earlier documentation discrepancies regarding block assembly parameters:

| Parameter | Tracked Configuration (`configtx.yaml`) | Isolated Deployment Tooling | Earlier Manuscript Text (Erroneous) | Verified Status |
| :--- | :---: | :---: | :---: | :--- |
| `MaxMessageCount` | **10** | **10** | 50 | Corrected to **10** |
| `BatchTimeout` | **2s** | **2s** | 2.0s | Verified: **2s** |
| `PreferredMaxBytes` | **512 KB** | **512 KB** | 512 KB | Verified: **512 KB** |
| `AbsoluteMaxBytes` | **99 MB** | **99 MB** | 99 MB | Verified: **99 MB** |

- **Historical Deployment Provenance:** The repository's tracked `healthscore-network/configtx/configtx.yaml` since initial commit `944fb0d` specifies `MaxMessageCount: 10` and `BatchTimeout: 2s`. Runtime ephemeral container logs from the historical run were not retained; however, all repository evidence establishes `MaxMessageCount: 10`.
- **Live Isolated Deployment:** Explicitly instantiated with `MaxMessageCount: 10` and `BatchTimeout: 2s` via `orchestrate_isolated_benchmark.sh`.
- **Correction:** All references in the manuscript describing `MaxMessageCount: 50` were erroneous assumptions and have been reconciled to the verified value of **10**.

---

## 5. Synthetic Performance Simulation & Calibration Residuals

The performance simulator (`caliper-benchmark/simulate_benchmark.py`) implements a **stochastic fluid-queueing model** with log-normal consensus jitter across 100 PRNG seeds. Complete mathematical formulation and assumptions are documented in [`SIMULATION_ASSUMPTIONS.md`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/results/simulated/20261018-011500/SIMULATION_ASSUMPTIONS.md).

| Workload Condition | Historical Throughput (TPS) | Simulated Median (TPS) | Throughput Residual | Historical Avg Latency (s) | Simulated Latency (s) | Latency Residual | Modeling Regime |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| Write: 50 TPS | 49.8 | **50.0** | +0.2 (+0.4%) | 0.04 | **0.05** | +0.01s | Sub-Saturation Linear |
| Write: 100 TPS | 99.9 | **100.0** | +0.1 (+0.1%) | 0.05 | **0.05** | 0.00s | Sub-Saturation Linear |
| Write: 200 TPS | 199.9 | **200.0** | +0.1 (+0.05%) | 0.06 | **0.05** | -0.01s | Sub-Saturation Linear |
| Write: 350 TPS (Knee) | — | **349.9** | — | — | **0.07** | — | Capacity Boundary |
| Write: 1,000 TPS (Stress) | 350.1 | **351.5** | +1.4 (+0.4%) | 18.00 | **9.27** | **-8.73s (-48.5%)** | Over-Saturation Queueing |
| Read: 100 TPS | — | **100.0** | — | — | **0.002** | — | State DB Direct Read |
| Read: 250 TPS | — | **250.0** | — | — | **0.002** | — | State DB Direct Read |
| Read: 500 TPS | 500.3 | **500.0** | -0.3 (-0.06%) | 0.00* | **0.002** | +0.002s | State DB Direct Read |

### Transparent Analysis of the Stress Latency Residual (-8.73s)
- **Root Cause:** In the empirical historical run, $10,000$ transactions were offered at $963.6$ TPS over $\approx 10.38$s, but committing the resulting backlog at $350.1$ TPS required $28.56$s total run duration. The empirical average confirmation latency across all transactions was $18.00$s.
- **Model Limitation:** The fluid-queueing formulation computes the integral of queue backlog during the active 10-second submission window ($W_q \approx 9.27$s) and does not model post-window backlog drain duration.
- **Scientific Disclosure:** The simulation must not be claimed to reproduce historical stress latency. It provides a conservative queueing lower bound under continuous submission rather than post-burst clearing dynamics.

---

## 6. Architectural Distinction: Chaincode TPS vs. End-to-End API Capacity

A critical systems distinction must be maintained:
- **Chaincode Protocol Throughput:** Hyperledger Fabric achieves $350.1$–$515.8$ write TPS (across empirical stress runs) and $500.3$–$500.6$ read TPS at the gateway level.
- **End-to-End HTTP API Capacity:** In synchronous execution, client requests to `/api/predict-score` trigger JWT verification, JSON parsing, Python subprocess initialization (`run_engine.py`), model unpickling, ML inference, loss simulation, and subsequent ledger submission.
- **Analytical Bound:** Because the Python inference process requires $\approx 40$–$50$ ms per invocation, a single synchronous worker process is analytically bounded to:
  $$\text{Capacity}_{\text{single-worker}} \approx \frac{1.0}{0.045\text{s}} \approx 20\text{–}25\text{ requests/second}$$
- **Architectural Recommendation:** Direct synchronous API calls cannot saturate the Fabric blockchain. Production architectures require asynchronous job queues (e.g., Redis Streams / Apache Kafka) to decouple inference from ledger commit.

---

## 7. How to Reproduce All Three Evidence Streams

```bash
# 1. Verify byte-for-byte integrity of historical report
python3 -c "
import hashlib
with open('caliper-benchmark/report.html', 'rb') as f:
    h = hashlib.sha256(f.read()).hexdigest()
assert h == 'af935716155e10e457f593c2bd22ad55776af362c1095bd84a8a76025c856672'
print('Historical report verified:', h)
"

# 2. Run benchmark test suite (17 passed)
ml_model/venv/bin/pytest caliper-benchmark/tests/ -v

# 3. Run performance simulator (100 seeds)
ml_model/venv/bin/python caliper-benchmark/simulate_benchmark.py --seeds 100

# 4. Check live Caliper results
cat caliper-benchmark/results/live/20261018-010200/run_manifest.json
cat caliper-benchmark/results/live/20261018-230500_stress_investigation/run_manifest.json
```
