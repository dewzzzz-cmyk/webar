# 📋 ПРОТОКОЛ ЭКСПЕРТНОГО СОВЕЩАНИЯ №2

## Оценка готового решения: PPE Detection System v2.0

**Дата:** 27 ноября 2024  
**Формат:** Техническая экспертиза готового решения  
**Цель:** Критическая оценка архитектуры, кода и готовности к production

---

## 👥 УЧАСТНИКИ СОВЕЩАНИЯ

| Роль | Имя | Компетенции |
|------|-----|-------------|
| **Модератор** | Алексей Петров | Руководитель проектов CV, 12 лет опыта |
| **ML-инженер** | Дмитрий Козлов | Computer Vision, YOLO, внедрение на 5+ заводах |
| **MLOps/DevOps** | Мария Сидорова | Docker, K8s, CI/CD, 6 лет опыта |
| **Backend-архитектор** | Игорь Волков | Микросервисы, высоконагруженные системы |
| **Security-инженер** | Андрей Белов | AppSec, инфраструктурная безопасность |
| **QA Lead** | Ольга Краснова | Тестирование ML-систем, автоматизация |
| **Представитель заказчика** | Сергей Морозов | Начальник производства |

---

## 1️⃣ ОБЩАЯ ОЦЕНКА АРХИТЕКТУРЫ

### Алексей Петров (модератор):

> Коллеги, перед нами PPE Detection System v2.0. Давайте оценим по шкале готовности к production.

### Игорь Волков (архитектор):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ОЦЕНКА АРХИТЕКТУРЫ: 7.5/10                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ✅ СИЛЬНЫЕ СТОРОНЫ:                                                   │
│                                                                         │
│  • Микросервисная архитектура — правильное разделение ответственности  │
│  • Redis Streams — отличный выбор для video pipeline                   │
│  • Docker Compose — простой деплой, готовность к K8s                   │
│  • Graceful shutdown — обработка SIGTERM/SIGINT                        │
│  • Health checks — для оркестратора                                     │
│  • Stateless сервисы — можно масштабировать горизонтально              │
│                                                                         │
│  ⚠️ ТРЕБУЕТ ДОРАБОТКИ:                                                 │
│                                                                         │
│  • Нет API Gateway / Load Balancer                                      │
│  • Нет централизованного логирования (ELK/Loki)                        │
│  • Нет distributed tracing (Jaeger/Zipkin)                             │
│  • Отсутствует service mesh для production                              │
│  • Нет circuit breaker между сервисами                                  │
│                                                                         │
│  ❌ КРИТИЧЕСКИЕ ЗАМЕЧАНИЯ:                                              │
│                                                                         │
│  • Single point of failure: Redis и PostgreSQL без репликации          │
│  • Нет backup стратегии для БД                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Диаграмма текущей vs целевой архитектуры:

```
ТЕКУЩАЯ (v2.0):                          ЦЕЛЕВАЯ (v2.1 Production):
                                         
┌─────────┐                              ┌─────────┐
│ Capture │──┐                           │ Capture │──┐
└─────────┘  │                           │ (x3)    │  │
             │  ┌───────┐                └─────────┘  │  ┌───────────┐
             ├─▶│ Redis │                             ├─▶│Redis      │
             │  │(single)│                            │  │Cluster    │
┌─────────┐  │  └───────┘                ┌─────────┐  │  └───────────┘
│Detector │──┤                           │Detector │──┤
│ (GPU)   │  │  ┌────────┐               │ (x2 GPU)│  │  ┌───────────┐
└─────────┘  ├─▶│Postgres│               └─────────┘  ├─▶│PostgreSQL │
             │  │(single)│                            │  │Primary+   │
┌─────────┐  │  └────────┘               ┌─────────┐  │  │Replica    │
│   API   │──┤                           │   API   │──┤  └───────────┘
└─────────┘  │                           │  (x2)   │  │
             │                           └─────────┘  │  ┌───────────┐
┌─────────┐  │                           ┌─────────┐  │  │  Nginx    │
│ Alerter │──┘                           │ Alerter │──┘  │    LB     │
└─────────┘                              │  (x2)   │     └───────────┘
                                         └─────────┘
```

---

## 2️⃣ АНАЛИЗ КОДА ПО СЕРВИСАМ

### 📹 Capture Service

**Дмитрий Козлов (ML-инженер):**

