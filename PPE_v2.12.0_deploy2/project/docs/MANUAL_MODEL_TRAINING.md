# 🛠️ Ручная сборка модели YOLO для PPE Detection

Если автоматическая загрузка датасета не работает, следуйте этой инструкции.

---

## 📋 Содержание

1. [Скачивание датасета с Roboflow](#1-скачивание-датасета-с-roboflow)
2. [Структура датасета](#2-структура-датасета)
3. [Обучение через командную строку](#3-обучение-через-командную-строку)
4. [Подключение модели к системе](#4-подключение-модели-к-системе)
5. [Устранение проблем](#5-устранение-проблем)

---

## 1. Скачивание датасета с Roboflow

### Вариант А: Через веб-интерфейс (без API ключа)

1. Перейдите на [Roboflow Universe](https://universe.roboflow.com/)
2. Найдите датасет (рекомендуется: "Construction Site Safety")
3. Нажмите **"Download Dataset"** → выберите **"YOLOv8"**
4. Скачайте ZIP архив

**Рекомендуемые датасеты:**
- [Construction Site Safety](https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety/dataset/30) - 5247 изображений
- [PPE Detection](https://universe.roboflow.com/ppe-detection-tlqgt/ppe-detection-2wk4o/dataset/3) - 3500 изображений

### Вариант Б: Через Python API (с API ключом)

```python
# Установка
pip install roboflow

# Скачивание
from roboflow import Roboflow

# API ключ из https://app.roboflow.com/settings/api
rf = Roboflow(api_key="YOUR_API_KEY")

# Выбор датасета
project = rf.workspace("roboflow-universe-projects").project("construction-site-safety")
version = project.version(30)

# Скачивание в формате YOLOv8
dataset = version.download("yolov8", location="./dataset")
```

### Вариант В: Через CLI

```bash
# Установка Roboflow CLI
pip install roboflow

# Авторизация
roboflow login

# Скачивание
roboflow download roboflow-universe-projects/construction-site-safety/30 --format yolov8
```

---

## 2. Структура датасета

После скачивания структура должна быть:

```
dataset/
├── data.yaml           # Конфигурация датасета
├── train/
│   ├── images/        # Изображения для обучения
│   │   ├── img001.jpg
│   │   ├── img002.jpg
│   │   └── ...
│   └── labels/        # Аннотации в YOLO формате
│       ├── img001.txt
│       ├── img002.txt
│       └── ...
└── valid/
    ├── images/        # Изображения для валидации
    └── labels/        # Аннотации для валидации
```

### Формат data.yaml

```yaml
path: /path/to/dataset
train: train/images
val: valid/images

nc: 5  # Количество классов
names:
  0: Hardhat
  1: NO-Hardhat
  2: Safety Vest
  3: NO-Safety Vest
  4: Person
```

### Формат аннотаций (YOLO)

Каждый `.txt` файл содержит строки формата:
```
<class_id> <center_x> <center_y> <width> <height>
```

Пример (`img001.txt`):
```
0 0.5 0.3 0.2 0.4
2 0.7 0.6 0.15 0.35
4 0.5 0.5 0.3 0.8
```

Координаты нормализованы (0-1 относительно размера изображения).

---

## 3. Обучение через командную строку

### Подготовка

```bash
# Установка ultralytics
pip install ultralytics

# Проверка GPU
python -c "import torch; print(torch.cuda.is_available())"
```

### Базовое обучение

```bash
# YOLOv8 Nano (быстро, базовая точность)
yolo detect train data=dataset/data.yaml model=yolov8n.pt epochs=50 imgsz=640

# YOLOv8 Medium (баланс скорости и точности)
yolo detect train data=dataset/data.yaml model=yolov8m.pt epochs=100 imgsz=640

# YOLOv8 XLarge (максимальная точность, нужно много VRAM)
yolo detect train data=dataset/data.yaml model=yolov8x.pt epochs=100 imgsz=640 batch=8
```

### Расширенные параметры

```bash
yolo detect train \
    data=dataset/data.yaml \
    model=yolov8m.pt \
    epochs=100 \
    imgsz=640 \
    batch=16 \
    lr0=0.01 \
    lrf=0.01 \
    patience=50 \
    augment=True \
    cache=True \
    device=0 \
    workers=8 \
    project=runs/train \
    name=ppe_model_v1
```

### Параметры для разных GPU

| GPU | Модель | Batch Size | Image Size |
|-----|--------|------------|------------|
| RTX 3060 (12GB) | YOLOv8m | 16 | 640 |
| RTX 3080 (10GB) | YOLOv8l | 8 | 640 |
| RTX 4090 (24GB) | YOLOv8x | 32 | 640 |
| RTX 5090 (32GB) | YOLOv8x | 64 | 1280 |

### YOLOv11 (новейшая модель)

```bash
# YOLOv11 использует имя yolo11, не yolov11
yolo detect train data=dataset/data.yaml model=yolo11n.pt epochs=100 imgsz=640
yolo detect train data=dataset/data.yaml model=yolo11m.pt epochs=100 imgsz=640
yolo detect train data=dataset/data.yaml model=yolo11x.pt epochs=100 imgsz=640
```

---

## 4. Подключение модели к системе

### Шаг 1: Найдите обученную модель

После обучения модель сохраняется в:
```
runs/train/ppe_model_v1/weights/best.pt
```

### Шаг 2: Скопируйте в систему

**Windows (PowerShell):**
```powershell
# Путь к системе PPE
$PPE_PATH = "C:\path\to\ppe_system_v2_new"

# Копирование модели
Copy-Item "runs\train\ppe_model_v1\weights\best.pt" "$PPE_PATH\models\custom_ppe_v1.pt"
```

**Linux/Mac:**
```bash
cp runs/train/ppe_model_v1/weights/best.pt /path/to/ppe_system/models/custom_ppe_v1.pt
```

### Шаг 3: Обновите конфигурацию

Отредактируйте `docker-compose.yml`:

```yaml
services:
  detector:
    environment:
      - MODEL_PATH=/app/models/custom_ppe_v1.pt
```

Или через `.env`:
```
MODEL_PATH=/app/models/custom_ppe_v1.pt
```

### Шаг 4: Перезапустите детектор

```bash
docker compose restart detector
```

### Шаг 5: Проверьте в Dashboard

1. Откройте http://localhost:3001
2. Перейдите в "Настройки" → "Модели YOLO"
3. Убедитесь что новая модель отображается

---

## 5. Устранение проблем

### Проблема: "CUDA out of memory"

**Решение:** Уменьшите batch size
```bash
yolo detect train ... batch=8  # или batch=4
```

### Проблема: "No labels found"

**Решение:** Проверьте структуру папок
```bash
# Должно быть:
# train/images/xxx.jpg
# train/labels/xxx.txt  (тот же префикс!)
```

### Проблема: "Invalid data.yaml"

**Решение:** Проверьте пути в data.yaml
```yaml
# Используйте абсолютные пути или относительные от data.yaml
path: .
train: train/images
val: valid/images
```

### Проблема: Низкая точность (mAP < 0.5)

**Решения:**
1. Увеличьте количество эпох: `epochs=200`
2. Используйте большую модель: `model=yolov8l.pt`
3. Увеличьте augmentation: `augment=True`
4. Добавьте больше данных

### Проблема: Модель не детектирует

**Решение:** Проверьте классы
```python
from ultralytics import YOLO
model = YOLO('best.pt')
print(model.names)  # Должны быть ваши классы
```

---

## 📊 Оценка модели

### Валидация

```bash
yolo detect val model=runs/train/ppe_model_v1/weights/best.pt data=dataset/data.yaml
```

### Метрики

- **mAP@0.5** — основной показатель (цель: >0.7)
- **mAP@0.5:0.95** — строгий показатель (цель: >0.5)
- **Precision** — точность (цель: >0.8)
- **Recall** — полнота (цель: >0.8)

### Тестирование на изображении

```bash
yolo detect predict model=best.pt source=test_image.jpg conf=0.25
```

### Тестирование на видео

```bash
yolo detect predict model=best.pt source=test_video.mp4 conf=0.25
```

---

## 🔧 Полезные команды

```bash
# Информация о модели
yolo info model=best.pt

# Экспорт в ONNX
yolo export model=best.pt format=onnx

# Экспорт в TensorRT (для NVIDIA)
yolo export model=best.pt format=engine device=0

# Бенчмарк скорости
yolo benchmark model=best.pt data=dataset/data.yaml imgsz=640
```

---

## 📚 Полезные ссылки

- [Ultralytics Docs](https://docs.ultralytics.com/)
- [Roboflow Universe](https://universe.roboflow.com/)
- [YOLOv8 Training Guide](https://docs.ultralytics.com/modes/train/)
- [PPE Datasets Collection](https://universe.roboflow.com/search?q=ppe+detection)

---

## ❓ Нужна помощь?

Если у вас возникли вопросы:
1. Проверьте логи: `docker logs ppe_detector --tail 50`
2. Откройте issue на GitHub
3. Проверьте документацию Ultralytics
