#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# HealthScore Hyperledger Caliper Benchmark & Simulation Suite Runner
# -----------------------------------------------------------------------------
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HISTORICAL_HASH="af935716155e10e457f593c2bd22ad55776af362c1095bd84a8a76025c856672"

usage() {
  echo "Usage: $0 <command> [options]"
  echo ""
  echo "Commands:"
  echo "  check-prereqs       Check host environment, Docker daemon, and image prerequisites"
  echo "  verify-historical   Verify byte-for-byte SHA-256 hash of historical Caliper report"
  echo "  live                Run Caliper against an existing running Fabric network (safe timestamped output)"
  echo "  isolated            Provision isolated 5-org testbed, deploy chaincode, run Caliper, and cleanup"
  echo "  simulate [args]     Run the fallback discrete-event queueing performance simulator"
  echo "  test-simulator      Run the pytest test suite for the queueing simulator"
  echo ""
  echo "Examples:"
  echo "  $0 check-prereqs"
  echo "  $0 verify-historical"
  echo "  $0 isolated"
  echo "  $0 simulate --seeds 100"
  echo "  $0 test-simulator"
  exit 1
}

cmd_check_prereqs() {
  echo "========================================================="
  echo " Checking Environment Prerequisites"
  echo "========================================================="
  local err=0

  echo -n "Checking Docker daemon... "
  if docker info >/dev/null 2>&1; then
    echo "✓ ONLINE ($(docker --version))"
  else
    echo "❌ OFFLINE or NOT ACCESSIBLE"
    err=1
  fi

  echo -n "Checking Node.js... "
  if command -v node >/dev/null 2>&1; then
    echo "✓ $(node --version)"
  else
    echo "❌ Missing Node.js"
    err=1
  fi

  echo -n "Checking Python environment... "
  if [ -f "$REPO_ROOT/ml_model/venv/bin/python" ]; then
    echo "✓ $($REPO_ROOT/ml_model/venv/bin/python --version)"
  else
    echo "❌ Missing virtualenv at ml_model/venv"
    err=1
  fi

  echo -n "Checking required Docker images... "
  local images=("hyperledger/fabric-tools:latest" "node:20-alpine" "hyperledger/fabric-nodeenv:2.5")
  for img in "${images[@]}"; do
    if docker image inspect "$img" >/dev/null 2>&1; then
      echo -n "✓ $img "
    else
      echo -n "⚠️ missing $img "
    fi
  done
  echo ""

  if [ $err -eq 0 ]; then
    echo "✓ All core prerequisites satisfied!"
  else
    echo "❌ Prerequisites check failed. Please resolve above items."
    return 1
  fi
}

cmd_verify_historical() {
  echo "========================================================="
  echo " Verifying Historical Caliper Report Integrity"
  echo " Target: $SCRIPT_DIR/report.html"
  echo " Expected SHA-256: $HISTORICAL_HASH"
  echo "========================================================="
  if [ ! -f "$SCRIPT_DIR/report.html" ]; then
    echo "❌ Error: $SCRIPT_DIR/report.html not found!"
    return 1
  fi
  local actual_hash
  actual_hash=$(python3 -c "import hashlib; print(hashlib.sha256(open('$SCRIPT_DIR/report.html', 'rb').read()).hexdigest())")
  if [ "$actual_hash" == "$HISTORICAL_HASH" ]; then
    echo "✓ VERIFIED: Historical report hash matches byte-for-byte."
    echo "  SHA-256: $actual_hash"
  else
    echo "❌ HASH MISMATCH!"
    echo "  Expected: $HISTORICAL_HASH"
    echo "  Actual:   $actual_hash"
    return 1
  fi
}

cmd_live() {
  echo "========================================================="
  echo " Running Caliper Against Existing Fabric Network"
  echo "========================================================="
  local timestamp
  timestamp="$(date +%Y%m%d-%H%M%S)"
  local outdir="$SCRIPT_DIR/results/live/$timestamp"
  mkdir -p "$outdir"

  # Run in a separate workspace so report.html cannot overwrite historical report
  local ws="/tmp/caliper_run_ws_$timestamp"
  mkdir -p "$ws"
  cp "$SCRIPT_DIR/benchmark.yaml" "$ws/benchmark.yaml"
  cp "$SCRIPT_DIR/workload.js" "$ws/workload.js"
  cp "$SCRIPT_DIR/networkconfig.yaml" "$ws/networkconfig.yaml"

  echo "--> Launching Caliper in $ws..."
  local exit_code=0
  (
    set -eo pipefail
    cd "$ws"
    npx caliper launch manager \
      --caliper-workspace "$ws" \
      --caliper-networkconfig networkconfig.yaml \
      --caliper-benchconfig benchmark.yaml \
      --caliper-flow-only-test \
      --caliper-fabric-gateway-enabled 2>&1 | tee "$outdir/console.log"
  ) || exit_code=$?

  if [ -f "$ws/report.html" ]; then
    mv "$ws/report.html" "$outdir/report.html"
  fi
  rm -rf "$ws"

  if [ $exit_code -ne 0 ]; then
    echo "❌ Live benchmark failed with exit code $exit_code"
    return $exit_code
  fi
  echo "✓ Live benchmark complete! Report saved to $outdir/report.html"
}

cmd_isolated() {
  echo "========================================================="
  echo " Provisioning Isolated Testbed & Running Caliper"
  echo "========================================================="
  bash "$SCRIPT_DIR/orchestrate_isolated_benchmark.sh" "$@"
}

cmd_simulate() {
  echo "========================================================="
  echo " Running Queueing Fallback Performance Simulation"
  echo "========================================================="
  local py="$REPO_ROOT/ml_model/venv/bin/python"
  if [ ! -f "$py" ]; then
    py="python3"
  fi
  "$py" "$SCRIPT_DIR/simulate_benchmark.py" "$@"
}

cmd_test_simulator() {
  echo "========================================================="
  echo " Running Simulator Test Suite"
  echo "========================================================="
  local pytest="$REPO_ROOT/ml_model/venv/bin/pytest"
  if [ ! -f "$pytest" ]; then
    pytest="pytest"
  fi
  "$pytest" "$SCRIPT_DIR/tests/test_simulate_benchmark.py" -v
}

# Subcommand dispatch
case "$1" in
  check-prereqs)
    shift
    cmd_check_prereqs "$@"
    ;;
  verify-historical)
    shift
    cmd_verify_historical "$@"
    ;;
  live)
    shift
    cmd_live "$@"
    ;;
  isolated)
    shift
    cmd_isolated "$@"
    ;;
  simulate)
    shift
    cmd_simulate "$@"
    ;;
  test-simulator)
    shift
    cmd_test_simulator "$@"
    ;;
  *)
    usage
    ;;
esac
