'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

const NAMES = ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank', 'Grace', 'Heidi', 'Ivan', 'Judy'];
const PRIORITIES = ['Routine', 'Urgent', 'STAT (Immediate)'];
const SCAN_TYPES = ['MRI Scan', 'CT Scan', 'X-Ray', 'Blood Test'];

/**
 * Workload module for the HealthScore smart contract.
 */
class HealthScoreWorkload extends WorkloadModuleBase {
    constructor() {
        super();
        this.txIndex = 0;
        this.preSeededPatientIds = [];
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
        this.targetFunction = this.roundArguments.targetFunction || 'createPatientRecord';
        this.chaincodeId = this.roundArguments.chaincodeId || 'healthscore';

        // For functions that need existing records, pre-seed patient data
        const needsPreSeeding = ['updateHealthScore', 'getPatientRecord', 'getAllPrescriptions', 'getAllScanOrders'];
        
        if (needsPreSeeding.includes(this.targetFunction)) {
            const seedCount = this.roundArguments.preSeedCount || 200;
            console.log(`  [Worker ${workerIndex}] Pre-seeding ${seedCount} patient records for '${this.targetFunction}'...`);
            
            for (let i = 0; i < seedCount; i++) {
                const patientId = `SEED_${this.targetFunction}_W${workerIndex}_${i}`;
                const name = NAMES[i % NAMES.length];
                const age = Math.floor(Math.random() * 80) + 10;
                const weight = Math.floor(Math.random() * 50) + 50;
                const height = Math.floor(Math.random() * 50) + 150;
                const history = 'Pre-seeded record for benchmark';

                const txArgs = {
                    contractId: this.chaincodeId,
                    contractFunction: 'createPatientRecord',
                    invokerIdentity: 'HospitalOrgAdmin',
                    contractArguments: [patientId, name, age.toString(), weight.toString(), height.toString(), history],
                };

                try {
                    await this.sutAdapter.sendRequests(txArgs);
                    this.preSeededPatientIds.push(patientId);
                } catch (e) {
                    // If already exists, still add to the list (idempotent)
                    const errorString = (e.message || '') + ' ' + (e.stack || '') + ' ' + (typeof e === 'object' ? JSON.stringify(e) : e.toString());
                    if (errorString.includes('already exists')) {
                        this.preSeededPatientIds.push(patientId);
                    } else {
                        console.error(`Error pre-seeding ${patientId}:`, e);
                        // Still push it so we don't crash, but it might fail later
                        this.preSeededPatientIds.push(patientId);
                    }
                }
            }
            console.log(`  [Worker ${workerIndex}] Pre-seeded ${this.preSeededPatientIds.length} patient records successfully.`);
        }
    }

    /**
     * Pick a pre-seeded patient ID sequentially to avoid MVCC conflicts.
     */
    _getPreSeededPatientId() {
        if (this.preSeededPatientIds.length === 0) {
            // Fallback — should not happen if init succeeded
            return `SEED_${this.targetFunction}_W${this.workerIndex}_0`;
        }
        
        // Initialize sequential index if it doesn't exist
        if (this.seedIndex === undefined) {
            this.seedIndex = 0;
        }
        
        const id = this.preSeededPatientIds[this.seedIndex];
        this.seedIndex = (this.seedIndex + 1) % this.preSeededPatientIds.length;
        return id;
    }

    /**
     * Assemble and submit a transaction.
     */
    async submitTransaction() {
        this.txIndex++;
        
        // Generate random but deterministic IDs based on worker index and timestamp to avoid collisions
        const randomId = `${this.workerIndex}_${Date.now()}_${this.txIndex}`;
        const patientId = `PAT_${randomId}`;
        
        const txArgs = {
            contractId: this.chaincodeId,
            contractFunction: this.targetFunction,
            invokerIdentity: 'HospitalOrgAdmin', // Can be set via config, fallback to typical admin/user identity
        };

        if (this.targetFunction === 'createPatientRecord') {
            const name = NAMES[Math.floor(Math.random() * NAMES.length)];
            const age = Math.floor(Math.random() * 80) + 10;
            const weight = Math.floor(Math.random() * 50) + 50;
            const height = Math.floor(Math.random() * 50) + 150;
            const history = 'No significant history';
            
            txArgs.contractArguments = [patientId, name, age.toString(), weight.toString(), height.toString(), history];
        } 
        else if (this.targetFunction === 'updateHealthScore') {
            // Use a pre-seeded patient ID that already exists on the ledger
            const existingPatientId = this._getPreSeededPatientId();
            const healthScore = Math.floor(Math.random() * 100);
            const riskScore = Math.floor(Math.random() * 100);
            const premium = Math.floor(Math.random() * 500) + 100;
            
            txArgs.contractArguments = [existingPatientId, healthScore.toString(), riskScore.toString(), premium.toString()];
        } 
        else if (this.targetFunction === 'createPrescription') {
            const rxId = `RX_${randomId}`;
            const medicine = 'Paracetamol 500mg';
            const frequency = '1-0-1';
            const duration = '5 days';
            const remarks = 'Take after meals';
            const ipfsHash = 'QmDummyHash12345';
            
            txArgs.contractArguments = [rxId, patientId, medicine, frequency, duration, remarks, ipfsHash];
        } 
        else if (this.targetFunction === 'requestScan') {
            const scanId = `SCAN_${randomId}`;
            const scanType = SCAN_TYPES[Math.floor(Math.random() * SCAN_TYPES.length)];
            const priority = PRIORITIES[Math.floor(Math.random() * PRIORITIES.length)];
            const notes = 'Patient reporting acute pain';
            
            txArgs.contractArguments = [scanId, patientId, scanType, priority, notes];
        } 
        else if (this.targetFunction === 'getPatientRecord') {
            // Use a pre-seeded patient ID that already exists on the ledger
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
