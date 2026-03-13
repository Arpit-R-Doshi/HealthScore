'use strict';

/**
 * HealthScore — Hyperledger Fabric Chaincode v2.0
 *
 * Role-Based Access Control (ABAC) via MSP ID check:
 * ─────────────────────────────────────────────────────────────────────────────
 *  Function               HospitalOrg  PatientOrg  PharmacyOrg  LabOrg  InsuranceOrg
 *  ─────────────────────────────────────────────────────────────────────────
 *  createPrescription       ✅ WRITE      ❌           ❌          ❌       ❌
 *  viewPrescription         ✅            ✅ (own)     ✅          ❌       ❌
 *  dispensePrescription     ❌            ❌           ✅ WRITE    ❌       ❌
 *  revokePrescription       ✅ WRITE      ❌           ❌          ❌       ❌
 *  requestScan              ✅ WRITE      ❌           ❌          ❌       ❌
 *  completeScan             ❌            ❌           ❌          ✅ WRITE ❌
 *  addMedicalFile           ✅            ✅ (own)     ❌          ✅       ❌
 *  createPatientRecord      ✅ WRITE      ❌           ❌          ❌       ❌
 *  getPatientRecord         ✅            ✅ (own)     ❌          ✅       ✅ (score only)
 *  updateHealthScore        ✅ WRITE      ❌           ❌          ❌       ❌
 *  getAllPrescriptions       ✅            ✅ (own)     ✅          ❌       ❌
 *  getAllScanOrders          ✅            ✅ (own)     ❌          ✅       ❌
 * ─────────────────────────────────────────────────────────────────────────────
 */

const { Contract } = require('fabric-contract-api');

// MSP ID constants — must match configtx.yaml exactly
const MSP = {
    HOSPITAL: 'HospitalOrgMSP',
    PATIENT: 'PatientOrgMSP',
    PHARMACY: 'PharmacyOrgMSP',
    LAB: 'LabOrgMSP',
    INSURANCE: 'InsuranceOrgMSP',
};

// Asset type tags stored on the ledger
const DOCTYPE = {
    PRESCRIPTION: 'prescription',
    SCAN_ORDER: 'scanOrder',
    PATIENT_RECORD: 'patientRecord',
    MEDICAL_FILE: 'medicalFile',
};

class HealthScoreContract extends Contract {

    // ═══════════════════════════════════════════════════════════════════════════
    // INTERNAL HELPERS
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * Returns the caller's MSP ID
     */
    _getMSP(ctx) {
        return ctx.clientIdentity.getMSPID();
    }

    /**
     * Throws if the caller's MSP is not one of the allowed MSPs
     * @param {Context} ctx
     * @param {string|string[]} allowedMSPs - one or more allowed MSP IDs
     * @param {string} action - description for the error message
     */
    _requireRole(ctx, allowedMSPs, action) {
        const callerMSP = this._getMSP(ctx);
        const allowed = Array.isArray(allowedMSPs) ? allowedMSPs : [allowedMSPs];
        if (!allowed.includes(callerMSP)) {
            throw new Error(
                `ACCESS DENIED: '${callerMSP}' cannot perform '${action}'. ` +
                `Allowed orgs: ${allowed.join(', ')}`
            );
        }
    }

    /**
     * Reads and parses a ledger state. Throws if not found.
     */
    async _getAsset(ctx, key) {
        const data = await ctx.stub.getState(key);
        if (!data || data.length === 0) {
            throw new Error(`Asset '${key}' not found on ledger`);
        }
        return JSON.parse(data.toString());
    }

    /**
     * Checks if a key exists on the ledger (returns boolean)
     */
    async _exists(ctx, key) {
        const data = await ctx.stub.getState(key);
        return data && data.length > 0;
    }

    /**
     * Serialises and saves an asset to the ledger
     */
    async _putAsset(ctx, key, asset) {
        await ctx.stub.putState(key, Buffer.from(JSON.stringify(asset)));
    }

