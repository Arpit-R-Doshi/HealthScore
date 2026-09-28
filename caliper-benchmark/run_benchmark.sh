#!/bin/bash
# -----------------------------------------------------------------------------
# Script to run Hyperledger Caliper Benchmark for HealthScore Network
# -----------------------------------------------------------------------------

cd "$(dirname "$0")"

echo "========================================================="
echo " Installing Hyperledger Caliper CLI..."
echo "========================================================="
npm install --no-save @hyperledger/caliper-cli@0.5.0

echo "========================================================="
echo " Binding Caliper to Fabric SDK..."
echo "========================================================="
npx caliper bind --caliper-bind-sut fabric:2.4

echo "========================================================="
echo " Running Benchmark..."
echo "========================================================="

# Note: Make sure the paths in networkconfig.yaml point to your actual admin cert/key.
# If the keystore file ends in _sk, you might need to update the path in networkconfig.yaml first.

npx caliper launch manager \
    --caliper-workspace . \
    --caliper-networkconfig networkconfig.yaml \
    --caliper-benchconfig benchmark.yaml \
    --caliper-flow-only-test \
    --caliper-fabric-gateway-enabled

echo "========================================================="
echo " Benchmark Complete. Check the generated report.html!"
echo "========================================================="
