#!/bin/bash
# ============================================================================
# PPE Detection System - Test Runner
# ============================================================================
# Runs regression and integration tests
#
# Usage:
#   ./run_regression_tests.sh          - Run all tests
#   ./run_regression_tests.sh unit     - Run only unit/regression tests
#   ./run_regression_tests.sh api      - Run only API integration tests
# ============================================================================

set -e

echo ""
echo "============================================================================"
echo "  PPE Detection System - Test Suite"
echo "============================================================================"
echo ""

TEST_TYPE=${1:-all}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found"
    exit 1
fi

# Install test dependencies
echo "[*] Installing test dependencies..."
pip3 install pytest pytest-asyncio httpx aiohttp -q 2>/dev/null || \
pip3 install --break-system-packages pytest pytest-asyncio httpx aiohttp -q 2>/dev/null || true

# Set Python path
export PYTHONPATH="${SCRIPT_DIR}/..:${SCRIPT_DIR}/../services/api:${PYTHONPATH}"

RESULT=0

run_unit_tests() {
    echo ""
    echo "[*] Running Regression Tests (Unit)..."
    echo "============================================================================"
    
    if python3 -m pytest "${SCRIPT_DIR}/regression" -v --tb=short; then
        echo "[PASSED] Regression tests passed"
    else
        echo "[FAILED] Regression tests failed"
        RESULT=1
    fi
}

run_api_tests() {
    echo ""
    echo "[*] Running API Integration Tests..."
    echo "============================================================================"
    echo "[!] Note: Requires running API server at http://localhost:8000"
    echo ""
    
    # Check if API is running
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "[WARN] API server not running, skipping integration tests"
        return
    fi
    
    if python3 -m pytest "${SCRIPT_DIR}/integration/test_training_v2_10_62.py" -v --tb=short; then
        echo "[PASSED] Integration tests passed"
    else
        echo "[FAILED] Integration tests failed"
        RESULT=1
    fi
}

case "$TEST_TYPE" in
    unit)
        run_unit_tests
        ;;
    api)
        run_api_tests
        ;;
    all)
        run_unit_tests
        run_api_tests
        ;;
    *)
        echo "Usage: $0 [unit|api|all]"
        exit 1
        ;;
esac

echo ""
echo "============================================================================"
if [ $RESULT -eq 0 ]; then
    echo "  TEST RESULT: PASSED"
else
    echo "  TEST RESULT: FAILED"
fi
echo "============================================================================"
echo ""

exit $RESULT
