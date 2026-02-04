# 🎓 ПРОТОКОЛ СОВЕЩАНИЯ ЭКСПЕРТОВ
## Модуль обучения модели PPE Detection System v2.5

**Дата:** 23 января 2026  
**Время:** 14:00 - 16:30 (MSK)  
**Формат:** Виртуальное совещание  
**Модератор:** AI Architect

---

## 👥 УЧАСТНИКИ СОВЕЩАНИЯ

| # | Эксперт | Специализация | Роль |
|---|---------|---------------|------|
| 1 | **Елена Нейронова** | ML Engineer, 10 лет | ML Pipeline & Model Training |
| 2 | **Андрей Датасетов** | Data Engineer, 8 лет | Data Pipeline & Storage |
| 3 | **Виктор Интерфейсов** | UX Designer, 12 лет | UI/UX для ML Tools |
| 4 | **Наталья Безопасная** | Security Architect, 9 лет | Security & Access Control |
| 5 | **Игорь Инфраструктуров** | MLOps Engineer, 7 лет | Infrastructure & Deployment |

---

# 📋 ПОВЕСТКА ДНЯ

1. Обзор текущей реализации модуля Training
2. Анализ UI/UX для разметки данных
3. Backend архитектура для обучения
4. ML Pipeline и оптимизация
5. Безопасность и контроль доступа
6. Инфраструктура для обучения
7. Roadmap и приоритеты

---

# 🎤 ХОД СОВЕЩАНИЯ

## 1. ВСТУПЛЕНИЕ (14:00 - 14:10)

**Модератор:** Коллеги, сегодня обсуждаем новый модуль обучения модели. Задача - оценить текущую реализацию и составить план доработок для production-ready решения.

---

## 2. ОБЗОР ТЕКУЩЕЙ РЕАЛИЗАЦИИ (14:10 - 14:30)

### Презентация текущего состояния

```
┌─────────────────────────────────────────────────────────────────┐
│  TRAINING MODULE v1.0 - ТЕКУЩЕЕ СОСТОЯНИЕ                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✅ Реализовано (Frontend):                                    │
│  ├─ 4 вкладки: Загрузка, Разметка, Обучение, Модели           │
│  ├─ Drag & Drop загрузка изображений                          │
│  ├─ Canvas-based annotation tool                               │
│  ├─ Визуализация bounding boxes                                │
│  ├─ Выбор классов объектов                                     │
│  ├─ Zoom in/out                                                │
│  ├─ Параметры обучения (epochs, batch_size, lr)               │
│  └─ Список моделей с метриками                                 │
│                                                                 │
│  ❌ Не реализовано (Backend):                                  │
│  ├─ API endpoints для Training                                 │
│  ├─ Хранение изображений и аннотаций                          │
│  ├─ Training job queue                                         │
│  ├─ Model versioning                                           │
│  └─ GPU resource management                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. ДИСКУССИЯ ЭКСПЕРТОВ

### 👤 Елена Нейронова (ML Engineer)

**Елена:** Начну с ML pipeline. Текущий UI хороший, но backend для обучения отсутствует полностью. Вот что нужно:

#### 🔬 ML Pipeline Requirements

```python
# Предлагаемая архитектура Training Service

class TrainingService:
    """
    Сервис обучения модели YOLOv8 на пользовательских данных.
    """
    
    def __init__(self):
        self.model = YOLO('yolov8n.pt')  # Base model
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    async def prepare_dataset(self, images: List[TrainingImage]) -> str:
        """
        Подготовка датасета в формате YOLO.
        
        Структура:
        dataset/
        ├── images/
        │   ├── train/
        │   └── val/
        ├── labels/
        │   ├── train/
        │   └── val/
        └── data.yaml
        """
        pass
    
    async def start_training(self, params: TrainingParams) -> TrainingJob:
        """
        Запуск обучения с параметрами:
        - epochs: 50-100
        - batch_size: 8-32 (зависит от GPU памяти)
        - imgsz: 640
        - augment: True
        - pretrained: True (transfer learning)
        """
        pass
    
    async def evaluate_model(self, model_path: str) -> ModelMetrics:
        """
        Оценка модели:
        - mAP@50
        - mAP@50-95
        - Precision/Recall per class
        - Confusion matrix
        """
        pass
