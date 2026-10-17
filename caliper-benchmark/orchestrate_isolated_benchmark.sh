#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Orchestrate Isolated 5-Organization Hyperledger Fabric Testbed & Caliper Run
# -----------------------------------------------------------------------------
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TESTBED_DIR="/tmp/healthscore_isolated_testbed_$(date +%s)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT_DIR="$REPO_ROOT/caliper-benchmark/results/live/$TIMESTAMP"

echo "=========================================================================="
echo " Starting Isolated Fabric Benchmark Orchestration"
echo " Workspace: $TESTBED_DIR"
echo " Results Destination: $OUTPUT_DIR"
echo "=========================================================================="

cleanup() {
  echo "--> Cleaning up isolated containers and testbed directory..."
  if [ -f "$TESTBED_DIR/compose/compose.yaml" ]; then
    docker compose -p hs_isolated -f "$TESTBED_DIR/compose/compose.yaml" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
  docker network rm fabric_healthscore >/dev/null 2>&1 || true
  rm -rf "$TESTBED_DIR"
  echo "✓ Cleanup completed."
}
trap cleanup EXIT

mkdir -p "$TESTBED_DIR"
cd "$TESTBED_DIR"

echo "--> Step 1: Writing crypto-config with EnableNodeOUs: true..."
cat << 'EOF' > crypto-config.yaml
OrdererOrgs:
  - Name: Orderer
    Domain: healthscore.com
    EnableNodeOUs: true
    Specs:
      - Hostname: orderer
        SANS:
          - localhost
          - 127.0.0.1
          - orderer.healthscore.com

PeerOrgs:
  - Name: HospitalOrg
    Domain: hospital.healthscore.com
    EnableNodeOUs: true
    Template:
      Count: 1
    Users:
      Count: 1
  - Name: PatientOrg
    Domain: patient.healthscore.com
    EnableNodeOUs: true
    Template:
      Count: 1
    Users:
      Count: 1
  - Name: PharmacyOrg
    Domain: pharmacy.healthscore.com
    EnableNodeOUs: true
    Template:
      Count: 1
    Users:
      Count: 1
  - Name: LabOrg
    Domain: lab.healthscore.com
    EnableNodeOUs: true
    Template:
      Count: 1
    Users:
      Count: 1
  - Name: InsuranceOrg
    Domain: insurance.healthscore.com
    EnableNodeOUs: true
    Template:
      Count: 1
    Users:
      Count: 1
EOF

mkdir -p organizations channel-artifacts peercfg configtx compose chaincode

echo "--> Step 2: Generating crypto material via cryptogen..."
docker run --rm -v "$TESTBED_DIR:/workspace" -w /workspace hyperledger/fabric-tools:latest cryptogen generate --config=/workspace/crypto-config.yaml --output=/workspace/organizations

echo "--> Step 3: Generating channel genesis block..."
cp "$REPO_ROOT/healthscore-network/configtx/configtx.yaml" "$TESTBED_DIR/configtx/configtx.yaml"
cp "$REPO_ROOT/healthscore-network/peercfg/core.yaml" "$TESTBED_DIR/peercfg/core.yaml"
cp -r "$REPO_ROOT/chaincode/"* "$TESTBED_DIR/chaincode/"
cp "$REPO_ROOT/healthscore-network/compose/compose-healthscore.yaml" "$TESTBED_DIR/compose/compose.yaml"

docker run --rm -v "$TESTBED_DIR:/workspace" -w /workspace -e FABRIC_CFG_PATH=/workspace/configtx hyperledger/fabric-tools:latest configtxgen -profile HealthScoreChannel -outputBlock /workspace/channel-artifacts/healthscorechannel.block -channelID healthscorechannel

echo "--> Step 4: Starting 5-organization peer and orderer containers..."
docker compose -p hs_isolated -f "$TESTBED_DIR/compose/compose.yaml" up -d
sleep 5