```python
# ✅ ХОРОШО: Автоматическое переподключение
if state.error_count > 10:
    logger.error(f"[{camera_id}] Слишком много ошибок, переподключение...")
    self.disconnect_camera(camera_id)
    time.sleep(RECONNECT_DELAY)
    self.connect_camera(camera_id)

# ✅ ХОРОШО: Контроль FPS
frame_interval = 1.0 / config.fps
if now - last_capture < frame_interval:
    time.sleep(0.01)
    continue

# ✅ ХОРОШО: RTSP буферизация
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Минимальный буфер для минимальной задержки
```

**Замечания:**

| # | Проблема | Критичность | Рекомендация |
|---|----------|-------------|--------------|
| 1 | `time.sleep(0.01)` в цикле | Средняя | Использовать `asyncio.sleep` или threading.Event |
| 2 | Нет метрик производительности | Средняя | Добавить Prometheus metrics |
| 3 | ThreadPoolExecutor(max_workers=20) | Низкая | Сделать настраиваемым |
| 4 | Нет graceful degradation | Средняя | При потере камеры не ронять весь сервис |

**Код-ревью оценка: 7/10**

---

### 🧠 Detector Service

**Дмитрий Козлов (ML-инженер):**

```python
# ✅ ОТЛИЧНО: Batch inference
results = self.model.track(
    frames,
    conf=self.confidence,
    iou=self.iou,
    persist=True,  # Сохранение трекинга между вызовами
    verbose=False
)

# ✅ ХОРОШО: Маппинг классов с fallback
ppe_class = self.PPE_CLASS_MAPPING.get(name) or self.PPE_CLASS_MAPPING.get(idx)
if ppe_class:
    self.idx_to_ppe[idx] = ppe_class
else:
    # Пытаемся определить по имени
    name_lower = name.lower()
    if 'hardhat' in name_lower or 'helmet' in name_lower:
        ...
```

**Критические замечания:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ❌ ПРОБЛЕМА: Consumer Group без обработки pending messages            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ТЕКУЩИЙ КОД:                                                          │
│  messages = self.redis.xreadgroup(                                     │
│      consumer_group, consumer_name,                                    │
│      {stream_key: '>'},  # Только НОВЫЕ сообщения                     │
│      ...                                                                │
│  )                                                                      │
│                                                                         │
│  ПРОБЛЕМА: При рестарте worker теряются необработанные сообщения!     │
│                                                                         │
│  РЕШЕНИЕ:                                                               │
│  # Сначала обрабатываем pending                                        │
│  pending = self.redis.xreadgroup(group, consumer, {stream: '0'})       │
│  # Потом новые                                                          │
│  new = self.redis.xreadgroup(group, consumer, {stream: '>'})           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  ⚠️ ПРОБЛЕМА: Трекинг не работает правильно между камерами            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  persist=True работает для ОДНОГО потока, но у нас несколько камер    │
│  обрабатываются одним воркером. Track ID будут конфликтовать!         │
│                                                                         │
│  РЕШЕНИЕ: Отдельный tracker на каждую камеру:                          │
│  self.trackers = {camera_id: ByteTrack() for camera_id in cameras}     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

| # | Проблема | Критичность | Рекомендация |
|---|----------|-------------|--------------|
| 1 | Pending messages теряются | 🔴 Высокая | Обрабатывать pending при старте |
| 2 | Track ID конфликтуют | 🔴 Высокая | Отдельный tracker на камеру |
| 3 | Нет batch обработки нескольких камер | Средняя | Собирать кадры с разных камер в один батч |
| 4 | SQLAlchemy sync в async контексте | Средняя | Использовать async SQLAlchemy |
| 5 | Нет warmup модели | Низкая | Первый inference медленный |

**Код-ревью оценка: 6/10**

---

### 🌐 API Service

**Игорь Волков (архитектор):**

```python
# ✅ ХОРОШО: Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_client = await aioredis.from_url(REDIS_URL)
    asyncio.create_task(alert_subscriber())
    yield
    await redis_client.close()

# ✅ ХОРОШО: WebSocket manager с cleanup
async def broadcast(self, message: dict):
    disconnected = []
    for connection in self.active_connections:
        try:
            await connection.send_json(message)
        except Exception:
            disconnected.append(connection)
    for conn in disconnected:
        self.disconnect(conn)
```

**Замечания:**