```

#### ⚠️ Критические замечания

| # | Issue | Severity | Рекомендация |
|---|-------|----------|--------------|
| ML-1 | Нет валидации данных | HIGH | Добавить проверку качества аннотаций |
| ML-2 | Нет train/val split | HIGH | Автоматическое разделение 80/20 |
| ML-3 | Нет early stopping | MEDIUM | Остановка при переобучении |
| ML-4 | Нет data augmentation UI | MEDIUM | Показать примеры аугментации |
| ML-5 | Минимум 10 изображений мало | HIGH | Минимум 50-100 на класс |

**Елена:** Особенно важен ML-5. 10 изображений - это демо, не production. Для реального fine-tuning нужно минимум 50 изображений на класс, а лучше 200+.

---

### 👤 Андрей Датасетов (Data Engineer)

**Андрей:** Согласен с Еленой. Добавлю про хранение данных:

#### 💾 Data Storage Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA STORAGE ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   Browser   │────▶│   API       │────▶│  MinIO/S3   │       │
│  │  (Upload)   │     │  Gateway    │     │  (Images)   │       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│                             │                    │              │
│                             ▼                    │              │
│                      ┌─────────────┐             │              │
│                      │  PostgreSQL │◀────────────┘              │
│                      │ (Metadata)  │                            │
│                      └─────────────┘                            │
│                             │                                   │
│                             ▼                                   │
│                      ┌─────────────┐                            │
│                      │   Redis     │                            │
│                      │  (Queue)    │                            │
│                      └─────────────┘                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 📊 Database Schema

```sql
-- Таблица изображений для обучения
CREATE TABLE training_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    uploaded_by VARCHAR(100) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    dataset_id UUID REFERENCES training_datasets(id),
    status VARCHAR(20) DEFAULT 'pending' -- pending, annotated, validated
);

-- Таблица аннотаций
CREATE TABLE annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_id UUID REFERENCES training_images(id) ON DELETE CASCADE,
    class_name VARCHAR(50) NOT NULL,
    bbox_x1 FLOAT NOT NULL,
    bbox_y1 FLOAT NOT NULL,
    bbox_x2 FLOAT NOT NULL,
    bbox_y2 FLOAT NOT NULL,
    confidence FLOAT,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(100)
);

-- Таблица датасетов
CREATE TABLE training_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    images_count INTEGER DEFAULT 0,
    annotations_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft' -- draft, ready, training, completed
);

-- Таблица задач обучения
CREATE TABLE training_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID REFERENCES training_datasets(id),
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed
    progress FLOAT DEFAULT 0,
    epochs_total INTEGER NOT NULL,
    epochs_completed INTEGER DEFAULT 0,
    current_loss FLOAT,
    best_map50 FLOAT,
    best_map50_95 FLOAT,
    config JSONB NOT NULL, -- training parameters
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_by VARCHAR(100) NOT NULL
);

-- Таблица версий моделей
CREATE TABLE model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    training_job_id UUID REFERENCES training_jobs(id),
    model_path VARCHAR(500) NOT NULL,
    map50 FLOAT NOT NULL,
    map50_95 FLOAT NOT NULL,
    precision_avg FLOAT,
    recall_avg FLOAT,
    metrics_per_class JSONB,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    activated_by VARCHAR(100)
);

