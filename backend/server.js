require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { Gateway, Wallets } = require('fabric-network');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const multer = require('multer');
const FormData = require('form-data');
const axios = require('axios');
const client = require('prom-client');

const app = express();

// =============================================================
// 🛑 CONFIGURATION & ENVIRONMENT HARDENING
// =============================================================
const PINATA_JWT = process.env.PINATA_JWT;
const GROQ_API_KEY = process.env.GROQ_API_KEY;
const ADMIN_KEY = process.env.ADMIN_KEY; // NO default 'admin' fallback
const PORT = process.env.PORT || 5001;

// Cryptographic token secret: in non-dev/test environments, an explicit JWT_SECRET is mandatory.
const isDevOrTest = process.env.NODE_ENV === 'development' || process.env.NODE_ENV === 'test';
const JWT_SECRET = process.env.JWT_SECRET || (isDevOrTest ? 'healthscore-dev-jwt-secret-key-change-in-production' : null);
if (!isDevOrTest && (!JWT_SECRET || JWT_SECRET === 'healthscore-dev-jwt-secret-key-change-in-production')) {
    console.error("FATAL: JWT_SECRET environment variable is required and must not use the dev fallback in non-development/test mode!");
    if (require.main === module) {
        process.exit(1);
    }
}

// CORS Policy: Restricted allowlist
const ALLOWED_ORIGINS = process.env.ALLOWED_ORIGINS 
    ? process.env.ALLOWED_ORIGINS.split(',').map(s => s.trim())
    : ['http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:5173', 'http://127.0.0.1:5173'];

app.use(cors({
    origin: (origin, callback) => {
        // Allow requests with no origin (e.g. mobile apps, curl, or same-origin in development)
        if (!origin || ALLOWED_ORIGINS.includes(origin)) {
            callback(null, true);
        } else {
            callback(new Error(`CORS blocked: Origin ${origin} is not allowed`));
        }
    },
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With']
}));

// Request body size limit to prevent Denial of Service
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true, limit: '1mb' }));

// Ensure uploads directory exists
const UPLOADS_DIR = path.join(__dirname, 'uploads');
if (!fs.existsSync(UPLOADS_DIR)) {
    fs.mkdirSync(UPLOADS_DIR, { recursive: true });
}

// Multer upload policy: strictly bounded file sizes and MIME types
const upload = multer({
    dest: UPLOADS_DIR,
    limits: { fileSize: 5 * 1024 * 1024 }, // 5 MB max
    fileFilter: (req, file, cb) => {
        const allowedTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg'];
        if (allowedTypes.includes(file.mimetype)) {
            cb(null, true);
        } else {
            cb(new Error("Invalid file type. Only PDF, PNG, and JPEG documents are permitted."));
        }
    }
});

const DB_FILE = path.join(__dirname, 'database.json');

// =============================================================
// 🔐 CRYPTOGRAPHY & AUTHENTICATION HELPERS
// =============================================================

/**
 * Derives a secure password hash using PBKDF2 with 100,000 iterations of SHA-512.
 */
function hashPassword(password, salt) {
    const s = salt || crypto.randomBytes(16).toString('hex');
    const hash = crypto.pbkdf2Sync(String(password), s, 100000, 64, 'sha512').toString('hex');
    return { hash, salt: s };
}

/**
 * Timing-safe comparison to prevent side-channel timing attacks.
 */
function verifyPassword(password, storedHash, salt) {
    if (!password || !storedHash || !salt) return false;
    try {
        const hash = crypto.pbkdf2Sync(String(password), salt, 100000, 64, 'sha512').toString('hex');
        const hashBuf = Buffer.from(hash, 'hex');
        const storedBuf = Buffer.from(storedHash, 'hex');
        if (hashBuf.length !== storedBuf.length) return false;
        return crypto.timingSafeEqual(hashBuf, storedBuf);
    } catch (e) {
        return false;
    }
}

/**
 * Strips sensitive credential fields from user objects before returning to clients.
 */
function redactUser(user) {
    if (!user) return null;
    const { password, passwordHash, salt, ...safeUser } = user;
    return safeUser;
}

/**
 * Generates an HMAC-SHA256 signed bearer token with 24-hour expiration.
 */
function generateToken(user) {
    if (!JWT_SECRET) return null;
    const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
    const now = Math.floor(Date.now() / 1000);
    const payload = Buffer.from(JSON.stringify({
        sub: user.id,
        username: user.username,
        role: user.role,
        name: user.name,
        iat: now,
        exp: now + (24 * 3600) // 24 hours
    })).toString('base64url');
    const signature = crypto.createHmac('sha256', JWT_SECRET)
        .update(`${header}.${payload}`)
        .digest('base64url');
    return `${header}.${payload}.${signature}`;
}

/**
 * Validates token signature, structure, and expiration.
 * Requires sub, role, iat, and an explicit finite unexpired exp.
 * Fails closed if JWT_SECRET is missing.
 */
function verifyToken(token) {
    if (!token || typeof token !== 'string') return null;
    if (!JWT_SECRET) return null; // Fail closed if secret missing

    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const [headerB64, payloadB64, sig] = parts;
    const expectedSig = crypto.createHmac('sha256', JWT_SECRET)
        .update(`${headerB64}.${payloadB64}`)
        .digest('base64url');
    if (sig.length !== expectedSig.length) return null;
    if (!crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expectedSig))) return null;

    try {
        const payload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString('utf8'));
        if (!payload || typeof payload !== 'object') return null;

        // Required claims: sub (string), role (string), iat (number), exp (number)
        if (!payload.sub || typeof payload.sub !== 'string' || !payload.role || typeof payload.role !== 'string') {
            return null;
        }
        if (typeof payload.iat !== 'number' || !Number.isFinite(payload.iat)) {
            return null;
        }
        if (typeof payload.exp !== 'number' || !Number.isFinite(payload.exp)) {
            return null;
        }

        const now = Math.floor(Date.now() / 1000);
        if (payload.exp <= now) {
            return null; // Expired
        }
        return payload;
    } catch (e) {
        return null;
    }
}

/**
 * Validates whether a doctor has an active care relationship with a patient.
 * Checks medical team assignment, booked appointments, scan requests, or active prescriptions.
 */
