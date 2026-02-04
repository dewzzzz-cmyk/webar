#!/bin/bash
# 🚀 PPE Detection System - Quick Start Script
# Использование: ./quick_start.sh [cpu|gpu]

set -e

MODE=${1:-cpu}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=================================================="
echo "🚀 PPE DETECTION SYSTEM - QUICK START"
echo "=================================================="
echo ""
echo "📍 Директория: $PROJECT_DIR"
echo "🖥️  Режим: $MODE"
echo ""

# Проверка Docker
echo "🔍 Проверка Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    echo "   Установите: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker daemon не запущен!"
    exit 1
fi
echo "✅ Docker OK"

# Проверка docker-compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose не установлен!"
    exit 1
fi
echo "✅ Docker Compose OK"

# Создаём .env если нет
if [ ! -f .env ]; then
    echo ""
    echo "📝 Создаём .env из примера..."
    cp .env.example .env
    
    # Генерируем случайный JWT_SECRET
    JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
    sed -i "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env 2>/dev/null || \
    sed -i '' "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
    
    echo "✅ .env создан"
    echo "⚠️  Отредактируйте .env для настройки Telegram и паролей"
fi

# Проверка модели
echo ""
echo "🔍 Проверка модели..."
if [ ! -f models/ppe_model.pt ] && [ ! -f models/yolov8n.pt ]; then
    echo "⚠️  Модель не найдена!"
    echo ""
    echo "   Скачайте модель одним из способов:"
    echo ""
    echo "   1. Автоматически (требует Python + ultralytics):"
    echo "      python scripts/setup_ppe_model.py"
    echo ""
    echo "   2. Вручную:"
    echo "      wget -O models/yolov8n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt"
    echo "      ln -sf yolov8n.pt models/ppe_model.pt"
    echo ""
    echo "   3. Через Python:"
    echo "      python -c \"from ultralytics import YOLO; YOLO('yolov8n.pt')\""
    echo "      mv yolov8n.pt models/"
    echo "      ln -sf yolov8n.pt models/ppe_model.pt"
    echo ""
    
    read -p "Продолжить без модели? (система не будет детектить) [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ Модель найдена"
fi

# Создаём директории
mkdir -p models logs

# Запускаем
echo ""
echo "🐳 Запуск контейнеров..."
echo ""

if [ "$MODE" == "gpu" ]; then
    echo "🎮 Режим GPU"
    docker-compose up -d
else
    echo "💻 Режим CPU (без GPU)"
    docker-compose --profile cpu up -d
fi

# Ждём запуска
echo ""
echo "⏳ Ожидание запуска сервисов..."
sleep 10

# Проверяем статус
echo ""
echo "📊 Статус сервисов:"
docker-compose ps

# Проверяем health
echo ""
echo "🏥 Проверка здоровья..."

# Redis
if docker-compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "✅ Redis: OK"
else
    echo "⚠️  Redis: проверьте логи"
fi

# PostgreSQL
if docker-compose exec -T postgres pg_isready -U ppe 2>/dev/null | grep -q "accepting"; then
    echo "✅ PostgreSQL: OK"
else
    echo "⚠️  PostgreSQL: проверьте логи"
fi

# API
sleep 5
if curl -s http://localhost:8000/health 2>/dev/null | grep -q "ok"; then
    echo "✅ API: OK"
else
    echo "⚠️  API: возможно ещё запускается..."
fi

echo ""
echo "=================================================="
echo "✅ СИСТЕМА ЗАПУЩЕНА!"
echo "=================================================="
echo ""
echo "🌐 Dashboard:  http://localhost:80"
echo "🔌 API:        http://localhost:8000"
echo "📖 API Docs:   http://localhost:8000/docs"
echo ""
echo "🔑 Вход по умолчанию:"
echo "   Логин:  admin"
echo "   Пароль: admin123"
echo ""
echo "📋 Полезные команды:"
echo "   docker-compose logs -f        # Смотреть логи"
echo "   docker-compose ps             # Статус сервисов"
echo "   docker-compose down           # Остановить"
echo "   docker-compose restart api    # Перезапустить сервис"
echo ""
echo "📊 Мониторинг (опционально):"
echo "   docker-compose --profile monitoring up -d"
echo "   Grafana:     http://localhost:3000"
echo "   Prometheus:  http://localhost:9090"
echo ""