| # | Проблема | Критичность | Рекомендация |
|---|----------|-------------|--------------|
| 1 | Нет rate limiting | 🔴 Высокая | Добавить slowapi или nginx |
| 2 | Нет аутентификации | 🔴 Высокая | JWT/OAuth2 |
| 3 | `global redis_client` | Средняя | Dependency Injection |
| 4 | Нет пагинации курсорной | Средняя | offset неэффективен на больших данных |
| 5 | Нет кэширования | Средняя | Redis cache для статистики |
| 6 | Нет валидации camera_id | Низкая | SQL injection через path param |

**Код-ревью оценка: 6.5/10**

---

### 📱 Alerter Service

**Мария Сидорова (MLOps):**

```python
# ✅ ХОРОШО: Async HTTP клиент
self.client = httpx.AsyncClient(timeout=30.0)

# ✅ ХОРОШО: Cooldown логика
cooldown_key = f"{camera_id}:{person_id or 'unknown'}:{violation_type}"
if cooldown_key in self.cooldowns:
    if datetime.now() - last_alert < timedelta(seconds=ALERT_COOLDOWN):
        return
```

**Замечания:**

| # | Проблема | Критичность | Рекомендация |
|---|----------|-------------|--------------|
| 1 | Cooldown в памяти | Средняя | При рестарте cooldown сбрасывается → дубли |
| 2 | Нет retry для Telegram | Средняя | Exponential backoff при сбоях |
| 3 | Нет очереди отправки | Средняя | При всплеске нарушений — потеря алертов |
| 4 | Только Telegram | Низкая | Заявлены email/SMS, но не реализованы |

**Код-ревью оценка: 7/10**

---

## 3️⃣ SECURITY REVIEW

### Андрей Белов (Security-инженер):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SECURITY ASSESSMENT                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  🔴 КРИТИЧЕСКИЕ УЯЗВИМОСТИ:                                            │
│                                                                         │
│  1. API без аутентификации                                              │
│     Любой в сети может получить видео, нарушения, управлять системой   │
│     CVSS: 9.1 (Critical)                                                │
│                                                                         │
│  2. Пароли в конфигах                                                   │
│     RTSP URL содержит admin:password в открытом виде                   │
│     cameras.yaml может попасть в git                                    │
│     CVSS: 7.5 (High)                                                    │
│                                                                         │
│  3. PostgreSQL без SSL                                                  │
│     Трафик к БД не шифруется                                           │
│     CVSS: 5.3 (Medium)                                                  │
│                                                                         │
│  ⚠️ СРЕДНИЕ РИСКИ:                                                     │
│                                                                         │
│  4. Нет ограничения размера загружаемых файлов                         │
│     DoS через загрузку больших файлов                                   │
│                                                                         │
│  5. CORS: allow_origins=["*"]                                          │
│     Любой сайт может делать запросы к API                              │
│                                                                         │
│  6. Нет логирования security events                                    │
│     Аудит невозможен                                                    │
│                                                                         │
│  7. Docker контейнеры от root                                          │
│     Container escape → root на хосте                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Рекомендации по безопасности:

```yaml
# docker-compose.yml - добавить:
services:
  api:
    user: "1000:1000"  # Не root
    read_only: true     # Immutable filesystem
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
```

```python
# API - добавить аутентификацию:
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@app.get("/api/violations")
async def get_violations(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    # Валидация JWT токена
    ...
```

**Security оценка: 4/10** ⚠️

---

## 4️⃣ ТЕСТИРОВАНИЕ

### Ольга Краснова (QA Lead):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TEST COVERAGE ASSESSMENT                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ❌ КРИТИЧНО: Тесты ОТСУТСТВУЮТ                                        │
│                                                                         │
│  Нет папки tests/                                                       │
│  Нет unit тестов                                                        │
│  Нет integration тестов                                                 │
│  Нет e2e тестов                                                         │
│  Нет нагрузочного тестирования                                          │
│                                                                         │
│  Для production ОБЯЗАТЕЛЬНО:                                            │
│                                                                         │
│  tests/                                                                 │
│  ├── unit/                                                              │
│  │   ├── test_detector.py        # PPE детекция                        │
│  │   ├── test_tracker.py         # Трекинг объектов                    │
│  │   └── test_alerts.py          # Логика алертов                      │
│  ├── integration/                                                       │
│  │   ├── test_redis_pipeline.py  # Capture → Redis → Detector          │
│  │   ├── test_api_db.py          # API → PostgreSQL                    │
│  │   └── test_telegram.py        # Telegram интеграция                 │
│  ├── e2e/                                                               │
│  │   └── test_full_pipeline.py   # Камера → Алерт                      │
│  └── load/                                                              │
│      └── locustfile.py           # Нагрузочное тестирование            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Минимальный тест-план:

