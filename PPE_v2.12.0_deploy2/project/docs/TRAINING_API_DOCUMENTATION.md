# 📚 Training API Documentation
## PPE Detection System v2.5

**Base URL:** `/api/training`  
**Версия:** 1.0  
**Формат:** REST JSON API

---

## 📋 ОБЗОР ENDPOINTS

### Datasets (Датасеты)
| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/datasets` | Список всех датасетов |
| `POST` | `/datasets` | Создать новый датасет |
| `GET` | `/datasets/{id}` | Получить датасет по ID |
| `DELETE` | `/datasets/{id}` | Удалить датасет |

### Images (Изображения)
| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/datasets/{id}/images` | Загрузить изображения |
| `GET` | `/datasets/{id}/images` | Список изображений в датасете |
| `GET` | `/images/{id}` | Получить изображение (файл) |
| `DELETE` | `/images/{id}` | Удалить изображение |

### Annotations (Аннотации/Разметка)
| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/images/{id}/annotations` | Список аннотаций изображения |
| `POST` | `/images/{id}/annotations` | Создать аннотацию |
| `POST` | `/images/{id}/annotations/batch` | Создать несколько аннотаций |
| `PUT` | `/annotations/{id}` | Обновить аннотацию |
| `DELETE` | `/annotations/{id}` | Удалить аннотацию |
| `GET` | `/images/{id}/history` | История аннотаций (для Undo) |
| `POST` | `/images/{id}/undo` | Отменить последнее действие |

### Training Jobs (Задачи обучения)
| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/jobs` | Список задач обучения |
| `POST` | `/jobs` | Создать задачу обучения |
| `GET` | `/jobs/{id}` | Статус задачи |
| `POST` | `/jobs/{id}/cancel` | Отменить обучение |
| `GET` | `/jobs/{id}/logs` | Логи обучения (для графиков) |
| `WS` | `/ws/progress/{id}` | WebSocket прогресса |

### Models (Модели)
| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/models` | Список всех моделей |
| `POST` | `/models/{id}/activate` | Активировать модель |
| `GET` | `/models/{id}/download` | Скачать модель (.pt) |

### Statistics (Статистика)
| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/stats/overview` | Общая статистика |
| `GET` | `/stats/class-distribution` | Распределение по классам |

---

## 🔐 АУТЕНТИФИКАЦИЯ

Training API использует JWT токены (те же что и основной API).

```http
Authorization: Bearer <token>
```

---

## 📖 ДЕТАЛЬНОЕ ОПИСАНИЕ

### 1. DATASETS

#### Создать датасет
```http
POST /api/training/datasets
Content-Type: application/json

{
  "name": "PPE Dataset January 2026",
  "description": "Данные с производственного цеха"
}
```

**Response 201:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "PPE Dataset January 2026",
  "description": "Данные с производственного цеха",
  "status": "draft",
  "images_count": 0,
  "annotations_count": 0,
  "created_by": "admin",
  "created_at": "2026-01-23T14:30:00Z"
}
```

#### Список датасетов
```http
GET /api/training/datasets?status=draft
```

**Response 200:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "PPE Dataset January 2026",
    "status": "draft",
    "images_count": 150,
    "annotations_count": 720,
    "created_by": "admin",
    "created_at": "2026-01-23T14:30:00Z"
  }
]
```

---

### 2. IMAGES

#### Загрузка изображений
```http
POST /api/training/datasets/{dataset_id}/images
Content-Type: multipart/form-data

files: [image1.jpg, image2.jpg, ...]
```

**Ограничения:**
- Максимум 100 файлов за запрос
- Максимум 10MB на файл
- Форматы: JPEG, PNG, WebP
- Размеры: 32x32 - 8192x8192 px

**Response 200:**
```json
{
  "uploaded": [
    {
      "id": "img-123",
      "filename": "worker_001.jpg",
      "width": 1920,
      "height": 1080
    }
  ],
  "errors": [
    {
      "filename": "bad_file.exe",
      "error": "Недопустимое расширение: .exe"
    }
  ],
  "total_uploaded": 10,
  "total_errors": 1
}
```

#### Список изображений (с пагинацией)
```http
GET /api/training/datasets/{dataset_id}/images?page=1&page_size=50&status=annotated
```

