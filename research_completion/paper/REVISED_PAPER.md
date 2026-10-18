# Evaluating High-Throughput Permissioned Blockchain for Healthcare Workflows: Fabric Performance with ACG-Inspired Risk Scoring and Premium Simulation

**Authors:** [Author Names Redacted for Peer Review]
**Affiliation:** [Institutional Affiliations Redacted for Double-Blind Peer Review]
**Date:** October 2026
**Document Classification:** Revised Research Manuscript (Version 3.0 — Blockchain-Centric Systems & Applied Evaluation Edition)
**Primary Repository Branch:** `feature/ml-pipeline-rebuild`
**Artifact Manifest:** [`experiment_registry.json`](../experiments/experiment_registry.json)
**Supplementary Reports:** [`BLOCKCHAIN_BENCHMARK_REPORT.md`](../BLOCKCHAIN_BENCHMARK_REPORT.md), [`PREMIUM_SIMULATION_VALIDATION.md`](../PREMIUM_SIMULATION_VALIDATION.md), [`FEATURE_ABLATION_REPORT.md`](../FEATURE_ABLATION_REPORT.md)

---

## Abstract

Permissioned distributed ledger architectures hold significant promise for healthcare administration, clinical auditability, and multiparty health insurance workflows by eliminating centralized single points of failure and enforcing tamper-evident execution. However, empirical adoption is hindered by uncertainty regarding transaction throughput ceilings, consensus queueing latency under load, and the computational cost of integrating off-chain risk inference with on-chain state recording.

In this paper, we evaluate **HealthScore**, an integrated architecture coupling a 5-organization Hyperledger Fabric consortium network (Hospital, Patient, Pharmacy, Diagnostic Laboratory, and Health Insurer) with an off-chain Adjusted Clinical Group (ACG)-inspired multi-disease risk model and configurable premium simulation. We establish three distinct, non-overlapping performance evidence streams: (i) an authoritative historical empirical Hyperledger Caliper benchmark across $24,500$ transactions (commit `944fb0d`), (ii) a verified live Caliper rerun on an isolated 5-organization testbed executing the expanded 11-round workload ($31,500$ transactions), and (iii) a reproducible stochastic fluid-queueing performance model across 100 seeds exploring theoretical saturation dynamics.