echo "--> Step 5: Joining orderer to healthscorechannel..."
docker run --rm --network fabric_healthscore -v "$TESTBED_DIR:/workspace" -w /workspace hyperledger/fabric-tools:latest osnadmin channel join \
  --channelID healthscorechannel \
  --config-block /workspace/channel-artifacts/healthscorechannel.block \
  -o orderer.healthscore.com:7053 \
  --ca-file /workspace/organizations/ordererOrganizations/healthscore.com/orderers/orderer.healthscore.com/msp/tlscacerts/tlsca.healthscore.com-cert.pem \
  --client-cert /workspace/organizations/ordererOrganizations/healthscore.com/orderers/orderer.healthscore.com/tls/server.crt \
  --client-key /workspace/organizations/ordererOrganizations/healthscore.com/orderers/orderer.healthscore.com/tls/server.key

sleep 3

echo "--> Step 6: Joining all 5 peers to channel..."
cat << 'EOF_PEERS' > join_peers.sh
#!/bin/bash
set -e
export FABRIC_CFG_PATH=/workspace/peercfg
export CORE_PEER_TLS_ENABLED=true

for ORG in hospital patient pharmacy lab insurance; do
  DOMAIN="${ORG}.healthscore.com"
  case "$ORG" in
    hospital) MSPID="HospitalOrgMSP"; PORT="7051" ;;
    patient)  MSPID="PatientOrgMSP";  PORT="8051" ;;
    pharmacy) MSPID="PharmacyOrgMSP"; PORT="9051" ;;
    lab)      MSPID="LabOrgMSP";      PORT="10051" ;;
    insurance)MSPID="InsuranceOrgMSP";PORT="11051" ;;
  esac

  export CORE_PEER_LOCALMSPID="$MSPID"
  export CORE_PEER_TLS_ROOTCERT_FILE="/workspace/organizations/peerOrganizations/${DOMAIN}/peers/peer0.${DOMAIN}/tls/ca.crt"
  export CORE_PEER_MSPCONFIGPATH="/workspace/organizations/peerOrganizations/${DOMAIN}/users/Admin@${DOMAIN}/msp"
  export CORE_PEER_ADDRESS="peer0.${DOMAIN}:${PORT}"

  peer channel join -b /workspace/channel-artifacts/healthscorechannel.block
  echo "✓ peer0.${ORG} joined successfully"
done
EOF_PEERS
chmod +x join_peers.sh
docker run --rm --network fabric_healthscore -v "$TESTBED_DIR:/workspace" -w /workspace hyperledger/fabric-tools:latest /workspace/join_peers.sh

echo "--> Step 7: Packaging, installing, approving, and committing chaincode..."
cat << 'EOF_DEPLOY' > deploy_chaincode.sh
#!/bin/bash
set -e
export FABRIC_CFG_PATH=/workspace/peercfg
export CORE_PEER_TLS_ENABLED=true

ORDERER_CA="/workspace/organizations/ordererOrganizations/healthscore.com/orderers/orderer.healthscore.com/msp/tlscacerts/tlsca.healthscore.com-cert.pem"
ORDERER_ADDR="orderer.healthscore.com:7050"
CHANNEL_NAME="healthscorechannel"
CC_NAME="healthscore"
CC_VERSION="2.0"
CC_SEQUENCE="1"
CC_END_POLICY="OutOf(3,'HospitalOrgMSP.peer','PatientOrgMSP.peer','PharmacyOrgMSP.peer','LabOrgMSP.peer','InsuranceOrgMSP.peer')"

set_org_env() {
  local ORG=$1
  DOMAIN="${ORG}.healthscore.com"
  case "$ORG" in
    hospital) MSPID="HospitalOrgMSP"; PORT="7051" ;;
    patient)  MSPID="PatientOrgMSP";  PORT="8051" ;;
    pharmacy) MSPID="PharmacyOrgMSP"; PORT="9051" ;;
    lab)      MSPID="LabOrgMSP";      PORT="10051" ;;
    insurance)MSPID="InsuranceOrgMSP";PORT="11051" ;;
  esac
  export CORE_PEER_LOCALMSPID="$MSPID"
  export CORE_PEER_TLS_ROOTCERT_FILE="/workspace/organizations/peerOrganizations/${DOMAIN}/peers/peer0.${DOMAIN}/tls/ca.crt"
  export CORE_PEER_MSPCONFIGPATH="/workspace/organizations/peerOrganizations/${DOMAIN}/users/Admin@${DOMAIN}/msp"
  export CORE_PEER_ADDRESS="peer0.${DOMAIN}:${PORT}"
}