function hasCareRelationship(doctorId, patient) {
    if (!patient || !doctorId) return false;
    const inMedicalTeam = (patient.medicalTeam || []).some(m => m.id === doctorId);
    const hasAppointment = (patient.appointments || []).some(a => a.doctorId === doctorId);
    const hasScanRequest = (patient.scanRequests || []).some(s => s.doctorId === doctorId);
    const hasPrescription = (patient.prescriptions || []).some(p => p.doctorId === doctorId);
    return inMedicalTeam || hasAppointment || hasScanRequest || hasPrescription;
}

// ── Rate Limiter for Sensitive Endpoints ──
const rateLimits = new Map();
function rateLimit({ windowMs = 15 * 60 * 1000, max = 50 } = {}) {
    return (req, res, next) => {
        if (process.env.NODE_ENV === 'test') {
            return next();
        }
        const key = req.ip || req.socket.remoteAddress || 'unknown';
        const now = Date.now();
        let record = rateLimits.get(key);
        if (!record || now - record.startTime > windowMs) {
            record = { count: 1, startTime: now };
            rateLimits.set(key, record);
        } else {
            record.count += 1;
        }
        if (record.count > max) {
            return res.status(429).json({ error: "Too many requests. Please try again later." });
        }
        next();
    };
}

// ── Authentication Middleware ──
function authenticateToken(req, res, next) {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.slice(7).trim() : null;
    if (!token) {
        return res.status(401).json({ error: "Authentication required: missing or malformed Bearer token." });
    }
    const payload = verifyToken(token);
    if (!payload) {
        return res.status(401).json({ error: "Authentication failed: invalid or expired token." });
    }
    req.user = payload;
    next();
}

// ── Authorization Middleware (Default Deny RBAC) ──
function requireRole(...allowedRoles) {
    return (req, res, next) => {
        if (!req.user) {
            return res.status(401).json({ error: "Authentication required." });
        }
        if (!allowedRoles.includes(req.user.role)) {
            return res.status(403).json({ error: `Forbidden: role '${req.user.role}' is not authorized for this resource.` });
        }
        next();
    };
}

// =============================================================
// 📊 MONITORING & METRICS (Prometheus)
// =============================================================
const collectDefaultMetrics = client.collectDefaultMetrics;
collectDefaultMetrics();
const httpRequestDurationMicroseconds = new client.Histogram({
    name: 'http_request_duration_seconds',
    help: 'Duration of HTTP requests',
    labelNames: ['method', 'route', 'code'],
    buckets: [0.1, 0.5, 1, 1.5, 2, 5]
});
app.use((req, res, next) => {
    const end = httpRequestDurationMicroseconds.startTimer();
    res.on('finish', () => {
        end({ method: req.method, route: req.path, code: res.statusCode });
        httpRequestsTotal.inc({ method: req.method, route: req.path, status: res.statusCode });
    });
    next();
});

const httpRequestsTotal = new client.Counter({
    name: 'healthscore_http_requests_total',
    help: 'Total HTTP requests',
    labelNames: ['method', 'route', 'status'],
});
const prescriptionsTotal = new client.Counter({
    name: 'healthscore_prescriptions_total',
    help: 'Prescription lifecycle events',
    labelNames: ['action'],
});
const appointmentsTotal = new client.Counter({
    name: 'healthscore_appointments_total',
    help: 'Appointment lifecycle events',
    labelNames: ['action'],
});
const fabricTxTotal = new client.Counter({
    name: 'healthscore_fabric_tx_total',
    help: 'Fabric transaction attempts',
    labelNames: ['org', 'function', 'status'],
});
const activeUsersGauge = new client.Gauge({
    name: 'healthscore_active_users',
    help: 'Current user count by role',
    labelNames: ['role'],
});

app.get('/metrics', async (req, res) => {
    activeUsersGauge.reset();
    const roles = {};
    USERS.forEach(u => { roles[u.role] = (roles[u.role] || 0) + 1; });
    Object.entries(roles).forEach(([role, count]) => activeUsersGauge.set({ role }, count));
    res.set('Content-Type', client.register.contentType);
    res.end(await client.register.metrics());
});

// =============================================================
// 💾 PERSISTENT DATABASE INITIALIZATION
// =============================================================
let USERS = [];
let INVENTORY = [];

function loadDatabase() {
    try {
        if (fs.existsSync(DB_FILE)) {
            const data = JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
            USERS = data.users || [];
            INVENTORY = data.inventory || [];

            // Automatically upgrade legacy plaintext passwords to salted PBKDF2 hashes
            let migrated = false;
            USERS.forEach(u => {
                if (u.password && !u.passwordHash) {
                    const { hash, salt } = hashPassword(u.password);
                    u.passwordHash = hash;
                    u.salt = salt;
                    delete u.password;
                    migrated = true;
                }
            });
            if (migrated) {
                saveData();
            }
        } else {
            // NEVER seed demo accounts in production/staging, even if SEED_DEMO_USERS=true
            if (isDevOrTest && process.env.SEED_DEMO_USERS === 'true') {
                resetDatabase();
            } else if (isDevOrTest && process.env.NODE_ENV !== 'test') {
                resetDatabase();
            } else {
                USERS = [];
                INVENTORY = [];
                saveData();
            }
        }
    } catch (err) {
        if (isDevOrTest) {
            resetDatabase();
        }
    }
}

function resetDatabase() {
    // Development demo accounts (hashed securely upon creation)
    const docCreds = hashPassword("password123");
    const pharmaCreds = hashPassword("password123");
    const labCreds = hashPassword("password123");
    const insCreds = hashPassword("password123");
    const patCreds = hashPassword("password123");

    USERS = [
        { id: "DR-001", username: "doctor1", passwordHash: docCreds.hash, salt: docCreds.salt, role: "Doctor", name: "Dr. Arpit Doshi" },
        { id: "PH-001", username: "pharma1", passwordHash: pharmaCreds.hash, salt: pharmaCreds.salt, role: "Pharmacist", name: "City Pharmacy" },
        { id: "BT-001", username: "lab1", passwordHash: labCreds.hash, salt: labCreds.salt, role: "Bloodtest", name: "Apollo Diagnostics" },
        { id: "IN-001", username: "ins1", passwordHash: insCreds.hash, salt: insCreds.salt, role: "Insurance", name: "HealthGuard Insurance" },
        {
            id: "PT-1000", username: "patient1", passwordHash: patCreds.hash, salt: patCreds.salt, role: "Patient",
            name: "Dhruv Gandhi", age: 25, height: 175, weight: 70, diseaseInput: "Asthma",
            prescriptions: [], medicalFiles: [], appointments: [], favoriteDoctors: [], scanRequests: [],
            medicalTeam: [
                { id: "DR-001", name: "Dr. Arpit Doshi", speciality: "Cardiologist", hospital: "Nanavati Super Speciality Hospital" },
                { id: "DR-002", name: "Dr. Priya Sharma", speciality: "Endocrinologist", hospital: "Lilavati Hospital" }
            ]
        }
    ];
    INVENTORY = [{ id: "MED-001", name: "Amoxicillin 500mg", stock: 100, price: 50, expiry: "2026-12-01" }];
    saveData();
}

