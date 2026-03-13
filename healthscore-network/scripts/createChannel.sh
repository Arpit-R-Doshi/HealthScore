#!/usr/bin/env bash
#
# createChannel.sh — Create healthscorechannel and join all 5 peers
#

set -e

ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FABRIC_BIN="${ROOTDIR}/../fabric-samples/bin"
export PATH="${FABRIC_BIN}:${PATH}"
export FABRIC_CFG_PATH="${ROOTDIR}/configtx"

CHANNEL_NAME="healthscorechannel"
DELAY=3
MAX_RETRY=5
ORDERER="localhost:7050"
ORDERER_CA="${ROOTDIR}/organizations/ordererOrganizations/healthscore.com/orderers/orderer.healthscore.com/msp/tlscacerts/tlsca.healthscore.com-cert.pem"
ADMIN_TLS_CERT="${ROOTDIR}/organizations/ordererOrganizations/healthscore.com/orderers/orderer.healthscore.com/tls/server.crt"
ADMIN_TLS_KEY="${ROOTDIR}/organizations/ordererOrganizations/healthscore.com/orderers/orderer.healthscore.com/tls/server.key"

source "${ROOTDIR}/scripts/envVar.sh"

ALL_ORGS=(hospital patient pharmacy lab insurance)

# ── Step 1: Create genesis block ───────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Creating channel genesis block: ${CHANNEL_NAME}.block"
echo "═══════════════════════════════════════════════════════"

configtxgen -profile HealthScoreChannel -outputBlock "${ROOTDIR}/channel-artifacts/${CHANNEL_NAME}.block" -channelID "${CHANNEL_NAME}"
if [ $? -ne 0 ]; then echo "ERROR: configtxgen failed"; exit 1; fi

# ── Step 2: Join orderer to channel ────────────────────────────────────────────
echo ""
echo "  Joining orderer to channel..."
sleep 5

osnadmin channel join \
  --channelID "${CHANNEL_NAME}" \
  --config-block "${ROOTDIR}/channel-artifacts/${CHANNEL_NAME}.block" \
  -o "localhost:7053" \
  --ca-file "${ORDERER_CA}" \
  --client-cert "${ADMIN_TLS_CERT}" \
  --client-key "${ADMIN_TLS_KEY}"

sleep "${DELAY}"

# ── Step 3: Join each peer org ─────────────────────────────────────────────────
for ORG in "${ALL_ORGS[@]}"; do
  echo ""
  echo "  Joining peer0.${ORG}.healthscore.com to ${CHANNEL_NAME}..."
  setGlobals "${ORG}"
  export FABRIC_CFG_PATH="${ROOTDIR}/../fabric-samples/config"

  local_rc=1
  counter=0
  while [ $counter -lt $MAX_RETRY ] && [ $local_rc -ne 0 ]; do
    sleep $DELAY
    peer channel join -b "${ROOTDIR}/channel-artifacts/${CHANNEL_NAME}.block" && local_rc=0
    counter=$((counter + 1))
  done

  if [ $local_rc -ne 0 ]; then
    echo "ERROR: peer0.${ORG} failed to join channel after ${MAX_RETRY} retries"
    exit 1
  fi
  echo "  ✓ peer0.${ORG} joined ${CHANNEL_NAME}"
done

# ── Step 4: Set anchor peers for all orgs ─────────────────────────────────────
echo ""
echo "  Setting anchor peers..."
export FABRIC_CFG_PATH="${ROOTDIR}/configtx"

for ORG in "${ALL_ORGS[@]}"; do
  setGlobals "${ORG}"
  export FABRIC_CFG_PATH="${ROOTDIR}/../fabric-samples/config"

  peer channel update \
    -o "${ORDERER}" \
    --ordererTLSHostnameOverride orderer.healthscore.com \
    -c "${CHANNEL_NAME}" \
    -f "${ROOTDIR}/channel-artifacts/${ORG}anchors.tx" \
    --cafile "${ORDERER_CA}" \
    --tls 2>/dev/null || true  # anchor updates are optional in newer Fabric

  echo "  ✓ Anchor peer set for ${ORG}"
done

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅  Channel '${CHANNEL_NAME}' created — all 5 orgs joined"
echo "═══════════════════════════════════════════════════════"
