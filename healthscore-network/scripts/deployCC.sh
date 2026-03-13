#!/usr/bin/env bash
#
# deployCC.sh — Package, install on all peers, approve, and commit the HealthScore chaincode
#

set -e

ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FABRIC_BIN="${ROOTDIR}/../fabric-samples/bin"
export PATH="${FABRIC_BIN}:${PATH}"

CHANNEL_NAME="healthscorechannel"
CC_NAME="healthscore"
CC_SRC_PATH="${ROOTDIR}/../chaincode"
CC_VERSION="2.0"
CC_SEQUENCE="1"
CC_LANG="node"
CC_INIT_FCN="NA"
# Endorsement policy: require majority (3 of 5) orgs to endorse
CC_END_POLICY="OutOf(3,'HospitalOrgMSP.peer','PatientOrgMSP.peer','PharmacyOrgMSP.peer','LabOrgMSP.peer','InsuranceOrgMSP.peer')"
DELAY=3
MAX_RETRY=5

ORDERER="localhost:7050"

source "${ROOTDIR}/scripts/envVar.sh"

ALL_ORGS=(hospital patient pharmacy lab insurance)

# ── Step 1: Package ────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Packaging chaincode: ${CC_NAME} v${CC_VERSION}"
echo "═══════════════════════════════════════════════════════"

export FABRIC_CFG_PATH="${ROOTDIR}/../fabric-samples/config"
setGlobals hospital

peer lifecycle chaincode package "${CC_NAME}.tar.gz" \
  --path "${CC_SRC_PATH}" \
  --lang "${CC_LANG}" \
  --label "${CC_NAME}_${CC_VERSION}"

echo "  ✓ Packaged → ${CC_NAME}.tar.gz"

# ── Step 2: Install on all peers ───────────────────────────────────────────────
echo ""
echo "  Installing on all 5 peer nodes..."

for ORG in "${ALL_ORGS[@]}"; do
  setGlobals "${ORG}"
  local_rc=1; counter=0
  while [ $counter -lt $MAX_RETRY ] && [ $local_rc -ne 0 ]; do
    sleep $DELAY
    peer lifecycle chaincode install "${CC_NAME}.tar.gz" && local_rc=0
    counter=$((counter + 1))
  done
  if [ $local_rc -ne 0 ]; then echo "ERROR: Install failed on ${ORG}"; exit 1; fi
  echo "  ✓ Installed on peer0.${ORG}"
done

# ── Step 3: Query installed — get package ID ───────────────────────────────────
setGlobals hospital
CC_PACKAGE_ID=$(peer lifecycle chaincode queryinstalled | grep "${CC_NAME}_${CC_VERSION}" | awk '{print $3}' | sed 's/,//')
echo ""
echo "  Package ID: ${CC_PACKAGE_ID}"
export CC_PACKAGE_ID

# ── Step 4: Approve for all orgs ──────────────────────────────────────────────
echo ""
echo "  Approving chaincode definition for all orgs..."

for ORG in "${ALL_ORGS[@]}"; do
  setGlobals "${ORG}"
  local_rc=1; counter=0
  while [ $counter -lt $MAX_RETRY ] && [ $local_rc -ne 0 ]; do
    sleep $DELAY
    peer lifecycle chaincode approveformyorg \
      -o "${ORDERER}" \
      --ordererTLSHostnameOverride orderer.healthscore.com \
      --tls --cafile "${ORDERER_CA}" \
      --channelID "${CHANNEL_NAME}" \
      --name "${CC_NAME}" \
      --version "${CC_VERSION}" \
      --package-id "${CC_PACKAGE_ID}" \
      --sequence "${CC_SEQUENCE}" \
      --signature-policy "${CC_END_POLICY}" && local_rc=0
    counter=$((counter + 1))
  done
  if [ $local_rc -ne 0 ]; then echo "ERROR: Approve failed for ${ORG}"; exit 1; fi
  echo "  ✓ Approved by ${ORG}"
done

# ── Step 5: Check commit readiness ────────────────────────────────────────────
echo ""
echo "  Checking commit readiness..."
setGlobals hospital
peer lifecycle chaincode checkcommitreadiness \
  --channelID "${CHANNEL_NAME}" \
  --name "${CC_NAME}" \
  --version "${CC_VERSION}" \
  --sequence "${CC_SEQUENCE}" \
  --signature-policy "${CC_END_POLICY}" \
  --output json

# ── Step 6: Commit ────────────────────────────────────────────────────────────
echo ""
echo "  Committing chaincode definition to channel..."

# Build --peerAddresses flags for all orgs
getPort() {
  case "$1" in
    hospital)  echo "7051" ;;
    patient)   echo "8051" ;;
    pharmacy)  echo "9051" ;;
    lab)       echo "10051" ;;
    insurance) echo "11051" ;;
  esac
}

PEER_ADDR_FLAGS=""
for ORG in "${ALL_ORGS[@]}"; do
  DOMAIN="${ORG}.healthscore.com"
  TLS_CERT="${ROOTDIR}/organizations/peerOrganizations/${DOMAIN}/peers/peer0.${DOMAIN}/tls/ca.crt"
  PORT=$(getPort "$ORG")
  PEER_ADDR_FLAGS="${PEER_ADDR_FLAGS} --peerAddresses localhost:${PORT} --tlsRootCertFiles ${TLS_CERT}"
done

setGlobals hospital
peer lifecycle chaincode commit \
  -o "${ORDERER}" \
  --ordererTLSHostnameOverride orderer.healthscore.com \
  --tls --cafile "${ORDERER_CA}" \
  --channelID "${CHANNEL_NAME}" \
  --name "${CC_NAME}" \
  --version "${CC_VERSION}" \
  --sequence "${CC_SEQUENCE}" \
  --signature-policy "${CC_END_POLICY}" \
  ${PEER_ADDR_FLAGS}

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅  Chaincode '${CC_NAME}' v${CC_VERSION} committed"
echo "      Endorsement: 3-of-5 orgs required"
echo "═══════════════════════════════════════════════════════"
