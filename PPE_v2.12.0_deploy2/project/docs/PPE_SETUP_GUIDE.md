# 🚀 PPE Detection System — Полный Гайд по Настройке

> **Версия:** 2.10.7  
> **Время настройки:** 10-15 минут (с GPU) / 20-30 минут (без GPU)

---

## 📋 Содержание

1. [Быстрый старт (5 минут)](#-быстрый-старт)
2. [Установка модели](#-шаг-1-установка-модели)
3. [Установка датасета](#-шаг-2-установка-датасета-для-обучения)
4. [Запуск системы](#-шаг-3-запуск-системы)
5. [Проверка работы](#-шаг-4-проверка-работы)
6. [Решение проблем](#-решение-проблем)

---

## ⚡ Быстрый Старт

### Минимальные требования
- Docker Desktop (Windows/Mac) или Docker + Docker Compose (Linux)
- 8 GB RAM (16 GB рекомендуется)
- GPU: опционально, но рекомендуется (NVIDIA GTX 1650+)

### Три команды для запуска

```bash
# 1. Клонировать проект
git clone <repo-url> ppe-system
cd ppe-system

# 2. Скопировать конфиг
cp .env.example .env

# 3. Запустить
docker compose up -d
```

**Готово!** Откройте http://localhost:3001

---

## 📦 Шаг 1: Установка Модели

### Вариант A: Через Dashboard (Рекомендуется) ⭐

1. Откройте http://localhost:3001
2. Перейдите в **Настройки** → **Модели**
3. Выберите модель из списка:
   - **YOLOv8 Nano** — для слабых GPU (6 MB)
   - **YOLOv11 Nano** — новейшая, быстрая (5 MB)
   - **YOLOv8 Medium** — баланс скорости/точности (52 MB)
4. Нажмите **"Загрузить"**
5. Дождитесь завершения
6. Нажмите **"Активировать"**

### Вариант B: Скачать вручную

```bash
# Скачать YOLOv8 Nano (самая маленькая)
wget https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8n.pt \
  -O models/ppe_model.pt

# Перезапустить детектор
docker compose restart detector
```

### Вариант C: PPE-модель с Roboflow

Для детекции касок и жилетов нужна специализированная модель:

1. Зарегистрируйтесь на https://app.roboflow.com (бесплатно)
2. Перейдите: https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety
3. Нажмите **Download** → **YOLOv8** → **Download zip**
4. Распакуйте и скопируйте `best.pt` → `models/ppe_model.pt`
5. Перезапустите: `docker compose restart detector`

---

## 📊 Шаг 2: Установка Датасета (для обучения)

### Вариант A: Через Dashboard (Рекомендуется) ⭐

1. Откройте http://localhost:3001
2. Перейдите в **Настройки** → **Датасеты** (или **Обучение**)
3. Выберите датасет из каталога:
   - **Construction PPE** — 5000+ изображений, каски/жилеты ⭐
   - **PPE Full** — полный набор СИЗ
   - **Demo Mini** — для быстрого теста
4. Нажмите **"Загрузить"**
5. Система автоматически настроит всё для обучения

### Вариант B: Roboflow с API ключом

```bash
# Установить roboflow
pip install roboflow

# Скачать датасет
python3 << 'EOF'
from roboflow import Roboflow

# Получите ключ на https://app.roboflow.com/settings/api
rf = Roboflow(api_key="ВАШ_API_КЛЮЧ")

project = rf.workspace("roboflow-universe-projects").project("construction-site-safety")
version = project.version(30)
version.download("yolov8", location="./datasets/ppe")
EOF
```

### Вариант C: Ручная загрузка

1. Перейдите на https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety/dataset/30
2. Нажмите **Download Dataset** → **YOLOv8** → **Download zip**
3. Распакуйте в папку `datasets/ppe/`

**Структура должна быть:**
```
datasets/ppe/
├── data.yaml           # Конфигурация
├── train/
│   ├── images/        # Изображения для обучения
│   └── labels/        # Разметка (YOLO формат)
└── valid/
    ├── images/        # Изображения для валидации
    └── labels/
```

---

## 🎬 Шаг 3: Запуск Системы

### Базовый запуск (CPU)

```bash
docker compose up -d
```

### С GPU (NVIDIA)

```bash
# Убедитесь что установлен NVIDIA Container Toolkit
nvidia-smi  # Проверка драйверов

# Запуск с GPU
docker compose --profile gpu up -d
```

### С модулем обучения

```bash
docker compose --profile training up -d
```

### Полный набор (GPU + Training)

```bash
docker compose --profile gpu --profile training up -d
```

---

## ✅ Шаг 4: Проверка Работы

### 1. Проверить статус контейнеров

```bash
docker compose ps
```

Все сервисы должны быть `healthy` или `running`:
```
NAME                STATUS
ppe-api             healthy
ppe-detector        running
ppe-dashboard       healthy
ppe-redis           healthy
ppe-postgres        healthy
```

### 2. Открыть Dashboard

- http://localhost:3001 — главная страница
- http://localhost:3001/settings — настройки, модели, датасеты
- http://localhost:3001/training — обучение модели

### 3. Проверить API

```bash
# Статус системы
curl http://localhost:8000/health

# Список моделей
curl http://localhost:8000/api/settings/models

# Каталог датасетов
curl http://localhost:8000/api/training/catalog/datasets
```

### 4. Тест детекции

```bash
# Через API
curl -X POST http://localhost:8000/api/detect \
  -F "file=@test_image.jpg"
```

---

## 🔧 Решение Проблем

### Проблема: "Model not found"

```bash
# Проверить наличие модели
ls -la models/

# Скачать если нет
wget https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8n.pt \
  -O models/ppe_model.pt

# Перезапустить
docker compose restart detector
```

### Проблема: "GPU not detected"

```bash
# Проверить драйвера
nvidia-smi

# Проверить Docker GPU support
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi

# Если не работает — установить NVIDIA Container Toolkit:
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
```

### Проблема: "Out of memory"

```bash
# Уменьшить batch_size в настройках
# Или использовать меньшую модель (YOLOv8 Nano)

# Очистить Docker кэш
docker system prune -af
```

### Проблема: Нет детекции СИЗ

Базовая YOLOv8 модель видит только общие объекты (person, car и т.д.).
Для детекции касок/жилетов нужна специализированная PPE модель:

1. Скачайте PPE модель с Roboflow (см. Шаг 1, Вариант C)
2. Или обучите свою модель в разделе "Обучение"

### Проблема: Медленная работа

```bash
# Проверить использование GPU
docker logs ppe-detector 2>&1 | grep -i cuda

# Если GPU не используется:
# 1. Проверить NVIDIA драйвера
# 2. Запустить с профилем GPU:
docker compose --profile gpu up -d
```

---

## 📚 Дополнительные Ресурсы

| Ресурс | Ссылка |
|--------|--------|
| Roboflow Universe (датасеты) | https://universe.roboflow.com |
| YOLO Документация | https://docs.ultralytics.com |
| Примеры PPE датасетов | https://universe.roboflow.com/search?q=ppe |

---

## 🆘 Поддержка

- 📧 Создайте Issue в репозитории
- 💬 Telegram: @ppe_support (если настроен)

---

**Версия документа:** 2.10.7  
**Обновлено:** Январь 2026
