require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { Gateway, Wallets } = require('fabric-network');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const multer = require('multer');
const FormData = require('form-data');
const axios = require('axios');
const client = require('prom-client');

const app = express();
app.use(cors());
app.use(express.json());

// =============================================================
// 🛑 CONFIGURATION (Keys loaded from .env)
// =============================================================
const PINATA_JWT = process.env.PINATA_JWT;
const GROQ_API_KEY = process.env.GROQ_API_KEY;
const ADMIN_KEY = process.env.ADMIN_KEY || 'admin';
const PORT = process.env.PORT || 5001;

const DB_FILE = 'database.json';
const upload = multer({ dest: 'uploads/' });

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

// ── Custom HealthScore Metrics ──
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
    // Refresh user gauge on every scrape
    activeUsersGauge.reset();
    const roles = {};
    USERS.forEach(u => { roles[u.role] = (roles[u.role] || 0) + 1; });
    Object.entries(roles).forEach(([role, count]) => activeUsersGauge.set({ role }, count));
    res.set('Content-Type', client.register.contentType);
    res.end(await client.register.metrics());
});

// =============================================================
// 💾 PERSISTENT DATABASE INIT (local cache — Fabric is source of truth for medical data)
// =============================================================
let USERS = [];
let INVENTORY = [];

function loadDatabase() {
    try {
        if (fs.existsSync(DB_FILE)) {
            const data = JSON.parse(fs.readFileSync(DB_FILE));
            USERS = data.users || [];
            INVENTORY = data.inventory || [];
        } else {
            resetDatabase();
        }
    } catch (err) { resetDatabase(); }
}

function resetDatabase() {
    USERS = [
        { id: "DR-001", username: "doctor1", password: "password123", role: "Doctor", name: "Dr. Arpit Doshi" },

        // ENTERPRISE ACCOUNTS
        { id: "PH-001", username: "pharma1", password: "password123", role: "Pharmacist", name: "City Pharmacy" },
        { id: "BT-001", username: "lab1", password: "password123", role: "Bloodtest", name: "Apollo Diagnostics" },
        { id: "IN-001", username: "ins1", password: "password123", role: "Insurance", name: "HealthGuard Insurance" },

        {
            id: "PT-1000", username: "patient1", password: "password123", role: "Patient",
            name: "Dhruv Gandhi", age: 25, height: 175, weight: 70, diseaseInput: "Asthma",
            prescriptions: [], medicalFiles: [], appointments: [], favoriteDoctors: [], scanRequests: [],
            medicalTeam: [
                { id: "DR-001", name: "Dr. Arpit Doshi", speciality: "Cardiologist", hospital: "Nanavati Super Speciality Hospital" },
                { id: "DR-002", name: "Dr. Priya Sharma", speciality: "Endocrinologist", hospital: "Lilavati Hospital" },
                { id: "DR-003", name: "Dr. Anil Desai", speciality: "Orthopedic Surgeon", hospital: "Kokilaben Hospital" },
                { id: "DR-004", name: "Dr. Vikram Patel", speciality: "Neurologist", hospital: "Breach Candy Hospital" }
            ]
        }
    ];
    INVENTORY = [{ id: "MED-001", name: "Amoxicillin 500mg", stock: 100, price: 50, expiry: "2026-12-01" }];
    saveData();
}

function saveData() {
    try { fs.writeFileSync(DB_FILE, JSON.stringify({ users: USERS, inventory: INVENTORY }, null, 2)); } catch (e) { }
}
loadDatabase();

// =============================================================
// 🔗 HYPERLEDGER FABRIC GATEWAY — 5-ORG NETWORK
// =============================================================
const ccpPath = path.resolve(__dirname, 'connection-healthscore.json');
const CHANNEL_NAME = 'healthscorechannel';
const CC_NAME = 'healthscore';

// Org names → wallet label + connection profile org name
const ORG_MAP = {
    hospital:  { wallet: 'hospital-admin',  org: 'HospitalOrg' },
    patient:   { wallet: 'patient-admin',   org: 'PatientOrg' },
    pharmacy:  { wallet: 'pharmacy-admin',  org: 'PharmacyOrg' },
    lab:       { wallet: 'lab-admin',       org: 'LabOrg' },
    insurance: { wallet: 'insurance-admin', org: 'InsuranceOrg' },
};

