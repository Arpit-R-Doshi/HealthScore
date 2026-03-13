#!/usr/bin/env bash
#
# network.sh — HealthScore 5-org Hyperledger Fabric Network
#
# Usage:
#   ./network.sh up                 - start nodes + create channel + deploy chaincode
#   ./network.sh up createChannel   - start nodes and create channel only
#   ./network.sh deployCC           - deploy/upgrade chaincode
#   ./network.sh down               - stop and clean all containers/volumes
#   ./network.sh restart            - down then up
#
# Org roles:
#   hospital  → Doctors  (port 7051)
#   patient   → Patients (port 8051)
#   pharmacy  → Pharmacists (port 9051)
#   lab       → Diagnostic Labs (port 10051)
#   insurance → Insurers, read-only (port 11051)

ROOTDIR="$(cd "$(dirname "$0")" && pwd)"
FABRIC_BIN="${ROOTDIR}/../fabric-samples/bin"
export PATH="${FABRIC_BIN}:${PATH}"
export FABRIC_CFG_PATH="${ROOTDIR}/configtx"

COMPOSE_FILE="${ROOTDIR}/compose/compose-healthscore.yaml"
CHANNEL_NAME="healthscorechannel"
CC_NAME="healthscore"

# ── Helpers ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fatal() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

checkPrereqs() {
  peer version > /dev/null 2>&1   || fatal "peer binary not found. Install Fabric binaries first."
  cryptogen version > /dev/null 2>&1 || fatal "cryptogen tool not found."
  configtxgen version > /dev/null 2>&1 || fatal "configtxgen tool not found."

  LOCAL_VERSION=$(peer version | sed -ne 's/^ Version: //p')
  info "Fabric peer version: ${LOCAL_VERSION}"

  # Only fail on genuinely unsupported v1.x versions — use || true to prevent set -e exit
  for V in "^1\.0\." "^1\.1\." "^1\.2\." "^1\.3\." "^1\.4\."; do
    echo "$LOCAL_VERSION" | grep -q "$V" && fatal "Unsupported Fabric version: ${LOCAL_VERSION}" || true
  done
}

# ── Generate crypto material using cryptogen ──────────────────────────────────
createOrgs() {
  info "Generating crypto material for all 5 orgs + orderer..."

  if [ -d "${ROOTDIR}/organizations/peerOrganizations" ]; then
    rm -rf "${ROOTDIR}/organizations/peerOrganizations" "${ROOTDIR}/organizations/ordererOrganizations"
  fi

  mkdir -p "${ROOTDIR}/organizations"

  for ORG in hospital patient pharmacy lab insurance; do
    info "  cryptogen → ${ORG}Org"
    cryptogen generate \
      --config="${ROOTDIR}/organizations/cryptogen/crypto-config-${ORG}.yaml" \
      --output="${ROOTDIR}/organizations" \
      || fatal "cryptogen failed for ${ORG}"
  done

  info "  cryptogen → ordererOrg"
  cryptogen generate \
    --config="${ROOTDIR}/organizations/cryptogen/crypto-config-orderer.yaml" \
    --output="${ROOTDIR}/organizations" \
    || fatal "cryptogen failed for orderer"

  info "✓ Crypto material generated for all orgs"
}

# ── Create genesis block for channel ─────────────────────────────────────────
createChannelArtifacts() {
  info "Generating channel genesis block..."
  mkdir -p "${ROOTDIR}/channel-artifacts"

  # configtxgen needs the TLS certs in organizations/ to already exist
  if [ ! -d "${ROOTDIR}/organizations/ordererOrganizations" ]; then
    fatal "Orderer crypto not found. Run createOrgs first."
  fi

  configtxgen \
    -profile HealthScoreChannel \
    -outputBlock "${ROOTDIR}/channel-artifacts/${CHANNEL_NAME}.block" \
    -channelID "${CHANNEL_NAME}" \
    || fatal "configtxgen failed"

  info "✓ Genesis block: channel-artifacts/${CHANNEL_NAME}.block"
}

