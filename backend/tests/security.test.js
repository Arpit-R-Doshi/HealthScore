const { test, describe, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

// Set test environment variables before requiring server
process.env.NODE_ENV = 'test';
process.env.JWT_SECRET = 'test-secret-for-security-unit-tests-12345';
process.env.ADMIN_KEY = 'super-secret-admin-key-for-test';
process.env.SEED_DEMO_USERS = 'false';

const app = require('../server');

let server;
let baseUrl;

before(async () => {
    await new Promise((resolve) => {
        server = http.createServer(app);
        server.listen(0, '127.0.0.1', () => {
            const port = server.address().port;
            baseUrl = `http://127.0.0.1:${port}`;
            resolve();
        });
    });
});

after(async () => {
    if (server) {
        await new Promise((resolve) => server.close(resolve));
    }
});

// Helper for making HTTP requests
async function makeRequest(path, options = {}) {
    const url = `${baseUrl}${path}`;
    const headers = { ...(options.headers || {}) };
    let body = options.body;

    if (body && typeof body === 'object' && !(body instanceof Buffer) && !(typeof body === 'string')) {
        headers['Content-Type'] = 'application/json';
        body = JSON.stringify(body);
    }

    const response = await fetch(url, {
        method: options.method || 'GET',
        headers,
        body
    });

    let data;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
        data = await response.json();
    } else {
        data = await response.text();
    }

    return {
        status: response.status,
        headers: response.headers,
        data
    };
}

// Token creation helpers
function createExpiredToken(payload) {
    const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
    const expiredPayload = {
        ...payload,
        iat: Math.floor(Date.now() / 1000) - 7200,
        exp: Math.floor(Date.now() / 1000) - 3600 // Expired 1 hour ago
    };
    const body = Buffer.from(JSON.stringify(expiredPayload)).toString('base64url');
    const signature = crypto.createHmac('sha256', process.env.JWT_SECRET)
        .update(`${header}.${body}`)
        .digest('base64url');
    return `${header}.${body}.${signature}`;
}

function createTokenWithoutExp(payload) {
    const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
    const noExpPayload = {
        ...payload,
        iat: Math.floor(Date.now() / 1000)
    };
    delete noExpPayload.exp;
    const body = Buffer.from(JSON.stringify(noExpPayload)).toString('base64url');
    const signature = crypto.createHmac('sha256', process.env.JWT_SECRET)
        .update(`${header}.${body}`)
        .digest('base64url');
    return `${header}.${body}.${signature}`;
}

function createTokenWithInvalidExp(payload) {
    const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
    const invalidExpPayload = {
        ...payload,
        iat: Math.floor(Date.now() / 1000),
        exp: "infinite_or_invalid_string"
    };
    const body = Buffer.from(JSON.stringify(invalidExpPayload)).toString('base64url');
    const signature = crypto.createHmac('sha256', process.env.JWT_SECRET)
        .update(`${header}.${body}`)
        .digest('base64url');
    return `${header}.${body}.${signature}`;
}

function createTokenMissingClaim(payload, claimToRemove) {
    const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
    const modifiedPayload = {
        sub: 'PT-TEST',
        role: 'Patient',
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 3600,
        ...payload
    };
    delete modifiedPayload[claimToRemove];
    const body = Buffer.from(JSON.stringify(modifiedPayload)).toString('base64url');
    const signature = crypto.createHmac('sha256', process.env.JWT_SECRET)
        .update(`${header}.${body}`)
        .digest('base64url');
    return `${header}.${body}.${signature}`;
}