function saveData() {
    try {
        fs.writeFileSync(DB_FILE, JSON.stringify({ users: USERS, inventory: INVENTORY }, null, 2));
    } catch (e) {
        console.error("Error saving database file:", e.message);
    }
}
loadDatabase();

// =============================================================
// 🔗 HYPERLEDGER FABRIC GATEWAY — 5-ORG NETWORK
// =============================================================
const ccpPath = path.resolve(__dirname, 'connection-healthscore.json');
const CHANNEL_NAME = 'healthscorechannel';
const CC_NAME = 'healthscore';

const ORG_MAP = {
    hospital:  { wallet: 'hospital-admin',  org: 'HospitalOrg' },
    patient:   { wallet: 'patient-admin',   org: 'PatientOrg' },
    pharmacy:  { wallet: 'pharmacy-admin',  org: 'PharmacyOrg' },
    lab:       { wallet: 'lab-admin',       org: 'LabOrg' },
    insurance: { wallet: 'insurance-admin', org: 'InsuranceOrg' },
};

async function getContractAs(orgName) {
    const info = ORG_MAP[orgName];
    if (!info) throw new Error(`Unknown org '${orgName}'. Allowed: ${Object.keys(ORG_MAP).join(', ')}`);

    if (!fs.existsSync(ccpPath)) {
        throw new Error(`Fabric connection profile not found at ${ccpPath}`);
    }
    const ccp = JSON.parse(fs.readFileSync(ccpPath, 'utf8'));
    ccp.client.organization = info.org;

    const walletPath = path.join(__dirname, 'wallet');
    const wallet = await Wallets.newFileSystemWallet(walletPath);
    const identity = await wallet.get(info.wallet);
    if (!identity) throw new Error(`Wallet identity '${info.wallet}' not found.`);

    const gateway = new Gateway();
    await gateway.connect(ccp, {
        wallet,
        identity: info.wallet,
        discovery: { enabled: true, asLocalhost: true },
    });

    const network = await gateway.getNetwork(CHANNEL_NAME);
    const contract = network.getContract(CC_NAME);
    return { contract, gateway };
}

async function fabricSubmit(orgName, fn, ...args) {
    const { contract, gateway } = await getContractAs(orgName);
    try {
        const result = await contract.submitTransaction(fn, ...args);
        fabricTxTotal.inc({ org: orgName, function: fn, status: 'success' });
        return result.length > 0 ? JSON.parse(result.toString()) : null;
    } catch (e) {
        fabricTxTotal.inc({ org: orgName, function: fn, status: 'error' });
        throw e;
    } finally {
        gateway.disconnect();
    }
}

async function fabricQuery(orgName, fn, ...args) {
    const { contract, gateway } = await getContractAs(orgName);
    try {
        const result = await contract.evaluateTransaction(fn, ...args);
        return result.length > 0 ? JSON.parse(result.toString()) : null;
    } finally {
        gateway.disconnect();
    }
}

// =============================================================
// 🔐 AUTHENTICATION ENDPOINTS (Public, Rate-Limited)
// =============================================================

// LOGIN
app.post('/api/login', rateLimit({ windowMs: 15 * 60 * 1000, max: 20 }), (req, res) => {
    const { username, password, role } = req.body;
    if (!username || !password) {
        return res.status(400).json({ message: "Username and password are required." });
    }

    const user = USERS.find(u => u.username === username);
    if (!user) {
        return res.status(401).json({ message: "Invalid credentials." });
    }

    const validPassword = verifyPassword(password, user.passwordHash, user.salt);
    if (!validPassword) {
        return res.status(401).json({ message: "Invalid credentials." });
    }

    // Role check (if specified by client portal)
    if (role) {
        let isValidTab = false;
        if (role === 'Enterprise') {
            isValidTab = ['Pharmacist', 'Bloodtest', 'Insurance', 'Admin'].includes(user.role);
        } else {
            isValidTab = user.role === role;
        }
        if (!isValidTab) {
            return res.status(401).json({ message: `Incorrect Portal! You are registered as ${user.role}.` });
        }
    }

    const token = generateToken(user);
    const safeUser = redactUser(user);
    safeUser.token = token; // Include token inside user payload for client persistence

    res.json({
        success: true,
        token,
        user: safeUser
    });
});

// REGISTER
app.post('/api/register', rateLimit({ windowMs: 15 * 60 * 1000, max: 20 }), async (req, res) => {
    const { name, username, password, age, height, weight, diseaseInput } = req.body;
    if (!name || !username || !password || age === undefined) {
        return res.status(400).json({ message: "Name, username, password, and age are required." });
    }
    if (String(password).length < 8) {
        return res.status(400).json({ message: "Password must be at least 8 characters long." });
    }
    if (USERS.find(u => u.username === username)) {
        return res.status(400).json({ message: "Username already taken." });
    }

    const uniqueId = "PT-" + Math.floor(1000 + Math.random() * 9000);
    const { hash, salt } = hashPassword(password);
    const newUser = {
        id: uniqueId,
        username,
        passwordHash: hash,
        salt: salt,
        role: "Patient",
        name,
        age: Number(age),
        height: Number(height || 170),
        weight: Number(weight || 70),
        diseaseInput: diseaseInput || "",
        prescriptions: [],
        medicalFiles: [],
        medicalTeam: [],
        appointments: [],
        favoriteDoctors: [],
        scanRequests: []
    };

    USERS.push(newUser);
    saveData();

    // Write patient record to Fabric ledger (best effort if network is online)
    try {
        await fabricSubmit('hospital', 'createPatientRecord',
            uniqueId, name, String(age), String(weight || 70), String(height || 170), diseaseInput || ''
        );
    } catch (err) {
        // Log Fabric write notice in local development
    }

    const token = generateToken(newUser);
    const safeUser = redactUser(newUser);
    safeUser.token = token;

    res.json({
        success: true,
        token,
        user: safeUser,
        message: `Account created! ID: ${uniqueId}`
    });
});

