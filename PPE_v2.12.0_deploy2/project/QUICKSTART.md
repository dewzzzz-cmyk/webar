# 🚀 PPE Detection System v2.10.8 — Quick Start

> **Полный гайд:** [docs/PPE_SETUP_GUIDE.md](docs/PPE_SETUP_GUIDE.md)

---

## ⚡ Запуск за 3 минуты

```bash
# 1. Скопировать конфиг
cp .env.example .env

# 2. Запустить
docker compose up -d

# 3. Открыть
open http://localhost:3001
```

**Готово!** 🎉

---

## 📦 Установка модели и датасета

### Через Dashboard (Рекомендуется)

1. Откройте http://localhost:3001
2. Перейдите в **Настройки**
3. В разделе **Модели** — нажмите "Загрузить" на нужной модели
4. В разделе **Датасеты** — нажмите "Загрузить" на нужном датасете

### Или вручную

```bash
# Скачать модель
wget https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8n.pt \
  -O models/ppe_model.pt

# Перезапустить детектор
docker compose restart detector
```

---

## 🖥️ Интерфейсы

| Сервис | URL | Логин |
|--------|-----|-------|
| Dashboard | http://localhost:3001 | admin / admin123 |
| API | http://localhost:8000/docs | - |
| Grafana | http://localhost:3002 | admin / admin |
| MinIO | http://localhost:9001 | minioadmin / minioadmin123 |

---

## 🎯 Профили запуска

```bash
# Базовый (CPU)
docker compose up -d

# С GPU (RTX 5090/4090/3090)
docker compose --profile gpu up -d

# С обучением
docker compose --profile training up -d

# С мониторингом
docker compose --profile monitoring up -d

# Всё вместе (GPU + обучение + мониторинг)
docker compose --profile gpu --profile training --profile monitoring up -d
```

---

## 📊 Управление

```bash
# Статус
docker compose ps

# Логи
docker compose logs -f detector

# Перезапуск
docker compose restart api

# Остановка
docker compose down
```

---

## ⚠️ Проблемы?

| Проблема | Решение |
|----------|---------|
| "Model not found" | Скачайте модель через Dashboard → Настройки |
| Нет детекции СИЗ | Нужна PPE модель с Roboflow (не базовая YOLO) |
| Видео зависает | Проверьте RTSP URL камер, v2.10.8 имеет защиту от зависаний |
| GPU не отображается | Перезапустите detector: `docker compose restart detector` |
| Скриншоты не работают | Проверьте что capture работает: `docker logs ppe_capture` |

---

## 🆕 Что нового в v2.10.8

- ✅ **Защита от зависания видео** — watchdog + таймауты в capture
- ✅ **GPU статус из Redis** — detector публикует статус, API читает
- ✅ **Улучшенные скриншоты** — async запись + информативные ошибки
- ✅ **PyTorch 2.7 + CUDA 12.8** — поддержка RTX 5090 Blackwell
| GPU не работает | `nvidia-smi` + NVIDIA Container Toolkit |
| Out of memory | Используйте меньшую модель (Nano) |

**Полный гайд с решением всех проблем:** [docs/PPE_SETUP_GUIDE.md](docs/PPE_SETUP_GUIDE.md)

---

## 📁 Что в комплекте

```
✅ Backend микросервисы (API, Detector, Capture, Alerter)
✅ React Dashboard с авторизацией
✅ Каталог моделей (YOLOv8/v11, скачивание в 1 клик)
✅ Каталог датасетов (PPE, скачивание в 1 клик)
✅ Модуль обучения собственных моделей
✅ Grafana + Prometheus мониторинг
✅ CI/CD (GitHub Actions)
✅ Kubernetes манифесты
✅ 86% покрытие тестами
```

---

**Версия:** 2.10.7  
**Дата:** Январь 2026