Our empirical blockchain benchmarks demonstrate:
1. **Sub-100ms Linear Operating Regime:** Across production healthcare write workloads (`createPatientRecord`, `updateHealthScore`, `createPrescription`, and `requestScan`), the Fabric network scales linearly up to $200$ transactions per second (TPS) with committed throughput of **$199.9$ – $200.2$ TPS**, average confirmation latency below **$0.06$ seconds** ($0.03$–$0.04$s median), and zero transaction failures ($0.00\%$).
2. **Distinct Saturation and Queueing Regimes:** We distinguish separate empirical stress measurements under a 1,000 TPS target load governed by Raft consensus batching, CouchDB endorsement write validation, and block-cutting boundaries (`BatchTimeout: 2s`, `MaxMessageCount: 10`): the historical baseline (commit `944fb0d`) observed **$350.1$ TPS** committed write throughput at $963.6$ TPS send rate ($18.00$s average latency); the 5-worker isolated testbed achieved **$515.8$ TPS** throughput at $615.7$ TPS send rate ($6.98$s average latency); and the 8-worker stress repetitions sustained **$485.27 \pm 14.60$ TPS** ($\text{ddof}=1$) at $742.70 \pm 62.62$ TPS actual send rate ($5.36 \pm 0.22$s average latency). Across all empirical runs, zero transactions were aborted or dropped ($0.00\%$ failure rate) while queueing latency expanded to multi-second delays.
3. **Decoupled Read Scalability:** Local peer CouchDB state evaluation (`getPatientRecord`) scales linearly across 100, 250, and 500 TPS to **$500.3$ – $500.6$ TPS** with sub-hundredth-second latency ($\le 0.01$s displayed average, rounded to $0.00$s within Caliper's 2-decimal display precision, max observed $0.09$–$0.13$s) by bypassing orderer consensus and multi-peer validation. All benchmark proposals were submitted under `HospitalOrgAdmin` through the Fabric Gateway.
4. **End-to-End Application Throughput Boundary:** We explicitly distinguish smart contract chaincode capacity ($350$–$500$ write / $500$ read TPS) from the end-to-end web client pipeline. The HTTP Express API, JWT authorization, and Python machine learning subprocess inference incur non-trivial process execution overhead ($\approx 40$–$50$ ms). Analytically, a single Node.js worker process synchronously awaiting Python inference and ledger response is bounded to an estimated $\approx 20$–$25$ requests per second ($1 / 0.045\text{s} \approx 22.2\text{ req/s}$) rather than an observed multi-client stress measurement, confirming that production deployments must decouple inference via asynchronous message queues.

We contextualize this distributed ledger capability with an audited machine learning pipeline evaluated across 46,458 records from three official Medical Expenditure Panel Survey (MEPS) cohorts (HC-251, HC-256, and HC-257 Panel 28 prospective follow-up). Controlled 17-scenario feature ablations isolate the contribution of our ACG-inspired condition clusters from composite multimorbidity and interaction terms: while disease clusters increase dollar regression $R^2$ from $0.0395$ (demographics alone) to $0.0771$ and double weighted Brier Skill Score from $+0.0506$ to $+0.1005$, composite interaction terms yield modest incremental predictive value ($\Delta R^2 = +0.0027$) despite dominating tree-based SHAP attribution ($39.0\%$). Finally, we formalize a transparent Value-at-Risk premium simulation $X_\alpha = B + (1+\alpha)G$ where dimensionless risk-loading $\alpha \ge 0$ scales synthetic Gamma loss above a base-cost floor $B$; empirical simulations across 60 scenarios calibrate to analytical Gamma quantiles within $0.7\%$.

---

## 1. Introduction and Research Questions

Modern healthcare information systems must simultaneously satisfy rigorous throughput, privacy, and integrity requirements. Clinical care, prescription issuance, diagnostic imaging, and insurance risk adjustment involve multiple distinct legal entities—hospitals, outpatient clinics, retail pharmacies, diagnostic laboratories, and insurance carriers. In traditional centralized architectures, these entities exchange records through point-to-point electronic data interchange (EDI) clearinghouses or centralized payer databases. Such centralized architectures suffer from critical structural weaknesses: proprietary data silos, high reconciliation overhead, single points of compromise, and the absence of an immutable, shared audit trail across institutional boundaries.

Permissioned distributed ledger technology (DLT), specifically Hyperledger Fabric, offers an enterprise-grade alternative by establishing a shared, append-only, cryptographically verified ledger governed by multi-organization consensus, role-based access control via Membership Service Providers (MSPs), and deterministic smart contracts (chaincode). However, in mission-critical healthcare environments, adopting permissioned blockchain hinges on empirical performance evidence:
- Can a permissioned consortium sustain real-world healthcare write transaction rates (patient registration, prescription issuance, score recording) with sub-second confirmation latency?
- At what offered load does the network encounter saturation, and how do consensus-backed state writes compare to read-only queries?
- How should computationally demanding analytics—such as chronic-disease risk prediction and insurance expenditure forecasting—be architected to avoid burdening the distributed ledger?

To resolve these questions, we investigate **HealthScore**, an audited enterprise architecture that decouples compute-heavy risk modeling and loss simulation into an off-chain engine while anchoring patient milestones, diagnostic requests, prescriptions, and verified risk scores onto an on-chain 5-organization Hyperledger Fabric network.

### Explicit Research Questions
Our investigation is guided by four primary research questions:

- **RQ1 (Throughput & Latency Scaling):** How do transaction throughput and confirmation latency scale as offered load increases for representative healthcare write operations (`createPatientRecord`, `updateHealthScore`, `createPrescription`, `requestScan`) versus read-only queries on a 5-organization Fabric network?
- **RQ2 (Saturation Dynamics & Bottlenecks):** What operating region, saturation knee, queueing trade-off, and transaction failure profile characterize the Fabric network under severe stress loads up to $1,000$ TPS, and how does chaincode throughput diverge from end-to-end application throughput?
- **RQ3 (ACG-Inspired Multi-Disease Incremental Value):** What isolated predictive evidence supports the custom ACG-inspired chronic-condition clusters versus composite multimorbidity penalties and age-by-comorbidity interaction terms across dollar expenditure regression and high-cost classification?
- **RQ4 (Configurable Risk-Loading Simulation):** How do configurable base-cost floors ($B$) and dimensionless risk-loading parameters ($\alpha$) govern the simulated loss distribution ($X_\alpha = B + (1+\alpha)G$), and how accurately do Monte Carlo simulated quantiles calibrate against analytical Gamma Value-at-Risk targets?

---

## 2. Related Work and Research Gap

### 2.1. Hyperledger Fabric Architecture and Benchmarking in Healthcare
Hyperledger Fabric [5] has emerged as the leading permissioned blockchain framework for enterprise consortia due to its modular execute-order-validate transaction lifecycle. Unlike public proof-of-work blockchains constrained to single-digit TPS (e.g., Bitcoin $\approx 7$ TPS, Ethereum $\approx 15$–$30$ TPS), Fabric achieves enterprise scale by executing chaincode endorsements in parallel before ordering transactions into blocks via Crash Fault Tolerant (CFT) Raft consensus [5].

Prior healthcare blockchain studies have proposed conceptual frameworks for electronic health records (EHRs) and consent management. However, many published works rely on qualitative proposals or simulated toy networks of 1–2 nodes, lacking standardized, reproducible performance evaluations. Hyperledger Caliper provides a standardized Linux Foundation benchmarking framework to measure throughput, latency, and resource consumption under controlled offered rates. In this work, we deploy Caliper v0.5.0 against an authoritative 5-organization Fabric topology, systematically characterizing both linear and saturated regimes.

### 2.2. Clinical Risk Adjustment & Multi-Disease Grouping
In health economics, risk adjustment models adjust capitation payments and identify high-cost patients. The Johns Hopkins ACG (Adjusted Clinical Groups) system, CMS Hierarchical Condition Categories (CMS-HCC), and Chronic Illness and Disability Payment System (CDPS) group thousands of ICD-10 diagnosis codes into clinical clusters.

However, existing commercial groupers are proprietary, centralized, and dependent on complete administrative billing claims unavailable in light digital health intakes. While machine learning researchers have attempted to predict healthcare costs using survey datasets such as MEPS, published models frequently suffer from training-inference feature leakage (relying on unobservable clinical survey questions), failure to evaluate arithmetic dollar calibration, and lack of prospective multi-year testing. We address this gap by establishing an open, ACG-inspired chronic-condition clustering design evaluated across three successive MEPS releases.

### 2.3. Actuarial Loss Simulation & Risk Loading
In insurance mathematics, healthcare losses exhibit extreme right-skewness, excess zeros, and heavy upper tails. Actuarial pricing utilizes compound Poisson-Gamma (Tweedie) GLMs and parametric Value-at-Risk (VaR) simulations to estimate required risk margins above expected losses. While prior health tech demonstrations often confuse statistical confidence intervals with loss percentiles or hardcode static premium offsets, we formulate a transparent, parameterized risk-loading formulation with closed-form analytical calibration.

---

## 3. HealthScore Architecture and Healthcare Transaction Lifecycle

HealthScore establishes a hybrid off-chain/on-chain architecture designed to maximize throughput while guaranteeing auditability:

```
[ Clinical User / Doctor / Patient ]
                 │ (HTTPS / Server-Verified JWT & Default-Deny RBAC)
                 ▼
     [ Express Node.js Gateway API ]
                 │
                 ├─► [ Secure Hashed Credential Store (PBKDF2) ]
                 ├─► [ Off-Chain Python Inference Engine ]
                 │         │
                 │         ▼ (SHA-256 Verified Model Manifest)
                 │   • Tweedie GLM (Expected Dollar Expenditure)
                 │   • Weighted Logistic Regressor (P90 High-Cost Classifier)
                 │   • Parametric Monte Carlo Loss Simulation (X_alpha = B + (1+alpha)G)
                 │
                 ▼ (Hyperledger Fabric SDK / Gateway)
[ Permissioned Hyperledger Fabric Network (5 Organizations) ]
                 │
                 ├─► [ HospitalOrgMSP ] (Doctors: Record Intake, Update Scores, Prescribe)
                 ├─► [ PatientOrgMSP ]  (Patients: Access Own Records)
                 ├─► [ PharmacyOrgMSP ] (Pharmacists: Query & Dispense Prescriptions)
                 ├─► [ LabOrgMSP ]      (Diagnostic Labs: Query Orders & Complete Scans)
                 ├─► [ InsuranceOrgMSP ](Insurers: Query Redacted Scores for Underwriting)
                 │
                 ├─► [ CFT Raft Ordering Service (orderer.healthscore.com) ]
                 ├─► [ Smart Contract Chaincode (index.js) ] (Enforces MSP Role Policies)
                 ├─► [ Append-Only Blockchain Ledger ] (Cryptographic Block Storage)
                 └─► [ CouchDB World State Database ] (Fast Key-Value Latest Snapshot)
```

### 3.1. What Remains Off-Chain vs. What is Recorded On-Chain
To preserve patient privacy under HIPAA/GDPR and prevent ledger bloat, raw clinical notes, free-text intake, biometric sensor streams, and high-dimensional model weight files remain strictly **off-chain**.

The blockchain ledger records only discrete, verifiable state milestones:
1. `createPatientRecord`: Patient registration with baseline demographic identifiers and initial clinical history.
2. `updateHealthScore`: Timestamped health risk score (0–100 percentile rank), model-predicted annual dollar expenditure, and simulated target premium, signed by `HospitalOrgMSP`.
3. `createPrescription`: Cryptographically signed medication order with dosage, frequency, and optional off-chain IPFS payload hash.
4. `dispensePrescription`: Status update executed exclusively by `PharmacyOrgMSP` recording dispensing timestamp and pharmacist ID.
5. `requestScan` & `completeScan`: Diagnostic order lifecycle managed collaboratively between `HospitalOrgMSP` and `LabOrgMSP`.

### 3.2. Ledger and World-State Distinction
Hyperledger Fabric maintains a fundamental architectural duality:
- **Append-Only Block Storage:** An immutable, cryptographic SHA-256 hash-chained log of every transaction block. When a patient's risk score is updated annually, the previous score is never overwritten or erased; the complete longitudinal trajectory remains immutably auditable.
- **CouchDB World-State Database:** A document database maintaining the current state snapshot. Key-based reads (`getPatientRecord`) execute directly against CouchDB on the endorsing peer without traversing ordering or consensus, achieving low-latency query performance ($\le 0.01$s displayed average, maximum $0.04$s historical / $0.13$s live).

### 3.3. MSP-Based Authorization Policy Matrix
The chaincode (`chaincode/index.js`) inspects the invoker's X.509 certificate and enforces strict Role-Based Access Control (RBAC):

| Smart Contract Method | HospitalOrg | PatientOrg | PharmacyOrg | LabOrg | InsuranceOrg |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `createPatientRecord` | ✅ **Write** | ❌ | ❌ | ❌ | ❌ |
| `getPatientRecord` | ✅ Read | ✅ Read (Own) | ❌ | ✅ Read | ✅ **Redacted** (Score Only) |
| `updateHealthScore` | ✅ **Write** | ❌ | ❌ | ❌ | ❌ |
| `createPrescription` | ✅ **Write** | ❌ | ❌ | ❌ | ❌ |
| `dispensePrescription` | ❌ | ❌ | ✅ **Write** | ❌ | ❌ |
| `requestScan` | ✅ **Write** | ❌ | ❌ | ❌ | ❌ |
| `completeScan` | ❌ | ❌ | ❌ | ✅ **Write** | ❌ |

---

## 4. Hyperledger Fabric Deployment and Benchmark Methodology

### 4.1. Network Topology and Configuration
The benchmark network comprises 5 peer organizations and a dedicated ordering service:
- **Peers:** 5 Fabric peer nodes (`peer0.hospital`, `peer0.patient`, `peer0.pharmacy`, `peer0.lab`, `peer0.insurance`), each running Hyperledger Fabric v2.4 with CouchDB state databases.
- **Ordering Service:** Single-node CFT Raft ordering service (`orderer.healthscore.com:7050`).
- **Channel & Chaincode:** Channel `healthscorechannel`, Node.js smart contract `healthscore` (contract SPI v2.0).
- **Block Formation Parameters:** `BatchTimeout = 2.0s`, `MaxMessageCount = 10`, `PreferredMaxBytes = 512 KB` (verified directly against `healthscore-network/configtx/configtx.yaml`).

### 4.2. Hardened Benchmark Workload Module
Benchmarking is driven by Hyperledger Caliper v0.5.0 using our hardened workload module (`caliper-benchmark/workload.js`). To eliminate measurement artifacts observed in standard Caliper testbeds, we implemented five methodological safeguards:
1. **Deterministic PRNG (Mulberry32):** Standard implementations use `Math.random()`, which creates non-reproducible transaction streams. We replace this with a 32-bit Mulberry32 PRNG deterministically seeded by worker and round indices ($S = S_0 + 7919 \cdot W_i + 997 \cdot R_i$).
2. **Fail-Closed Record Pre-seeding:** Read and update rounds (`updateHealthScore`, `getPatientRecord`) require pre-existing ledger records. The workload pre-seeds 200 unique records per worker. If pre-seeding fails, the error is counted explicitly and the run is halted, preventing uncreated records from artificially inflating error rates.
3. **Collision-Free Monotonic Keying:** Transaction keys combine a unique run prefix, worker index, and transaction sequence (`PAT_R{round}_W{worker}_TX{seq}`), guaranteeing zero key collisions across repeated runs.
4. **Valid Schema Arguments:** All clinical arguments conform strictly to chaincode expectations (numeric string serialization, valid priority enums).
5. **Configurable Invoker Identity:** The workload explicitly declares the invoker identity (`HospitalOrgAdmin`). We report throughput honestly as single-identity client protocol capacity rather than falsely inferring a 5-organization concurrent client submission.

---

## 5. Blockchain Throughput, Latency, and Saturation Results

### 5.1. Classification of Evidence and Historical Empirical Baseline
To maintain strict scientific integrity, this investigation evaluates three distinct, non-overlapping performance evidence streams:
1. **Class 1: Historical Empirical Baseline (Commit `944fb0d`):** 8 test rounds and $24,500$ transactions executed against the original 5-organization Fabric network. Preserved byte-for-byte in [`caliper-benchmark/report.html`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/report.html) (SHA-256: `af935716155e10e457f593c2bd22ad55776af362c1095bd84a8a76025c856672`).
2. **Class 2: New Live Empirical Caliper Rerun (Run `20261018-010200`):** 11 test rounds and $31,500$ transactions executed on an isolated, freshly provisioned 5-organization testbed (`HospitalOrg`, `PatientOrg`, `PharmacyOrg`, `LabOrg`, `InsuranceOrg` + Raft `OrdererOrg`) deployed with identical chaincode and endorsement policies. Saved under [`caliper-benchmark/results/live/20261018-010200/`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/results/live/20261018-010200/).
3. **Class 3: Synthetic Queueing Simulation Projections:** A reproducible stochastic fluid-queueing performance model with log-normal consensus jitter (`caliper-benchmark/simulate_benchmark.py`) executed across 100 PRNG seeds to explore queue accumulation and sensitivity envelopes, calibrated to historical baselines within $+0.4\%$ throughput residual ($351.53$ vs $350.1$ TPS). Saved under [`caliper-benchmark/results/simulated/20261018-011500/`](file:///Users/arpitdoshi/Desktop/ipd/HealthScore/caliper-benchmark/results/simulated/20261018-011500/).

The historical empirical baseline results (Commit `944fb0d`, $24,500$ transactions) are transcribed below:

| Benchmark Workload Round | Target Function | Configured Target (TPS) | Actual Send Rate (TPS) | Total Txs | Succ Txs | Fail Txs | Failure Rate | Min Lat (s) | Max Lat (s) | Avg Lat (s) | Committed Throughput (TPS) | Operational Regime |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `createPatientRecord-50-tps` | `createPatientRecord` | 50 | 50.5 | 500 | 500 | 0 | **0.00%** | 0.03 | 0.21 | 0.10 | **50.3** | Linear / Sub-100ms |
| `createPatientRecord-100-tps` | `createPatientRecord` | 100 | 100.5 | 1,000 | 1,000 | 0 | **0.00%** | 0.02 | 0.13 | 0.06 | **100.2** | Linear / Sub-100ms |
| `createPatientRecord-200-tps` | `createPatientRecord` | 200 | 200.5 | 2,000 | 2,000 | 0 | **0.00%** | 0.02 | 0.10 | 0.04 | **199.9** | Optimal Operating Peak |
| `createPatientRecord-1000-tps`| `createPatientRecord` | 1,000 | 963.6 | 10,000 | 10,000 | 0 | **0.00%** | 0.54 | 21.14 | 18.00 | **350.1** | **Saturation Ceiling (Knee)** |
| `updateHealthScore-200-tps` | `updateHealthScore` | 200 | 200.5 | 2,000 | 2,000 | 0 | **0.00%** | 0.02 | 0.36 | 0.06 | **200.0** | Score Write Invariance |
| `createPrescription-200-tps` | `createPrescription` | 200 | 200.5 | 2,000 | 2,000 | 0 | **0.00%** | 0.02 | 0.35 | 0.05 | **200.0** | Clinical Prescription Write |
| `requestScan-200-tps` | `requestScan` | 200 | 200.5 | 2,000 | 2,000 | 0 | **0.00%** | 0.02 | 0.25 | 0.04 | **200.0** | Lab Order Write |
| `getPatientRecord-500-tps` | `getPatientRecord` | 500 | 500.4 | 5,000 | 5,000 | 0 | **0.00%** | 0.00 | 0.04 | 0.00* | **500.3** | **State Query (No Consensus)** |

*\* Note: Average latency displayed as `0.00`s in Caliper HTML output represents two-decimal display rounding ($\le 0.01$s). Maximum observed latency was $0.04$s.*
*Totals:* **$24,500$ submitted transactions**, **$24,500$ committed successes**, **$0$ failures ($0.00\%)**.

### 5.2. Verified Live Caliper Rerun on Isolated 5-Organization Testbed
To independently verify the expanded 11-round benchmark matrix ($31,500$ transactions) without risking host credentials or conflicting with production configurations, we provisioned an isolated 5-organization Fabric network with fresh cryptographic material (`EnableNodeOUs: true`), deployed `healthscore` chaincode v2.0, and executed Hyperledger Caliper v0.5.0 directly against the testbed:

| Benchmark Workload Round | Target Function | Configured Target (TPS) | Actual Send Rate (TPS) | Total Txs | Succ Txs | Fail Txs | Failure Rate | Min Lat (s) | Max Lat (s) | Avg Lat (s) | Committed Throughput (TPS) | Operational Regime |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `createPatientRecord-50-tps` | `createPatientRecord` | 50 | 50.5 | 500 | 500 | 0 | **0.00%** | 0.02 | 0.27 | 0.09 | **50.4** | Linear / Sub-100ms |
| `createPatientRecord-100-tps` | `createPatientRecord` | 100 | 100.5 | 1,000 | 1,000 | 0 | **0.00%** | 0.02 | 0.21 | 0.05 | **100.3** | Linear / Sub-100ms |
| `createPatientRecord-200-tps` | `createPatientRecord` | 200 | 200.5 | 2,000 | 2,000 | 0 | **0.00%** | 0.01 | 0.09 | 0.03 | **200.2** | Optimal Operating Peak |
| `createPatientRecord-350-tps` | `createPatientRecord` | 350 | 350.6 | 3,500 | 3,500 | 0 | **0.00%** | 0.01 | 0.15 | 0.03 | **349.9** | Saturation Boundary Knee |
| `createPatientRecord-1000-tps`| `createPatientRecord` | 1,000 | 615.7 | 10,000 | 10,000 | 0 | **0.00%** | 0.12 | 11.18 | 6.98 | **515.8** | **Over-Saturation Stress** |
| `updateHealthScore-200-tps` | `updateHealthScore` | 200 | 200.5 | 2,000 | 2,000 | 0 | **0.00%** | 0.01 | 0.06 | 0.03 | **200.1** | Score Write Invariance |
| `createPrescription-200-tps` | `createPrescription` | 200 | 200.5 | 2,000 | 2,000 | 0 | **0.00%** | 0.02 | 0.10 | 0.03 | **200.2** | Clinical Prescription Write |
| `requestScan-200-tps` | `requestScan` | 200 | 200.5 | 2,000 | 2,000 | 0 | **0.00%** | 0.01 | 0.07 | 0.03 | **200.2** | Lab Order Write |
| `getPatientRecord-100-tps` | `getPatientRecord` | 100 | 100.5 | 1,000 | 1,000 | 0 | **0.00%** | 0.00 | 0.02 | 0.01 | **100.4** | Baseline State Query |
| `getPatientRecord-250-tps` | `getPatientRecord` | 250 | 250.5 | 2,500 | 2,500 | 0 | **0.00%** | 0.00 | 0.01 | 0.00* | **250.4** | Intermediate State Query |
| `getPatientRecord-500-tps` | `getPatientRecord` | 500 | 500.4 | 5,000 | 5,000 | 0 | **0.00%** | 0.00 | 0.13 | 0.00* | **500.3** | High-Rate State Query |

*\* Note: Average latencies displayed as `0.00`s in Caliper HTML output reflect two-decimal rounding ($\le 0.01$s). Maximum query latencies reached $0.01$s ($250$ TPS) and $0.13$s ($500$ TPS).*
*Totals:* **$31,500$ submitted transactions**, **$31,500$ committed successes**, **$0$ failures ($0.00\%)**. Total execution duration: $646.16$ seconds.

*Controlled Stress Scaling with 8 Workers (`20261018-205500_stress_investigation` and `20261018-230500_stress_investigation`):* To evaluate whether the actual send rate of $615.7$ TPS observed in the 11-round run was bounded by client-side load-generation bottlenecks, we executed controlled follow-up experiments using 8 Caliper worker processes across intermediate load steps ($350$, $500$, $750$ TPS) and three repetitions of the $1,000$ TPS stress condition ($25,480$ transactions each). In the initial run, expanding to 8 workers increased the achieved client send rate from $615.7$ TPS to **$856.3$ TPS** (mean under 1,000 TPS target: **$782.23 \pm 74.20$ TPS**, sample standard deviation with $\text{ddof}=1$), with committed write throughput sustaining **$416.80 \pm 17.04$ TPS** ($\text{ddof}=1$) across all three repetitions ($424.3$, $428.8$, $397.3$ TPS) with zero transaction failures ($0/15,000$). In the corrected live rerun (`20261018-230500_stress_investigation`), the three 1,000 TPS write repetitions sustained **$485.27 \pm 14.60$ TPS** ($\text{ddof}=1$; individual runs: $470.6$, $499.8$, $485.4$ TPS) at an actual send rate of **$742.70 \pm 62.62$ TPS** ($\text{ddof}=1$). Continuous container telemetry recorded during the corrected run showed the Caliper runner container peaking at $375.5\%$ CPU (saturating nearly 4 full CPU cores) while the orderer peaked at $57.6\%$ CPU. These observations indicate that the shortfall in achieving the 1,000 TPS offered rate was primarily a client-side workload-generation bottleneck, though the exact internal mechanism within the Node.js runner (e.g., ECDSA signing vs. V8 event loop scheduling vs. gRPC serialization) remains unisolated without dedicated profiler traces. All transactions were submitted under administrative identity `HospitalOrgAdmin`.

### 5.3. Synthetic Queueing Simulation and Calibration Residuals
To support continuous integration and explore theoretical queue dynamics when physical hardware or Docker is unavailable, we formulated a stochastic fluid-queueing model (`simulate_benchmark.py`) with Raft consensus jitter. Consensus writes are modeled with a calibrated Raft consensus commitment capacity $\mu_w = 350.1$ TPS (derived from the historical baseline) and log-normal jitter ($\sigma = 0.08$–$0.12$). Read queries bypass consensus and execute locally against CouchDB with capacity $\mu_r = 1,200.0$ QPS.

We simulated 100 independent PRNG seeds per scenario, producing median estimates and a synthetic variability range (5th–95th percentile sensitivity envelope, visualized in [`fig5b_caliper_simulation_projection.png`](../figures/fig5b_caliper_simulation_projection.png)). As shown in Table 5c, simulated throughput closely tracks historical empirical measurements in the linear regime, while revealing the theoretical limitations of a fluid model under extreme over-saturation:

| Workload Condition | Historical Throughput (TPS) | Simulated Median (TPS) | Throughput Residual | Historical Avg Latency (s) | Simulated Latency (s) | Latency Residual |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Write: 50 TPS | 50.3 | **49.99** | -0.31 (-0.62%) | 0.10 | **0.133** | +0.033s |
| Write: 100 TPS | 100.2 | **99.98** | -0.22 (-0.22%) | 0.06 | **0.084** | +0.024s |
| Write: 200 TPS | 199.9 | **199.96** | +0.06 (+0.03%) | 0.04 | **0.060** | +0.020s |
| Write: 350 TPS (Knee) | — | **349.40** | — | — | **0.065** | — |
| Write: 1,000 TPS (Stress)| 350.1 | **351.53** | +1.43 (+0.41%) | 18.00 | **9.268** | **-8.732s (-48.5%)** |
| Read: 100 TPS | — | **100.00** | — | — | **0.002** | — |
| Read: 250 TPS | — | **250.00** | — | — | **0.002** | — |
| Read: 500 TPS | 500.3 | **500.00** | -0.30 (-0.06%) | 0.00 (2-dec) | **0.002** | +0.002s |

*Critical Residual and Modeling Boundaries Analysis:*
1. **Linear Regime Goodness-of-Fit:** For offered rates between $50$ and $200$ TPS, simulated throughput tracks historical points within $\pm 0.6\%$, with latency residuals bounded within $+0.033$s.
2. **Stress Latency Underestimation (-8.73s Residual):** For the 1,000 TPS write stress round, the historical benchmark recorded an average latency of **$18.00$ seconds** (max $21.14$s). The fluid queueing model calculates an average latency of **$9.268$ seconds** strictly over the nominal $10$-second submission window ($T_{\text{submit}} = 10,000 / 1,000 = 10$s). This large residual occurs because the fluid model calculates queue delay strictly during active transaction arrivals, whereas in physical Fabric execution, Raft ordering backpressure and serial peer CouchDB commit queuing caused transactions to linger until the entire $10,000$-transaction backlog drained ($28.56$s total run duration).
3. **Out-of-Calibration Empirical Observation (Live Rerun):** In the live isolated rerun (`20261018-010200`), achieved write throughput reached **$515.8$ TPS** (at $615.7$ TPS send rate) with **$6.98$ seconds** average latency. The simulation model ($\mu_w = 350.1$ TPS) does NOT predict $515.8$ TPS because it was calibrated to the historical baseline; the live rerun represents an independent empirical observation under different container runtime and client dispatch conditions.
4. **Sensitivity Envelopes vs. Empirical Confidence Intervals:** The P5–P95 range across 100 synthetic seeds reflects parameter sensitivity to stochastic arrival and consensus jitter; it does not substitute for empirical confidence intervals from repeated physical hardware runs.

### 5.4. Analysis of Performance Regimes and Saturation Dynamics (RQ1 & RQ2)
Both empirical runs (visualized in [`fig5_blockchain_benchmarks.png`](../figures/fig5_blockchain_benchmarks.png)) and the queueing model reveal three distinct operational regimes:

1. **Linear Throughput Regime ($0 \to 200$ TPS):**
   For all write transactions submitted up to $200$ TPS, committed throughput tracks the offered rate perfectly ($1:1$ ratio). End-to-end confirmation latency remains tightly bounded between $0.03$s and $0.10$s. Because transactions arrive faster than the 2-second `BatchTimeout`, the orderer cuts blocks primarily based on transaction count (`MaxMessageCount = 10`, verified in `configtx.yaml`), ensuring rapid block formation and sub-tenth-second confirmation.
2. **Cross-Function Write Invariance:**
   At the standard operating point of $200$ TPS, write throughput is virtually identical across diverse business operations: `createPatientRecord` ($199.9$–$200.2$ TPS, $0.03$–$0.04$s), `updateHealthScore` ($200.0$–$200.1$ TPS, $0.03$–$0.06$s), `createPrescription` ($200.0$–$200.2$ TPS, $0.03$–$0.05$s), and `requestScan` ($200.0$–$200.2$ TPS, $0.03$–$0.04$s). This confirms that transaction confirmation time is dominated by Raft ordering and peer block validation rather than chaincode execution complexity.
3. **Empirical Saturation Dynamics and Queueing Delay Under Stress Load:**
   We report four distinct empirical observations under nominal 1,000 TPS target load, reflecting different client worker concurrency levels and container runtime environments:
   - *Historical Baseline (commit `944fb0d`):* Single-client Caliper load generation achieved an actual send rate of **$963.6$ TPS**, observing network saturation at **$350.1$ TPS** committed write throughput with an average confirmation latency of **$18.00$ seconds** (max $21.14$s). This serves as a historical baseline rather than a universal capacity ceiling.
   - *5-Worker Isolated Deployment (`20261018-010200`):* Caliper achieved an actual send rate of **$615.7$ TPS**, reaching **$515.8$ TPS** committed throughput with an average confirmation latency of **$6.98$ seconds** (max $11.18$s).
   - *8-Worker Initial Stress Investigation (`20261018-205500_stress_investigation`):* Three independent 1,000 TPS write repetitions sustained **$416.80 \pm 17.04$ TPS** committed throughput at an actual send rate of **$782.23 \pm 74.20$ TPS** with **$7.04 \pm 0.53$ seconds** average confirmation latency ($N=3$, sample standard deviation with $\text{ddof}=1$; individual throughputs: $424.3$, $428.8$, $397.3$ TPS).
   - *8-Worker Corrected Stress Investigation (`20261018-230500_stress_investigation`):* Three independent 1,000 TPS write repetitions sustained **$485.27 \pm 14.60$ TPS** committed throughput at an actual send rate of **$742.70 \pm 62.62$ TPS** with **$5.36 \pm 0.22$ seconds** average latency ($N=3$, $\text{ddof}=1$; individual throughputs: $470.6$, $499.8$, $485.4$ TPS).
   Continuous container telemetry recorded during the 8-worker run revealed that the Caliper runner container peaked at $375.5\%$ CPU utilization (~4 full CPU cores), indicating that the send rate shortfall below 1,000 TPS is primarily a client-side workload-generation bottleneck. Crucially, across all empirical runs, zero transactions were aborted or dropped ($0.00\%$ failure rate), demonstrating high protocol resilience under peak stress. All requests were submitted under administrative identity `HospitalOrgAdmin`.
4. **Decoupled Read Query Scalability ($500.3$ – $500.6$ TPS):**
   In contrast to consensus-backed writes, read-only queries (`getPatientRecord`) scale effortlessly across 100, 250, and 500 TPS to **$500.3$ – $500.6$ TPS** with sub-hundredth-second latency ($\le 0.01$s displayed average, rounded to $0.00$s or $0.01$s within Caliper's 2-decimal display precision, with maximum latency bounded between $0.04$s and $0.13$s). Because read queries evaluate local CouchDB state and bypass Raft ordering, block cutting, and multi-peer gossip endorsement, query capacity is decoupled from consensus bottlenecks. An earlier round in run `20261018-205500` was misconfigured with action-only arguments and defaulted to write transactions; this was formally documented and invalidated as read evidence via `ERRATUM.md`, with verified read metrics established in runs `20261018-010200` and `20261018-230500`.

### 5.5. Chaincode Throughput vs. End-to-End Application Throughput
A critical scientific distinction must be maintained: **Hyperledger Caliper measures smart contract transaction throughput at the Fabric Gateway level, NOT full end-to-end application throughput.**

In production operation, a user request flows through:
$$\text{Client HTTP} \xrightarrow{\text{TLS / Network}} \text{Node.js API} \xrightarrow{\text{Auth / RBAC}} \text{Python Subprocess (ML Inference)} \xrightarrow{\text{IPC}} \text{Fabric SDK} \xrightarrow{\text{gRPC}} \text{Peer / Orderer}$$

While the Fabric chaincode sustains $350$–$515$ write TPS, the Python ML inference engine (`run_engine.py`) takes approximately $40$–$50$ ms to load models, engineer features, predict expenditure, and simulate loss. Analytically, a single Node.js worker process synchronously executing full end-to-end inference and ledger submission is bounded to an estimated:
$$\text{Capacity}_{\text{single-worker}} \approx \frac{1.0}{0.045\text{s}} \approx 20\text{–}25\text{ requests per second}$$

This numerical range represents an **analytical single-worker latency estimate** derived from Python subprocess execution time, rather than an empirical multi-client stress measurement. To achieve the full $200$–$350$ TPS capacity of the blockchain in production, the application must decouple inference from ledger writing via asynchronous message queues (e.g., RabbitMQ or Redis Streams).

---

## 6. ACG-Inspired Chronic-Condition Feature Engineering and ML Evaluation

### 6.1. Feature Definitions and Input Availability Parity
HealthScore maps patient clinical indicators into 11 observable features adhering strictly to **Input Availability Parity**:

$$\begin{aligned}
\text{Cardio\_ACG} &= \text{HIBPDX} + \text{CHDDX} + \text{MIDX} + \text{STRKDX} \quad (\text{Range: } 0–4) \\
\text{Metabolic\_ACG} &= \text{DIABDX\_M18} + \text{CHOLDX} \quad (\text{Range: } 0–2) \\
\text{Respiratory\_ACG} &= \text{ASTHDX} + \text{EMPHDX} + \text{CHBRON31} \quad (\text{Range: } 0–3) \\
\text{Oncology\_ACG} &= \text{CANCERDX} \quad (\text{Range: } 0–1) \\
\text{Musculoskeletal\_ACG} &= \text{ARTHDX} + \text{JTPAIN31\_M18} \quad (\text{Range: } 0–2) \\
\text{Psychiatric\_ACG} &= (\text{ADDPRS42} \in [1,2,3]) + \text{ADHDADDX} \quad (\text{Range: } 0–2) \\
\text{Comorbidity\_Count} &= \sum_{c=1}^6 \mathbb{I}(\text{Cluster}_c > 0) \quad (\text{Range: } 0–6) \\
\text{Multimorbidity\_Penalty} &= (\text{Comorbidity\_Count})^2 \quad (\text{Range: } 0–36) \\
\text{Age\_x\_Comorbidity} &= \min(\text{Age}, 85) \times \text{Comorbidity\_Count} \quad (\text{Range: } 0–510)
\end{aligned}$$

*Clinical Intake Parity Note:* In the live application, patient conditions are mapped via standardized intake (`parse_structured_clinical_conditions`). Absence of condition mentions is encoded as an uninformative zero default; this represents unobserved baseline status, NOT confirmed clinical wellness.

### 6.2. Controlled Feature Ablation Study (RQ3)
To evaluate the isolated incremental contribution of each architectural component, we executed 17 controlled ablation experiments on the held-out MEPS test partition ($N=3,755$). All models were refit on training data under identical hyperparameters (Tweedie GLM with power $p=1.5, \alpha=1.0$; Logistic Regression on Target 2 survey-weighted P90 with normalized sampling weights):

| Ablation Model Specification | Feature Count | Features Included | Dollar $R^2$ | $\Delta R^2$ vs. Ref | Weighted BSS | $\Delta$ BSS vs. Ref | ROC-AUC |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **Full Observable Reference** | **11** | All 11 Observable Features | **0.0798** | **0.0000** | **+0.1025** | **0.0000** | **0.7654** |
| Demographics Only | 2 | `AGE23X`, `Gender_Male` | 0.0395 | -0.0403 | +0.0506 | -0.0519 | 0.7099 |
| Condition Clusters Alone (No Composites) | 8 | Demographics + 6 ACG Clusters | 0.0771 | -0.0027 | +0.1005 | -0.0020 | 0.7640 |
| Clusters + Comorbidity Count | 9 | Demographics + 6 Clusters + Count | 0.0787 | -0.0011 | +0.1004 | -0.0021 | 0.7641 |
| Clusters + Multimorbidity Penalty | 9 | Demographics + 6 Clusters + $\text{Count}^2$ | 0.0769 | -0.0029 | +0.1017 | -0.0008 | 0.7648 |
| Clusters + Age $\times$ Comorbidity | 9 | Demographics + 6 Clusters + Age $\times$ Count | 0.0766 | -0.0032 | +0.1007 | -0.0018 | 0.7643 |
| Without Multimorbidity Penalty | 10 | 11 Features minus $\text{Count}^2$ | 0.0783 | -0.0015 | +0.1009 | -0.0016 | 0.7649 |
| Without Age $\times$ Comorbidity | 10 | 11 Features minus Age $\times$ Count | **0.0804** | **+0.0006** | **+0.1027** | **+0.0001** | **0.7654** |
| Without Multimorbidity & Interaction | 9 | Demographics + 6 Clusters + Count | 0.0787 | -0.0011 | +0.1004 | -0.0021 | 0.7641 |
| Clinical Conditions Only (No Demographics) | 8 | 6 Clusters + Count + Penalty | 0.0791 | -0.0007 | +0.0996 | -0.0029 | 0.7619 |
| Without Cardiovascular | 10 | 11 Features minus `Cardio_ACG` | 0.0785 | -0.0013 | +0.0970 | -0.0056 | 0.7634 |
| Without Metabolic | 10 | 11 Features minus `Metabolic_ACG` | 0.0792 | -0.0006 | +0.0957 | -0.0069 | 0.7628 |
| Without Respiratory | 10 | 11 Features minus `Respiratory_ACG` | 0.0764 | -0.0035 | +0.0979 | -0.0046 | 0.7635 |
| Without Oncology | 10 | 11 Features minus `Oncology_ACG` | 0.0788 | -0.0010 | +0.0969 | -0.0056 | 0.7645 |
| Without Musculoskeletal | 10 | 11 Features minus `Musculoskeletal_ACG`| 0.0802 | +0.0004 | +0.1012 | -0.0013 | 0.7651 |
| Without Psychiatric Condition | 10 | 11 Features minus `Psychiatric_ACG` | 0.0774 | -0.0024 | +0.1026 | +0.0001 | 0.7653 |
| **Oracle 14 Features (Upper Bound)** | **14** | Observable + SAQ Survey Variables | **0.0927** | **+0.0129** | **+0.1314** | **+0.0289** | **0.7904** |

### Key Scientific Findings from the Ablation Experiments:
1. **Primary Explanatory Lift from Chronic Clusters:** Moving from demographics alone to the 6 chronic-condition clusters provides a massive predictive leap: dollar $R^2$ nearly doubles from $0.0395$ to $0.0771$ ($\Delta R^2 = +0.0376$), and weighted BSS jumps from $+0.0506$ to $+0.1005$ ($\Delta \text{BSS} = +0.0499$).
2. **Modest Incremental Value of Interaction Composites:** While tree-based SHAP attributions assign $39.0\%$ of model importance to `Age_x_Comorbidity`, linear regression ablation demonstrates that composite terms provide modest incremental variance explanation ($\Delta R^2 = +0.0027$ between 8-feature clusters alone and the 11-feature full design). In fact, removing `Age_x_Comorbidity` yields $R^2 = 0.0804$, showing that collinearity between age, count, and interaction absorbs variance without improving generalized linear fit.
3. **Clinical Cluster Sensitivity:** `Respiratory_ACG` accounts for the largest individual condition drop ($\Delta R^2 = -0.0035$), reflecting high hospitalization and prescription costs associated with chronic respiratory illness.

### 6.3. External Cross-Year (HC-256) and Prospective (HC-257) Validation
- **HC-256 Cross-Year Transfer ($N = 18,979$):** Evaluated on the 2024 calendar-year survey, the frozen 11-feature Weighted Classifier achieved an unweighted ROC-AUC of **0.7828** (PR-AUC $= 0.3229$) with Weighted BSS of **+0.1266** and calibration slope of **1.0554**. Tweedie GLM tracked the rising population mean ($$9,266.75$ observed) with a predicted mean of **$8,473.71**.
- **HC-257 Prospective Forecasting ($N = 8,708$ Panel 28 Cohort):** Predicting Year 2 expenditure (`TOTEXPY2`) from Year 1 baseline predictors, the classifier achieved prospective ROC-AUC of **0.7807** (Adult SAQ subcohort: **0.7466**, BSS $= +0.1212$).
- **The Econometric Persistence Principle:** Predicting Year 2 spending directly from Year 1 lagged spending (`TOTEXPY1`) achieved an $R^2$ of **0.1204** (MAE: $\$8,625.76$), significantly outperforming the diagnosis-based Tweedie model ($R^2 = 0.0652$). This highlights the fundamental econometric principle that historical consumption patterns dominate cross-sectional diagnosis flags.

---

## 7. Configurable Loss and Premium Simulation (RQ4)

### 7.1. Mathematical Formulation
In HealthScore, the output labeled `premium` is formalized as an exploratory parametric Value-at-Risk (VaR) simulation rather than an actuarially certified quote:
$$X_\alpha = B + (1 + \alpha) G$$
where:
- $B \ge 0$ is the configurable base-cost floor in USD (default: $\$500.00$), representing administrative baseline overhead.
- $G \sim \text{Gamma}(k, \theta)$ with shape $k = 1.5$ and scale $\theta = \hat{y} / 1.5$, ensuring $E[G] = k\theta = \hat{y}$ (the Tweedie model-predicted expenditure).
- $\alpha \ge 0$ is a dimensionless **risk-loading parameter** (default: $\alpha = 0.0$).
- Target simulated premium is defined as the 95th percentile loss: $\text{Premium} = \text{Percentile}_{95}(X_\alpha)$.

Under this definition, setting $\alpha = 0.0$ strictly reproduces the un-loaded baseline ($X_0 = B + G$). Increasing $\alpha$ scales the synthetic loss component, representing a more conservative risk-loaded pricing scenario.

### 7.2. Systematic Sensitivity Analysis Across 60 Scenarios
We executed a complete grid sensitivity analysis across 4 base-cost scenarios ($B \in \{0, 250, 500, 1000\}$), 5 risk-loading levels ($\alpha \in \{0.0, 0.10, 0.25, 0.50, 1.00\}$), and 3 expenditure tiers ($y \in \{\$1,500, \$5,000, \$15,000\}$) using Common Random Numbers (CRN) with $N = 20,000$ draws per scenario (visualized in [`fig6_premium_sensitivity.png`](../figures/fig6_premium_sensitivity.png)):

| Expenditure Tier | Base Floor $B$ | Risk-Loading $\alpha$ | Simulated P5 ($) | Simulated P50 ($) | Simulated P95 Target Premium ($) | Analytical Gamma P95 ($) | Approximation Error | Premium Uplift vs. Baseline |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Moderate ($5,000) | $0.00 | 0.00 | $727.60 | $4,007.41 | **$13,116.94** | $13,024.55 | +0.709% | Baseline ($0.00) |
| Moderate ($5,000) | $0.00 | 0.10 | $800.36 | $4,408.15 | **$14,428.63** | $14,327.00 | +0.709% | +$1,311.69 (+10.00%) |
| Moderate ($5,000) | $0.00 | 0.25 | $909.50 | $5,009.26 | **$16,396.17** | $16,280.68 | +0.709% | +$3,279.23 (+25.00%) |
| Moderate ($5,000) | $0.00 | 0.50 | $1,091.40 | $6,011.11 | **$19,675.41** | $19,536.82 | +0.709% | +$6,558.47 (+50.00%) |
| Moderate ($5,000) | $0.00 | 1.00 | $1,455.20 | $8,014.81 | **$26,233.88** | $26,049.09 | +0.709% | +$13,116.94 (+100.00%) |
| Moderate ($5,000) | $500.00 | 0.00 | $1,227.60 | $4,507.41 | **$13,616.94** | $13,524.55 | +0.683% | Baseline ($0.00) |
| Moderate ($5,000) | $500.00 | 0.10 | $1,300.36 | $4,908.15 | **$14,928.63** | $14,827.00 | +0.685% | +$1,311.69 (+9.63%) |
| Moderate ($5,000) | $500.00 | 0.25 | $1,409.50 | $5,509.26 | **$16,896.17** | $16,780.68 | +0.688% | +$3,279.23 (+24.08%) |
| Moderate ($5,000) | $500.00 | 0.50 | $1,591.40 | $6,511.11 | **$20,175.41** | $20,036.82 | +0.692% | +$6,558.47 (+48.16%) |
| Moderate ($5,000) | $500.00 | 1.00 | $1,955.20 | $8,514.81 | **$26,733.88** | $26,549.09 | +0.696% | +$13,116.94 (+96.33%) |

### Analytical Verification:
For any quantile $q \in (0, 1)$, the theoretical Value-at-Risk under our formulation is:
$$Q_{X_\alpha}(q) = B + (1 + \alpha) Q_G(q) = B + (1 + \alpha) \cdot \text{Gamma}^{-1}(q; k=1.5, \theta=\hat{y}/1.5)$$
As demonstrated in the table, empirical Monte Carlo simulation at $N = 20,000$ tracks closed-form analytical quantiles within **$0.68\%$ to $0.71\%$** error across all scenarios, verifying both mathematical rigor and numerical stability.

---

## 8. Integrated Discussion: Performance, Practical Use, and Trade-Offs

### 8.1. Consortium Throughput in Healthcare Operations
Our findings provide concrete guidance for deploying permissioned blockchains in healthcare consortia:
- **Operating Capacity:** With linear throughput up to $200$ write TPS and saturation at $350$ write TPS, a 5-organization Fabric network comfortably supports regional and national transaction rates. For example, a major metropolitan health network processing 500,000 clinical encounters per day generates an average load of $\approx 6$–$10$ TPS, peaking at $\approx 50$–$75$ TPS during peak operating hours—well within HealthScore's sub-100ms operating window.
- **Queueing Latency Trade-Off:** Systems engineers must not configure offered load beyond the $350$ TPS knee. While no transactions fail at $1,000$ TPS, confirmation latency increases 180-fold (from $0.10$s to $18.00$s). Production implementations must employ rate limiters and backpressure buffers to maintain operation within the sub-second linear zone.

### 8.2. Ledger Growth and State Pruning
Because Fabric maintains append-only block files, transaction history grows monotonically. At 200 TPS continuous load with $\approx 1.5$ KB per transaction, the ledger expands by $\approx 1.08$ GB per hour. However, read queries execute against CouchDB world state, whose size is bounded by the active patient population ($O(N_{\text{patients}})$) rather than cumulative transaction history ($O(N_{\text{transactions}})$).

---

## 9. Limitations and Threats to Validity

1. **Iterative Benchmark Split:** The HC-251 held-out test partition ($N=3,755$) was utilized during iterative development; it constitutes an established benchmark test set rather than fresh confirmatory data.
2. **Panel 28 Longitudinal Cohort Overlap:** MEPS HC-251 and HC-257 are not independent cohorts. HC-251 contains Panel 28 baseline records, whereas HC-257 tracks these same individuals across 2023–2024. This evaluation evaluates longitudinal within-subject stability, not out-of-sample population transfer.
3. **Survey Variance Bounds:** Reported $95\%$ confidence intervals derive from non-parametric bootstrap resampling ($B=200$). They do not incorporate complex survey design variables (strata and primary sampling units) through Taylor series linearization.
4. **Input Availability Parity vs. Clinical Diagnosis Validation:** While the 11-feature model achieves software-level parity with intake forms, regex-based parsing is a heuristic intake proxy, not an official clinical diagnostic classification grouper.
5. **Exploratory Loss Simulation Status:** The Monte Carlo premium calculation is strictly a parametric Value-at-Risk demonstration. It is not actuarially certified and does not account for statutory capital reserves, reinsurance, or Affordable Care Act (ACA) Medical Loss Ratio (MLR) mandates.
6. **Benchmark Environment Scope and Evidence Separation:** To maintain strict scientific integrity, historical empirical measurements (commit `944fb0d`, 8 rounds, 24,500 txs) are preserved byte-for-byte in `caliper-benchmark/report.html`. Live isolated re-execution verified the expanded 11-round matrix ($31,500$ txs) with zero failures under identical chaincode and Raft consensus. Workload measurements reflect single-identity client submission through `HospitalOrgAdmin` rather than a concurrent 5-organization client pool. Synthetic projections (`simulate_benchmark.py`) provide exploratory capacity models and are strictly separated from empirical Caliper telemetry.

---

## 10. Conclusion

This paper presented an empirical evaluation of **HealthScore**, unifying a 5-organization permissioned Hyperledger Fabric blockchain consortium with an ACG-inspired multi-disease risk engine and configurable premium simulation. Our benchmarks demonstrate that Hyperledger Fabric achieves production-grade scalability: sustaining $200$ write TPS with sub-$100$ms latency, saturating at $350.1$ TPS with zero transaction failures, and serving read queries at $500.3$ TPS with low query latency ($\le 0.01$s displayed average, maximum $0.04$s historical / $0.13$s live). Controlled feature ablations confirm that custom ACG-inspired condition clusters deliver the dominant predictive gain in healthcare expenditure modeling, while composite interaction terms provide modest incremental variance explanation. Finally, we establish an explicit, analytically verified Value-at-Risk premium simulation, demonstrating mathematical transparency and reproducibility across all operational layers.

---

## References

1. Agency for Healthcare Research and Quality (AHRQ). *Medical Expenditure Panel Survey (MEPS) HC-251, HC-256, and HC-257 Public Use Data Files*. U.S. Department of Health and Human Services, 2023–2026.
2. Androulaki, E., Barger, A., Bortnikov, V., Cachin, C., Christidis, K., De Caro, A., Enyeart, D., Ferris, C., Laventman, G., Manevich, Y., et al. *Hyperledger Fabric: a distributed operating system for permissioned blockchains*. In *Proceedings of the Thirteenth EuroSys Conference*, pp. 1–15, 2018. DOI: 10.1145/3190508.3190538.
3. Hyperledger Foundation. *Hyperledger Caliper: A blockchain benchmark framework*. Linux Foundation Project Documentation, 2022–2026. URL: https://hyperledger.github.io/caliper/.
4. Ellis, R. P., & Ash, A. S. *Refinements to the Diagnostic Cost Group (DCG) model*. *Inquiry*, 32(4), pp. 418–429, 1995.
5. Weiner, J. P., Starfield, B. H., Steinwachs, D. M., & Mumford, L. M. *Development and application of a population-oriented measure of ambulatory care morbidity: The Johns Hopkins ACG Case-Mix System*. *Medical Care*, 29(5), pp. 452–472, 1991.
6. Tweedie, M. C. K. *An index which distinguishes between some important exponential families*. In *Statistics: Applications and New Directions*, Proceedings of the Indian Statistical Institute Golden Jubilee International Conference, pp. 579–604, 1984.
7. Lundberg, S. M., & Lee, S. I. *A unified approach to interpreting model predictions*. In *Advances in Neural Information Processing Systems (NeurIPS)*, 30, pp. 4765–4774, 2017.
8. Steyerberg, E. W., Vickers, A. J., Cook, N. R., Gerds, T., Gonen, M., Obuchowski, N., Pencina, M. J., & Kattan, M. W. *Assessing the performance of prediction models: a framework for traditional and novel measures*. *Epidemiology*, 21(1), pp. 128–138, 2010.
9. Brier, G. W. *Verification of forecasts expressed in terms of probability*. *Monthly Weather Review*, 78(1), pp. 1–3, 1950.
10. Centers for Medicare & Medicaid Services (CMS). *Report to Congress: Risk Adjustment in Medicare Advantage*. U.S. Department of Health and Human Services, 2024.
