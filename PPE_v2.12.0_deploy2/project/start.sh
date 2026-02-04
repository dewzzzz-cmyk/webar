#!/bin/bash

# PPE Detection System v2.8 - Start Script
# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

show_menu() {
    clear
    echo -e "${CYAN}"
    echo "  ╔═══════════════════════════════════════════════════════════════╗"
    echo "  ║           🦺 PPE DETECTION SYSTEM v2.8                        ║"
    echo "  ║              Система контроля СИЗ                             ║"
    echo "  ╠═══════════════════════════════════════════════════════════════╣"
    echo "  ║                                                               ║"
    echo "  ║   [1] 🚀 Быстрый запуск (start)                              ║"
    echo "  ║   [2] 📦 Полная установка (install)                          ║"
    echo "  ║   [3] 🔄 Перезапуск (restart)                                ║"
    echo "  ║   [4] 🔨 Пересборка + запуск (rebuild)                       ║"
    echo "  ║   [5] ⏹️  Остановить систему (stop)                           ║"
    echo "  ║   [6] 📊 Статус контейнеров (status)                         ║"
    echo "  ║   [7] 📋 Логи (logs)                                         ║"
    echo "  ║   [8] 🧹 Очистка Docker (clean)                              ║"
    echo "  ║   [9] 🌐 Открыть в браузере                                  ║"
    echo "  ║   [0] ❌ Выход                                                ║"
    echo "  ║                                                               ║"
    echo "  ╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_docker() {
    echo -e "${BLUE}[*] Проверка Docker...${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker не установлен!${NC}"
        echo "Установите Docker: https://docs.docker.com/get-docker/"
        return 1
    fi
    
    if ! docker info &> /dev/null; then
        echo -e "${RED}❌ Docker не запущен!${NC}"
        echo "Запустите Docker и попробуйте снова."
        return 1
    fi
    
    echo -e "${GREEN}    ✓ Docker работает${NC}"
    return 0
}

check_env() {
    if [ ! -f .env ]; then
        echo -e "${BLUE}[*] Создание .env...${NC}"
        if [ -f .env.example ]; then
            cp .env.example .env
        else
            cat > .env << EOF
JWT_SECRET=your-super-secret-jwt-key-change-in-production-min-32-chars
POSTGRES_PASSWORD=ppe_secure_password_2024
REDIS_PASSWORD=redis_password_2024
MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=minio_secure_password_2024
EOF
        fi
        echo -e "${GREEN}    ✓ .env создан${NC}"
    fi
}

health_check() {
    echo ""
    echo -e "${CYAN}  Проверка сервисов:${NC}"
    echo "  ─────────────────"
    
    # Check API
    if curl -s -o /dev/null -w "" http://localhost:8000/health 2>/dev/null; then
        echo -e "  API:        ${GREEN}✅ Работает (порт 8000)${NC}"
    else
        echo -e "  API:        ${RED}❌ Недоступен${NC}"
    fi
    
    # Check Dashboard
    if curl -s -o /dev/null -w "" http://localhost 2>/dev/null; then
        echo -e "  Dashboard:  ${GREEN}✅ Работает (порт 80)${NC}"
    else
        echo -e "  Dashboard:  ${RED}❌ Недоступен${NC}"
    fi
    
    # Check containers
    RUNNING=$(docker compose ps -q 2>/dev/null | wc -l)
    echo "  Контейнеры: $RUNNING запущено"
}

show_urls() {
    echo -e "${CYAN}"
    echo "  ┌─────────────────────────────────────────────────────────────┐"
    echo "  │  🌐 Dashboard:    http://localhost                          │"
    echo "  │  🔌 API:          http://localhost:8000                     │"
    echo "  │  📚 API Docs:     http://localhost:8000/docs                │"
    echo "  │  📊 Grafana:      http://localhost:3001  (admin/admin)      │"
    echo "  └─────────────────────────────────────────────────────────────┘"
    echo -e "${NC}"
}

do_start() {
    clear
    echo -e "${CYAN}  🚀 Быстрый запуск...${NC}"
    echo "  ═══════════════════════════════════════════════════════════════"
    echo ""
    
    check_docker || return
    check_env
    
    echo -e "${BLUE}[*] Запуск контейнеров...${NC}"
    docker compose up -d
    
    echo ""
    echo -e "${GREEN}  ✅ Система запущена!${NC}"
    echo ""
    show_urls
    read -p "Нажмите Enter для продолжения..."
}