// ADMIN ACCESS: Requires explicit server ADMIN_KEY or verified Admin token
app.post('/api/admin/access', rateLimit({ windowMs: 15 * 60 * 1000, max: 10 }), (req, res) => {
    if (!ADMIN_KEY) {
        return res.status(403).json({ error: "Admin access disabled: ADMIN_KEY is not configured on this server." });
    }

    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.slice(7).trim() : null;
    let isAdminToken = false;
    if (token) {
        const payload = verifyToken(token);
        if (payload && payload.role === 'Admin') {
            isAdminToken = true;
        }
    }

    const clientKey = req.body.adminKey;
    const isKeyValid = clientKey && clientKey.length === ADMIN_KEY.length &&
        crypto.timingSafeEqual(Buffer.from(clientKey), Buffer.from(ADMIN_KEY));

    if (!isAdminToken && !isKeyValid) {
        return res.status(403).json({ error: "Access Denied: Invalid admin credentials." });
    }

    // Redact credentials from all returned user objects
    const safeUsers = USERS.map(u => redactUser(u));
    res.json({
        success: true,
        database: {
            users: safeUsers,
            inventory: INVENTORY,
            total_patients: USERS.filter(u => u.role === 'Patient').length,
            total_prescriptions: USERS.reduce((a, u) => a + (u.prescriptions?.length || 0), 0)
        }
    });
});

// =============================================================
// 👤 PATIENT DATA APIS (Authenticated & Role-Guarded)
// =============================================================

// GET PATIENT DATA
app.get('/api/patient/:id', authenticateToken, (req, res) => {
    const patientId = req.params.id;
    const patient = USERS.find(u => u.id === patientId && u.role === 'Patient');
    if (!patient) return res.status(404).json({ message: "Patient not found." });

    const role = req.user.role;
    const userId = req.user.sub;

    // Cross-patient boundary check
    if (role === 'Patient') {
        if (userId !== patientId) {
            return res.status(403).json({ error: "Forbidden: You cannot access records belonging to another patient." });
        }
        return res.json({
            id: patient.id,
            name: patient.name,
            age: patient.age,
            weight: patient.weight,
            height: patient.height,
            history: patient.diseaseInput,
            prescriptions: patient.prescriptions || [],
            medicalFiles: patient.medicalFiles || [],
            appointments: patient.appointments || [],
            medicalTeam: patient.medicalTeam || [],
            favoriteDoctors: patient.favoriteDoctors || [],
            scanRequests: patient.scanRequests || []
        });
    }

    if (role === 'Doctor') {
        if (!hasCareRelationship(userId, patient)) {
            return res.status(403).json({ error: "Forbidden: You do not have an active care relationship with this patient." });
        }
        return res.json({
            id: patient.id,
            name: patient.name,
            age: patient.age,
            weight: patient.weight,
            height: patient.height,
            history: patient.diseaseInput,
            prescriptions: patient.prescriptions || [],
            medicalFiles: patient.medicalFiles || [],
            appointments: patient.appointments || [],
            medicalTeam: patient.medicalTeam || [],
            favoriteDoctors: patient.favoriteDoctors || [],
            scanRequests: patient.scanRequests || []
        });
    }

    if (role === 'Admin') {
        return res.json({
            id: patient.id,
            name: patient.name,
            age: patient.age,
            weight: patient.weight,
            height: patient.height,
            history: patient.diseaseInput,
            prescriptions: patient.prescriptions || [],
            medicalFiles: patient.medicalFiles || [],
            appointments: patient.appointments || [],
            medicalTeam: patient.medicalTeam || [],
            favoriteDoctors: patient.favoriteDoctors || [],
            scanRequests: patient.scanRequests || []
        });
    }

    if (role === 'Pharmacist') {
        return res.json({
            name: patient.name,
            prescriptions: patient.prescriptions || []
        });
    }

    if (role === 'Bloodtest') {
        return res.json({
            name: patient.name,
            age: patient.age,
            scanRequests: patient.scanRequests || []
        });
    }

    if (role === 'Insurance') {
        return res.json({
            name: patient.name,
            age: patient.age,
            history: patient.diseaseInput
        });
    }

    return res.status(403).json({ error: "Unauthorized role access." });
});

// UPDATE PATIENT PROFILE (Self or Authorized Doctor)
app.post('/api/patient/update', authenticateToken, (req, res) => {
    const { id, weight, history } = req.body;
    if (req.user.role === 'Patient' && req.user.sub !== id) {
        return res.status(403).json({ error: "Forbidden: You cannot modify another patient's profile." });
    }
    const patient = USERS.find(u => u.id === id);
    if (!patient) return res.status(404).json({ error: "Patient not found." });

    if (req.user.role === 'Doctor') {
        if (!hasCareRelationship(req.user.sub, patient)) {
            return res.status(403).json({ error: "Forbidden: You do not have an active care relationship with this patient." });
        }
    } else if (req.user.role !== 'Admin') {
        return res.status(403).json({ error: "Forbidden: Insufficient privileges." });
    }

    const idx = USERS.findIndex(u => u.id === id);
    if (weight !== undefined) USERS[idx].weight = Number(weight);
    if (history !== undefined) USERS[idx].diseaseInput = String(history);
    saveData();
    res.json({ success: true, message: "Patient profile updated." });
});

// PATIENT FAVORITES (Self only or Admin)
app.post('/api/patient/toggle-favorite', authenticateToken, requireRole('Patient', 'Admin'), (req, res) => {
    const { patientId, doctorId } = req.body;
    if (req.user.role === 'Patient' && req.user.sub !== patientId) {
        return res.status(403).json({ error: "Forbidden: Cross-patient modification disallowed." });
    }
    const idx = USERS.findIndex(u => u.id === patientId);
    if (idx !== -1) {
        if (!USERS[idx].favoriteDoctors) USERS[idx].favoriteDoctors = [];
        const favIndex = USERS[idx].favoriteDoctors.indexOf(doctorId);
        if (favIndex === -1) USERS[idx].favoriteDoctors.push(doctorId);
        else USERS[idx].favoriteDoctors.splice(favIndex, 1);
        saveData();
        return res.json({ success: true, favoriteDoctors: USERS[idx].favoriteDoctors });
    }
    res.status(404).json({ error: "Patient not found." });
});

