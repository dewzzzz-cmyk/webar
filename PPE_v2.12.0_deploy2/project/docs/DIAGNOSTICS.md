# 📋 Диагностика PPE Detection System

## Быстрый сбор логов для AI анализа

### Способ 1: Через меню (рекомендуется)
```cmd
start.bat → [L] Collect Logs
```

Создаёт файл `logs/ppe_logs_YYYYMMDD_HHMM.txt` со всеми логами.

### Способ 2: Полная диагностика
```cmd
start.bat → [E] Export Full Diagnostics
```

Создаёт папку `diagnostics/diag_YYYYMMDD_HHMM/` с:
- Логами всех контейнеров (500+ строк каждый)
- Информацией о Docker
- Состоянием GPU
- Конфигурацией системы
- Результатами health check
- **SUMMARY_FOR_AI.txt** - сводный файл для копирования

### Способ 3: Тестирование сервисов
```cmd
start.bat → [T] Test All Services
```

Проверяет работоспособность всех 8 сервисов:
1. PostgreSQL
2. Redis  
3. API Health
4. Dashboard
5. API Docs
6. Training Module
7. Detector
8. GPU в Detector

---

## Как передать логи на анализ

### Вариант A: Копировать текст
1. Запустить `[L] Collect Logs`
2. Открыть созданный файл
3. `Ctrl+A` → `Ctrl+C`
4. Вставить в чат с AI

### Вариант B: Загрузить файл
1. Запустить `[E] Export Full Diagnostics`
2. Перетащить `SUMMARY_FOR_AI.txt` в чат

### Вариант C: Команды вручную
```cmd
:: Все логи API (последние 200 строк)
docker logs ppe_api --tail 200 > api_log.txt

:: Все логи detector
docker logs ppe_detector --tail 100 > detector_log.txt

:: Состояние контейнеров
docker ps -a > containers.txt
```

---

## Структура диагностического файла

```
================================================================
PPE DETECTION SYSTEM - DIAGNOSTIC LOG
================================================================
Generated: DD.MM.YYYY HH:MM:SS
Version: 2.10.30

=== SYSTEM INFO ===
Computer, User, OS

=== DOCKER VERSION ===
Docker, Docker Compose versions

=== CONTAINER STATUS ===
Список контейнеров и их статусы

=== API LOGS (last 100 lines) ===
Логи FastAPI сервера

=== DETECTOR LOGS (last 50 lines) ===
Логи детектора YOLO

=== TRAINING LOGS (last 50 lines) ===
Логи модуля обучения

=== HEALTH CHECK RESULTS ===
Результаты проверки работоспособности

=== ENVIRONMENT (.env check) ===
Проверка переменных окружения
================================================================
```

---

## Типичные проблемы и что искать в логах

### API не запускается
Искать в API LOGS:
- `JWT_SECRET` - должен быть установлен
- `Connection refused` - проблема с Redis/PostgreSQL
- `ModuleNotFoundError` - отсутствует зависимость

### Детектор не работает
Искать в DETECTOR LOGS:
- `CUDA not available` - нет GPU
- `Model not found` - модель не загружена
- `Out of memory` - нехватка GPU памяти

### Dashboard пустой
Искать в DASHBOARD LOGS:
- `502 Bad Gateway` - API не отвечает
- `CORS error` - проблема с nginx.conf
- `WebSocket failed` - проблема с WS соединением

### Training не работает
Искать в TRAINING LOGS:
- `Dataset not found` - датасет не загружен
- `Permission denied` - проблема с правами
- `GPU memory` - нехватка памяти при обучении

---

## Полезные команды для диагностики

```cmd
:: Проверить здоровье API
curl http://localhost:8000/health

:: Проверить Training API
curl http://localhost:8000/api/training/status

:: Проверить GPU в Docker
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi

:: Посмотреть использование ресурсов
docker stats --no-stream

:: Проверить логи конкретного контейнера в реальном времени
docker logs ppe_api -f --tail 50
```
