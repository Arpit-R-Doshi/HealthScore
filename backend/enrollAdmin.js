/**
 * enrollAdmin.js — Populate Fabric wallet with admin identities for all 5 orgs
 *
 * Uses the pre-generated cryptogen certificates (no CA enrollment needed).
 * Creates wallet entries:
 *   hospital-admin  → HospitalOrgMSP
 *   patient-admin   → PatientOrgMSP
 *   pharmacy-admin  → PharmacyOrgMSP
 *   lab-admin       → LabOrgMSP
 *   insurance-admin → InsuranceOrgMSP
 */

const { Wallets } = require('fabric-network');
const path = require('path');
const fs = require('fs');

const NETWORK_ROOT = path.resolve(__dirname, '../healthscore-network/organizations/peerOrganizations');

const ORGS = [
    { name: 'hospital',  mspId: 'HospitalOrgMSP',  domain: 'hospital.healthscore.com' },
    { name: 'patient',   mspId: 'PatientOrgMSP',   domain: 'patient.healthscore.com' },
    { name: 'pharmacy',  mspId: 'PharmacyOrgMSP',  domain: 'pharmacy.healthscore.com' },
    { name: 'lab',       mspId: 'LabOrgMSP',       domain: 'lab.healthscore.com' },
    { name: 'insurance', mspId: 'InsuranceOrgMSP', domain: 'insurance.healthscore.com' },
];

async function main() {
    const walletPath = path.join(__dirname, 'wallet');
    const wallet = await Wallets.newFileSystemWallet(walletPath);

    for (const org of ORGS) {
        const label = `${org.name}-admin`;

        // Check if already enrolled
        const existing = await wallet.get(label);
        if (existing) {
            console.log(`  ✓ ${label} already exists in wallet — skipping`);
            continue;
        }

        // Read admin certificate and private key from cryptogen output
        const certDir = path.join(NETWORK_ROOT, org.domain, 'users', `Admin@${org.domain}`, 'msp', 'signcerts');
        const keyDir  = path.join(NETWORK_ROOT, org.domain, 'users', `Admin@${org.domain}`, 'msp', 'keystore');

        // signcerts: there's typically one file (cert.pem or Admin@...-cert.pem)
        const certFiles = fs.readdirSync(certDir);
        if (certFiles.length === 0) {
            console.error(`  ✗ No certificate found in ${certDir}`);
            continue;
        }
        const certificate = fs.readFileSync(path.join(certDir, certFiles[0]), 'utf8');

        // keystore: there's typically one file (the private key)
        const keyFiles = fs.readdirSync(keyDir);
        if (keyFiles.length === 0) {
            console.error(`  ✗ No private key found in ${keyDir}`);
            continue;
        }
        const privateKey = fs.readFileSync(path.join(keyDir, keyFiles[0]), 'utf8');

        // Create and store the X.509 identity
        const identity = {
            credentials: { certificate, privateKey },
            mspId: org.mspId,
            type: 'X.509',
        };

        await wallet.put(label, identity);
        console.log(`  ✓ Enrolled ${label} (${org.mspId})`);
    }

    console.log('\n✅  All wallet identities ready.\n');
}

main().catch(err => {
    console.error('Enrollment failed:', err);
    process.exit(1);
});
