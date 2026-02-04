# 🦺 PPE Detection System v2.1

**Система контроля средств индивидуальной защиты на производстве**

Микросервисная архитектура + React Dashboard для мониторинга соблюдения требований охраны труда.

![Dashboard Preview](docs/dashboard-preview.png)

## ✨ Возможности

- 🎥 **RTSP камеры** — поддержка IP-камер (Hikvision, Dahua, Axis)
- 🧠 **YOLOv8 детекция** — каски, жилеты, очки, перчатки
- 📱 **Telegram алерты** — мгновенные уведомления о нарушениях
- 🖥️ **React Dashboard** — веб-интерфейс с live-видео
- 📊 **Аналитика** — графики, статистика, экспорт Excel
- 🔐 **JWT авторизация** — защищённый API
- 🐳 **Docker** — простое развёртывание

## 🏗️ Архитектура

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Камеры    │───▶│   Capture   │───▶│  Detector   │
│   (RTSP)    │    │   Service   │    │  (YOLOv8)   │
└─────────────┘    └──────┬──────┘    └──────┬──────┘
                         │                  │
                         ▼                  ▼
                  ┌─────────────────────────────────┐
                  │         Redis Streams           │
                  └─────────────────────────────────┘
                                │
                  ┌─────────────┼─────────────┐
                  ▼             ▼             ▼
           ┌──────────┐  ┌──────────┐  ┌──────────┐
           │   API    │  │ Postgres │  │ Alerter  │
           │(FastAPI) │  │    DB    │  │(Telegram)│
           └────┬─────┘  └──────────┘  └──────────┘
                │
                ▼
         ┌──────────────┐
         │  Dashboard   │
         │   (React)    │
         └──────────────┘
```

## 🚀 Быстрый старт

### Требования

- Docker 20.10+
- Docker Compose 2.0+
- 8 GB RAM
- NVIDIA GPU (опционально)

### 1. Настройка

```bash
# Распаковать
cd ppe_system_v2

# Создать .env
cp .env.example .env

# Отредактировать пароли и Telegram токен
nano .env
```

### 2. Модель детекции

```bash
# Запустить мастер настройки
python scripts/setup_model.py
```

### 3. Запуск

```bash
# С GPU
docker compose up -d

# Без GPU
docker compose --profile cpu up -d
```

### 4. Открыть Dashboard

| Сервис | URL | Логин |
|--------|-----|-------|
| **Dashboard** | http://localhost | admin / admin123 |
| API Docs | http://localhost:8000/docs | - |

## 📁 Структура

```
ppe_system_v2/
├── dashboard/              # 🖥️ React веб-интерфейс
│   ├── src/
│   │   ├── pages/         # Dashboard, Violations, Analytics
│   │   ├── components/    # CameraCard, ViolationCard
│   │   └── hooks/         # useWebSocket
│   └── Dockerfile
├── services/
│   ├── capture/           # 📹 RTSP захват камер
│   ├── detector/          # 🧠 YOLOv8 детекция
│   ├── api/               # 🌐 FastAPI + WebSocket
│   └── alerter/           # 📱 Telegram бот
├── configs/
│   ├── cameras.yaml       # Настройка камер
│   └── zones.yaml         # Зоны и правила СИЗ
├── models/                # PPE модели (.pt)
├── scripts/
│   ├── setup_model.py     # Мастер настройки модели
│   └── init_db.sql        # Схема PostgreSQL
├── tests/                 # Unit и integration тесты
├── docker-compose.yml
└── .env.example
```

## 🖥️ Dashboard

### Экраны

1. **Мониторинг** — сетка камер + лента нарушений
2. **Журнал** — таблица нарушений с фильтрами
3. **Аналитика** — графики и статистика
4. **Настройки** — камеры, зоны, пользователи

### Функции

- 📹 Live-видео с камер (WebSocket)
- 🔔 Звуковые уведомления
- 📊 Экспорт в Excel
- 🖥️ Kiosk mode для диспетчерской
- 📱 Адаптивный дизайн

## ⚙️ Конфигурация

### Камеры (configs/cameras.yaml)

```yaml
cameras:
  - id: cam_entrance
    name: "Входная группа"
    rtsp_url: "rtsp://admin:password@192.168.1.100:554/stream"
    fps: 5
    zone_id: zone_entrance
```

### Зоны (configs/zones.yaml)

```yaml
zones:
  - id: zone_welding
    name: "Сварочный участок"
    required_ppe:
      - hardhat
      - vest
      - glasses
      - gloves
    cooldown_seconds: 30
```

### Переменные окружения (.env)

```env
# Database
POSTGRES_PASSWORD=your_secure_password

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789

# Security
JWT_SECRET=your_very_long_secret_key
API_USERNAME=admin
API_PASSWORD=secure_password
```

## 📡 API

### Авторизация

```bash
# Получить токен
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Использовать токен
curl http://localhost:8000/api/violations \
  -H "Authorization: Bearer <token>"
```

### Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | /api/auth/login | Авторизация |
| GET | /api/violations | Список нарушений |
| GET | /api/statistics | Статистика |
| GET | /api/cameras | Список камер |
| WS | /ws | Real-time события |

## 🔧 Разработка

### Локальный запуск Dashboard

```bash
cd dashboard
npm install
npm run dev  # http://localhost:3000
```

### Тесты

```bash
cd tests
pip install -r requirements.txt
pytest
```

## 📊 Мониторинг

```bash
# Запуск с Prometheus + Grafana
docker compose --profile monitoring up -d

# Grafana: http://localhost:3000 (admin/admin)
```

## 🆘 Troubleshooting

### Камера не подключается

```bash
# Проверить RTSP URL
ffprobe rtsp://admin:password@192.168.1.100:554/stream
```

### Модель не найдена

```bash
# Запустить мастер настройки
python scripts/setup_model.py
```

### GPU не определяется

```bash
# Проверить NVIDIA драйверы
nvidia-smi

# Использовать CPU версию
docker compose --profile cpu up -d
```

## 📝 Changelog

### v2.1.0
- ✨ React Dashboard с Tailwind CSS
- 🔐 JWT аутентификация + Rate limiting
- 🛠️ Исправлен трекинг между камерами
- 🛠️ Cooldown в Redis (не в памяти)
- 🛠️ Обработка pending messages
- 📊 Экспорт в Excel

### v2.0.0
- 🏗️ Микросервисная архитектура
- 📹 RTSP поддержка
- 📱 Telegram алерты
- 🐳 Docker Compose

## 📄 Лицензия

MIT License

---

**PPE Detection System** — разработано для безопасности на производстве 🦺