-- Индексы
CREATE INDEX idx_training_images_dataset ON training_images(dataset_id);
CREATE INDEX idx_annotations_image ON annotations(image_id);
CREATE INDEX idx_training_jobs_status ON training_jobs(status);
CREATE INDEX idx_model_versions_active ON model_versions(is_active);
```

#### ⚠️ Data Issues

| # | Issue | Severity | Рекомендация |
|---|-------|----------|--------------|
| D-1 | Нет версионирования датасетов | HIGH | Добавить dataset versions |
| D-2 | Нет backup аннотаций | HIGH | Автоматический backup |
| D-3 | Нет дедупликации изображений | MEDIUM | Hash-based deduplication |
| D-4 | Нет экспорта в COCO/YOLO | MEDIUM | Поддержка стандартных форматов |

---

### 👤 Виктор Интерфейсов (UX Designer)

**Виктор:** UI для разметки - это ключевой момент. Текущая реализация базовая, но для production нужно больше:

#### 🎨 UX Improvements

```
┌─────────────────────────────────────────────────────────────────┐
│                    ANNOTATION UI IMPROVEMENTS                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ТЕКУЩЕЕ СОСТОЯНИЕ:              ПРЕДЛАГАЕМОЕ:                 │
│  ─────────────────               ──────────────                 │
│  ✅ Базовый canvas               ✅ + Polygon tool              │
│  ✅ Bounding boxes               ✅ + Auto-suggest boxes        │
│  ✅ Zoom                         ✅ + Pan/drag canvas           │
│  ✅ Class selector               ✅ + Keyboard shortcuts        │
│  ❌ No undo/redo                 ✅ + Undo/Redo (Ctrl+Z/Y)     │
│  ❌ No copy/paste                ✅ + Copy/Paste annotations    │
│  ❌ No batch operations          ✅ + Batch class change        │
│  ❌ No progress tracking         ✅ + Annotation progress bar   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 🖥️ Wireframe: Improved Annotation Interface

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🎓 Обучение модели                                          [admin] 🔔│
├─────────────────────────────────────────────────────────────────────────┤
│  [Загрузка] [▼ Разметка] [Обучение] [Модели]                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐  ┌────────────────────────────────────┐  ┌─────────┐│
│  │ 📁 Изображения│  │  ┌─────────────────────────────┐  │  │ Классы  ││
│  │              │  │  │                             │  │  │         ││
│  │ ┌──┐ img1.jpg│  │  │      [Рабочая область]     │  │  │ ○ person││
│  │ │✓ │ 3 boxes │  │  │                             │  │  │ ● hardhat│
│  │ └──┘         │  │  │    ┌─────────────────┐      │  │  │ ○ no_hat││
│  │ ┌──┐ img2.jpg│  │  │    │    👷 Person    │      │  │  │ ○ vest  ││
│  │ │  │ 0 boxes │  │  │    │  ┌──────────┐  │      │  │  │ ○ no_vest│
│  │ └──┘         │  │  │    │  │ hardhat  │  │      │  │  │         ││
│  │ ┌──┐ img3.jpg│  │  │    │  └──────────┘  │      │  │  ├─────────┤│
│  │ │✓ │ 5 boxes │  │  │    └─────────────────┘      │  │  │ Инструм.││
│  │ └──┘         │  │  │                             │  │  │ [□] Draw││
│  │              │  │  └─────────────────────────────┘  │  │ [◇] Poly││
│  │ Progress:    │  │                                    │  │ [↖] Sel ││
│  │ ████░░ 60%   │  │  [🔍-] 100% [🔍+]  [↶] [↷]       │  │ [✋] Pan ││
│  │              │  │                                    │  │         ││
│  │ [◀ Prev]     │  │  ┌────────────────────────────┐   │  ├─────────┤│
│  │ [Next ▶]     │  │  │ Shortcuts: D=Draw V=Select │   │  │ Горячие ││
│  │              │  │  │ Del=Remove  1-7=Classes    │   │  │ 1=person││
│  └──────────────┘  │  └────────────────────────────┘   │  │ 2=hardhat│
│                    └────────────────────────────────────┘  │ 3=no_hat││
│                                                             └─────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

#### ⚠️ UX Issues

| # | Issue | Severity | Рекомендация |
|---|-------|----------|--------------|
| UX-1 | Нет Undo/Redo | HIGH | Добавить историю действий |
| UX-2 | Нет keyboard shortcuts | HIGH | 1-9 для классов, D/V для tools |
| UX-3 | Нет progress indicator | MEDIUM | Показать % размеченных |
| UX-4 | Нет batch operations | MEDIUM | Выделить несколько boxes |
| UX-5 | Canvas 976 строк | HIGH | Разбить на компоненты |
| UX-6 | Нет автосохранения | HIGH | Сохранять каждые 30 сек |
| UX-7 | Нет AI-assisted annotation | LOW | Smart suggestions |