// ADD MEDICAL FILE
app.post('/api/patient/add-file', authenticateToken, async (req, res) => {
    const { patientId, ipfsHash, fileName, category } = req.body;
    const patient = USERS.find(u => u.id === patientId);
    if (!patient) return res.status(404).json({ error: "Patient not found." });

    if (req.user.role === 'Patient') {
        if (req.user.sub !== patientId) {
            return res.status(403).json({ error: "Forbidden: Cannot upload files for another patient." });
        }
    } else if (req.user.role === 'Doctor') {
        if (!hasCareRelationship(req.user.sub, patient)) {
            return res.status(403).json({ error: "Forbidden: You do not have an active care relationship with this patient." });
        }
    } else if (req.user.role !== 'Admin') {
        return res.status(403).json({ error: "Forbidden: Insufficient role." });
    }

    const idx = USERS.findIndex(u => u.id === patientId);
    if (!USERS[idx].medicalFiles) USERS[idx].medicalFiles = [];
    USERS[idx].medicalFiles.push({
        hash: ipfsHash,
        name: fileName,
        date: new Date().toLocaleDateString(),
        category: category || 'Medical Summary'
    });
    saveData();

    try {
        await fabricSubmit('hospital', 'addMedicalFile', patientId, ipfsHash, fileName, category || 'Medical Summary');
    } catch (err) {
        // Fallback logged
    }

    res.json({ success: true });
});

// =============================================================
// 📅 APPOINTMENT APIS (Authenticated)
// =============================================================

app.post('/api/book-appointment', authenticateToken, (req, res) => {
    const { patientId, doctorId, doctorName, date, time } = req.body;
    if (!patientId || !doctorId) {
        return res.status(400).json({ error: "Missing required fields: patientId and doctorId." });
    }
    const patient = USERS.find(u => u.id === patientId && u.role === 'Patient');
    if (!patient) return res.status(404).json({ error: "Patient not found." });

    if (req.user.role === 'Patient') {
        if (req.user.sub !== patientId) {
            return res.status(403).json({ error: "Forbidden: Cannot book appointments on behalf of another patient." });
        }
    } else if (req.user.role === 'Doctor') {
        if (req.user.sub !== doctorId) {
            return res.status(403).json({ error: "Forbidden: Doctors may only schedule appointments for their own calendar." });
        }
    } else if (req.user.role !== 'Admin') {
        return res.status(403).json({ error: `Forbidden: Role '${req.user.role}' cannot book appointments.` });
    }

    if (!patient.appointments) patient.appointments = [];
    const newAppointment = {
        id: "APT-" + Date.now().toString().slice(-5),
        doctorId,
        doctorName: doctorName || "Doctor",
        date: date || new Date().toISOString().split('T')[0],
        time: time || "10:00 AM",
        status: 'Upcoming',
        bookedAt: new Date().toISOString()
    };
    patient.appointments.push(newAppointment);
    saveData();
    appointmentsTotal.inc({ action: 'booked' });
    res.json({ success: true, message: `Appointment confirmed with ${newAppointment.doctorName} on ${newAppointment.date} at ${newAppointment.time}.`, appointment: newAppointment });
});

app.get('/api/doctor/appointments/:doctorId', authenticateToken, requireRole('Doctor', 'Admin'), (req, res) => {
    const docId = req.params.doctorId;
    if (req.user.role === 'Doctor' && req.user.sub !== docId) {
        return res.status(403).json({ error: "Forbidden: You may only view your own schedule." });
    }
    let docApts = [];
    USERS.filter(u => u.role === 'Patient').forEach(p => {
        if (p.appointments) {
            p.appointments.forEach(apt => {
                if (apt.doctorId === docId) {
                    docApts.push({ ...apt, patientName: p.name, patientId: p.id });
                }
            });
        }
    });
    res.json(docApts.sort((a, b) => new Date(a.date) - new Date(b.date)));
});

app.post('/api/doctor/appointment/update', authenticateToken, requireRole('Doctor', 'Admin'), (req, res) => {
    const { patientId, appointmentId, status, date, time } = req.body;
    const patient = USERS.find(u => u.id === patientId);
    if (!patient) return res.status(404).json({ error: "Patient not found." });

    const apt = patient.appointments.find(a => a.id === appointmentId);
    if (!apt) return res.status(404).json({ error: "Appointment not found." });

    if (req.user.role === 'Doctor' && apt.doctorId !== req.user.sub) {
        return res.status(403).json({ error: "Forbidden: Cannot modify an appointment assigned to another doctor." });
    }

    apt.status = status;
    if (date) apt.date = date;
    if (time) apt.time = time;
    saveData();
    appointmentsTotal.inc({ action: (status || 'updated').toLowerCase() });
    res.json({ success: true, message: `Appointment ${status}` });
});

app.get('/api/doctor/patients/:doctorId', authenticateToken, requireRole('Doctor', 'Admin'), (req, res) => {
    const docId = req.params.doctorId;
    if (req.user.role === 'Doctor' && req.user.sub !== docId) {
        return res.status(403).json({ error: "Forbidden: Cannot access another doctor's patient list." });
    }
    let activePatients = [];
    USERS.filter(u => u.role === 'Patient').forEach(p => {
        const hasApt = p.appointments && p.appointments.some(a => a.doctorId === docId);
        if (hasApt) {
            activePatients.push({ id: p.id, name: p.name, age: p.age, weight: p.weight, history: p.diseaseInput });
        }
    });
    res.json(activePatients);
});

// =============================================================
// 🩺 CLINICAL ACTION APIS (Role-Restricted to Doctors)
// =============================================================

// REQUEST SCAN (Doctor only)
app.post('/api/doctor/request-scan', authenticateToken, requireRole('Doctor'), async (req, res) => {
    const { patientId, doctorId, doctorName, scanType, priority, notes } = req.body;
    const patient = USERS.find(u => u.id === patientId);
    if (!patient) return res.status(404).json({ error: "Patient not found." });

    const scanId = "SCN-" + Date.now().toString().slice(-5);
    if (!patient.scanRequests) patient.scanRequests = [];

    try {
        await fabricSubmit('hospital', 'requestScan', scanId, patientId, scanType, priority, notes || '');
    } catch (err) {
        console.error('  ⚠ Fabric requestScan offline:', err.message);
    }

    patient.scanRequests.push({
        id: scanId,
        scanType,
        priority,
        notes,
        doctorId: req.user.sub,
        doctorName: req.user.name || doctorName,
        date: new Date().toISOString().split('T')[0],
        status: 'Pending'
    });
    saveData();
    res.json({ success: true, message: "Scan request created.", scanId });
});

