'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

const NAMES = ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank', 'Grace', 'Heidi', 'Ivan', 'Judy'];
const PRIORITIES = ['Routine', 'Urgent', 'STAT (Immediate)'];
const SCAN_TYPES = ['MRI Scan', 'CT Scan', 'X-Ray', 'Blood Test'];

/**
 * Deterministic pseudo-random number generator (Mulberry32)
 * Ensures reproducible workload arguments without Math.random().
 *
 * @param {number} seed 32-bit unsigned integer seed
 * @returns {function(): number} PRNG returning floats in [0, 1)
 */
function createMulberry32(seed) {
    let s = (seed >>> 0) || 1337;
    return function() {
        s = (s + 0x6D2B79F5) | 0;
        let t = Math.imul(s ^ (s >>> 15), 1 | s);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

/**
 * Workload module for the HealthScore smart contract.
 * Hardened for deterministic input generation, robust pre-seeding,
 * non-colliding run IDs, explicit error accounting, and invoker configurability.
 */
class HealthScoreWorkload extends WorkloadModuleBase {
    constructor() {
        super();
        this.txIndex = 0;
        this.preSeededPatientIds = [];
        this.seedIndex = 0;
        this.setupFailures = 0;
    }

    /**
     * Initialize the workload module.
     * @param {number} workerIndex The 0-based index of the worker.
     * @param {number} totalWorkers The total number of workers.
     * @param {number} roundIndex The 0-based index of the round.
     * @param {Object} roundArguments The round arguments provided in the benchmark config.
     * @param {Object} sutAdapter The adapter to the SUT.
     * @param {Object} sutContext The SUT-specific context.
     */
    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
        await super.initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext);

        if (!this.roundArguments || !this.roundArguments.targetFunction) {
            throw new Error(
                `[Worker ${workerIndex}] Missing required argument 'targetFunction'. ` +
                `Benchmark round configurations must specify 'targetFunction' explicitly to prevent silent fallback to write transactions.`
            );
        }
        if (this.roundArguments.action) {
            throw new Error(
                `[Worker ${workerIndex}] Invalid argument 'action' provided in roundArguments. ` +
                `Use 'targetFunction' explicitly instead of 'action'.`
            );
        }

        this.targetFunction = this.roundArguments.targetFunction;
        this.chaincodeId = this.roundArguments.chaincodeId || 'healthscore';
        this.invokerIdentity = this.roundArguments.invokerIdentity || 'HospitalOrgAdmin';

        console.log(`  [Worker ${workerIndex}] Initialized round with targetFunction='${this.targetFunction}', chaincode='${this.chaincodeId}', invoker='${this.invokerIdentity}'`);

        // Deterministic PRNG seeded per worker and round
        const baseSeed = (this.roundArguments.seed || 104729) + (workerIndex * 7919) + (roundIndex * 997);
        this.prng = createMulberry32(baseSeed);

        // Run prefix ensures monotonic uniqueness across consecutive runs and workers without key collisions
        const customPrefix = this.roundArguments.runPrefix ? `${this.roundArguments.runPrefix}_` : '';
        this.runPrefix = `${customPrefix}R${roundIndex}_W${workerIndex}`;

        // Functions requiring pre-existing ledger records
        const needsPreSeeding = ['updateHealthScore', 'getPatientRecord', 'getAllPrescriptions', 'getAllScanOrders'];

        if (needsPreSeeding.includes(this.targetFunction)) {
            const seedCount = this.roundArguments.preSeedCount !== undefined ? this.roundArguments.preSeedCount : 200;
            if (seedCount <= 0) {
                throw new Error(
                    `[Worker ${workerIndex}] Invalid preSeedCount: ${seedCount} for targetFunction '${this.targetFunction}'. ` +
                    `Read and update rounds require preSeedCount > 0 to populate ledger records.`
                );
            }
            console.log(`  [Worker ${workerIndex}] Pre-seeding ${seedCount} patient records for '${this.targetFunction}' (Invoker: ${this.invokerIdentity})...`);

            for (let i = 0; i < seedCount; i++) {
                const patientId = `SEED_${this.runPrefix}_${this.targetFunction}_${i}`;
                const name = NAMES[i % NAMES.length];
                const age = (Math.floor(this.prng() * 70) + 18).toString();
                const weight = (Math.floor(this.prng() * 50) + 50).toString();
                const height = (Math.floor(this.prng() * 40) + 150).toString();
                const history = 'Pre-seeded patient record for benchmark evaluation';

                const txArgs = {
                    contractId: this.chaincodeId,
                    contractFunction: 'createPatientRecord',
                    invokerIdentity: this.invokerIdentity,
                    contractArguments: [patientId, name, age, weight, height, history],
                };

                try {
                    await this.sutAdapter.sendRequests(txArgs);
                    this.preSeededPatientIds.push(patientId);
                } catch (e) {
                    const errorString = String(e && (e.message || e.stack || e));
                    if (errorString.includes('already exists')) {
                        // Idempotent re-run: record already committed in previous test round
                        this.preSeededPatientIds.push(patientId);
                    } else {
                        this.setupFailures++;
                        console.error(`  [Worker ${workerIndex}] Pre-seeding failed for ${patientId}: ${errorString}`);
                    }
                }
            }

            if (this.preSeededPatientIds.length === 0) {
                throw new Error(
                    `[Worker ${workerIndex}] Pre-seeding failed completely for '${this.targetFunction}'. ` +
                    `Setup failures: ${this.setupFailures}, Seeded records: 0. Halting round to prevent invalid transaction submissions.`
                );
            }

            console.log(`  [Worker ${workerIndex}] Successfully prepared ${this.preSeededPatientIds.length} seeded records (${this.setupFailures} setup failures).`);
        }
    }

    /**
     * Pick a pre-seeded patient ID sequentially across worker transactions to avoid concurrent MVCC write conflicts.
     * @returns {string} Pre-seeded patient ID
     */
    _getPreSeededPatientId() {
        if (this.preSeededPatientIds.length === 0) {
            throw new Error(`[Worker ${this.workerIndex}] Attempted to access pre-seeded record for '${this.targetFunction}', but no seeded records exist.`);
        }
        const id = this.preSeededPatientIds[this.seedIndex];
        this.seedIndex = (this.seedIndex + 1) % this.preSeededPatientIds.length;
        return id;
    }

    /**
     * Assemble and submit a single benchmark transaction.
     * Guarantees deterministic values, valid schema arguments, and unique keys.
     */
    async submitTransaction() {
        this.txIndex++;
        const txId = `${this.runPrefix}_TX${this.txIndex}`;
        const patientId = `PAT_${txId}`;

        const txArgs = {
            contractId: this.chaincodeId,
            contractFunction: this.targetFunction,
            invokerIdentity: this.invokerIdentity,
        };

        if (this.targetFunction === 'createPatientRecord') {
            const name = NAMES[Math.floor(this.prng() * NAMES.length)];
            const age = (Math.floor(this.prng() * 70) + 18).toString();
            const weight = (Math.floor(this.prng() * 50) + 50).toString();
            const height = (Math.floor(this.prng() * 40) + 150).toString();
            const history = 'Standard intake record for benchmark throughput assessment';

            txArgs.contractArguments = [patientId, name, age, weight, height, history];
        }
        else if (this.targetFunction === 'updateHealthScore') {
            const existingPatientId = this._getPreSeededPatientId();
            const healthScore = Math.floor(this.prng() * 100).toString();
            const riskScore = (Math.floor(this.prng() * 10000) / 100).toFixed(2);
            const premium = (Math.floor(this.prng() * 200000) / 100 + 500).toFixed(2);

            txArgs.contractArguments = [existingPatientId, healthScore, riskScore, premium];
        }
        else if (this.targetFunction === 'createPrescription') {
            const rxId = `RX_${txId}`;
            // Use seeded patient ID if available, else monotonic ID
            const targetPatientId = this.preSeededPatientIds.length > 0 ? this._getPreSeededPatientId() : patientId;
            const medicine = 'Atorvastatin 20mg';
            const frequency = '1-0-0';
            const duration = '30 days';
            const remarks = 'Standard clinical maintenance';
            const ipfsHash = 'QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco';

            txArgs.contractArguments = [rxId, targetPatientId, medicine, frequency, duration, remarks, ipfsHash];
        }
        else if (this.targetFunction === 'requestScan') {
            const scanId = `SCAN_${txId}`;
            const targetPatientId = this.preSeededPatientIds.length > 0 ? this._getPreSeededPatientId() : patientId;
            const scanType = SCAN_TYPES[Math.floor(this.prng() * SCAN_TYPES.length)];
            const priority = PRIORITIES[Math.floor(this.prng() * PRIORITIES.length)];
            const notes = 'Diagnostic imaging request for throughput profiling';

            txArgs.contractArguments = [scanId, targetPatientId, scanType, priority, notes];
        }
        else if (this.targetFunction === 'getPatientRecord') {
            const existingPatientId = this._getPreSeededPatientId();
            txArgs.contractArguments = [existingPatientId];
            txArgs.readOnly = true;
        }
        else if (this.targetFunction === 'getAllPrescriptions') {
            const existingPatientId = this._getPreSeededPatientId();
            txArgs.contractArguments = [existingPatientId];
            txArgs.readOnly = true;
        }
        else {
            txArgs.contractArguments = [patientId];
        }

        return this.sutAdapter.sendRequests(txArgs);
    }
}

function createWorkloadModule() {
    return new HealthScoreWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;