**Виктор:** Особенно критичен UX-1. Пользователи ОБЯЗАТЕЛЬНО будут ошибаться при разметке. Без Undo/Redo это будет очень frustrаting.

---

### 👤 Наталья Безопасная (Security Architect)

**Наталья:** Модуль обучения создаёт новые векторы атак. Вот что нужно защитить:

#### 🔒 Security Concerns

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY THREAT MODEL                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  UPLOAD THREATS:                                                │
│  ├─ Malicious files (не изображения)                           │
│  ├─ ZIP bombs / очень большие файлы                            │
│  ├─ Image-based exploits (ImageMagick vulnerabilities)         │
│  └─ DoS через массовую загрузку                                │
│                                                                 │
│  TRAINING THREATS:                                              │
│  ├─ Resource exhaustion (GPU/CPU)                              │
│  ├─ Model poisoning (вредоносные аннотации)                    │
│  ├─ Unauthorized model deployment                               │
│  └─ Data exfiltration через модель                             │
│                                                                 │
│  ACCESS CONTROL:                                                │
│  ├─ Кто может загружать данные?                                │
│  ├─ Кто может запускать обучение?                              │
│  ├─ Кто может активировать модель?                             │
│  └─ Audit trail всех действий                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 🛡️ Security Requirements

```python
# Безопасная загрузка изображений
class SecureImageUpload:
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_FILES_PER_REQUEST = 100
    MAX_TOTAL_SIZE = 500 * 1024 * 1024  # 500MB per request
    
    @staticmethod
    def validate_image(file: UploadFile) -> bool:
        # 1. Check extension
        ext = Path(file.filename).suffix.lower()
        if ext not in SecureImageUpload.ALLOWED_EXTENSIONS:
            raise ValueError(f"Invalid extension: {ext}")
        
        # 2. Check file size
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        if size > SecureImageUpload.MAX_FILE_SIZE:
            raise ValueError(f"File too large: {size}")
        
        # 3. Verify magic bytes (actual image check)
        header = file.file.read(16)
        file.file.seek(0)
        if not SecureImageUpload._is_valid_image_header(header):
            raise ValueError("Invalid image format")
        
        # 4. Try to actually open as image (catches malformed files)
        try:
            img = Image.open(file.file)
            img.verify()
            file.file.seek(0)
        except Exception:
            raise ValueError("Cannot open as image")
        
        return True
    
    @staticmethod
    def _is_valid_image_header(header: bytes) -> bool:
        # JPEG: FF D8 FF
        # PNG: 89 50 4E 47
        # WebP: 52 49 46 46 ... 57 45 42 50
        jpeg = header[:3] == b'\xff\xd8\xff'
        png = header[:4] == b'\x89PNG'
        webp = header[:4] == b'RIFF' and header[8:12] == b'WEBP'
        return jpeg or png or webp
```

#### 🔐 Role-Based Access Control

```yaml
# Roles for Training Module
roles:
  viewer:
    - training.images.view
    - training.annotations.view
    - training.models.view
    
  annotator:
    - training.images.view
    - training.images.upload
    - training.annotations.view
    - training.annotations.create
    - training.annotations.edit_own
    
  trainer:
    - annotator.*
    - training.jobs.create
    - training.jobs.view
    - training.models.view
    
  admin:
    - trainer.*
    - training.annotations.delete
    - training.annotations.verify
    - training.models.activate
    - training.models.delete
    - training.jobs.cancel
```

#### ⚠️ Security Issues

| # | Issue | Severity | Рекомендация |
|---|-------|----------|--------------|
| S-1 | Нет валидации файлов | CRITICAL | Magic bytes + PIL verify |
| S-2 | Нет rate limiting на upload | HIGH | 100 файлов/час |
| S-3 | Нет RBAC | HIGH | Roles: viewer/annotator/trainer/admin |
| S-4 | Нет audit log | HIGH | Логировать все действия |
| S-5 | Нет квот на storage | MEDIUM | Лимиты per user/team |
| S-6 | Нет sandboxing training | MEDIUM | Изолированные контейнеры |

---