/**
 * Connect to the Fabric gateway as a specific organisation.
 * Returns a { contract, gateway } pair. Caller MUST disconnect the gateway after use.
 */
async function getContractAs(orgName) {
    const info = ORG_MAP[orgName];
    if (!info) throw new Error(`Unknown org '${orgName}'. Allowed: ${Object.keys(ORG_MAP).join(', ')}`);

    const ccp = JSON.parse(fs.readFileSync(ccpPath, 'utf8'));
    // Override the client organisation so the gateway routes to the correct peer
    ccp.client.organization = info.org;

    const walletPath = path.join(__dirname, 'wallet');
    const wallet = await Wallets.newFileSystemWallet(walletPath);
    const identity = await wallet.get(info.wallet);
    if (!identity) throw new Error(`Wallet identity '${info.wallet}' not found. Run: node enrollAdmin.js`);

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

/**
 * Helper — execute a Fabric transaction and automatically disconnect
 */
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
// 📅 APPOINTMENT & DOCTOR APIs (off-chain — scheduling data)
// =============================================================
app.post('/api/book-appointment', (req, res) => {
    const { patientId, doctorId, doctorName, date, time } = req.body;
    const patientIndex = USERS.findIndex(u => u.id === patientId);

    if (patientIndex !== -1) {
        if (!USERS[patientIndex].appointments) USERS[patientIndex].appointments = [];
        const newAppointment = { id: "APT-" + Date.now().toString().slice(-5), doctorId, doctorName, date, time, status: 'Upcoming', bookedAt: new Date().toISOString() };
        USERS[patientIndex].appointments.push(newAppointment);
        saveData();
        res.json({ success: true, message: `Appointment confirmed with ${doctorName} on ${date} at ${time}.`, appointment: newAppointment });
        appointmentsTotal.inc({ action: 'booked' });
    } else {
        res.status(404).json({ error: "Patient not found." });
    }
});

app.get('/api/doctor/appointments/:doctorId', (req, res) => {
    const docId = req.params.doctorId;
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

app.post('/api/doctor/appointment/update', (req, res) => {
    const { patientId, appointmentId, status, date, time } = req.body;
    const patient = USERS.find(u => u.id === patientId);
    if (!patient) return res.status(404).json({ error: "Patient not found" });

    const apt = patient.appointments.find(a => a.id === appointmentId);
    if (!apt) return res.status(404).json({ error: "Appointment not found" });

    apt.status = status;
    if (date) apt.date = date;
    if (time) apt.time = time;
    saveData();
    appointmentsTotal.inc({ action: status.toLowerCase() });
    res.json({ success: true, message: `Appointment ${status}` });
});

app.get('/api/doctor/patients/:doctorId', (req, res) => {
    const docId = req.params.doctorId;
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
// 🩺 DOCTOR → REQUEST SCAN (On-chain via HospitalOrg)
// =============================================================
app.post('/api/doctor/request-scan', async (req, res) => {
    const { patientId, doctorId, doctorName, scanType, priority, notes } = req.body;
    const patient = USERS.find(u => u.id === patientId);
    if (!patient) return res.status(404).json({ error: "Patient not found" });

    const scanId = "SCN-" + Date.now().toString().slice(-5);
    if (!patient.scanRequests) patient.scanRequests = [];

    // Write to Fabric ledger via HospitalOrg
    try {
        await fabricSubmit('hospital', 'requestScan', scanId, patientId, scanType, priority, notes || '');
        console.log(`  ⛓  Scan ${scanId} recorded on ledger`);
    } catch (err) {
        console.error('  ⚠  Fabric requestScan failed (saving locally):', err.message);
    }

    // Always update local cache
    patient.scanRequests.push({
        id: scanId, scanType, priority, notes, doctorId, doctorName,
        date: new Date().toISOString().split('T')[0], status: 'Pending'
    });
    saveData();
    res.json({ success: true, message: "Scan request sent to patient." });
});

// =============================================================
// 🤖 GROQ AI CHATBOT (off-chain)
// =============================================================
app.post('/api/chat', async (req, res) => {
    const { patientData, messages } = req.body;
    try {
        if (!GROQ_API_KEY) throw new Error("Missing API Key");

        const systemPrompt = {
            role: "system",
            content: `You are HealthScore AI, an empathetic medical and fitness assistant for a patient named ${patientData.name}. 
            Their profile: Age ${patientData.age}, Weight ${patientData.weight}kg, Height ${patientData.height}cm. 
            Medical History: ${patientData.diseaseInput || 'None reported'}. 
            
            IMPORTANT STRICT INSTRUCTIONS:
            1. You MUST ONLY answer questions related to health, fitness, nutrition, biology, and medical wellness.
            2. If the user asks about ANYTHING else (e.g., coding, math, politics, movies, general trivia, etc.), you MUST decline politely by saying: "I am a specialized HealthScore AI assistant. I can only help you with questions related to your health, fitness, and wellness."
            3. Do NOT provide formal medical diagnoses.
            4. Always recommend consulting their doctor for serious issues.
            5. Keep your responses concise (under 4 sentences).`
        };

        const response = await axios.post('https://api.groq.com/openai/v1/chat/completions', {
            model: "llama-3.3-70b-versatile",
            messages: [systemPrompt, ...messages],
            temperature: 0.5
        }, {
            headers: { 'Authorization': `Bearer ${GROQ_API_KEY}`, 'Content-Type': 'application/json' }
        });

        res.json({ reply: response.data.choices[0].message.content });
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: "AI Error" });
    }
});

// =============================================================
// 🔐 CORE APIs (Auth, IPFS)
// =============================================================

// PATIENT FAVORITES (off-chain)
app.post('/api/patient/toggle-favorite', (req, res) => {
    const { patientId, doctorId } = req.body;
    const idx = USERS.findIndex(u => u.id === patientId);
    if (idx !== -1) {
        if (!USERS[idx].favoriteDoctors) USERS[idx].favoriteDoctors = [];
        const favIndex = USERS[idx].favoriteDoctors.indexOf(doctorId);
        if (favIndex === -1) USERS[idx].favoriteDoctors.push(doctorId);
        else USERS[idx].favoriteDoctors.splice(favIndex, 1);
        saveData();
        return res.json({ success: true, favoriteDoctors: USERS[idx].favoriteDoctors });
    }
    res.status(404).json({ error: "Patient not found" });
});

// ADMIN BACKDOOR
app.post('/api/admin/access', (req, res) => {
    if (req.body.adminKey !== ADMIN_KEY) return res.status(403).json({ error: "DENIED" });
    res.json({ success: true, database: { users: USERS, inventory: INVENTORY, total_patients: USERS.filter(u => u.role === 'Patient').length, total_prescriptions: USERS.reduce((a, u) => a + (u.prescriptions?.length || 0), 0) } });
});

// AUTHENTICATION (ENTERPRISE ROUTING LOGIC)
app.post('/api/login', (req, res) => {
    const { username, password, role } = req.body;
    const user = USERS.find(u => u.username === username && u.password === password);
    if (!user) return res.status(401).json({ message: "Invalid credentials." });

    let isValidTab = false;
    if (role === 'Enterprise') {
        isValidTab = ['Pharmacist', 'Bloodtest', 'Insurance'].includes(user.role);
    } else {
        isValidTab = user.role === role;
    }
    if (!isValidTab) return res.status(401).json({ message: `Incorrect Portal! You are a ${user.role}.` });
    res.json({ success: true, user });
});

// REGISTER → creates local user + patient record on Fabric ledger
app.post('/api/register', async (req, res) => {
    const { name, username, password, age, height, weight, diseaseInput } = req.body;
    if (USERS.find(u => u.username === username)) return res.status(400).json({ message: "Username taken." });
    const uniqueId = "PT-" + Math.floor(1000 + Math.random() * 9000);
    const newUser = { id: uniqueId, username, password, role: "Patient", name, age: Number(age), height: Number(height), weight: Number(weight), diseaseInput, prescriptions: [], medicalFiles: [], medicalTeam: [], appointments: [], favoriteDoctors: [], scanRequests: [] };
    USERS.push(newUser);
    saveData();

    // Write patient record to Fabric ledger
    try {
        await fabricSubmit('hospital', 'createPatientRecord',
            uniqueId, name, String(age), String(weight), String(height), diseaseInput || ''
        );
        console.log(`  ⛓  Patient ${uniqueId} created on ledger`);
    } catch (err) {
        console.error('  ⚠  Fabric createPatientRecord failed:', err.message);
    }

    res.json({ success: true, user: newUser, message: `Account created! ID: ${uniqueId}` });
});

// FETCH PATIENT DATA (ROLE BASED — reads from local cache)
app.get('/api/patient/:id', (req, res) => {
    const { role } = req.query;
    const patient = USERS.find(u => u.id === req.params.id && u.role === 'Patient');
    if (!patient) return res.status(404).json({ message: "Patient not found" });

    if (role === 'Doctor' || role === 'Patient') {
        res.json({ name: patient.name, age: patient.age, weight: patient.weight, height: patient.height, history: patient.diseaseInput, prescriptions: patient.prescriptions || [], medicalFiles: patient.medicalFiles || [], appointments: patient.appointments || [], medicalTeam: patient.medicalTeam || [], favoriteDoctors: patient.favoriteDoctors || [], scanRequests: patient.scanRequests || [] });
    }
    else if (role === 'Pharmacist') {
        res.json({ name: patient.name, prescriptions: patient.prescriptions });
    }
    else if (role === 'Bloodtest') {
        res.json({ name: patient.name, age: patient.age, scanRequests: patient.scanRequests || [] });
    }
    else if (role === 'Insurance') {
        res.json({ name: patient.name, age: patient.age, history: patient.diseaseInput });
    }
    else {
        res.status(403).json({ message: "Unauthorized" });
    }
});

app.post('/api/patient/update', (req, res) => { const { id, weight, history } = req.body; const idx = USERS.findIndex(u => u.id === id); if (idx !== -1) { USERS[idx].weight = Number(weight); USERS[idx].diseaseInput = history; saveData(); return res.json({ success: true }); } res.status(404).json({ error: "Not found" }); });

// ADD MEDICAL FILE → IPFS hash tracked on Fabric ledger
app.post('/api/patient/add-file', async (req, res) => {
    const { patientId, ipfsHash, fileName, category } = req.body;
    const idx = USERS.findIndex(u => u.id === patientId);
    if (idx === -1) return res.status(404).json({ error: "Not found" });

    if (!USERS[idx].medicalFiles) USERS[idx].medicalFiles = [];
    USERS[idx].medicalFiles.push({ hash: ipfsHash, name: fileName, date: new Date().toLocaleDateString(), category: category || 'Medical Summary' });
    saveData();

    // Record on Fabric ledger
    try {
        await fabricSubmit('hospital', 'addMedicalFile',
            patientId, ipfsHash, fileName, category || 'Medical Summary'
        );
        console.log(`  ⛓  Medical file for ${patientId} recorded on ledger`);
    } catch (err) {
        console.error('  ⚠  Fabric addMedicalFile failed:', err.message);
    }

    res.json({ success: true });
});

// =============================================================
// 🧪 BLOODTEST: Mark scan complete + upload report (On-chain via LabOrg)
// =============================================================
app.post('/api/bloodtest/complete-scan', async (req, res) => {
    try {
        const { patientId, scanId, ipfsHash, fileName, scanType } = req.body;
        const patient = USERS.find(u => u.id === patientId && u.role === 'Patient');
        if (!patient) return res.status(404).json({ error: 'Patient not found' });
        const scan = (patient.scanRequests || []).find(s => s.id === scanId);
        if (!scan) return res.status(404).json({ error: 'Scan request not found' });

        // Write to Fabric ledger via LabOrg
        try {
            await fabricSubmit('lab', 'completeScan', scanId, ipfsHash || '', fileName || '');
            console.log(`  ⛓  Scan ${scanId} completed on ledger`);
        } catch (err) {
            console.error('  ⚠  Fabric completeScan failed:', err.message);
        }

        // Update local cache
        scan.status = 'Completed';
        scan.reportHash = ipfsHash;
        scan.reportName = fileName;
        scan.completedDate = new Date().toLocaleDateString();
        if (!patient.medicalFiles) patient.medicalFiles = [];
        const category = (scanType || '').toLowerCase().includes('blood') || (scanType || '').toLowerCase().includes('urine') ? 'Test Report' : 'Scan';
        if (ipfsHash) patient.medicalFiles.push({ hash: ipfsHash, name: fileName, date: new Date().toLocaleDateString(), category });
        saveData();
        res.json({ success: true });
    } catch (e) { res.status(500).json({ error: e.message }); }
});

// BLOODTEST: All patients with scan requests (for history view)
app.get('/api/bloodtest/patients', (req, res) => {
    const patients = USERS
        .filter(u => u.role === 'Patient' && u.scanRequests && u.scanRequests.length > 0)
        .map(p => ({ id: p.id, name: p.name, age: p.age, scanRequests: p.scanRequests }));
    res.json(patients);
});

// =============================================================
// 💊 INVENTORY APIs (off-chain — pharmacy internal)
// =============================================================
app.get('/api/inventory', (req, res) => res.json(INVENTORY));
app.post('/api/inventory/add', (req, res) => { const { name, stock, price, expiry } = req.body; const existing = INVENTORY.find(i => i.name.toLowerCase() === name.toLowerCase()); if (existing) { existing.stock += Number(stock); existing.expiry = expiry; } else { INVENTORY.push({ id: "MED-" + Date.now(), name, stock: Number(stock), price: Number(price), expiry }); } saveData(); res.json({ success: true }); });
app.get('/api/pharmacist/logs', (req, res) => { let logs = []; USERS.filter(u => u.role === 'Patient').forEach(p => { p.prescriptions.forEach(rx => { if (rx.dispensedDate) logs.push({ date: rx.dispensedDate, patientName: p.name, medicine: rx.medicine, rxId: rx.id }); }); }); res.json(logs); });

// =============================================================
// 📤 IPFS UPLOAD
// =============================================================
app.post('/api/upload', upload.single('file'), async (req, res) => { try { if (!PINATA_JWT) throw new Error("Missing PINATA_JWT"); const formData = new FormData(); formData.append('file', fs.createReadStream(req.file.path)); const r = await axios.post("https://api.pinata.cloud/pinning/pinFileToIPFS", formData, { headers: { 'Authorization': `Bearer ${PINATA_JWT}`, ...formData.getHeaders() } }); fs.unlinkSync(req.file.path); res.json({ success: true, ipfsHash: r.data.IpfsHash }); } catch (e) { res.status(500).json({ error: "Upload Failed" }); } });

// =============================================================
// ⛓  PRESCRIPTION — On-chain via HospitalOrg (FIXED)
// =============================================================
app.post('/api/prescription', async (req, res) => {
    try {
        const { patientId, medicine, frequency, duration, remarks, ipfsHash } = req.body;
        const rxId = "RX-" + Date.now().toString().slice(-6);

        // Write to Fabric ledger via HospitalOrg
        await fabricSubmit('hospital', 'createPrescription',
            rxId, patientId, medicine, frequency || '', duration || '', remarks || '', ipfsHash || ''
        );
        console.log(`  ⛓  Prescription ${rxId} recorded on ledger`);

        // Update local cache
        const idx = USERS.findIndex(u => u.id === patientId);
        if (idx !== -1) {
            if (!USERS[idx].prescriptions) USERS[idx].prescriptions = [];
            USERS[idx].prescriptions.push({ id: rxId, medicine, frequency, duration, remarks, ipfsHash, status: 'ACTIVE' });
            saveData();
        }

        prescriptionsTotal.inc({ action: 'created' });
        res.json({ success: true, message: `Prescription ${rxId} recorded on blockchain.` });
    } catch (e) {
        console.error('Prescription error:', e.message);
        res.status(500).json({ error: e.message });
    }
});

// =============================================================
// ⛓  DISPENSE — On-chain via PharmacyOrg
// =============================================================
app.post('/api/dispense', async (req, res) => {
    try {
        const { rxId, patientId, medicineName } = req.body;
        const item = INVENTORY.find(i => i.name.toLowerCase() === medicineName.toLowerCase());
        if (!item || item.stock <= 0) return res.status(400).json({ error: "Out of stock." });

        // Write to Fabric ledger via PharmacyOrg
        await fabricSubmit('pharmacy', 'dispensePrescription', rxId, 'PHARMA_01');
        console.log(`  ⛓  Prescription ${rxId} dispensed on ledger`);

        // Update local cache
        item.stock -= 1;
        const pIdx = USERS.findIndex(u => u.id === patientId);
        if (pIdx !== -1) { const rx = USERS[pIdx].prescriptions.find(r => r.id === rxId); if (rx) { rx.dispensedDate = new Date().toLocaleString(); rx.status = 'DISPENSED'; } }
        saveData();
        prescriptionsTotal.inc({ action: 'dispensed' });
        res.json({ success: true, message: "Dispensed and recorded on blockchain." });
    } catch (e) {
        console.error('Dispense error:', e.message);
        res.status(500).json({ error: e.message });
    }
});

// ⛓  REVOKE PRESCRIPTION — On-chain via HospitalOrg (Doctor only)
app.post('/api/prescription/revoke', async (req, res) => {
    try {
        const { rxId, patientId, reason } = req.body;
        if (!rxId) return res.status(400).json({ error: "Missing rxId" });

        // Write to Fabric ledger via HospitalOrg
        await fabricSubmit('hospital', 'revokePrescription', rxId, reason || '');
        console.log(`  ⛓  Prescription ${rxId} revoked on ledger`);

        // Update local cache
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
        console.error('Revoke error:', e.message);
        res.status(500).json({ error: e.message });
    }
});

// =============================================================
// ⛓  LEDGER QUERY ENDPOINTS — Direct blockchain reads
// =============================================================
app.get('/api/prescription/ledger/:id', async (req, res) => {
    try {
        const result = await fabricQuery('hospital', 'viewPrescription', req.params.id);
        res.json(result);
    } catch (e) { res.status(404).json({ error: "Not found on Blockchain" }); }
});

app.get('/api/ledger/patient/:id', async (req, res) => {
    try {
        const result = await fabricQuery('hospital', 'getPatientRecord', req.params.id);
        res.json(result);
    } catch (e) { res.status(404).json({ error: "Patient not found on ledger" }); }
});

app.get('/api/ledger/prescriptions/:patientId', async (req, res) => {
    try {
        const result = await fabricQuery('hospital', 'getAllPrescriptions', req.params.patientId);
        res.json(result);
    } catch (e) { res.status(404).json({ error: "No prescriptions found on ledger" }); }
});

app.get('/api/ledger/scans/:patientId', async (req, res) => {
    try {
        const result = await fabricQuery('hospital', 'getAllScanOrders', req.params.patientId);
        res.json(result);
    } catch (e) { res.status(404).json({ error: "No scan orders found on ledger" }); }
});

// =============================================================
// 🧠 MACHINE LEARNING ENGINE (off-chain calculation, score saved to ledger)
// =============================================================
app.post('/api/calculate-score', (req, res) => {
    const pythonPath = path.join(__dirname, '../ml_model/venv/bin/python3');
    const scriptPath = path.join(__dirname, '../ml_model/run_engine.py');
    const pythonProcess = spawn(pythonPath, ['-u', scriptPath, JSON.stringify(req.body)]);
    let resultData = "";
    pythonProcess.stdout.on('data', d => resultData += d.toString());
    pythonProcess.on('close', async c => {
        if (c === 0 && resultData.trim()) {
            const parsed = JSON.parse(resultData);
            res.json(parsed);

            // Save health score to ledger (fire-and-forget)
            if (req.body.patientId && parsed.health_score) {
                try {
                    await fabricSubmit('hospital', 'updateHealthScore',
                        req.body.patientId,
                        String(parsed.health_score),
                        String(parsed.risk_score || 0),
                        String(parsed.premium || 0)
                    );
                    console.log(`  ⛓  Health score for ${req.body.patientId} updated on ledger`);
                } catch (err) {
                    console.error('  ⚠  Fabric updateHealthScore skipped:', err.message);
                }
            }
        } else {
            res.status(500).json({ error: "ML Error" });
        }
    });
});

app.listen(PORT, () => console.log(`🚀 Server v24.0 (Fabric 5-Org Integration) on Port ${PORT}`));