**Response 200:**
```json
{
  "items": [
    {
      "id": "img-123",
      "filename": "abc123.jpg",
      "original_filename": "worker_001.jpg",
      "width": 1920,
      "height": 1080,
      "file_size": 245760,
      "status": "annotated",
      "uploaded_at": "2026-01-23T14:35:00Z",
      "annotations_count": 5
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50
}
```

**Статусы изображений:**
- `pending` - загружено, не размечено
- `annotated` - есть аннотации
- `validated` - проверено

---

### 3. ANNOTATIONS

#### Создать аннотацию
```http
POST /api/training/images/{image_id}/annotations
Content-Type: application/json

{
  "class_name": "no_hardhat",
  "bbox_x1": 0.12,
  "bbox_y1": 0.08,
  "bbox_x2": 0.35,
  "bbox_y2": 0.45
}
```

**Координаты bbox:** Нормализованные (0-1), относительно размера изображения.

**Доступные классы:**
| Класс | Описание |
|-------|----------|
| `person` | Человек |
| `hardhat` | Каска надета ✓ |
| `no_hardhat` | Без каски ❌ |
| `vest` | Жилет надет ✓ |
| `no_vest` | Без жилета ❌ |
| `glasses` | Очки надеты ✓ |
| `no_glasses` | Без очков ⚠️ |

**Response 201:**
```json
{
  "id": "ann-456",
  "class_name": "no_hardhat",
  "bbox": [0.12, 0.08, 0.35, 0.45],
  "confidence": null,
  "created_by": "admin",
  "created_at": "2026-01-23T15:00:00Z",
  "verified": false
}
```

#### Batch создание аннотаций
```http
POST /api/training/images/{image_id}/annotations/batch
Content-Type: application/json

{
  "annotations": [
    {"class_name": "person", "bbox_x1": 0.1, "bbox_y1": 0.1, "bbox_x2": 0.4, "bbox_y2": 0.9},
    {"class_name": "no_hardhat", "bbox_x1": 0.12, "bbox_y1": 0.08, "bbox_x2": 0.35, "bbox_y2": 0.25}
  ]
}
```

---

### 4. TRAINING JOBS

#### Создать задачу обучения
```http
POST /api/training/jobs
Content-Type: application/json

{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Training Run #1",
  "epochs": 50,
  "batch_size": 16,
  "learning_rate": 0.001,
  "image_size": 640,
  "augmentation": true,
  "pretrained": true
}
```

**Параметры обучения:**
| Параметр | По умолчанию | Диапазон | Описание |
|----------|--------------|----------|----------|
| `epochs` | 50 | 1-500 | Количество эпох |
| `batch_size` | 16 | 4-64 | Размер batch |
| `learning_rate` | 0.001 | 0.00001-0.1 | Learning rate |
| `image_size` | 640 | 320-1280 | Размер изображения для обучения |
| `augmentation` | true | - | Аугментация данных |
| `pretrained` | true | - | Использовать pretrained веса |

**Response 201:**
```json
{
  "id": "job-789",
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Training Run #1",
  "status": "queued",
  "progress": 0,
  "epochs_total": 50,
  "epochs_completed": 0,
  "current_loss": null,
  "best_map50": null,
  "created_at": "2026-01-23T15:30:00Z",
  "started_at": null,
  "error_message": null
}
```

**Статусы задачи:**
- `pending` - создана, ожидает
- `queued` - в очереди Celery
- `running` - выполняется
- `completed` - завершена успешно
- `failed` - ошибка
- `cancelled` - отменена

#### Логи обучения (для графиков)
```http
GET /api/training/jobs/{job_id}/logs
```

**Response 200:**
```json
{
  "logs": [
    {
      "epoch": 1,
      "train_loss": 0.8523,
      "val_loss": 0.7845,
      "map50": 0.45,
      "map50_95": 0.32,
      "learning_rate": 0.001,
      "timestamp": "2026-01-23T15:35:00Z"
    },
    {
      "epoch": 2,
      "train_loss": 0.6234,
      "val_loss": 0.5912,
      "map50": 0.58,
      "map50_95": 0.41,
      "learning_rate": 0.001,
      "timestamp": "2026-01-23T15:40:00Z"
    }
  ]
}
```