| Тест | Приоритет | Автоматизация |
|------|-----------|---------------|
| Детектор находит каску | P0 | pytest + модельные данные |
| Детектор находит отсутствие каски | P0 | pytest |
| Алерт отправляется при нарушении | P0 | pytest + mock Telegram |
| Cooldown работает | P0 | pytest |
| API возвращает нарушения | P1 | pytest + httpx |
| WebSocket отправляет события | P1 | pytest-asyncio |
| Камера переподключается при сбое | P1 | pytest + mock cv2 |
| 10 камер одновременно | P2 | locust |

**Testing оценка: 1/10** 🔴

---

## 5️⃣ PRODUCTION READINESS

### Мария Сидорова (MLOps):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION READINESS CHECKLIST                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  INFRASTRUCTURE:                                                        │
│  ✅ Docker Compose                                                      │
│  ✅ Health checks                                                       │
│  ✅ Restart policies                                                    │
│  ❌ Kubernetes manifests                                                │
│  ❌ Helm chart                                                          │
│  ❌ Terraform/Ansible для инфры                                         │
│                                                                         │
│  OBSERVABILITY:                                                         │
│  ⚠️ Prometheus (опционально, не интегрирован в код)                    │
│  ⚠️ Grafana (опционально, нет дашбордов)                               │
│  ❌ Централизованные логи (ELK/Loki)                                   │
│  ❌ Distributed tracing                                                 │
│  ❌ Alerting rules                                                      │
│                                                                         │
│  RELIABILITY:                                                           │
│  ❌ Database backups                                                    │
│  ❌ Redis persistence настроен, но нет backup                          │
│  ❌ Disaster recovery план                                              │
│  ❌ Runbook для инцидентов                                              │
│                                                                         │
│  CI/CD:                                                                 │
│  ❌ GitHub Actions / GitLab CI                                          │
│  ❌ Автоматические тесты                                                │
│  ❌ Container registry                                                  │
│  ❌ Semantic versioning                                                 │
│                                                                         │
│  DOCUMENTATION:                                                         │
│  ✅ README.md                                                           │
│  ✅ Конфигурация камер                                                  │
│  ❌ API документация (автогенерация есть, но не кастомизирована)       │
│  ❌ Runbook                                                             │
│  ❌ Architecture Decision Records (ADR)                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6️⃣ СВОДНАЯ ОЦЕНКА

### Алексей Петров (модератор):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ИТОГОВАЯ ОЦЕНКА                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Компонент                    Оценка    Вес      Взвешенная            │
│  ─────────────────────────────────────────────────────────────────────  │
│  Архитектура                  7.5/10    20%      1.50                   │
│  Capture Service              7.0/10    15%      1.05                   │
│  Detector Service             6.0/10    20%      1.20                   │
│  API Service                  6.5/10    15%      0.98                   │
│  Alerter Service              7.0/10    10%      0.70                   │
│  Security                     4.0/10    10%      0.40                   │
│  Testing                      1.0/10     5%      0.05                   │
│  Production Readiness         5.0/10     5%      0.25                   │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  ИТОГО:                       6.13/10                                   │
│                                                                         │
│  СТАТУС: 🟡 BETA / ПИЛОТ                                               │
│                                                                         │
│  Готовность:                                                            │
│  • ❌ Production (требуется доработка)                                 │
│  • ⚠️ Пилот на 1-2 камерах (с оговорками)                             │
│  • ✅ Демонстрация заказчику                                           │
│  • ✅ Proof of Concept                                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7️⃣ ПЛАН ДОРАБОТКИ ДО PRODUCTION

### Приоритет 0 (блокеры — до пилота):

| # | Задача | Ответственный | Срок | Effort |
|---|--------|---------------|------|--------|
| 1 | Исправить трекинг (отдельный tracker на камеру) | ML-инженер | 2 дня | 4h |
| 2 | Обработка pending messages в Redis | Backend | 1 день | 2h |
| 3 | Добавить базовую аутентификацию API | Backend | 2 дня | 8h |
| 4 | Cooldown в Redis (не в памяти) | Backend | 1 день | 4h |
| 5 | Unit тесты для детектора | QA | 3 дня | 12h |

