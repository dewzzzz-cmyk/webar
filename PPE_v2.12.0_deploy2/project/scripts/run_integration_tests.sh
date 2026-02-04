#!/bin/bash
# =============================================================================
# PPE Detection System - Integration Tests Runner
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=================================================="
echo "🧪 PPE Detection - Integration Tests"
echo "=================================================="

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен"
    exit 1
fi

# Parse arguments
CLEAN=false
KEEP=false
VERBOSE=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --clean) CLEAN=true ;;
        --keep) KEEP=true ;;
        -v|--verbose) VERBOSE="-v" ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Clean up if requested
if [ "$CLEAN" = true ]; then
    echo "🧹 Очистка предыдущих тестовых контейнеров..."
    docker-compose -f docker-compose.test.yml down -v --remove-orphans 2>/dev/null || true
fi

# Create results directory
mkdir -p test-results

echo ""
echo "📦 Запуск тестовых сервисов..."
docker-compose -f docker-compose.test.yml up -d test-postgres test-redis

echo ""
echo "⏳ Ожидание готовности БД..."
sleep 5

# Wait for postgres
for i in {1..30}; do
    if docker-compose -f docker-compose.test.yml exec -T test-postgres pg_isready -U ppe_test -d ppe_test_db &>/dev/null; then
        echo "✅ PostgreSQL готов"
        break
    fi
    echo "   Ожидание PostgreSQL... ($i/30)"
    sleep 2
done

# Wait for redis
for i in {1..30}; do
    if docker-compose -f docker-compose.test.yml exec -T test-redis redis-cli ping &>/dev/null; then
        echo "✅ Redis готов"
        break
    fi
    echo "   Ожидание Redis... ($i/30)"
    sleep 1
done

echo ""
echo "🚀 Запуск API сервиса..."
docker-compose -f docker-compose.test.yml up -d test-api

echo ""
echo "⏳ Ожидание готовности API..."
for i in {1..60}; do
    if curl -s http://localhost:8001/health &>/dev/null; then
        echo "✅ API готов"
        break
    fi
    echo "   Ожидание API... ($i/60)"
    sleep 2
done

echo ""
echo "🧪 Запуск тестов..."
echo "=================================================="

# Run tests
docker-compose -f docker-compose.test.yml run --rm test-runner \
    pytest tests/integration/ $VERBOSE \
    --tb=short \
    --junitxml=/app/test-results/integration.xml \
    --html=/app/test-results/integration.html \
    --self-contained-html \
    || TEST_EXIT_CODE=$?

echo ""
echo "=================================================="

# Copy results
if [ -f test-results/integration.html ]; then
    echo "📊 Отчёт: test-results/integration.html"
fi

if [ -f test-results/integration.xml ]; then
    echo "📋 JUnit XML: test-results/integration.xml"
fi

# Cleanup unless --keep
if [ "$KEEP" = false ]; then
    echo ""
    echo "🧹 Остановка тестовых контейнеров..."
    docker-compose -f docker-compose.test.yml down -v
else
    echo ""
    echo "ℹ️  Контейнеры оставлены запущенными (--keep)"
    echo "   Остановить: docker-compose -f docker-compose.test.yml down -v"
fi

echo ""
if [ "${TEST_EXIT_CODE:-0}" -eq 0 ]; then
    echo "✅ Все тесты прошли!"
else
    echo "❌ Некоторые тесты провалились (exit code: $TEST_EXIT_CODE)"
    exit $TEST_EXIT_CODE
fi
