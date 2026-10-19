# ERRATUM: Benchmark Run 20261018-205500_stress_investigation

**Date Recorded:** 2026-10-18  
**Run ID:** `20261018-205500_stress_investigation`  
**Status:** Historical execution output preserved byte-for-byte; Round 7 invalidated as read-query performance evidence.

---

## 1. Description of Semantic Configuration Defect

In benchmark configuration `benchmark_expanded.yaml` for run `20261018-205500_stress_investigation`, Round 7 (`getPatientRecord-500-tps`) specified workload arguments as:

```yaml
workload:
  module: workload.js
  arguments:
    action: getPatientRecord
```

However, `caliper-benchmark/workload.js` inspected `this.roundArguments.targetFunction`:

```javascript
this.targetFunction = this.roundArguments.targetFunction || 'createPatientRecord';
```

Because `targetFunction` was not provided in `arguments` (and `action` was not an inspected field), the workload defaulted to `this.targetFunction = 'createPatientRecord'`.

## 2. Consequences of the Defect

1. **Incorrect Transaction Type:** Rather than evaluating read-only queries against local CouchDB peer state, Round 7 submitted 2,496 `createPatientRecord` transaction proposals to the endorsement and Raft ordering pipeline.
2. **Read-Only Flag Not Set:** `txArgs.readOnly = true` was never asserted for this round.
3. **Invalidation of Read Metrics:** The reported metrics for Round 7:
   - Committed Throughput: **349.5 TPS**
   - Average Latency: **3.01 seconds**
   - Minimum Latency: **1.01 seconds**
   - Maximum Latency: **4.25 seconds**
   **MUST NOT** be reported or interpreted as read-query performance. They represent consensus write performance under an offered load of 494.8 TPS.
4. **Invalidation Status:** Round 7 of this run is **INVALID** as read-query evidence.

## 3. Validity of Write Stress Repetitions

Rounds 1 through 6 in this run were intended as `createPatientRecord` write transactions. Because `targetFunction` defaulted to `'createPatientRecord'`, these rounds executed the intended write chaincode function.

Specifically, the three 1,000 TPS over-saturation write repetitions (Rounds 4, 5, 6) executed valid write transactions:
- **Repetition 1:** Send Rate 707.9 TPS, Throughput 424.3 TPS, Avg Latency 6.69 s, Max Latency 8.75 s
- **Repetition 2:** Send Rate 856.3 TPS, Throughput 428.8 TPS, Avg Latency 6.78 s, Max Latency 8.43 s
- **Repetition 3:** Send Rate 782.5 TPS, Throughput 397.3 TPS, Avg Latency 7.65 s, Max Latency 9.81 s

**Sample Statistics ($ddof=1$ across $N=3$ independent repetitions):**
- Actual Send Rate: $782.23 \pm 74.20$ TPS
- Committed Throughput: $416.80 \pm 17.01$ TPS
- Average Latency: $7.04 \pm 0.53$ s
- Maximum Latency: $9.00 \pm 0.72$ s

## 4. Preservation and Corrective Action

In accordance with strict scientific integrity principles:
1. No raw benchmark measurement outputs in this directory (`report.html`, `live_benchmark_results.json`, `live_benchmark_results.csv`, `benchmark_expanded.yaml`, `console.log`) have been altered.
2. `workload.js` and `verify_benchmark_artifacts.py` have been patched to require explicit `targetFunction`, reject `action`-only arguments, and validate label-operation consistency.
3. A fully corrected benchmark run with explicit `targetFunction: getPatientRecord` and ledger pre-seeding (`preSeedCount: 50`) has been executed in a separate timestamped run directory.

## 5. Transaction Accounting: Configured vs. Submitted Allocation

The benchmark configuration (`benchmark_expanded.yaml`) defined 7 rounds specifying a nominal total of **25,500** configured round transactions. Because Hyperledger Caliper distributes transactions across $W=8$ workers using integer division ($\lfloor \text{txNumber} / W \rfloor \times W$), rounds with non-divisible transaction targets experienced an allocation shortfall:
- Round 1 (`createPatientRecord-350-tps`): $1,750$ configured $\to 1,744$ submitted ($\lfloor 1750 / 8 \rfloor \times 8 = 218 \times 8 = 1,744$; shortfall: $6$)
- Round 2 (`createPatientRecord-500-tps`): $2,500$ configured $\to 2,496$ submitted ($\lfloor 2500 / 8 \rfloor \times 8 = 312 \times 8 = 2,496$; shortfall: $4$)
- Round 3 (`createPatientRecord-750-tps`): $3,750$ configured $\to 3,744$ submitted ($\lfloor 3750 / 8 \rfloor \times 8 = 468 \times 8 = 3,744$; shortfall: $6$)
- Round 4 (`createPatientRecord-1000-tps-rep1`): $5,000$ configured $\to 5,000$ submitted ($\lfloor 5000 / 8 \rfloor \times 8 = 625 \times 8 = 5,000$; shortfall: $0$)
- Round 5 (`createPatientRecord-1000-tps-rep2`): $5,000$ configured $\to 5,000$ submitted ($\lfloor 5000 / 8 \rfloor \times 8 = 625 \times 8 = 5,000$; shortfall: $0$)
- Round 6 (`createPatientRecord-1000-tps-rep3`): $5,000$ configured $\to 5,000$ submitted ($\lfloor 5000 / 8 \rfloor \times 8 = 625 \times 8 = 5,000$; shortfall: $0$)
- Round 7 (`getPatientRecord-500-tps`): $2,500$ configured $\to 2,496$ submitted ($\lfloor 2500 / 8 \rfloor \times 8 = 312 \times 8 = 2,496$; shortfall: $4$)

**Summary Accounting:**
- **Configured Benchmark-Round Transactions:** $25,500$
- **Submitted / Recorded Benchmark-Round Transactions:** $25,480$
- **Worker Allocation Shortfall:** $20$ unsubmitted proposals ($0.078\%$)
- **Reported Failures Among Submitted Transactions:** $0$ ($0.00\%$ failure rate among submitted)
- **Pre-seeding Setup Writes:** $0$
- **Total Testbed Workload Requests Processed:** $25,480$