### 👤 Игорь Инфраструктуров (MLOps Engineer)

**Игорь:** Инфраструктура для обучения - это отдельная большая тема. Вот архитектура:

#### 🏗️ Training Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      TRAINING INFRASTRUCTURE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         ┌─────────────┐                                 │
│                         │   Browser   │                                 │
│                         └──────┬──────┘                                 │
│                                │                                        │
│                         ┌──────▼──────┐                                 │
│                         │   API GW    │                                 │
│                         │  (FastAPI)  │                                 │
│                         └──────┬──────┘                                 │
│                                │                                        │
│         ┌──────────────────────┼──────────────────────┐                │
│         │                      │                      │                │
│  ┌──────▼──────┐       ┌──────▼──────┐       ┌──────▼──────┐          │
│  │   MinIO     │       │  PostgreSQL │       │    Redis    │          │
│  │  (Images)   │       │  (Metadata) │       │   (Queue)   │          │
│  └─────────────┘       └─────────────┘       └──────┬──────┘          │
│                                                      │                 │
│                                               ┌──────▼──────┐          │
│                                               │   Celery    │          │
│                                               │   Worker    │          │
│                                               └──────┬──────┘          │
│                                                      │                 │
│                    ┌─────────────────────────────────┼─────────────┐   │
│                    │                                 │             │   │
│             ┌──────▼──────┐                  ┌──────▼──────┐      │   │
│             │  Training   │                  │  Training   │      │   │
│             │  Pod (GPU)  │                  │  Pod (GPU)  │      │   │
│             │  Worker 1   │                  │  Worker 2   │      │   │
│             └─────────────┘                  └─────────────┘      │   │
│                                                                   │   │
│                    ┌─────────────────────────────────────────────┐│   │
│                    │           Kubernetes Cluster               ││   │
│                    └─────────────────────────────────────────────┘│   │
│                                                                   │   │
└───────────────────────────────────────────────────────────────────────┘
```

#### 📦 Kubernetes Resources for Training

```yaml
# training-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: training-job-${JOB_ID}
  namespace: ppe-training
spec:
  backoffLimit: 2
  activeDeadlineSeconds: 86400  # 24 hours max
  template:
    spec:
      restartPolicy: Never
      
      # GPU scheduling
      nodeSelector:
        nvidia.com/gpu: "true"
      
      tolerations:
      - key: "nvidia.com/gpu"
        operator: "Exists"
        effect: "NoSchedule"
      
      containers:
      - name: trainer
        image: ppe-trainer:latest
        
        resources:
          requests:
            memory: "8Gi"
            cpu: "4"
            nvidia.com/gpu: 1
          limits:
            memory: "16Gi"
            cpu: "8"
            nvidia.com/gpu: 1
        
        env:
        - name: JOB_ID
          value: "${JOB_ID}"
        - name: DATASET_PATH
          value: "/data/datasets/${DATASET_ID}"
        - name: MODEL_OUTPUT
          value: "/data/models/${JOB_ID}"
        - name: EPOCHS
          value: "${EPOCHS}"
        - name: BATCH_SIZE
          value: "${BATCH_SIZE}"
        
        volumeMounts:
        - name: datasets
          mountPath: /data/datasets
          readOnly: true
        - name: models
          mountPath: /data/models
        - name: cache
          mountPath: /root/.cache
      
      volumes:
      - name: datasets
        persistentVolumeClaim:
          claimName: training-datasets-pvc
      - name: models
        persistentVolumeClaim:
          claimName: training-models-pvc
      - name: cache
        emptyDir:
          sizeLimit: 10Gi

---
# GPU ResourceQuota
apiVersion: v1
kind: ResourceQuota
metadata:
  name: training-gpu-quota
  namespace: ppe-training
spec:
  hard:
    requests.nvidia.com/gpu: "2"  # Max 2 GPUs total
    limits.nvidia.com/gpu: "2"