# ── Start containers ──────────────────────────────────────────────────────────
networkUp() {
  checkPrereqs

  if [ ! -d "${ROOTDIR}/organizations/peerOrganizations" ] || [ ! -d "${ROOTDIR}/organizations/ordererOrganizations" ]; then
    createOrgs
  else
    info "Crypto material already exists — skipping cryptogen"
  fi

  createChannelArtifacts

  info "Starting Docker containers..."
  docker compose -f "${COMPOSE_FILE}" up -d 2>&1 \
    || fatal "docker compose failed — is Docker running?"

  echo ""
  docker ps --filter label=service=hyperledger-fabric --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
  echo ""
  info "✓ Network is up — 6 containers running (1 orderer + 5 peers)"
}

# ── Create channel and join all peers ────────────────────────────────────────
createChannel() {
  info "Waiting 8s for orderer to initialize..."
  sleep 8
  bash "${ROOTDIR}/scripts/createChannel.sh" || fatal "createChannel.sh failed"
}

# ── Deploy chaincode ──────────────────────────────────────────────────────────
deployCC() {
  info "Deploying chaincode '${CC_NAME}' to '${CHANNEL_NAME}'..."
  bash "${ROOTDIR}/scripts/deployCC.sh" || fatal "deployCC.sh failed"
}

# ── Stop and clean everything ─────────────────────────────────────────────────
networkDown() {
  warn "Stopping HealthScore network and removing all volumes..."

  docker compose -f "${COMPOSE_FILE}" down --volumes --remove-orphans 2>/dev/null || true
  docker rm -f $(docker ps -aq --filter label=service=hyperledger-fabric) 2>/dev/null || true
  docker rm -f $(docker ps -aq --filter name='dev-peer*') 2>/dev/null || true
  docker image rm -f $(docker images -aq --filter reference='dev-peer*') 2>/dev/null || true

  rm -rf "${ROOTDIR}/organizations/peerOrganizations" \
         "${ROOTDIR}/organizations/ordererOrganizations" \
         "${ROOTDIR}/channel-artifacts" \
         "${ROOTDIR}/${CC_NAME}.tar.gz"

  info "✓ Network stopped and cleaned"
}

# ── Print help ────────────────────────────────────────────────────────────────
printHelp() {
  echo ""
  echo "Usage: ./network.sh <command>"
  echo ""
  echo "Commands:"
  echo "  up                   Generate crypto, start containers, create channel, deploy chaincode"
  echo "  up createChannel     Start containers and create channel only (skip chaincode deploy)"
  echo "  createChannel        Create channel on a running network"
  echo "  deployCC             Package, install, approve and commit chaincode"
  echo "  down                 Stop containers and remove all volumes/artifacts"
  echo "  restart              down then up"
  echo ""
  echo "Network topology:"
  echo "  hospital  → HospitalOrgMSP  | peer0:7051  | Doctors"
  echo "  patient   → PatientOrgMSP   | peer0:8051  | Patients"
  echo "  pharmacy  → PharmacyOrgMSP  | peer0:9051  | Pharmacists"
  echo "  lab       → LabOrgMSP       | peer0:10051 | Blood-test Labs"
  echo "  insurance → InsuranceOrgMSP | peer0:11051 | Insurers (read-only)"
  echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then printHelp; exit 0; fi

MODE="$1"; shift

case "$MODE" in
  up)
    if [[ $# -ge 1 && "$1" == "createChannel" ]]; then
      networkUp
      createChannel
    else
      networkUp
      createChannel
      deployCC
    fi
    ;;
  createChannel) createChannel ;;
  deployCC)      deployCC ;;
  down)          networkDown ;;
  restart)       networkDown; networkUp; createChannel; deployCC ;;
  *)             printHelp; exit 1 ;;
esac