    /**
     * Returns current timestamp as ISO string
     */
    _timestamp(ctx) {
        const ts = ctx.stub.getTxTimestamp();
        return new Date(ts.seconds.low * 1000).toISOString();
    }

    /**
     * Rich-query helper — runs a selector and returns all results
     */
    async _richQuery(ctx, query) {
        const iterator = await ctx.stub.getQueryResult(JSON.stringify(query));
        const results = [];
        let res = await iterator.next();
        while (!res.done) {
            if (res.value && res.value.value.toString()) {
                results.push(JSON.parse(res.value.value.toString()));
            }
            res = await iterator.next();
        }
        await iterator.close();
        return results;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PATIENT RECORDS
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * UC-01: Create a patient record (Doctor only)
     * Key: "PATIENT::<patientId>"
     */
    async createPatientRecord(ctx, patientId, name, age, weight, height, history) {
        this._requireRole(ctx, MSP.HOSPITAL, 'createPatientRecord');

        const key = `PATIENT::${patientId}`;
        if (await this._exists(ctx, key)) {
            throw new Error(`Patient record '${patientId}' already exists`);
        }

        const record = {
            docType: DOCTYPE.PATIENT_RECORD,
            id: patientId,
            name,
            age: parseInt(age),
            weight: parseFloat(weight),
            height: parseFloat(height),
            history,
            healthScore: null,
            medicalFiles: [],
            createdAt: this._timestamp(ctx),
            createdBy: this._getMSP(ctx),
        };

        await this._putAsset(ctx, key, record);
        return JSON.stringify(record);
    }

    /**
     * UC-02: Get patient record
     *  - HospitalOrg: full record
     *  - PatientOrg:  full record (own patient assumed — consent model left for v3)
     *  - LabOrg:      full record (needed to process scans)
     *  - InsuranceOrg: redacted record — only healthScore + age (no PII)
     */
    async getPatientRecord(ctx, patientId) {
        const callerMSP = this._getMSP(ctx);
        const allowed = [MSP.HOSPITAL, MSP.PATIENT, MSP.LAB, MSP.INSURANCE];
        if (!allowed.includes(callerMSP)) {
            throw new Error(`ACCESS DENIED: '${callerMSP}' cannot read patient records`);
        }

        const key = `PATIENT::${patientId}`;
        const record = await this._getAsset(ctx, key);

        // Insurers get a redacted view — no PII
        if (callerMSP === MSP.INSURANCE) {
            return JSON.stringify({
                id: record.id,
                age: record.age,
                healthScore: record.healthScore,
                redacted: true,
            });
        }

        return JSON.stringify(record);
    }

    /**
     * UC-03: Update health score (Doctor only)
     */
    async updateHealthScore(ctx, patientId, healthScore, riskScore, premium) {
        this._requireRole(ctx, MSP.HOSPITAL, 'updateHealthScore');

        const key = `PATIENT::${patientId}`;
        const record = await this._getAsset(ctx, key);

        record.healthScore = parseFloat(healthScore);
        record.riskScore = parseFloat(riskScore);
        record.premium = parseFloat(premium);
        record.updatedAt = this._timestamp(ctx);
        record.updatedBy = this._getMSP(ctx);

        await this._putAsset(ctx, key, record);
        return JSON.stringify(record);
    }

    /**
     * UC-04: Add a medical file hash (Doctor, Patient, or Lab)
     */
    async addMedicalFile(ctx, patientId, fileHash, fileName, category) {
        this._requireRole(ctx, [MSP.HOSPITAL, MSP.PATIENT, MSP.LAB], 'addMedicalFile');

        const allowedCategories = ['Test Report', 'Scan', 'Medical Summary'];
        if (!allowedCategories.includes(category)) {
            throw new Error(`Invalid category '${category}'. Allowed: ${allowedCategories.join(', ')}`);
        }

        const patKey = `PATIENT::${patientId}`;
        const record = await this._getAsset(ctx, patKey);

        const fileEntry = {
            docType: DOCTYPE.MEDICAL_FILE,
            hash: fileHash,
            name: fileName,
            category,
            uploadedBy: this._getMSP(ctx),
            date: this._timestamp(ctx),
        };

        record.medicalFiles.push(fileEntry);
        record.updatedAt = this._timestamp(ctx);

        await this._putAsset(ctx, patKey, record);
        return JSON.stringify(fileEntry);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PRESCRIPTIONS
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * UC-05: Create a prescription (Doctor only)
     * Key: "RX::<id>"
     */
    async createPrescription(ctx, id, patientId, medicine, frequency, duration, remarks, ipfsHash) {
        this._requireRole(ctx, MSP.HOSPITAL, 'createPrescription');

        const key = `RX::${id}`;
        if (await this._exists(ctx, key)) {
            throw new Error(`Prescription '${id}' already exists`);
        }

        const prescription = {
            docType: DOCTYPE.PRESCRIPTION,
            id,
            patientId,
            medicine,
            frequency,
            duration,
            remarks,
            ipfsHash: ipfsHash || '',
            status: 'ACTIVE',
            issuedAt: this._timestamp(ctx),
            issuedBy: this._getMSP(ctx),
            dispensedAt: null,
            dispensedBy: null,
        };

        await this._putAsset(ctx, key, prescription);
        return JSON.stringify(prescription);
    }

    /**
     * UC-06: View a prescription (Doctor, Patient, Pharmacist)
     */
    async viewPrescription(ctx, id) {
        this._requireRole(ctx, [MSP.HOSPITAL, MSP.PATIENT, MSP.PHARMACY], 'viewPrescription');
        const key = `RX::${id}`;
        const rx = await this._getAsset(ctx, key);
        return JSON.stringify(rx);
    }

    /**
     * UC-07: Dispense a prescription (Pharmacist only)
     */
    async dispensePrescription(ctx, id, pharmacistId) {
        this._requireRole(ctx, MSP.PHARMACY, 'dispensePrescription');

        const key = `RX::${id}`;
        const rx = await this._getAsset(ctx, key);

        if (rx.status === 'DISPENSED') {
            throw new Error(`Prescription '${id}' has already been dispensed`);
        }
        if (rx.status !== 'ACTIVE') {
            throw new Error(`Prescription '${id}' is not in ACTIVE status (status: ${rx.status})`);
        }

        rx.status = 'DISPENSED';
        rx.pharmacistId = pharmacistId;
        rx.dispensedAt = this._timestamp(ctx);
        rx.dispensedBy = this._getMSP(ctx);

        await this._putAsset(ctx, key, rx);
        return JSON.stringify(rx);
    }

    /**
     * UC-07b: Revoke a prescription (Doctor only)
     * Only ACTIVE prescriptions can be revoked.
     */
    async revokePrescription(ctx, id, reason) {
        this._requireRole(ctx, MSP.HOSPITAL, 'revokePrescription');

        const key = `RX::${id}`;
        const rx = await this._getAsset(ctx, key);

        if (rx.status === 'REVOKED') {
            throw new Error(`Prescription '${id}' is already revoked`);
        }
        if (rx.status === 'DISPENSED') {
            throw new Error(`Prescription '${id}' has already been dispensed — cannot revoke`);
        }

        rx.status = 'REVOKED';
        rx.revokedAt = this._timestamp(ctx);
        rx.revokedBy = this._getMSP(ctx);
        rx.revokeReason = reason || '';

        await this._putAsset(ctx, key, rx);
        return JSON.stringify(rx);
    }

    /**
     * UC-08: Get all prescriptions for a patient (Doctor, Patient, Pharmacist)
     */
    async getAllPrescriptions(ctx, patientId) {
        this._requireRole(ctx, [MSP.HOSPITAL, MSP.PATIENT, MSP.PHARMACY], 'getAllPrescriptions');

        const results = await this._richQuery(ctx, {
            selector: { docType: DOCTYPE.PRESCRIPTION, patientId },
            sort: [{ issuedAt: 'desc' }],
        });
        return JSON.stringify(results);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // SCAN / LAB ORDERS
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * UC-09: Request a scan / lab test (Doctor only)
     * Key: "SCAN::<id>"
     */
    async requestScan(ctx, id, patientId, scanType, priority, notes) {
        this._requireRole(ctx, MSP.HOSPITAL, 'requestScan');

        const validPriorities = ['Routine', 'Urgent', 'STAT (Immediate)'];
        if (!validPriorities.includes(priority)) {
            throw new Error(`Invalid priority '${priority}'. Allowed: ${validPriorities.join(', ')}`);
        }

        const key = `SCAN::${id}`;
        if (await this._exists(ctx, key)) {
            throw new Error(`Scan order '${id}' already exists`);
        }

        const order = {
            docType: DOCTYPE.SCAN_ORDER,
            id,
            patientId,
            scanType,
            priority,
            notes,
            status: 'PENDING',
            requestedAt: this._timestamp(ctx),
            requestedBy: this._getMSP(ctx),
            completedAt: null,
            reportHash: null,
            reportName: null,
        };

        await this._putAsset(ctx, key, order);
        return JSON.stringify(order);
    }

    /**
     * UC-10: Complete a scan and attach the IPFS report hash (Lab only)
     */
    async completeScan(ctx, id, reportHash, reportName) {
        this._requireRole(ctx, MSP.LAB, 'completeScan');

        const key = `SCAN::${id}`;
        const order = await this._getAsset(ctx, key);

        if (order.status === 'COMPLETED') {
            throw new Error(`Scan order '${id}' is already completed`);
        }

        order.status = 'COMPLETED';
        order.reportHash = reportHash;
        order.reportName = reportName;
        order.completedAt = this._timestamp(ctx);
        order.completedBy = this._getMSP(ctx);

        await this._putAsset(ctx, key, order);

        // Also add the report file to the patient's vault
        const patKey = `PATIENT::${order.patientId}`;
        if (await this._exists(ctx, patKey)) {
            const patRecord = await this._getAsset(ctx, patKey);
            patRecord.medicalFiles.push({
                docType: DOCTYPE.MEDICAL_FILE,
                hash: reportHash,
                name: reportName || `${order.scanType}-report`,
                category: order.scanType.toLowerCase().includes('scan') ? 'Scan' : 'Test Report',
                uploadedBy: this._getMSP(ctx),
                date: this._timestamp(ctx),
            });
            patRecord.updatedAt = this._timestamp(ctx);
            await this._putAsset(ctx, patKey, patRecord);
        }

        return JSON.stringify(order);
    }

    /**
     * UC-11: Get all scan orders for a patient (Doctor, Patient, Lab)
     */
    async getAllScanOrders(ctx, patientId) {
        this._requireRole(ctx, [MSP.HOSPITAL, MSP.PATIENT, MSP.LAB], 'getAllScanOrders');

        const results = await this._richQuery(ctx, {
            selector: { docType: DOCTYPE.SCAN_ORDER, patientId },
            sort: [{ requestedAt: 'desc' }],
        });
        return JSON.stringify(results);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // UTILITY / ADMIN
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * Returns the calling identity's MSP ID — useful for smoke-testing ABAC
     */
    async whoAmI(ctx) {
        return JSON.stringify({
            mspId: this._getMSP(ctx),
            clientId: ctx.clientIdentity.getID(),
        });
    }

    /**
     * Ledger existence check
     */
    async assetExists(ctx, key) {
        const exists = await this._exists(ctx, key);
        return JSON.stringify({ key, exists });
    }
}

module.exports.HealthScoreContract = HealthScoreContract;
module.exports.contracts = [HealthScoreContract];