```

#### 📊 Training Job Flow

```
┌────────────────────────────────────────────────────────────────────┐
│                     TRAINING JOB LIFECYCLE                         │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  [User] ─── Start Training ───▶ [API] ─── Create Job ───▶ [Redis] │
│                                                              │     │
│                                                              ▼     │
│  [Dashboard] ◀─── Progress ─── [API] ◀─── Status ─── [Worker]     │
│       │                                                  │         │
│       │                                                  ▼         │
│       │                                          ┌─────────────┐   │
│       │                                          │   PENDING   │   │
│       │                                          └──────┬──────┘   │
│       │                                                 │          │
│       │                              GPU Available? ────┤          │
│       │                                     │           │          │
│       │                                     ▼           ▼          │
│       │                              ┌───────────┐ ┌─────────┐    │
│       │                              │  RUNNING  │ │ QUEUED  │    │
│       │                              └─────┬─────┘ └─────────┘    │
│       │                                    │                       │
│       │               ┌────────────────────┴────────────────┐     │
│       │               │                                      │     │
│       │               ▼                                      ▼     │
│       │        ┌─────────────┐                       ┌─────────┐  │
│       └─────── │  COMPLETED  │                       │  FAILED │  │
│                └─────────────┘                       └─────────┘  │
│                      │                                             │
│                      ▼                                             │
│              [Model Saved] ───▶ [Evaluation] ───▶ [Ready to Deploy]│
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

#### ⚠️ Infrastructure Issues

| # | Issue | Severity | Рекомендация |
|---|-------|----------|--------------|
| I-1 | Нет job queue | CRITICAL | Celery + Redis |
| I-2 | Нет GPU scheduling | CRITICAL | K8s GPU operator |
| I-3 | Нет model storage | HIGH | MinIO/S3 |
| I-4 | Нет progress streaming | HIGH | WebSocket + Redis Pub/Sub |
| I-5 | Нет auto-scaling | MEDIUM | KEDA для GPU pods |
| I-6 | Нет job timeout | MEDIUM | 24h max |

---

## 4. ОБЩАЯ ДИСКУССИЯ (15:30 - 16:00)

**Модератор:** Спасибо всем за детальный анализ. Давайте обсудим приоритеты.

**Елена:** Считаю, что без backend модуль бесполезен. Нужно начать с API.

**Андрей:** Согласен. База данных и storage - первый приоритет.

**Виктор:** Но пока нет backend, можно улучшить UX. Undo/Redo и shortcuts не требуют API.

**Наталья:** Безопасность должна быть с самого начала. Валидация файлов - must have.

**Игорь:** Инфраструктура для обучения - это отдельный сервис. Можно делать параллельно.

---

## 5. РЕШЕНИЯ И ROADMAP (16:00 - 16:30)

### 📋 Согласованный Roadmap

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TRAINING MODULE ROADMAP                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PHASE 1: Foundation (2 недели)                                        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                     │
│  ├─ [Backend] Database schema + migrations                             │
│  ├─ [Backend] Training API endpoints (CRUD)                            │
│  ├─ [Backend] Image upload с валидацией                                │
│  ├─ [Frontend] Undo/Redo для annotations                               │
│  └─ [Frontend] Keyboard shortcuts                                       │
│                                                                         │
│  PHASE 2: Core Training (2 недели)                                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                     │
│  ├─ [Backend] Training service (Celery worker)                         │
│  ├─ [Backend] Job queue + status tracking                              │
│  ├─ [Backend] Model evaluation + metrics                               │
│  ├─ [Frontend] Real-time progress via WebSocket                        │
│  └─ [Frontend] Training charts (loss, mAP)                             │
│                                                                         │
│  PHASE 3: Production Ready (2 недели)                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                    │
│  ├─ [DevOps] GPU Kubernetes resources                                  │
│  ├─ [DevOps] MinIO for model storage                                   │
│  ├─ [Security] RBAC implementation                                     │
│  ├─ [Security] Audit logging                                           │
│  └─ [ML] Data augmentation + validation                                │
│                                                                         │
│  PHASE 4: Advanced Features (2 недели)                                 │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                   │
│  ├─ [ML] Auto-suggest annotations (pre-labeling)                       │
│  ├─ [ML] Active learning suggestions                                   │
│  ├─ [Frontend] Polygon annotations                                     │
│  ├─ [Frontend] Dataset export (COCO, YOLO)                             │
│  └─ [DevOps] Model A/B testing                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 🎯 Phase 1 Tasks (Детально)