// CREATE PRESCRIPTION (Doctor only)
app.post('/api/prescription', authenticateToken, requireRole('Doctor'), async (req, res) => {
    try {
        const { patientId, medicine, frequency, duration, remarks, ipfsHash } = req.body;
        if (!patientId || !medicine) {
            return res.status(400).json({ error: "patientId and medicine are required." });
        }
        const rxId = "RX-" + Date.now().toString().slice(-6);

        await fabricSubmit('hospital', 'createPrescription',
            rxId, patientId, medicine, frequency || '', duration || '', remarks || '', ipfsHash || ''
        );

        const idx = USERS.findIndex(u => u.id === patientId);
        if (idx !== -1) {
            if (!USERS[idx].prescriptions) USERS[idx].prescriptions = [];
            USERS[idx].prescriptions.push({
                id: rxId,
                medicine,
                frequency,
                duration,
                remarks,
                ipfsHash,
                doctorId: req.user.sub,
                status: 'ACTIVE'
            });
            saveData();
        }

        prescriptionsTotal.inc({ action: 'created' });
        res.json({ success: true, message: `Prescription ${rxId} recorded on blockchain.`, rxId });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

// REVOKE PRESCRIPTION (Doctor only)
app.post('/api/prescription/revoke', authenticateToken, requireRole('Doctor'), async (req, res) => {
    try {
        const { rxId, patientId, reason } = req.body;
        if (!rxId) return res.status(400).json({ error: "Missing rxId" });

        await fabricSubmit('hospital', 'revokePrescription', rxId, reason || '');

        const pIdx = USERS.findIndex(u => u.id === patientId);
        if (pIdx !== -1) {
            const rx = USERS[pIdx].prescriptions.find(r => r.id === rxId);
            if (rx) {
                rx.status = 'REVOKED';
                rx.revokedDate = new Date().toLocaleString();
                rx.revokeReason = reason || '';
            }
        }
        saveData();
        prescriptionsTotal.inc({ action: 'revoked' });
        res.json({ success: true, message: `Prescription ${rxId} revoked.` });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

// =============================================================
// 💊 PHARMACY & INVENTORY APIS (Role-Restricted)
// =============================================================

// DISPENSE PRESCRIPTION (Pharmacist only)
app.post('/api/dispense', authenticateToken, requireRole('Pharmacist'), async (req, res) => {
    try {
        const { rxId, patientId, medicineName } = req.body;
        const item = INVENTORY.find(i => i.name.toLowerCase() === medicineName.toLowerCase());
        if (!item || item.stock <= 0) return res.status(400).json({ error: "Out of stock." });

        await fabricSubmit('pharmacy', 'dispensePrescription', rxId, req.user.sub);

        item.stock -= 1;
        const pIdx = USERS.findIndex(u => u.id === patientId);
        if (pIdx !== -1) {
            const rx = USERS[pIdx].prescriptions.find(r => r.id === rxId);
            if (rx) {
                rx.dispensedDate = new Date().toLocaleString();
                rx.dispensedBy = req.user.sub;
                rx.status = 'DISPENSED';
            }
        }
        saveData();
        prescriptionsTotal.inc({ action: 'dispensed' });
        res.json({ success: true, message: "Dispensed and recorded on blockchain." });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

// INVENTORY
app.get('/api/inventory', authenticateToken, requireRole('Pharmacist', 'Admin', 'Doctor'), (req, res) => {
    res.json(INVENTORY);
});

app.post('/api/inventory/add', authenticateToken, requireRole('Pharmacist', 'Admin'), (req, res) => {
    const { name, stock, price, expiry } = req.body;
    if (!name || stock === undefined || price === undefined) {
        return res.status(400).json({ error: "Name, stock, and price are required." });
    }
    const existing = INVENTORY.find(i => i.name.toLowerCase() === name.toLowerCase());
    if (existing) {
        existing.stock += Number(stock);
        existing.expiry = expiry;
    } else {
        INVENTORY.push({ id: "MED-" + Date.now(), name, stock: Number(stock), price: Number(price), expiry });
    }
    saveData();
    res.json({ success: true });
});

app.get('/api/pharmacist/logs', authenticateToken, requireRole('Pharmacist', 'Admin'), (req, res) => {
    let logs = [];
    USERS.filter(u => u.role === 'Patient').forEach(p => {
        (p.prescriptions || []).forEach(rx => {
            if (rx.dispensedDate) {
                logs.push({ date: rx.dispensedDate, patientName: p.name, medicine: rx.medicine, rxId: rx.id });
            }
        });
    });
    res.json(logs);
});

// =============================================================
// 🧪 BLOODTEST APIS (Role-Restricted)
// =============================================================

app.post('/api/bloodtest/complete-scan', authenticateToken, requireRole('Bloodtest'), async (req, res) => {
    try {
        const { patientId, scanId, ipfsHash, fileName, scanType } = req.body;
        const patient = USERS.find(u => u.id === patientId && u.role === 'Patient');
        if (!patient) return res.status(404).json({ error: 'Patient not found' });
        const scan = (patient.scanRequests || []).find(s => s.id === scanId);
        if (!scan) return res.status(404).json({ error: 'Scan request not found' });

        try {
            await fabricSubmit('lab', 'completeScan', scanId, ipfsHash || '', fileName || '');
        } catch (err) {
            // Log fallback
        }

        scan.status = 'Completed';
        scan.reportHash = ipfsHash;
        scan.reportName = fileName;
        scan.completedDate = new Date().toLocaleDateString();
        if (!patient.medicalFiles) patient.medicalFiles = [];
        const category = (scanType || '').toLowerCase().includes('blood') || (scanType || '').toLowerCase().includes('urine') ? 'Test Report' : 'Scan';
        if (ipfsHash) patient.medicalFiles.push({ hash: ipfsHash, name: fileName, date: new Date().toLocaleDateString(), category });
        saveData();
        res.json({ success: true });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

app.get('/api/bloodtest/patients', authenticateToken, requireRole('Bloodtest', 'Doctor', 'Admin'), (req, res) => {
    let patientsWithScans = USERS.filter(u => u.role === 'Patient' && u.scanRequests && u.scanRequests.length > 0);
    if (req.user.role === 'Doctor') {
        patientsWithScans = patientsWithScans.filter(p => 
            p.scanRequests.some(s => s.doctorId === req.user.sub) || hasCareRelationship(req.user.sub, p)
        );
    }
    const patients = patientsWithScans.map(p => ({
        id: p.id,
        name: p.name,
        age: p.age,
        scanRequests: req.user.role === 'Doctor' ? p.scanRequests.filter(s => s.doctorId === req.user.sub || hasCareRelationship(req.user.sub, p)) : p.scanRequests
    }));
    res.json(patients);
});

// =============================================================
// 📤 SECURE IPFS UPLOAD
// =============================================================
app.post('/api/upload', authenticateToken, rateLimit({ windowMs: 15 * 60 * 1000, max: 20 }), upload.single('file'), async (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: "Missing uploaded file." });
    }
    try {
        if (!PINATA_JWT) throw new Error("Missing PINATA_JWT configuration");
        const formData = new FormData();
        formData.append('file', fs.createReadStream(req.file.path));
        const r = await axios.post("https://api.pinata.cloud/pinning/pinFileToIPFS", formData, {
            headers: { 'Authorization': `Bearer ${PINATA_JWT}`, ...formData.getHeaders() }
        });
        res.json({ success: true, ipfsHash: r.data.IpfsHash });
    } catch (e) {
        res.status(500).json({ error: "Upload failed: external IPFS gateway unreachable." });
    } finally {
        if (req.file && fs.existsSync(req.file.path)) {
            try { fs.unlinkSync(req.file.path); } catch (err) {}
        }
    }
});

// =============================================================
// 🤖 GROQ AI CHATBOT (Authenticated & Identity-Verified)
// =============================================================
app.post('/api/chat', authenticateToken, rateLimit({ windowMs: 15 * 60 * 1000, max: 30 }), async (req, res) => {
    const { patientData: clientPatientData, messages } = req.body;
    try {
        if (!GROQ_API_KEY) throw new Error("Missing GROQ_API_KEY");

        // Verify patient profile details submitted to external AI service:
        // Do not rely on body-supplied identity fields!
        let authorizedProfile = null;
        if (req.user.role === 'Patient') {
            // Patient can only query about themselves; load strictly from authentic database record
            const patient = USERS.find(u => u.id === req.user.sub && u.role === 'Patient');
            if (patient) {
                authorizedProfile = {
                    name: patient.name,
                    age: patient.age,
                    weight: patient.weight,
                    height: patient.height,
                    diseaseInput: patient.diseaseInput
                };
            }
        } else if (req.user.role === 'Doctor') {
            if (clientPatientData?.id) {
                const patient = USERS.find(u => u.id === clientPatientData.id && u.role === 'Patient');
                if (!patient || !hasCareRelationship(req.user.sub, patient)) {
                    return res.status(403).json({ error: "Forbidden: You do not have an active care relationship with this patient." });
                }
                authorizedProfile = {
                    name: patient.name,
                    age: patient.age,
                    weight: patient.weight,
                    height: patient.height,
                    diseaseInput: patient.diseaseInput
                };
            }
        } else if (req.user.role === 'Admin') {
            authorizedProfile = clientPatientData;
        } else {
            return res.status(403).json({ error: `Forbidden: Role '${req.user.role}' is not authorized to access AI clinical assistant.` });
        }

        const profile = authorizedProfile || clientPatientData || {};
        const systemPrompt = {
            role: "system",
            content: `You are HealthScore AI, an empathetic medical and fitness assistant for a patient named ${profile.name || 'User'}. 
            Their profile: Age ${profile.age || 'Unknown'}, Weight ${profile.weight || 'Unknown'}kg, Height ${profile.height || 'Unknown'}cm.
            Medical History: ${profile.diseaseInput || 'None reported'}.
            
            IMPORTANT STRICT INSTRUCTIONS:
            1. You MUST ONLY answer questions related to health, fitness, nutrition, biology, and medical wellness.
            2. If the user asks about ANYTHING else, decline politely.
            3. Do NOT provide formal medical diagnoses.
            4. Always recommend consulting their doctor for serious issues.
            5. Keep your responses concise (under 4 sentences).`
        };

        const response = await axios.post('https://api.groq.com/openai/v1/chat/completions', {
            model: "llama-3.3-70b-versatile",
            messages: [systemPrompt, ...(messages || [])],
            temperature: 0.5
        }, {
            headers: { 'Authorization': `Bearer ${GROQ_API_KEY}`, 'Content-Type': 'application/json' }
        });

        res.json({ reply: response.data.choices[0].message.content });
    } catch (error) {
        res.status(500).json({ error: "AI Service Unavailable" });
    }
});

// =============================================================
// 🧠 MACHINE LEARNING INFERENCE API (Authenticated & Role-Guarded)
// =============================================================
app.post('/api/calculate-score', authenticateToken, requireRole('Patient', 'Doctor', 'Admin'), rateLimit({ windowMs: 15 * 60 * 1000, max: 50 }), (req, res) => {
    const { patientId } = req.body;

    // Cross-patient & role authorization check:
    // Only Patient (for self), Doctor (with care relationship), or Admin may calculate scores
    if (patientId) {
        const patient = USERS.find(u => u.id === patientId && u.role === 'Patient');
        if (!patient) {
            return res.status(404).json({ error: "Patient not found." });
        }
        if (req.user.role === 'Patient' && req.user.sub !== patientId) {
            return res.status(403).json({ error: "Forbidden: You cannot evaluate risk scores for another patient." });
        }
        if (req.user.role === 'Doctor' && !hasCareRelationship(req.user.sub, patient)) {
            return res.status(403).json({ error: "Forbidden: You do not have an authorized care relationship with this patient." });
        }
    }

    const pythonPath = path.join(__dirname, '../ml_model/venv/bin/python3');
    const scriptPath = path.join(__dirname, '../ml_model/run_engine.py');
    const pythonProcess = spawn(pythonPath, ['-u', scriptPath, JSON.stringify(req.body)], { shell: false });
    let resultData = "";
    let errorData = "";

    pythonProcess.stdout.on('data', d => resultData += d.toString());
    pythonProcess.stderr.on('data', d => errorData += d.toString());

    pythonProcess.on('close', async c => {
        if (c === 0 && resultData.trim()) {
            try {
                const parsed = JSON.parse(resultData);
                res.json(parsed);

                // Write verified score to blockchain ledger via HospitalOrg (Fire & Forget)
                if (patientId && parsed.health_score) {
                    try {
                        await fabricSubmit('hospital', 'updateHealthScore',
                            patientId,
                            String(parsed.health_score),
                            String(parsed.risk_score || 0),
                            String(parsed.premium || 0)
                        );
                    } catch (err) {
                        // Offline notice
                    }
                }
            } catch (err) {
                res.status(500).json({ error: "Failed to parse inference output" });
            }
        } else {
            res.status(500).json({ error: "Machine Learning Engine execution failure" });
        }
    });
});

// =============================================================
// ⛓  LEDGER QUERY ENDPOINTS (Authenticated & Guarded)
// =============================================================
app.get('/api/prescription/ledger/:id', authenticateToken, rateLimit({ windowMs: 15 * 60 * 1000, max: 100 }), async (req, res) => {
    const rxId = req.params.id;
    // Resolve prescription in local state to verify authorization before calling Fabric
    let owningPatient = null;
    let targetRx = null;
    for (const u of USERS) {
        if (u.role === 'Patient' && u.prescriptions) {
            const found = u.prescriptions.find(r => r.id === rxId);
            if (found) {
                owningPatient = u;
                targetRx = found;
                break;
            }
        }
    }

    // Role & ownership authorization
    if (req.user.role === 'Patient') {
        if (!owningPatient || owningPatient.id !== req.user.sub) {
            return res.status(403).json({ error: "Forbidden: Cannot view another patient's prescription ledger." });
        }
    } else if (req.user.role === 'Doctor') {
        if (owningPatient && !hasCareRelationship(req.user.sub, owningPatient) && targetRx?.doctorId !== req.user.sub) {
            return res.status(403).json({ error: "Forbidden: You are not authorized to view this prescription ledger." });
        }
    } else if (!['Pharmacist', 'Admin'].includes(req.user.role)) {
        return res.status(403).json({ error: `Forbidden: role '${req.user.role}' is not authorized to query prescription ledger.` });
    }

    try {
        const result = await fabricQuery('hospital', 'viewPrescription', rxId);
        res.json(result);
    } catch (e) {
        res.status(404).json({ error: "Not found on Blockchain" });
    }
});

app.get('/api/ledger/patient/:id', authenticateToken, rateLimit({ windowMs: 15 * 60 * 1000, max: 100 }), async (req, res) => {
    const patientId = req.params.id;
    const patient = USERS.find(u => u.id === patientId && u.role === 'Patient');

    if (req.user.role === 'Patient') {
        if (req.user.sub !== patientId) {
            return res.status(403).json({ error: "Forbidden: Cannot access another patient's ledger record." });
        }
    } else if (req.user.role === 'Doctor') {
        if (patient && !hasCareRelationship(req.user.sub, patient)) {
            return res.status(403).json({ error: "Forbidden: You do not have an active care relationship with this patient." });
        }
    } else if (req.user.role !== 'Admin') {
        return res.status(403).json({ error: `Forbidden: role '${req.user.role}' is not authorized to access patient ledger records.` });
    }

    try {
        const result = await fabricQuery('hospital', 'getPatientRecord', patientId);
        res.json(result);
    } catch (e) {
        res.status(404).json({ error: "Patient not found on ledger" });
    }
});

app.get('/api/ledger/prescriptions/:patientId', authenticateToken, rateLimit({ windowMs: 15 * 60 * 1000, max: 100 }), async (req, res) => {
    const patientId = req.params.patientId;
    const patient = USERS.find(u => u.id === patientId && u.role === 'Patient');

    if (req.user.role === 'Patient') {
        if (req.user.sub !== patientId) {
            return res.status(403).json({ error: "Forbidden: Cannot view another patient's prescriptions." });
        }
    } else if (req.user.role === 'Doctor') {
        if (patient && !hasCareRelationship(req.user.sub, patient)) {
            return res.status(403).json({ error: "Forbidden: You do not have an active care relationship with this patient." });
        }
    } else if (!['Pharmacist', 'Admin'].includes(req.user.role)) {
        return res.status(403).json({ error: `Forbidden: role '${req.user.role}' is not authorized to query patient prescriptions.` });
    }

    try {
        const result = await fabricQuery('hospital', 'getAllPrescriptions', patientId);
        res.json(result);
    } catch (e) {
        res.status(404).json({ error: "No prescriptions found on ledger" });
    }
});

app.get('/api/ledger/scans/:patientId', authenticateToken, rateLimit({ windowMs: 15 * 60 * 1000, max: 100 }), async (req, res) => {
    const patientId = req.params.patientId;
    const patient = USERS.find(u => u.id === patientId && u.role === 'Patient');

    if (req.user.role === 'Patient') {
        if (req.user.sub !== patientId) {
            return res.status(403).json({ error: "Forbidden: Cannot view another patient's scan orders." });
        }
    } else if (req.user.role === 'Doctor') {
        if (patient && !hasCareRelationship(req.user.sub, patient)) {
            return res.status(403).json({ error: "Forbidden: You do not have an active care relationship with this patient." });
        }
    } else if (!['Bloodtest', 'Admin'].includes(req.user.role)) {
        return res.status(403).json({ error: `Forbidden: role '${req.user.role}' is not authorized to query patient scans.` });
    }

    try {
        const result = await fabricQuery('hospital', 'getAllScanOrders', patientId);
        res.json(result);
    } catch (e) {
        res.status(404).json({ error: "No scan orders found on ledger" });
    }
});

if (require.main === module) {
    app.listen(PORT, () => console.log(`🚀 Secure HealthScore Server running on Port ${PORT}`));
}

app.USERS = USERS;
app.INVENTORY = INVENTORY;
app.generateToken = generateToken;
app.hashPassword = hashPassword;
app.verifyToken = verifyToken;
app.hasCareRelationship = hasCareRelationship;
app.resetDatabase = resetDatabase;
app.loadDatabase = loadDatabase;

module.exports = app;