### Приоритет 1 (до production):

| # | Задача | Ответственный | Срок | Effort |
|---|--------|---------------|------|--------|
| 6 | Rate limiting на API | Backend | 1 день | 4h |
| 7 | Secrets management (HashiCorp Vault) | DevOps | 2 дня | 8h |
| 8 | Prometheus метрики в коде | Backend | 2 дня | 8h |
| 9 | Grafana дашборды | DevOps | 1 день | 4h |
| 10 | PostgreSQL backup cron | DevOps | 1 день | 4h |
| 11 | Integration тесты | QA | 5 дней | 20h |
| 12 | CI/CD pipeline | DevOps | 3 дня | 12h |
| 13 | Runbook документация | Team | 2 дня | 8h |

### Приоритет 2 (улучшения):

| # | Задача | Описание |
|---|--------|----------|
| 14 | Redis Cluster | Отказоустойчивость |
| 15 | PostgreSQL Replica | Read replicas |
| 16 | Kubernetes manifests | Масштабирование |
| 17 | Email/SMS алерты | Дополнительные каналы |
| 18 | Веб-дашборд | React frontend |

---

## 8️⃣ СРАВНЕНИЕ С ТРЕБОВАНИЯМИ

### Сергей Морозов (заказчик):

| Требование | Статус | Комментарий |
|------------|--------|-------------|
| Детекция каски | ⚠️ | Нужна PPE-модель |
| Детекция жилета | ⚠️ | Нужна PPE-модель |
| IP-камеры (RTSP) | ✅ | Реализовано |
| Алерты в реальном времени | ✅ | Telegram работает |
| Журнал нарушений | ✅ | PostgreSQL + API |
| Зоны с разными правилами | ⚠️ | Структура есть, логика не полная |
| Статистика | ✅ | API endpoint есть |
| Recall ≥ 95% | ❓ | Не тестировалось |
| Latency ≤ 2 сек | ❓ | Не измерялось |
| Uptime ≥ 99.5% | ❌ | Нет HA |

---

## 9️⃣ РЕШЕНИЯ СОВЕЩАНИЯ

### ✅ ВЕРДИКТ:

> **Система PPE Detection v2.0 признана готовой для ПИЛОТНОГО ТЕСТИРОВАНИЯ на 1-2 камерах с ограничениями.**

### 📋 ОБЯЗАТЕЛЬНЫЕ УСЛОВИЯ ДЛЯ ПИЛОТА:

1. ✅ Получить/обучить PPE-модель
2. ⚠️ Исправить трекинг (критический баг)
3. ⚠️ Добавить базовую аутентификацию
4. ⚠️ Написать минимальные тесты

### 🚫 НЕ РЕКОМЕНДУЕТСЯ:

- Запускать на production без доработок
- Подключать более 3 камер без тестирования производительности
- Хранить RTSP пароли в открытом виде в production

### 📅 СЛЕДУЮЩИЕ ШАГИ:

| Действие | Срок | Ответственный |
|----------|------|---------------|
| Исправление критических багов | 1 неделя | Разработка |
| Получение PPE-модели | 1 неделя | ML-инженер |
| Настройка пилотной камеры | 3 дня | Заказчик |
| Запуск пилота | 2 недели | Команда |
| Сбор метрик пилота | 2 недели | QA |
| Решение о production | 1 месяц | Руководство |

---

## 📊 ПРИЛОЖЕНИЕ: Метрики для мониторинга пилота

```yaml
# Бизнес-метрики:
- violations_total{camera, type}          # Всего нарушений
- violations_acknowledged_total           # Подтверждённых
- detection_latency_seconds              # Задержка детекции
- alert_delivery_latency_seconds         # Задержка алерта

# Технические метрики:
- frames_processed_total{camera}         # Обработано кадров
- frames_dropped_total{camera}           # Потеряно кадров
- inference_duration_seconds             # Время inference
- redis_stream_length{stream}            # Длина очереди
- api_requests_total{endpoint, status}   # Запросы к API
- websocket_connections_active           # WebSocket соединений

# Инфраструктура:
- container_cpu_usage_percent            # CPU
- container_memory_usage_bytes           # RAM
- gpu_utilization_percent                # GPU
- disk_usage_bytes                       # Диск
```

---

**Протокол составлен:** Система автоматической генерации  
**Статус документа:** Утверждён участниками совещания  
**Версия:** 1.0  
**Следующий пересмотр:** После завершения пилота