| # | Task | Owner | Estimate | Priority |
|---|------|-------|----------|----------|
| 1.1 | DB schema для training | Андрей | 4h | P0 |
| 1.2 | API: POST /training/images | Андрей | 4h | P0 |
| 1.3 | API: GET/POST /training/annotations | Андрей | 4h | P0 |
| 1.4 | Image validation (security) | Наталья | 4h | P0 |
| 1.5 | Frontend: Undo/Redo | Виктор | 8h | P0 |
| 1.6 | Frontend: Keyboard shortcuts | Виктор | 4h | P1 |
| 1.7 | Frontend: Refactor to components | Виктор | 8h | P1 |
| 1.8 | API: Datasets CRUD | Андрей | 4h | P1 |
| 1.9 | Storage: MinIO setup | Игорь | 4h | P1 |
| 1.10 | Tests: Unit + Integration | ALL | 8h | P1 |

**TOTAL Phase 1:** ~52 часов / 2 недели

---

## 6. ГОЛОСОВАНИЕ ПО ПРИОРИТЕТАМ

```
┌─────────────────────────────────────────────────────────────────┐
│                  ГОЛОСОВАНИЕ ЭКСПЕРТОВ                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Вопрос: Какой функционал КРИТИЧЕН для MVP?                    │
│                                                                 │
│  ✅ Backend API (CRUD)           - 5/5 голосов (100%)          │
│  ✅ Image validation             - 5/5 голосов (100%)          │
│  ✅ Undo/Redo                    - 4/5 голосов (80%)           │
│  ✅ Keyboard shortcuts           - 4/5 голосов (80%)           │
│  ⬜ Polygon annotations          - 2/5 голосов (40%)           │
│  ⬜ Auto-suggest                 - 1/5 голосов (20%)           │
│                                                                 │
│  Вопрос: Минимальное кол-во изображений для обучения?          │
│                                                                 │
│  ⬜ 10 изображений               - 0/5 голосов                 │
│  ⬜ 50 изображений               - 1/5 голосов                 │
│  ✅ 100 изображений              - 3/5 голосов (60%)           │
│  ⬜ 200 изображений              - 1/5 голосов                 │
│                                                                 │
│  РЕШЕНИЕ: Минимум 100 изображений, минимум 50 на класс        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. ACTION ITEMS

### Немедленные действия (эта неделя)

| # | Action | Owner | Deadline |
|---|--------|-------|----------|
| 1 | Создать DB migration для training tables | Андрей | 25.01 |
| 2 | Реализовать SecureImageUpload class | Наталья | 25.01 |
| 3 | Разбить Training.tsx на компоненты | Виктор | 26.01 |
| 4 | Добавить Undo/Redo в annotation | Виктор | 27.01 |
| 5 | Настроить MinIO в docker-compose | Игорь | 25.01 |
| 6 | Написать Training API spec (OpenAPI) | Елена | 24.01 |

### Follow-up совещание

**Дата:** 30 января 2026, 14:00  
**Повестка:** Review Phase 1 progress, планирование Phase 2

---

## 📊 ИТОГОВАЯ ОЦЕНКА МОДУЛЯ TRAINING

```
╔═══════════════════════════════════════════════════════════════════╗
║                  TRAINING MODULE ASSESSMENT                       ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  Current State:     ████░░░░░░░░░░░░░░░░  20%  (UI only)        ║
║                                                                   ║
║  After Phase 1:     ████████░░░░░░░░░░░░  40%  (+ Backend)      ║
║  After Phase 2:     ████████████░░░░░░░░  60%  (+ Training)     ║
║  After Phase 3:     ████████████████░░░░  80%  (+ Production)   ║
║  After Phase 4:     ████████████████████  100% (+ Advanced)     ║
║                                                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  Estimated Timeline: 8 недель до production-ready               ║
║  Estimated Effort:   ~200 человеко-часов                        ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## 📝 ПОДПИСИ УЧАСТНИКОВ

