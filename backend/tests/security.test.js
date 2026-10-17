const { test, describe, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const crypto = require('node:crypto');

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

    if (body && typeof body === 'object' && !(body instanceof Buffer)) {
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

// Helper to create an expired JWT
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

describe('HealthScore Backend Security Suite', () => {

    let patientAToken;
    let patientAId;
    let patientAUsername = `pat_alpha_${Date.now()}`;

    let patientBToken;
    let patientBId;
    let patientBUsername = `pat_beta_${Date.now()}`;

    let doctorToken;
    let doctorId = `DOC-${Date.now()}`;
    let doctorUsername = `dr_house_${Date.now()}`;

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

        // Create Doctor Fixture directly
        const docPw = app.hashPassword('DoctorPassword123!');
        const doctorUser = {
            id: doctorId,
            username: doctorUsername,
            passwordHash: docPw.hash,
            salt: docPw.salt,
            role: 'Doctor',
            name: 'Dr. Gregory House',
            specialty: 'Diagnostics',
            appointments: [],
            scanRequests: []
        };
        app.USERS.push(doctorUser);
        doctorToken = app.generateToken(doctorUser);
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
            assert.ok(res.data.token);
        });

        test('Login fails with invalid password (401)', async () => {
            const res = await makeRequest('/api/login', {
                method: 'POST',
                body: {
                    username: patientAUsername,
                    password: 'WrongPassword'
                }
            });
            assert.equal(res.status, 401);
            assert.match(res.data.message, /Invalid credentials/i);
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
                    patientId: patientBId,
                    weight: 90
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
            assert.match(res.data.error, /Cannot access another patient's ledger record/i);
        });

        test('Patient A cannot trigger ML score inference for Patient B (403 Forbidden)', async () => {
            const res = await makeRequest('/api/calculate-score', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: {
                    patientId: patientBId,
                    age: 40,
                    weight: 75,
                    height: 175
                }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /Cannot evaluate risk scores for another patient/i);
        });
    });

    describe('4. Role-Based Access Control (Default-Deny Authorization)', () => {
        test('Patient cannot create prescription (403 Forbidden, Doctor only)', async () => {
            const res = await makeRequest('/api/prescription', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: {
                    patientId: patientBId,
                    medicine: 'Amoxicillin'
                }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /is not authorized for this resource/i);
        });

        test('Patient cannot dispense prescription (403 Forbidden, Pharmacist only)', async () => {
            const res = await makeRequest('/api/dispense', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: {
                    rxId: 'RX-123456',
                    patientId: patientAId,
                    medicineName: 'Paracetamol'
                }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /is not authorized for this resource/i);
        });

        test('Doctor cannot dispense prescription (403 Forbidden, Pharmacist only)', async () => {
            const res = await makeRequest('/api/dispense', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${doctorToken}` },
                body: {
                    rxId: 'RX-123456',
                    patientId: patientAId,
                    medicineName: 'Paracetamol'
                }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /is not authorized for this resource/i);
        });

        test('Patient cannot add inventory (403 Forbidden)', async () => {
            const res = await makeRequest('/api/inventory/add', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: {
                    name: 'Aspirin',
                    stock: 100,
                    price: 10
                }
            });
            assert.equal(res.status, 403);
        });

        test('Patient cannot access bloodtest completion (403 Forbidden)', async () => {
            const res = await makeRequest('/api/bloodtest/complete-scan', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: {
                    patientId: patientAId,
                    scanId: 'SC-123'
                }
            });
            assert.equal(res.status, 403);
        });
    });

    describe('5. Admin Endpoint Protections & Credential Requirements', () => {
        test('Admin access without key fails (403 Forbidden)', async () => {
            const res = await makeRequest('/api/admin/access', {
                method: 'POST',
                body: {}
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /Access Denied: Invalid admin credentials/i);
        });

        test('Admin access with wrong key fails (403 Forbidden)', async () => {
            const res = await makeRequest('/api/admin/access', {
                method: 'POST',
                body: { adminKey: 'wrong-admin-key' }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /Access Denied: Invalid admin credentials/i);
        });

        test('Admin access with default key "admin" fails when actual key is different', async () => {
            const res = await makeRequest('/api/admin/access', {
                method: 'POST',
                body: { adminKey: 'admin' }
            });
            assert.equal(res.status, 403);
            assert.match(res.data.error, /Access Denied: Invalid admin credentials/i);
        });

        test('Admin access with correct key succeeds (200 OK) and credentials are redacted', async () => {
            const res = await makeRequest('/api/admin/access', {
                method: 'POST',
                body: { adminKey: 'super-secret-admin-key-for-test' }
            });
            assert.equal(res.status, 200);
            assert.equal(res.data.success, true);
            assert.ok(Array.isArray(res.data.database.users));
            // Ensure no user returned has password or passwordHash
            for (const user of res.data.database.users) {
                assert.equal(user.password, undefined);
                assert.equal(user.passwordHash, undefined);
                assert.equal(user.salt, undefined);
            }
        });
    });

    describe('6. Request Body Size Limits & Payload Constraints', () => {
        test('Reject payload larger than 1MB (413 Payload Too Large)', async () => {
            const largeData = 'A'.repeat(1.5 * 1024 * 1024); // 1.5MB string
            const res = await makeRequest('/api/patient/update', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${patientAToken}` },
                body: {
                    patientId: patientAId,
                    diseaseInput: largeData
                }
            });
            assert.equal(res.status, 413);
        });
    });

    describe('7. File Upload Safeguards', () => {
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
    });
});