set_org_env hospital
peer lifecycle chaincode package /workspace/healthscore.tar.gz \
  --path /workspace/chaincode \
  --lang node \
  --label healthscore_2.0

for ORG in hospital patient pharmacy lab insurance; do
  set_org_env "$ORG"
  peer lifecycle chaincode install /workspace/healthscore.tar.gz
done

set_org_env hospital
CC_PACKAGE_ID=$(peer lifecycle chaincode queryinstalled | grep healthscore_2.0 | awk '{print $3}' | sed 's/,//')

for ORG in hospital patient pharmacy lab insurance; do
  set_org_env "$ORG"
  peer lifecycle chaincode approveformyorg \
    -o "${ORDERER_ADDR}" \
    --ordererTLSHostnameOverride orderer.healthscore.com \
    --tls --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --version "${CC_VERSION}" \
    --package-id "${CC_PACKAGE_ID}" \
    --sequence "${CC_SEQUENCE}" \
    --signature-policy "${CC_END_POLICY}"
done

set_org_env hospital
peer lifecycle chaincode commit \
  -o "${ORDERER_ADDR}" \
  --ordererTLSHostnameOverride orderer.healthscore.com \
  --tls --cafile "${ORDERER_CA}" \
  --channelID "${CHANNEL_NAME}" \
  --name "${CC_NAME}" \
  --version "${CC_VERSION}" \
  --sequence "${CC_SEQUENCE}" \
  --signature-policy "${CC_END_POLICY}" \
  --peerAddresses peer0.hospital.healthscore.com:7051 --tlsRootCertFiles /workspace/organizations/peerOrganizations/hospital.healthscore.com/peers/peer0.hospital.healthscore.com/tls/ca.crt \
  --peerAddresses peer0.patient.healthscore.com:8051 --tlsRootCertFiles /workspace/organizations/peerOrganizations/patient.healthscore.com/peers/peer0.patient.healthscore.com/tls/ca.crt \
  --peerAddresses peer0.pharmacy.healthscore.com:9051 --tlsRootCertFiles /workspace/organizations/peerOrganizations/pharmacy.healthscore.com/peers/peer0.pharmacy.healthscore.com/tls/ca.crt

echo "✓ Chaincode committed successfully."
EOF_DEPLOY
chmod +x deploy_chaincode.sh
docker run --rm --network fabric_healthscore -v "$TESTBED_DIR:/workspace" -w /workspace hyperledger/fabric-tools:latest /workspace/deploy_chaincode.sh

echo "--> Step 8: Configuring Caliper execution workspace..."
mkdir -p "$TESTBED_DIR/caliper_ws"
cp "$REPO_ROOT/caliper-benchmark/benchmark.yaml" "$TESTBED_DIR/caliper_ws/benchmark.yaml"
cp "$REPO_ROOT/caliper-benchmark/workload.js" "$TESTBED_DIR/caliper_ws/workload.js"

# Generate isolated networkconfig with internal Docker hostnames
ADMIN_KEY_NAME=$(basename $(ls "$TESTBED_DIR/organizations/peerOrganizations/hospital.healthscore.com/users/Admin@hospital.healthscore.com/msp/keystore/"*))
cat << EOF_NET > "$TESTBED_DIR/caliper_ws/networkconfig.yaml"
name: HealthScoreIsolatedNetwork
version: "2.0.0"

caliper:
  blockchain: fabric

channels:
  - channelName: healthscorechannel
    contracts:
      - id: healthscore

organizations:
  - mspid: HospitalOrgMSP
    identities:
      certificates:
        - name: HospitalOrgAdmin
          clientPrivateKey:
            path: /workspace/organizations/peerOrganizations/hospital.healthscore.com/users/Admin@hospital.healthscore.com/msp/keystore/$ADMIN_KEY_NAME
          clientSignedCert:
            path: /workspace/organizations/peerOrganizations/hospital.healthscore.com/users/Admin@hospital.healthscore.com/msp/signcerts/Admin@hospital.healthscore.com-cert.pem
    connectionProfile:
      path: /caliper_ws/connection.json
      discover: false
