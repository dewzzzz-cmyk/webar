#!/bin/bash
# =============================================================================
# PPE Detection System - Test Runner
# =============================================================================
# 
# Usage:
#   ./run_tests.sh              - Run all tests
#   ./run_tests.sh unit         - Run only unit tests
#   ./run_tests.sh integration  - Run only integration tests  
#   ./run_tests.sh coverage     - Run with coverage report
#   ./run_tests.sh quick        - Quick smoke tests
#
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  PPE Detection System - Test Runner ${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Install dependencies if needed
install_deps() {
    echo -e "${YELLOW}Installing test dependencies...${NC}"
    pip install -q -r "$SCRIPT_DIR/requirements.txt"
}

# Run unit tests
run_unit() {
    echo -e "${GREEN}Running unit tests...${NC}"
    cd "$PROJECT_DIR"
    python -m pytest tests/unit/ -v --tb=short
}

# Run integration tests  
run_integration() {
    echo -e "${GREEN}Running integration tests...${NC}"
    cd "$PROJECT_DIR"
    python -m pytest tests/integration/ -v --tb=short
}

# Run all tests
run_all() {
    echo -e "${GREEN}Running all tests...${NC}"
    cd "$PROJECT_DIR"
    python -m pytest tests/ -v --tb=short
}

# Run with coverage
run_coverage() {
    echo -e "${GREEN}Running tests with coverage...${NC}"
    cd "$PROJECT_DIR"
    python -m pytest tests/ \
        --cov=services \
        --cov-report=html:tests/coverage_html \
        --cov-report=term-missing \
        --cov-fail-under=50 \
        -v --tb=short
    echo ""
    echo -e "${GREEN}Coverage report generated: tests/coverage_html/index.html${NC}"
}

# Quick smoke tests
run_quick() {
    echo -e "${GREEN}Running quick smoke tests...${NC}"
    cd "$PROJECT_DIR"
    python -m pytest tests/unit/test_training_api.py -v --tb=short -x -q
}

# Main
case "${1:-all}" in
    unit)
        run_unit
        ;;
    integration)
        run_integration
        ;;
    coverage)
        run_coverage
        ;;
    quick)
        run_quick
        ;;
    install)
        install_deps
        ;;
    all|"")
        run_all
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo "Usage: $0 [unit|integration|coverage|quick|install|all]"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Tests completed!${NC}"