do_install() {
    clear
    echo -e "${CYAN}  📦 Полная установка PPE System v2.8${NC}"
    echo "  ═══════════════════════════════════════════════════════════════"
    echo ""
    
    check_docker || return
    
    # Create .env
    echo -e "${BLUE}[1/5] Проверка конфигурации...${NC}"
    check_env
    
    # Create directories
    echo -e "${BLUE}[2/5] Создание директорий...${NC}"
    mkdir -p models logs data
    echo -e "${GREEN}      ✓ Директории созданы${NC}"
    
    # Stop old containers
    echo -e "${BLUE}[3/5] Остановка старых контейнеров...${NC}"
    docker compose down 2>/dev/null
    echo -e "${GREEN}      ✓ Готово${NC}"
    
    # Build
    echo -e "${BLUE}[4/5] Сборка контейнеров (это может занять 5-10 минут)...${NC}"
    echo ""
    docker compose build --no-cache
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}[!] Ошибка сборки!${NC}"
        read -p "Нажмите Enter..."
        return
    fi
    
    # Start
    echo ""
    echo -e "${BLUE}[5/5] Запуск системы...${NC}"
    docker compose up -d
    
    # Wait
    echo ""
    echo -e "${BLUE}[*] Ожидание готовности сервисов...${NC}"
    sleep 10
    
    # Health check
    echo -e "${BLUE}[*] Проверка состояния...${NC}"
    health_check
    
    echo ""
    echo -e "${GREEN}  ╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}  ║                  ✅ УСТАНОВКА ЗАВЕРШЕНА!                      ║${NC}"
    echo -e "${GREEN}  ╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    show_urls
    echo ""
    echo "  Логин: admin"
    echo "  Пароль: admin123"
    echo ""
    read -p "Нажмите Enter для продолжения..."
}

do_restart() {
    clear
    echo -e "${CYAN}  🔄 Перезапуск системы...${NC}"
    echo "  ═══════════════════════════════════════════════════════════════"
    echo ""
    
    check_docker || return
    
    echo -e "${BLUE}[*] Перезапуск контейнеров...${NC}"
    docker compose restart
    
    echo ""
    echo -e "${GREEN}  ✅ Система перезапущена!${NC}"
    echo ""
    sleep 3
    health_check
    read -p "Нажмите Enter для продолжения..."
}

do_rebuild() {
    clear
    echo -e "${CYAN}  🔨 Пересборка и запуск${NC}"
    echo "  ═══════════════════════════════════════════════════════════════"
    echo ""
    echo "  Это пересоберёт ВСЕ контейнеры с нуля."
    echo "  Используйте после обновления файлов."
    echo ""
    read -p "Продолжить? (y/n): " confirm
    [ "$confirm" != "y" ] && return
    
    check_docker || return
    check_env
    
    echo ""
    echo -e "${BLUE}[1/4] Остановка контейнеров...${NC}"
    docker compose down
    echo -e "${GREEN}      ✓ Готово${NC}"
    
    echo -e "${BLUE}[2/4] Очистка старых образов...${NC}"
    docker compose rm -f 2>/dev/null
    echo -e "${GREEN}      ✓ Готово${NC}"
    
    echo -e "${BLUE}[3/4] Пересборка (это займёт несколько минут)...${NC}"
    echo ""
    docker compose build --no-cache
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}[!] Ошибка сборки!${NC}"
        read -p "Нажмите Enter..."
        return
    fi
    
    echo ""
    echo -e "${BLUE}[4/4] Запуск...${NC}"
    docker compose up -d
    
    echo ""
    echo -e "${BLUE}[*] Ожидание готовности...${NC}"
    sleep 10
    
    health_check
    
    echo ""
    echo -e "${GREEN}  ✅ Пересборка завершена!${NC}"
    echo ""
    show_urls
    read -p "Нажмите Enter для продолжения..."
}

do_stop() {
    clear
    echo -e "${CYAN}  ⏹️  Остановка системы...${NC}"
    echo "  ═══════════════════════════════════════════════════════════════"
    echo ""
    
    docker compose down
    
    echo ""
    echo -e "${GREEN}  ✅ Система остановлена${NC}"
    echo ""
    read -p "Нажмите Enter для продолжения..."
}