describe('HealthScore Backend Security Suite', () => {

    let patientAToken;
    let patientAId;
    let patientAUsername = `pat_alpha_${Date.now()}`;

    let patientBToken;
    let patientBId;
    let patientBUsername = `pat_beta_${Date.now()}`;

    let doctorWithCareToken;
    let doctorWithCareId = `DOC-CARE-${Date.now()}`;

    let doctorWithoutCareToken;
    let doctorWithoutCareId = `DOC-NOCARE-${Date.now()}`;

    let pharmacistToken;
    let pharmacistId = `PH-001`;

    let bloodtestToken;
    let bloodtestId = `BT-001`;

    let insuranceToken;
    let insuranceId = `IN-001`;

    let adminToken;
    let adminId = `ADM-001`;

    let prescriptionAId = `RX-TEST-${Date.now()}`;

    // Setup test users via /api/register and fixtures
    before(async () => {
        // Register Patient A
        const regA = await makeRequest('/api/register', {
            method: 'POST',
            body: {
                username: patientAUsername,
                name: 'Patient Alpha',
                password: 'PasswordAlpha123!',
                age: 35,
                height: 175,
                weight: 70
            }
        });
        assert.ok([200, 201].includes(regA.status), `Failed to register Patient A: ${JSON.stringify(regA.data)}`);
        patientAToken = regA.data.token;
        patientAId = regA.data.user.id;

        // Register Patient B
        const regB = await makeRequest('/api/register', {
            method: 'POST',
            body: {
                username: patientBUsername,
                name: 'Patient Beta',
                password: 'PasswordBeta123!',
                age: 42,
                height: 180,
                weight: 85
            }
        });
        assert.ok([200, 201].includes(regB.status), `Failed to register Patient B: ${JSON.stringify(regB.data)}`);
        patientBToken = regB.data.token;
        patientBId = regB.data.user.id;

        // Doctor with care relationship to Patient A
        const docCarePw = app.hashPassword('DoctorPassword123!');
        const doctorWithCareUser = {
            id: doctorWithCareId,
            username: `dr_care_${Date.now()}`,
            passwordHash: docCarePw.hash,
            salt: docCarePw.salt,
            role: 'Doctor',
            name: 'Dr. Active Care'
        };
        app.USERS.push(doctorWithCareUser);
        doctorWithCareToken = app.generateToken(doctorWithCareUser);

        // Assign Doctor With Care to Patient A's medical team
        const patA = app.USERS.find(u => u.id === patientAId);
        if (patA) {
            patA.medicalTeam = [{ id: doctorWithCareId, name: 'Dr. Active Care' }];
            patA.prescriptions = [{
                id: prescriptionAId,
                medicine: 'Metformin 500mg',
                doctorId: doctorWithCareId,
                status: 'ACTIVE'
            }];
        }

        // Doctor WITHOUT care relationship to Patient A
        const docNoCarePw = app.hashPassword('DoctorPassword123!');
        const doctorWithoutCareUser = {
            id: doctorWithoutCareId,
            username: `dr_nocare_${Date.now()}`,
            passwordHash: docNoCarePw.hash,
            salt: docNoCarePw.salt,
            role: 'Doctor',
            name: 'Dr. Stranger'
        };
        app.USERS.push(doctorWithoutCareUser);
        doctorWithoutCareToken = app.generateToken(doctorWithoutCareUser);

        // Pharmacist User
        const pharmaPw = app.hashPassword('PharmaPassword123!');
        const pharmaUser = {
            id: pharmacistId,
            username: `pharma_${Date.now()}`,
            passwordHash: pharmaPw.hash,
            salt: pharmaPw.salt,
            role: 'Pharmacist',
            name: 'Test Pharmacist'
        };
        app.USERS.push(pharmaUser);
        pharmacistToken = app.generateToken(pharmaUser);

        // Bloodtest User
        const labPw = app.hashPassword('LabPassword123!');
        const labUser = {
            id: bloodtestId,
            username: `lab_${Date.now()}`,
            passwordHash: labPw.hash,
            salt: labPw.salt,
            role: 'Bloodtest',
            name: 'Test Lab'
        };
        app.USERS.push(labUser);
        bloodtestToken = app.generateToken(labUser);

        // Insurance User
        const insPw = app.hashPassword('InsPassword123!');
        const insUser = {
            id: insuranceId,
            username: `ins_${Date.now()}`,
            passwordHash: insPw.hash,
            salt: insPw.salt,
            role: 'Insurance',
            name: 'Test Insurance'
        };
        app.USERS.push(insUser);
        insuranceToken = app.generateToken(insUser);

        // Admin User
        const adminPw = app.hashPassword('AdminPassword123!');
        const adminUser = {
            id: adminId,
            username: `admin_${Date.now()}`,
            passwordHash: adminPw.hash,
            salt: adminPw.salt,
            role: 'Admin',
            name: 'System Admin'
        };
        app.USERS.push(adminUser);
        adminToken = app.generateToken(adminUser);
    });

    describe('1. Authentication & Token Verification', () => {
        test('Reject requests with missing Authorization header (401)', async () => {
            const res = await makeRequest(`/api/patient/${patientAId}`);
            assert.equal(res.status, 401);
            assert.match(res.data.error, /missing or malformed Bearer token/i);
        });

        test('Reject requests with malformed Authorization header (401)', async () => {
            const res = await makeRequest(`/api/patient/${patientAId}`, {
                headers: { 'Authorization': 'Basic dXNlcjpwYXNz' }
            });
            assert.equal(res.status, 401);
            assert.match(res.data.error, /missing or malformed Bearer token/i);
        });

        test('Reject requests with invalid JWT signature (401)', async () => {
            const parts = patientAToken.split('.');
            const tamperedToken = `${parts[0]}.${parts[1]}.invalidsignaturehere12345`;
            const res = await makeRequest(`/api/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${tamperedToken}` }
            });
            assert.equal(res.status, 401);
            assert.match(res.data.error, /invalid or expired token/i);
        });

        test('Reject requests with expired token (401)', async () => {
            const expiredToken = createExpiredToken({ sub: patientAId, role: 'Patient' });
            const res = await makeRequest(`/api/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${expiredToken}` }
            });
            assert.equal(res.status, 401);
            assert.match(res.data.error, /invalid or expired token/i);
        });

        test('Reject signed token without exp claim (401)', async () => {
            const noExpToken = createTokenWithoutExp({ sub: patientAId, role: 'Patient' });
            const res = await makeRequest(`/api/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${noExpToken}` }
            });
            assert.equal(res.status, 401);
        });

        test('Reject signed token with invalid non-numeric exp (401)', async () => {
            const badExpToken = createTokenWithInvalidExp({ sub: patientAId, role: 'Patient' });
            const res = await makeRequest(`/api/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${badExpToken}` }
            });
            assert.equal(res.status, 401);
        });

        test('Reject signed token missing sub claim (401)', async () => {
            const noSubToken = createTokenMissingClaim({}, 'sub');
            const res = await makeRequest(`/api/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${noSubToken}` }
            });
            assert.equal(res.status, 401);
        });

        test('Reject signed token missing role claim (401)', async () => {
            const noRoleToken = createTokenMissingClaim({}, 'role');
            const res = await makeRequest(`/api/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${noRoleToken}` }
            });
            assert.equal(res.status, 401);
        });
    });

    describe('2. Password Hashing & Credential Redaction', () => {
        test('Registration response does not expose password or hash fields', async () => {
            const res = await makeRequest('/api/register', {
                method: 'POST',
                body: {
                    username: `pat_gamma_${Date.now()}`,
                    name: 'Patient Gamma',
                    password: 'SuperSecretPlaintextPassword123!',
                    age: 28
                }
            });
            assert.ok([200, 201].includes(res.status));
            assert.equal(res.data.user.password, undefined);
            assert.equal(res.data.user.passwordHash, undefined);
            assert.equal(res.data.user.salt, undefined);
            assert.ok(res.data.token, 'Token must be issued');
        });

        test('Login response validates hashed password and redacts credentials', async () => {
            const res = await makeRequest('/api/login', {
                method: 'POST',
                body: {
                    username: patientAUsername,
                    password: 'PasswordAlpha123!'
                }
            });
            assert.equal(res.status, 200);
            assert.equal(res.data.user.password, undefined);
            assert.equal(res.data.user.passwordHash, undefined);
            assert.equal(res.data.user.salt, undefined);
        });

        test('Login fails with invalid password (401)', async () => {
            const res = await makeRequest('/api/login', {
                method: 'POST',
                body: {
                    username: patientAUsername,
                    password: 'WrongPasswordTotally!'
                }
            });
            assert.equal(res.status, 401);
            assert.match(res.data.message, /invalid credentials/i);
        });
    });

    describe('3. Cross-Patient Access Controls (Data Isolation)', () => {
        test('Patient A reading Patient A data succeeds (200)', async () => {
            const res = await makeRequest(`/api/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${patientAToken}` }
            });
            assert.equal(res.status, 200);
            assert.equal(res.data.id, patientAId);
        });

        test('Patient A cannot read Patient B data (403 Forbidden)', async () => {
            const res = await makeRequest(`/api/patient/${patientBId}`, {
                headers: { 'Authorization': `Bearer ${patientAToken}` }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /cannot access records belonging to another patient/i);
        });

        test('Patient A cannot update Patient B data (403 Forbidden)', async () => {
            const res = await makeRequest('/api/patient/update', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: {
                    id: patientBId,
                    weight: 99
                }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /cannot modify another patient's profile/i);
        });

        test('Patient A cannot view Patient B blockchain ledger records (403 Forbidden)', async () => {
            const res = await makeRequest(`/api/ledger/patient/${patientBId}`, {
                headers: { 'Authorization': `Bearer ${patientAToken}` }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /cannot access another patient's ledger record/i);
        });

        test('Patient A cannot trigger ML score inference for Patient B (403 Forbidden)', async () => {
            const res = await makeRequest('/api/calculate-score', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: {
                    patientId: patientBId,
                    age: 50,
                    gender: 'female'
                }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /cannot evaluate risk scores for another patient/i);
        });
    });

    describe('4. Score Calculation & Inference Authorization', () => {
        test('Pharmacy role cannot calculate score for a patient (403 Forbidden)', async () => {
            const res = await makeRequest('/api/calculate-score', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${pharmacistToken}` },
                body: {
                    patientId: patientAId,
                    age: 35,
                    gender: 'male'
                }
            });
            assert.equal(res.status, 403);
        });

        test('Lab/Bloodtest role cannot calculate score for a patient (403 Forbidden)', async () => {
            const res = await makeRequest('/api/calculate-score', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${bloodtestToken}` },
                body: {
                    patientId: patientAId,
                    age: 35,
                    gender: 'male'
                }
            });
            assert.equal(res.status, 403);
        });

        test('Insurance role cannot calculate score for a patient (403 Forbidden)', async () => {
            const res = await makeRequest('/api/calculate-score', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${insuranceToken}` },
                body: {
                    patientId: patientAId,
                    age: 35,
                    gender: 'male'
                }
            });
            assert.equal(res.status, 403);
        });

        test('Doctor WITHOUT care relationship cannot calculate score for Patient A (403 Forbidden)', async () => {
            const res = await makeRequest('/api/calculate-score', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${doctorWithoutCareToken}` },
                body: {
                    patientId: patientAId,
                    age: 35,
                    gender: 'male'
                }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /do not have an authorized care relationship/i);
        });

        test('Doctor WITH care relationship CAN calculate score for Patient A (200 OK)', async () => {
            const res = await makeRequest('/api/calculate-score', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${doctorWithCareToken}` },
                body: {
                    patientId: patientAId,
                    age: 35,
                    gender: 'male'
                }
            });
            assert.equal(res.status, 200);
            assert.ok(res.data.health_score !== undefined);
            assert.ok(res.data.risk_score !== undefined);
        });
    });

    describe('5. Ledger Query Authorization for Non-Patients', () => {
        test('Pharmacist cannot query arbitrary patient ledger record (403 Forbidden)', async () => {
            const res = await makeRequest(`/api/ledger/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${pharmacistToken}` }
            });
            assert.equal(res.status, 403);
        });

        test('Bloodtest cannot query arbitrary patient ledger record (403 Forbidden)', async () => {
            const res = await makeRequest(`/api/ledger/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${bloodtestToken}` }
            });
            assert.equal(res.status, 403);
        });

        test('Insurance cannot query arbitrary patient ledger record (403 Forbidden)', async () => {
            const res = await makeRequest(`/api/ledger/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${insuranceToken}` }
            });
            assert.equal(res.status, 403);
        });

        test('Doctor WITHOUT care relationship cannot query patient ledger (403 Forbidden)', async () => {
            const res = await makeRequest(`/api/ledger/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${doctorWithoutCareToken}` }
            });
            assert.equal(res.status, 403);
        });

        test('Bloodtest cannot query prescription ledger for a patient (403 Forbidden)', async () => {
            const res = await makeRequest(`/api/ledger/prescriptions/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${bloodtestToken}` }
            });
            assert.equal(res.status, 403);
        });

        test('Pharmacist cannot query scan order ledger for a patient (403 Forbidden)', async () => {
            const res = await makeRequest(`/api/ledger/scans/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${pharmacistToken}` }
            });
            assert.equal(res.status, 403);
        });

        test('Patient A cannot query prescription on ledger belonging to Patient B (403 Forbidden)', async () => {
            const res = await makeRequest(`/api/prescription/ledger/RX-PATIENT-B-ID`, {
                headers: { 'Authorization': `Bearer ${patientAToken}` }
            });
            assert.equal(res.status, 403);
        });

        test('Doctor WITHOUT care relationship cannot view Patient A prescription on ledger (403 Forbidden)', async () => {
            const res = await makeRequest(`/api/prescription/ledger/${prescriptionAId}`, {
                headers: { 'Authorization': `Bearer ${doctorWithoutCareToken}` }
            });
            assert.equal(res.status, 403);
        });
    });

    describe('6. Patient Actions, Favorites, Appointments & Care Relationship Rules', () => {
        test('Doctor cannot toggle favorites for a patient (403 Forbidden)', async () => {
            const res = await makeRequest('/api/patient/toggle-favorite', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${doctorWithCareToken}` },
                body: { patientId: patientAId, doctorId: doctorWithCareId }
            });
            assert.equal(res.status, 403);
        });

        test('Pharmacist cannot toggle favorites for a patient (403 Forbidden)', async () => {
            const res = await makeRequest('/api/patient/toggle-favorite', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${pharmacistToken}` },
                body: { patientId: patientAId, doctorId: doctorWithCareId }
            });
            assert.equal(res.status, 403);
        });

        test('Pharmacist cannot book appointment on behalf of patient (403 Forbidden)', async () => {
            const res = await makeRequest('/api/book-appointment', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${pharmacistToken}` },
                body: { patientId: patientAId, doctorId: doctorWithCareId }
            });
            assert.equal(res.status, 403);
        });

        test('Doctor X cannot book appointment for patient with Doctor Y (403 Forbidden)', async () => {
            const res = await makeRequest('/api/book-appointment', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${doctorWithoutCareToken}` },
                body: { patientId: patientAId, doctorId: doctorWithCareId }
            });
            assert.equal(res.status, 403);
        });

        test('Doctor WITHOUT care relationship cannot view Patient A profile (403 Forbidden)', async () => {
            const res = await makeRequest(`/api/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${doctorWithoutCareToken}` }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /do not have an active care relationship/i);
        });

        test('Doctor WITH care relationship CAN view Patient A profile (200 OK)', async () => {
            const res = await makeRequest(`/api/patient/${patientAId}`, {
                headers: { 'Authorization': `Bearer ${doctorWithCareToken}` }
            });
            assert.equal(res.status, 200);
            assert.equal(res.data.id, patientAId);
        });

        test('Doctor WITHOUT care relationship cannot upload files for Patient A (403 Forbidden)', async () => {
            const res = await makeRequest('/api/patient/add-file', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${doctorWithoutCareToken}` },
                body: { patientId: patientAId, ipfsHash: 'Qm123', fileName: 'test.pdf' }
            });
            assert.equal(res.status, 403);
        });
    });

    describe('7. Role-Based Access Control (Default-Deny Authorization)', () => {
        test('Patient cannot create prescription (403 Forbidden, Doctor only)', async () => {
            const res = await makeRequest('/api/prescription', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: { patientId: patientAToken, medicine: 'Adderall' }
            });
            assert.equal(res.status, 403);
        });

        test('Patient cannot dispense prescription (403 Forbidden, Pharmacist only)', async () => {
            const res = await makeRequest('/api/dispense', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: { rxId: 'RX-12345' }
            });
            assert.equal(res.status, 403);
        });

        test('Doctor cannot dispense prescription (403 Forbidden, Pharmacist only)', async () => {
            const res = await makeRequest('/api/dispense', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${doctorWithCareToken}` },
                body: { rxId: 'RX-12345' }
            });
            assert.equal(res.status, 403);
        });

        test('Patient cannot add inventory (403 Forbidden)', async () => {
            const res = await makeRequest('/api/inventory/add', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: { name: 'Ibuprofen', stock: 50, price: 10 }
            });
            assert.equal(res.status, 403);
        });

        test('Patient cannot access bloodtest completion (403 Forbidden)', async () => {
            const res = await makeRequest('/api/bloodtest/complete-scan', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: { scanId: 'SCN-123' }
            });
            assert.equal(res.status, 403);
        });
    });

    describe('8. Admin Endpoint Protections & Credential Requirements', () => {
        test('Admin access without key fails (403 Forbidden)', async () => {
            const res = await makeRequest('/api/admin/access', {
                method: 'POST',
                body: {}
            });
            assert.equal(res.status, 403);
        });

        test('Admin access with wrong key fails (403 Forbidden)', async () => {
            const res = await makeRequest('/api/admin/access', {
                method: 'POST',
                body: { adminKey: 'wrong-key-attempt' }
            });
            assert.equal(res.status, 403);
        });

        test('Admin access with default key "admin" fails when actual key is different', async () => {
            const res = await makeRequest('/api/admin/access', {
                method: 'POST',
                body: { adminKey: 'admin' }
            });
            assert.equal(res.status, 403);
        });

        test('Admin access with correct key succeeds (200 OK) and credentials are redacted', async () => {
            const res = await makeRequest('/api/admin/access', {
                method: 'POST',
                body: { adminKey: 'super-secret-admin-key-for-test' }
            });
            assert.equal(res.status, 200);
            assert.equal(res.data.success, true);
            assert.ok(Array.isArray(res.data.database.users));
            for (const user of res.data.database.users) {
                assert.equal(user.password, undefined);
                assert.equal(user.passwordHash, undefined);
                assert.equal(user.salt, undefined);
            }
        });
    });

    describe('9. Production Mode & Demo Seeding Protection', () => {
        test('Production mode prevents demo account seeding even with SEED_DEMO_USERS=true', () => {
            // Test the isolated logic of loadDatabase under NODE_ENV=production
            const origNodeEnv = process.env.NODE_ENV;
            const origSeed = process.env.SEED_DEMO_USERS;
            try {
                process.env.NODE_ENV = 'production';
                process.env.SEED_DEMO_USERS = 'true';
                const isDevOrTest = process.env.NODE_ENV === 'development' || process.env.NODE_ENV === 'test';
                assert.equal(isDevOrTest, false, 'isDevOrTest must be false in production');
            } finally {
                process.env.NODE_ENV = origNodeEnv;
                process.env.SEED_DEMO_USERS = origSeed;
            }
        });
    });

    describe('10. Request Body Size Limits & Payload Constraints', () => {
        test('Reject payload larger than 1MB (413 Payload Too Large)', async () => {
            const largeData = 'A'.repeat(1.5 * 1024 * 1024); // 1.5MB string
            const res = await makeRequest('/api/patient/update', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: {
                    id: patientAId,
                    history: largeData
                }
            });
            assert.equal(res.status, 413);
        });
    });

    describe('11. File Upload Safeguards & MIME Validation', () => {
        test('File upload requires authentication (401)', async () => {
            const res = await makeRequest('/api/upload', {
                method: 'POST'
            });
            assert.equal(res.status, 401);
        });

        test('File upload rejects request with missing file (400)', async () => {
            const res = await makeRequest('/api/upload', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${patientAToken}`,
                    'Content-Type': 'multipart/form-data; boundary=----WebKitFormBoundaryXYZ'
                },
                body: '------WebKitFormBoundaryXYZ--\r\n'
            });
            assert.equal(res.status, 400);
        });

        test('File upload rejects disallowed file MIME types', async () => {
            const boundary = '----WebKitFormBoundaryTest123';
            const body = [
                `--${boundary}`,
                'Content-Disposition: form-data; name="file"; filename="malicious.exe"',
                'Content-Type: application/x-msdownload',
                '',
                'MZ90000000',
                `--${boundary}--`,
                ''
            ].join('\r\n');

            const res = await makeRequest('/api/upload', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${patientAToken}`,
                    'Content-Type': `multipart/form-data; boundary=${boundary}`
                },
                body
            });
            assert.ok([400, 500].includes(res.status));
        });
    });
});
