# 🚀 Быстрое тестирование PPE System v2.10.19

## Требования

- Docker Desktop (Windows/Mac) или Docker + Docker Compose (Linux)
- 8 GB RAM минимум
- 10 GB свободного места на диске
- Интернет-соединение (для загрузки образов и тестовых RTSP потоков)

## Шаг 1: Распаковка и запуск

```bash
# Распакуйте архив ppe_v2.10.19_camera_fix.zip
unzip ppe_v2.10.19_camera_fix.zip -d ppe_system
cd ppe_system

# Запустите систему
docker compose up -d

# Подождите ~2-3 минуты пока все сервисы запустятся
```

## Шаг 2: Проверка запуска

```bash
# Все контейнеры должны быть Running
docker ps

# Ожидаемый вывод:
# ppe_dashboard   ... Up
# ppe_api         ... Up
# ppe_detector    ... Up
# ppe_capture     ... Up
# ppe_redis       ... Up
# ppe_postgres    ... Up (healthy)
```

## Шаг 3: Открытие Dashboard

1. Откройте браузер: **http://localhost:3001**
2. Войдите:
   - Логин: `admin`
   - Пароль: `admin`

## Шаг 4: Проверка функционала

### 4.1 Камеры (Мониторинг)
- Перейдите на вкладку **Мониторинг**
- Должны отображаться 2 тестовые камеры:
  - "Тест Wowza #1"
  - "Тест Wowza #2"
- Если камеры показывают "Camera Offline" - это нормально, тестовые потоки могут быть недоступны

### 4.2 Настройки → Датасеты
- Перейдите **Настройки** → вкладка с датасетами
- Проверьте что датасеты НЕ показывают "Загружен" без реальных данных
- Введите Roboflow API ключ для загрузки датасета

### 4.3 Обучение → Модели
- Перейдите **Обучение**
- Должна отображаться базовая модель "PPE Base Model (YOLOv8n)"

### 4.4 Создание датасета
- Нажмите **+** рядом с "Датасет"
- Введите название
- Нажмите **Создать**
- Датасет должен создаться (даже без PostgreSQL - используется файловый fallback)

## Диагностика проблем

### Камеры не показывают изображение

```bash
# Проверьте логи capture сервиса
docker logs ppe_capture --tail 50

# Проверьте Redis
docker exec ppe_redis redis-cli keys "raw:*"
docker exec ppe_redis redis-cli keys "camera:*"
```

### "Не удалось создать датасет"

```bash
# Проверьте PostgreSQL
docker logs ppe_postgres --tail 20

# Проверьте что postgres healthy
docker ps | grep postgres
```

### API не отвечает

```bash
# Проверьте логи API
docker logs ppe_api --tail 50

# Проверьте health
curl http://localhost:8000/health
```

## Тестовые RTSP потоки

В системе настроены 2 публичных тестовых потока от Wowza:

| Камера | URL |
|--------|-----|
| Тест Wowza #1 | `rtsp://716f898c7b71.entrypoint.cloud.wowza.com:1935/app-8F9K44lJ/304679fe_stream2` |
| Тест Wowza #2 | `rtsp://807e9439d5ca.entrypoint.cloud.wowza.com:1935/app-rC94792j/068b9c9a_stream2` |

> ⚠️ Тестовые потоки могут быть недоступны или перегружены. Это не проблема системы.

## Добавление своей камеры

### Через веб-интерфейс:
1. Настройки → Камеры → Добавить камеру
2. Введите:
   - ID: `my-camera-1`
   - Название: `Моя камера`
   - URL: `rtsp://user:pass@192.168.1.100:554/stream`
3. Нажмите Сохранить

### Через файл конфигурации:
```yaml
# configs/cameras.yaml
cameras:
  - id: my-camera-1
    name: "Моя камера"
    url: "rtsp://user:pass@192.168.1.100:554/stream"
    enabled: true
    fps: 5
```

Затем перезапустите capture:
```bash
docker compose restart capture
```

## Проверка с VLC

Перед добавлением камеры в систему, проверьте RTSP поток через VLC:

1. Откройте VLC
2. Медиа → Открыть сетевой поток
3. Введите RTSP URL
4. Нажмите Воспроизвести

Если VLC показывает видео - камера работает и можно добавлять в систему.

## Остановка системы

```bash
docker compose down
```

## Полная очистка (включая данные)

```bash
docker compose down -v
docker system prune -f
```

---

## Чеклист успешного тестирования

- [ ] Docker контейнеры запущены (6 штук)
- [ ] Dashboard открывается на http://localhost:3001
- [ ] Авторизация работает (admin/admin)
- [ ] Мониторинг показывает камеры (хотя бы placeholder)
- [ ] Датасеты НЕ показывают "Загружен" без данных
- [ ] Создание датасета работает
- [ ] API health endpoint отвечает

**Если все пункты выполнены - система готова к использованию!**