do_status() {
    clear
    echo -e "${CYAN}  📊 Статус контейнеров${NC}"
    echo "  ═══════════════════════════════════════════════════════════════"
    echo ""
    
    docker compose ps
    
    echo ""
    echo "  ───────────────────────────────────────────────────────────────"
    
    health_check
    
    echo ""
    read -p "Нажмите Enter для продолжения..."
}

do_logs() {
    while true; do
        clear
        echo -e "${CYAN}  📋 Выбор логов${NC}"
        echo "  ═══════════════════════════════════════════════════════════════"
        echo ""
        echo "   [1] Все логи (последние 50 строк)"
        echo "   [2] API"
        echo "   [3] Dashboard"
        echo "   [4] Detector"
        echo "   [5] Capture"
        echo "   [6] PostgreSQL"
        echo "   [7] Следить за логами в реальном времени (Ctrl+C для выхода)"
        echo "   [0] Назад"
        echo ""
        read -p "Выберите [0-7]: " logchoice
        
        case $logchoice in
            1) docker compose logs --tail 50; read -p "Нажмите Enter..." ;;
            2) docker compose logs api --tail 100; read -p "Нажмите Enter..." ;;
            3) docker compose logs dashboard --tail 100; read -p "Нажмите Enter..." ;;
            4) docker compose logs detector --tail 100; read -p "Нажмите Enter..." ;;
            5) docker compose logs capture --tail 100; read -p "Нажмите Enter..." ;;
            6) docker compose logs postgres --tail 100; read -p "Нажмите Enter..." ;;
            7) echo "Нажмите Ctrl+C для выхода..."; docker compose logs -f --tail 20 ;;
            0) return ;;
        esac
    done
}

do_clean() {
    while true; do
        clear
        echo -e "${CYAN}  🧹 Очистка Docker${NC}"
        echo "  ═══════════════════════════════════════════════════════════════"
        echo ""
        echo "   [1] Лёгкая очистка (удаление остановленных контейнеров)"
        echo "   [2] Средняя очистка (+ неиспользуемые образы)"
        echo -e "   [3] Полная очистка (+ volumes) ${RED}⚠️  УДАЛИТ ДАННЫЕ БД!${NC}"
        echo "   [0] Назад"
        echo ""
        read -p "Выберите [0-3]: " cleanchoice
        
        case $cleanchoice in
            1)
                echo ""
                echo -e "${BLUE}[*] Лёгкая очистка...${NC}"
                docker compose down
                docker container prune -f
                echo -e "${GREEN}✓ Готово${NC}"
                read -p "Нажмите Enter..."
                ;;
            2)
                echo ""
                echo -e "${BLUE}[*] Средняя очистка...${NC}"
                docker compose down
                docker system prune -f
                echo -e "${GREEN}✓ Готово${NC}"
                read -p "Нажмите Enter..."
                ;;
            3)
                echo ""
                echo -e "${RED}⚠️  ВНИМАНИЕ: Это удалит ВСЕ данные включая базу данных!${NC}"
                read -p "Вы уверены? Введите 'YES' для подтверждения: " confirmclean
                if [ "$confirmclean" == "YES" ]; then
                    echo ""
                    echo -e "${BLUE}[*] Полная очистка...${NC}"
                    docker compose down -v
                    docker system prune -af --volumes
                    echo -e "${GREEN}✓ Готово${NC}"
                else
                    echo "Отменено."
                fi
                read -p "Нажмите Enter..."
                ;;
            0) return ;;
        esac
    done
}

do_browser() {
    echo -e "${BLUE}[*] Открытие браузера...${NC}"
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost
    elif command -v open &> /dev/null; then
        open http://localhost
    else
        echo "Откройте браузер вручную: http://localhost"
    fi
    sleep 2
}

# Main loop
while true; do
    show_menu
    read -p "Выберите опцию [0-9]: " choice
    
    case $choice in
        1) do_start ;;
        2) do_install ;;
        3) do_restart ;;
        4) do_rebuild ;;
        5) do_stop ;;
        6) do_status ;;
        7) do_logs ;;
        8) do_clean ;;
        9) do_browser ;;
        0)
            echo ""
            echo -e "${CYAN}  👋 До свидания!${NC}"
            echo ""
            exit 0
            ;;
        *)
            echo "Неверный выбор!"
            sleep 1
            ;;
    esac
done