---

### 5. WEBSOCKET PROGRESS

#### Подключение
```javascript
const ws = new WebSocket('ws://localhost:8000/api/training/ws/progress/job-789');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

#### Сообщения прогресса
```json
{
  "type": "progress",
  "data": {
    "status": "running",
    "stage": "training",
    "epoch": 10,
    "total_epochs": 50,
    "progress": 20.0,
    "train_loss": 0.4521,
    "val_loss": 0.3892,
    "map50": 0.72,
    "message": "Epoch 10/50"
  }
}
```

#### Сообщение завершения
```json
{
  "type": "progress",
  "data": {
    "status": "completed",
    "stage": "done",
    "progress": 100,
    "map50": 0.85,
    "map50_95": 0.72,
    "model_id": "model-abc123",
    "message": "Обучение завершено! mAP@50=0.850"
  }
}
```

---

### 6. MODELS

#### Список моделей
```http
GET /api/training/models
```

**Response 200:**
```json
[
  {
    "id": "model-default",
    "name": "PPE Base Model (YOLOv8n)",
    "description": "Pretrained model",
    "map50": 0.85,
    "map50_95": 0.72,
    "is_active": true,
    "created_at": "2026-01-01T00:00:00Z",
    "training_images_count": 5000
  },
  {
    "id": "model-custom-123",
    "name": "PPE Custom Model (2026-01-23)",
    "description": "Fine-tuned on 150 images, 50 epochs",
    "map50": 0.88,
    "map50_95": 0.75,
    "is_active": false,
    "created_at": "2026-01-23T16:00:00Z",
    "training_images_count": 150
  }
]
```

#### Активировать модель
```http
POST /api/training/models/{model_id}/activate
```

**Response 200:**
```json
{
  "status": "activated",
  "model_id": "model-custom-123"
}
```

После активации модель автоматически используется детектором.

#### Скачать модель
```http
GET /api/training/models/{model_id}/download
```

**Response:** Файл `*.pt` (PyTorch weights)

---

### 7. STATISTICS

#### Общая статистика
```http
GET /api/training/stats/overview
```

**Response 200:**
```json
{
  "datasets": 5,
  "images": 1250,
  "annotations": 6200,
  "completed_jobs": 12,
  "running_jobs": 1,
  "models": 8
}
```

#### Распределение по классам
```http
GET /api/training/stats/class-distribution?dataset_id=550e8400...
```

**Response 200:**
```json
{
  "distribution": [
    {"class_name": "person", "count": 1500, "percentage": 24.19},
    {"class_name": "hardhat", "count": 1200, "percentage": 19.35},
    {"class_name": "no_hardhat", "count": 800, "percentage": 12.90},
    {"class_name": "vest", "count": 1100, "percentage": 17.74},
    {"class_name": "no_vest", "count": 900, "percentage": 14.52},
    {"class_name": "glasses", "count": 400, "percentage": 6.45},
    {"class_name": "no_glasses", "count": 300, "percentage": 4.84}
  ],
  "total": 6200
}
```

---

## ⚠️ КОДЫ ОШИБОК

| Код | Описание |
|-----|----------|
| 400 | Bad Request - невалидные данные |
| 401 | Unauthorized - требуется аутентификация |
| 403 | Forbidden - доступ запрещён |
| 404 | Not Found - ресурс не найден |
| 409 | Conflict - дубликат (например, изображение уже существует) |
| 422 | Validation Error - ошибка валидации |
| 500 | Internal Server Error |

**Формат ошибки:**
```json
{
  "detail": "Описание ошибки"
}
```

---

## 📊 WORKFLOW ИСПОЛЬЗОВАНИЯ

```
1. Создать датасет
   POST /datasets

2. Загрузить изображения (минимум 100 рекомендуется)
   POST /datasets/{id}/images

3. Разметить изображения
   POST /images/{id}/annotations

4. Проверить статистику
   GET /stats/class-distribution

5. Запустить обучение
   POST /jobs

6. Мониторить прогресс
   WS /ws/progress/{job_id}

7. Активировать новую модель
   POST /models/{id}/activate
```

---

**Последнее обновление:** 23 января 2026
