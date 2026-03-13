#!/usr/bin/env bash
#
# envVar.sh — Set peer environment variables for a given org
# Usage: source scripts/envVar.sh && setGlobals hospital
#

ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)"
# Fallback if BASH_SOURCE doesn't work (e.g. zsh)
if [ -z "$ROOTDIR" ] || [ ! -d "$ROOTDIR/organizations" ]; then
  ROOTDIR="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
fi
# Final fallback — use a known absolute path
if [ ! -d "$ROOTDIR/organizations" ]; then
  ROOTDIR="/Users/arpitdoshi/HealthScore-Project/healthscore-network"
fi

setGlobals() {
  local ORG=$1

  case "$ORG" in
    hospital)
      DOMAIN="hospital.healthscore.com"
      MSPID="HospitalOrgMSP"
      PORT="7051"
      ;;
    patient)
      DOMAIN="patient.healthscore.com"
      MSPID="PatientOrgMSP"
      PORT="8051"
      ;;
    pharmacy)
      DOMAIN="pharmacy.healthscore.com"
      MSPID="PharmacyOrgMSP"
      PORT="9051"
      ;;
    lab)
      DOMAIN="lab.healthscore.com"
      MSPID="LabOrgMSP"
      PORT="10051"
      ;;
    insurance)
      DOMAIN="insurance.healthscore.com"
      MSPID="InsuranceOrgMSP"
      PORT="11051"
      ;;
    *)
      echo "ERROR: Unknown org '$ORG'. Valid: hospital | patient | pharmacy | lab | insurance"
      return 1
      ;;
  esac

  export FABRIC_CFG_PATH="${ROOTDIR}/../fabric-samples/config"
  export CORE_PEER_TLS_ENABLED=true
  export CORE_PEER_LOCALMSPID="$MSPID"
  export CORE_PEER_TLS_ROOTCERT_FILE="${ROOTDIR}/organizations/peerOrganizations/${DOMAIN}/peers/peer0.${DOMAIN}/tls/ca.crt"
  export CORE_PEER_MSPCONFIGPATH="${ROOTDIR}/organizations/peerOrganizations/${DOMAIN}/users/Admin@${DOMAIN}/msp"
  export CORE_PEER_ADDRESS="localhost:${PORT}"
  export ORDERER_CA="${ROOTDIR}/organizations/ordererOrganizations/healthscore.com/orderers/orderer.healthscore.com/msp/tlscacerts/tlsca.healthscore.com-cert.pem"
  export ORDERER_ADMIN_TLS_SIGN_CERT="${ROOTDIR}/organizations/ordererOrganizations/healthscore.com/orderers/orderer.healthscore.com/tls/server.crt"
  export ORDERER_ADMIN_TLS_PRIVATE_KEY="${ROOTDIR}/organizations/ordererOrganizations/healthscore.com/orderers/orderer.healthscore.com/tls/server.key"

  echo "  Globals set → org=${ORG} msp=${MSPID} peer=localhost:${PORT}"
}

printGlobals() {
  echo "CORE_PEER_LOCALMSPID     = $CORE_PEER_LOCALMSPID"
  echo "CORE_PEER_ADDRESS        = $CORE_PEER_ADDRESS"
  echo "CORE_PEER_MSPCONFIGPATH  = $CORE_PEER_MSPCONFIGPATH"
}