- ✅ Елена Нейронова, ML Engineer
- ✅ Андрей Датасетов, Data Engineer  
- ✅ Виктор Интерфейсов, UX Designer
- ✅ Наталья Безопасная, Security Architect
- ✅ Игорь Инфраструктуров, MLOps Engineer

**Протокол составлен:** 23 января 2026  
**Следующее совещание:** 30 января 2026, 14:00

---

*Конец протокола*

---

## 📋 РЕЗУЛЬТАТЫ СОВЕЩАНИЯ v2.10.45

### Дата: 2026-01-29

### Выявленные проблемы

#### КРИТИЧЕСКАЯ: Аннотации не отображаются после добавления

**Симптом:** Пользователь рисует bbox, но аннотация не появляется на canvas.

**Корневая причина:**
```
1. currentImage хранится в useState (строка 42)
2. При клике на изображение создаётся КОПИЯ объекта
3. После addAnnotationMutation.mutate() вызывается invalidateQueries
4. React Query обновляет массив images с новой аннотацией
5. НО! currentImage остаётся старой копией БЕЗ новой аннотации
6. Canvas рендерит currentImage.annotations → пустой массив
```

**Диаграмма потока данных (ДО исправления):**
```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│ User clicks │───►│setCurrentImage│───►│ currentImage    │
│   image     │    │   (copy)     │    │ (old snapshot)  │
└─────────────┘    └──────────────┘    └────────┬────────┘
                                                │
┌─────────────┐    ┌──────────────┐    ┌────────▼────────┐
│ User draws  │───►│  mutation    │───►│ invalidateQuery │
│   bbox      │    │  onSuccess   │    │ (images array)  │
└─────────────┘    └──────────────┘    └────────┬────────┘
                                                │
                                       ┌────────▼────────┐
                                       │ images updated  │
                                       │ (with new ann)  │
                                       └────────┬────────┘
                                                │
                                       ┌────────▼────────┐
                                       │  currentImage   │
                                       │  NOT UPDATED!   │ ← ПРОБЛЕМА
                                       └─────────────────┘
```

**Решение (v2.10.45):**
```javascript
// Sync currentImage with images (v2.10.45)
useEffect(() => {
  if (currentImage && images.length > 0) {
    const updatedImage = images.find(img => img.id === currentImage.id);
    if (updatedImage) {
      const currentAnnCount = currentImage.annotations?.length ?? 0;
      const updatedAnnCount = updatedImage.annotations?.length ?? 0;
      if (currentAnnCount !== updatedAnnCount) {
        setCurrentImage(updatedImage);
      }
    }
  }
}, [images, currentImage]);
```

**Диаграмма потока данных (ПОСЛЕ исправления):**
```
┌─────────────────┐    ┌──────────────────┐
│ invalidateQuery │───►│ images updated   │
│                 │    │ (with new ann)   │
└─────────────────┘    └────────┬─────────┘
                                │
                       ┌────────▼─────────┐
                       │ useEffect fires  │
                       │ (images changed) │
                       └────────┬─────────┘
                                │
                       ┌────────▼─────────┐
                       │ find updated img │
                       │ by currentImage.id│
                       └────────┬─────────┘
                                │
                       ┌────────▼─────────┐
                       │setCurrentImage   │
                       │ (synced!)        │
                       └────────┬─────────┘
                                │
                       ┌────────▼─────────┐
                       │ Canvas renders   │
                       │ new annotation ✓ │
                       └─────────────────┘
```

#### СРЕДНЯЯ: Дублирующий файл Training.tsx

**Проблема:** Два файла Training.tsx:
- `/dashboard/src/Training.tsx` (1602 строки) - НЕ ИСПОЛЬЗУЕТСЯ
- `/dashboard/src/pages/Training.tsx` (1467 строк) - АКТИВНЫЙ

**Решение:** Удалён неиспользуемый файл.

### Участники экспертного совещания

| Роль | Зона ответственности |
|------|---------------------|
| Planner | Архитектурный анализ |
| Code Reviewer | Поиск багов |
| Build Error Resolver | TypeScript/сборка |
| TDD Guide | Анализ потоков данных |
| Refactor Cleaner | Удаление дубликатов |

### Статус: ✅ РЕШЕНО

