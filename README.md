# HealthScore Network

A comprehensive blockchain-powered healthcare management system built with React, Node.js, and Hyperledger Fabric.

## Overview

HealthScore provides a secure, decentralized platform connecting Patients, Doctors, Pharmacists, Blood Test Labs, and Insurance providers. It leverages a 5-organization local Hyperledger Fabric network to ensure medical records and prescriptions are tamper-proof and securely shared.

The system also features live system monitoring through an integrated Prometheus and Grafana stack, viewable via a dedicated master Admin Dashboard.

## Prerequisites

Before running this project, ensure you have the following installed:
- **Node.js** (v18+ recommended)
- **Docker & Docker Compose** (Ensure the Docker daemon is running)
- **Git**

## Environment Variables (.env)

Create a `.env` file in the `backend/` directory with the following variables:

```env
# Port for the Node.js Backend
PORT=5001

# Master Admin Key to bypass Lock Screen on the /admin route
ADMIN_KEY="admin"

# Pinata API JWT for IPFS file uploads (Used for Medical Records/Vault)
PINATA_JWT="your_pinata_jwt_here"

# Groq API Key for the Patient AI Assistant Chatbot
GROQ_API_KEY="your_groq_api_key_here"
```

## Running the Project

Follow these steps to spin up the entire ecosystem (Blockchain + Backend + Frontend + Monitoring).

### 1. Initialize the Blockchain Network
First, you need to spin up the 5-organization Hyperledger Fabric network and install the Chaincode.
```bash
# From the project root
./install-fabric.sh
```
*(Note: This is a heavy initialization script. On the very first run, it will download necessary Docker images, build the crypto material, create the channel, and deploy the chaincode. This can take anywhere from **5 to 10 minutes** depending on your internet connection. Subsequent runs of `./resume.sh` will be instant.)*

### 2. Start the Backend Server
The backend handles API requests, interacts with the Fabric SDK, and exposes Prometheus metrics.
```bash
cd backend
npm install
node server.js
```
The backend will start on `http://localhost:5001`. On first boot, it will automatically enroll the admin identities for all 5 organizations into the Fabric wallets.

### 3. Start the Frontend Application
The frontend is a Vite-powered React application.
```bash
# In a new terminal tab
cd frontend
npm install
npm run dev
```
The frontend will start on `http://localhost:5173`.

### 4. Start the Monitoring Stack (Optional but Recommended)
To view live metrics (HTTP requests, Fabric transaction rates, memory usage, etc.), start the Grafana and Prometheus containers:
```bash
# In a new terminal tab, from the project root
docker compose -f monitoring/docker-compose.monitor.yml up -d
```
- **Grafana Live Dashboard:** `http://localhost:3001` (Dashboard auto-provisioned)
- **Admin App View:** Navigate to `http://localhost:5173/admin` and enter your `ADMIN_KEY` to view the embedded monitoring widgets.

## Pausing and Resuming

Since the Hyperledger Fabric network runs in Docker containers, you don't need to rebuild the network from scratch every time you stop working.

To **pause** the network without losing data (stops Fabric peers + Monitoring):
```bash
./stop.sh
```

To **resume** the network with all previous ledger data intact:
```bash
./resume.sh
```

## System Architecture

- **Frontend:** React, Vite, Framer Motion, Lucide Icons
- **Backend:** Node.js, Express, Fabric SDK (`fabric-network`), Prom-Client
- **Blockchain:** Hyperledger Fabric v2.x (5 Orgs: Hospital, Patient, Pharmacy, Lab, Insurance)
- **Monitoring:** Prometheus (scraping Backend + Fabric Peers + Orderer), Grafana
- **External APIs:** Pinata (IPFS), Groq (AI Chat)

## Default Login Credentials

You can test the platform immediately by logging in with the default seeded accounts. 
**(The password for all default accounts is `password123`)**

| Role | Username | Dashboard Route |
|---|---|---|
| **Patient** | `patient1` | `/patient` |
| **Doctor** | `doctor1` | `/doctor` |
| **Pharmacist** | `pharma1` | `/pharmacist` |
| **Blood Test Lab** | `lab1` | `/bloodtest` |
| **Insurance** | `ins1` | `/insurance` |

To view the **Master Admin Dashboard** for monitoring: 
Navigate to `/admin` and enter the `ADMIN_KEY` password (default: **admin**).