EOF_NET

cat << 'EOF_CONN' > "$TESTBED_DIR/caliper_ws/connection.json"
{
  "name": "HealthScoreIsolatedNetwork",
  "version": "1.0.0",
  "client": {
    "organization": "HospitalOrgMSP",
    "connection": {
      "timeout": {
        "peer": { "endorser": "300" },
        "orderer": "300"
      }
    }
  },
  "channels": {
    "healthscorechannel": {
      "orderers": ["orderer.healthscore.com"],
      "peers": {
        "peer0.hospital.healthscore.com": {
          "endorsingPeer": true,
          "chaincodeQuery": true,
          "ledgerQuery": true,
          "eventSource": true
        }
      }
    }
  },
  "organizations": {
    "HospitalOrgMSP": {
      "mspid": "HospitalOrgMSP",
      "peers": ["peer0.hospital.healthscore.com"]
    }
  },
  "orderers": {
    "orderer.healthscore.com": {
      "url": "grpcs://orderer.healthscore.com:7050",
      "tlsCACerts": {
        "path": "/workspace/organizations/ordererOrganizations/healthscore.com/orderers/orderer.healthscore.com/msp/tlscacerts/tlsca.healthscore.com-cert.pem"
      },
      "grpcOptions": {
        "ssl-target-name-override": "orderer.healthscore.com"
      }
    }
  },
  "peers": {
    "peer0.hospital.healthscore.com": {
      "url": "grpcs://peer0.hospital.healthscore.com:7051",
      "tlsCACerts": {
        "path": "/workspace/organizations/peerOrganizations/hospital.healthscore.com/peers/peer0.hospital.healthscore.com/tls/ca.crt"
      },
      "grpcOptions": {
        "ssl-target-name-override": "peer0.hospital.healthscore.com"
      }
    }
  }
}
EOF_CONN

echo "--> Step 9: Executing Hyperledger Caliper v0.5.0 in isolated container..."
mkdir -p "$OUTPUT_DIR"
START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

docker run --rm \
  --network fabric_healthscore \
  -v "$TESTBED_DIR:/workspace" \
  -v "$TESTBED_DIR/caliper_ws:/caliper_ws" \
  -w /caliper_ws \
  node:20-alpine \
  sh -c "npm install --no-save @hyperledger/caliper-cli@0.5.0 && npx caliper bind --caliper-bind-sut fabric:2.4 && npx caliper launch manager --caliper-workspace /caliper_ws --caliper-networkconfig /caliper_ws/networkconfig.yaml --caliper-benchconfig /caliper_ws/benchmark.yaml --caliper-flow-only-test --caliper-fabric-gateway-enabled" 2>&1 | tee "$OUTPUT_DIR/console.log"

EXIT_CODE=${PIPESTATUS[0]}
END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

if [ $EXIT_CODE -ne 0 ]; then
  echo "❌ Benchmark failed with exit code $EXIT_CODE"
  exit $EXIT_CODE
fi

if [ -f "$TESTBED_DIR/caliper_ws/report.html" ]; then
  cp "$TESTBED_DIR/caliper_ws/report.html" "$OUTPUT_DIR/report.html"
  echo "✓ Output report copied to $OUTPUT_DIR/report.html"
fi

cat << EOF_MANIFEST > "$OUTPUT_DIR/run_manifest.json"
{
  "run_id": "$TIMESTAMP",
  "start_time": "$START_TIME",
  "end_time": "$END_TIME",
  "exit_code": $EXIT_CODE,
  "status": "COMPLETED_SUCCESS",
  "evidence_class": "Class 2: New Live Empirical Caliper Rerun (Isolated Testbed)",
  "network_topology": "5 Organizations (Hospital, Patient, Pharmacy, Lab, Insurance) + Raft Orderer",
  "caliper_version": "0.5.0",
  "fabric_version": "2.4/2.5",
  "workspace": "$OUTPUT_DIR"
}
EOF_MANIFEST

echo "=========================================================================="
echo " Benchmark Execution Succeeded! Saved to $OUTPUT_DIR"
echo "=========================================================================="
