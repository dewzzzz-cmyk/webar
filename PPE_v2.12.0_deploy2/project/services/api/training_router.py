"""
Training API Router v1.0
API для модуля обучения модели PPE Detection

Функционал:
- CRUD датасетов
- Загрузка изображений с валидацией (безопасность)
- CRUD аннотаций с историей (Undo/Redo)
- Управление задачами обучения
- Версионирование моделей
"""

from __future__ import annotations  # Для forward references в типах

import os
import io
import json
import uuid
import hashlib
import logging
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query, status, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, validator
from PIL import Image
import aiofiles

# ============================================================================
# Configuration
# ============================================================================

logger = logging.getLogger('training_api')

TRAINING_IMAGES_PATH = os.getenv('TRAINING_IMAGES_PATH', '/app/training_data/images')
TRAINING_MODELS_PATH = os.getenv('TRAINING_MODELS_PATH', '/app/training_data/models')
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'minio:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin123')
MINIO_BUCKET = os.getenv('MINIO_BUCKET', 'training-images')

# Ensure directories exist
Path(TRAINING_IMAGES_PATH).mkdir(parents=True, exist_ok=True)
Path(TRAINING_MODELS_PATH).mkdir(parents=True, exist_ok=True)

# ============================================================================
# API Keys Management - Global Functions
# ============================================================================

API_KEYS_FILE = Path(os.getenv('CONFIG_PATH', '/app/configs')) / 'api_keys.json'

def _load_api_keys() -> dict:
    """Загрузить API ключи из файла"""
    try:
        if API_KEYS_FILE.exists():
            with open(API_KEYS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load API keys: {e}")
    return {}

def _save_api_keys(keys: dict) -> bool:
    """Сохранить API ключи в файл"""
    try:
        API_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(API_KEYS_FILE, 'w') as f:
            json.dump(keys, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save API keys: {e}")
        return False

# ============================================================================
# Security - Secure Image Upload
# ============================================================================

class SecureImageUpload:
    """Secure image validation and upload (Security Expert requirements)."""
    
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
    ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_FILES_PER_REQUEST = 100
    MIN_IMAGE_SIZE = 32
    MAX_IMAGE_SIZE = 8192
    
    # Magic bytes
    MAGIC_BYTES = {
        b'\xff\xd8\xff': ('jpeg', 'image/jpeg'),
        b'\x89PNG\r\n\x1a\n': ('png', 'image/png'),
    }
    
    @classmethod
    def validate(cls, file: UploadFile) -> dict:
        """
        Validate uploaded file.
        Returns: dict with file info
        Raises: ValueError if invalid
        """
        # 1. Check filename
        if not file.filename:
            raise ValueError("Имя файла обязательно")
        
        ext = Path(file.filename).suffix.lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise ValueError(f"Недопустимое расширение: {ext}")
        
        # 2. Read content
        content = file.file.read()
        file.file.seek(0)
        
        # 3. Check size
        size = len(content)
        if size > cls.MAX_FILE_SIZE:
            raise ValueError(f"Файл слишком большой: {size / 1024 / 1024:.1f}MB")
        if size < 100:
            raise ValueError("Файл слишком маленький")
        
        # 4. Verify magic bytes
        detected_format = None
        detected_mime = None
        for magic, (fmt, mime) in cls.MAGIC_BYTES.items():
            if content.startswith(magic):
                detected_format = fmt
                detected_mime = mime
                break
        
        # WebP check
        if content[:4] == b'RIFF' and content[8:12] == b'WEBP':
            detected_format = 'webp'
            detected_mime = 'image/webp'
        
        if not detected_format:
            raise ValueError("Неверный формат изображения")
        
        # 5. Open and verify with PIL
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
            
            # Re-open for dimensions
            img = Image.open(io.BytesIO(content))
            width, height = img.size
            
            if width < cls.MIN_IMAGE_SIZE or height < cls.MIN_IMAGE_SIZE:
                raise ValueError(f"Изображение слишком маленькое: {width}x{height}")
            if width > cls.MAX_IMAGE_SIZE or height > cls.MAX_IMAGE_SIZE:
                raise ValueError(f"Изображение слишком большое: {width}x{height}")
                
        except (IOError, SyntaxError) as e:
            raise ValueError(f"Не удалось открыть изображение: {e}")
        
        # 6. Calculate hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        return {
            'content': content,
            'size': size,
            'width': width,
            'height': height,
            'hash': file_hash,
            'format': detected_format,
            'mime_type': detected_mime,
        }
    
    @classmethod
    async def save(cls, content: bytes, filename: str, dataset_id: str) -> str:
        """Save image to local storage."""
        ext = Path(filename).suffix.lower()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        
        dataset_dir = Path(TRAINING_IMAGES_PATH) / dataset_id
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = dataset_dir / unique_name
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        return str(file_path)


# ============================================================================
# Dataset Normalization - ЕДИНАЯ ФУНКЦИЯ ДЛЯ ВСЕХ ИСТОЧНИКОВ
# ============================================================================

def normalize_dataset(raw_data: dict, source_type: str = "unknown") -> dict:
    """
    Нормализует данные датасета из любого источника.
    Гарантирует соответствие DatasetResponse.
    
    Args:
        raw_data: Сырые данные из PostgreSQL, metadata.json, data.yaml или screenshots
        source_type: Тип источника ('postgres', 'metadata', 'yaml', 'screenshots', 'unknown')
    
    Returns:
        dict: Нормализованный словарь, соответствующий DatasetResponse
    """
    # 1. Нормализация ID (UUID → string)
    raw_id = raw_data.get('id')
    if raw_id is None:
        dataset_id = ""
    elif hasattr(raw_id, 'hex'):  # UUID object from asyncpg
        dataset_id = str(raw_id)
    else:
        dataset_id = str(raw_id)
    
    # 2. Нормализация created_at (пустая строка → None, ISO string → datetime)
    created_at = raw_data.get('created_at')
    if created_at == "" or created_at is None:
        created_at = None
    elif isinstance(created_at, str) and created_at:
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            created_at = None
    # datetime объекты из PostgreSQL оставляем как есть
    
    # 3. Нормализация classes (JSONB → list, None → [])
    classes = raw_data.get('classes')
    if classes is None:
        classes = []
    elif isinstance(classes, str):
        try:
            classes = json.loads(classes)
        except (json.JSONDecodeError, TypeError):
            classes = []
    
    # 4. Собираем нормализованный результат
    return {
        "id": dataset_id,
        "name": raw_data.get('name') or dataset_id or "Unknown",
        "description": raw_data.get('description') or None,
        "status": raw_data.get('status', 'created'),
        "images_count": int(raw_data.get('images_count', 0) or 0),
        "annotations_count": int(raw_data.get('annotations_count', 0) or 0),
        "labeled_count": int(raw_data.get('labeled_count', 0) or 0),
        "created_by": raw_data.get('created_by') or None,
        "created_at": created_at,
        "classes": classes,
        "source": raw_data.get('source', source_type),
        "path": raw_data.get('path'),
    }


# ============================================================================
# Pydantic Schemas
# ============================================================================

class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

class DatasetResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str = "created"
    images_count: int = 0
    annotations_count: int = 0
    labeled_count: int = 0
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    # Дополнительные поля для датасетов из каталога
    classes: Optional[List[str]] = None
    source: Optional[str] = None
    path: Optional[str] = None

class ImageResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    url: str  # URL для загрузки изображения
    width: int
    height: int
    file_size: int
    status: str
    uploaded_at: datetime
    annotations_count: int = 0
    annotations: List['AnnotationResponse'] = []  # Аннотации для этого изображения

class AnnotationCreate(BaseModel):
    class_name: str = Field(..., min_length=1, max_length=50)
    bbox_x1: float = Field(..., ge=0, le=1)
    bbox_y1: float = Field(..., ge=0, le=1)
    bbox_x2: float = Field(..., ge=0, le=1)
    bbox_y2: float = Field(..., ge=0, le=1)
    
    @validator('bbox_x2')
    def validate_x2(cls, v, values):
        if 'bbox_x1' in values and v <= values['bbox_x1']:
            raise ValueError('bbox_x2 must be > bbox_x1')
        return v
    
    @validator('bbox_y2')
    def validate_y2(cls, v, values):
        if 'bbox_y1' in values and v <= values['bbox_y1']:
            raise ValueError('bbox_y2 must be > bbox_y1')
        return v

# v2.10.61: Model for updating annotations (optional fields)
class AnnotationUpdate(BaseModel):
    class_name: Optional[str] = Field(None, min_length=1, max_length=50)
    bbox_x1: Optional[float] = Field(None, ge=0, le=1)
    bbox_y1: Optional[float] = Field(None, ge=0, le=1)
    bbox_x2: Optional[float] = Field(None, ge=0, le=1)
    bbox_y2: Optional[float] = Field(None, ge=0, le=1)

class AnnotationResponse(BaseModel):
    id: str
    class_name: str
    bbox: List[float]
    confidence: Optional[float]
    created_by: str
    created_at: datetime
    verified: bool

class TrainingJobCreate(BaseModel):
    dataset_id: str
    name: Optional[str] = None
    
    # Model selection
    model_type: str = Field(
        "yolov8", 
        description="Model architecture: yolov8, yolov9, yolov10, yolov11"
    )
    model_size: str = Field(
        "n",
        description="Model size: n (nano), s (small), m (medium), l (large), x (xlarge)"
    )
    
    # Data split
    train_split: float = Field(0.7, ge=0.5, le=0.9, description="Training set ratio")
    val_split: float = Field(0.2, ge=0.05, le=0.4, description="Validation set ratio")
    test_split: float = Field(0.1, ge=0.0, le=0.2, description="Test set ratio")
    
    # Training parameters
    epochs: int = Field(50, ge=1, le=500)
    batch_size: int = Field(16, ge=4, le=128)  # Increased max for RTX 5090
    learning_rate: float = Field(0.001, ge=0.00001, le=0.1)
    image_size: int = Field(640, ge=320, le=1280)
    augmentation: bool = True
    pretrained: bool = True
    
    # Advanced options
    optimizer: str = Field("auto", description="Optimizer: auto, SGD, Adam, AdamW")
    patience: int = Field(50, ge=0, le=100, description="Early stopping patience (0=disabled)")
    
    @validator('model_type')
    def validate_model_type(cls, v):
        valid_types = ['yolov8', 'yolov9', 'yolov10', 'yolov11', 'yolo11']
        if v.lower() not in valid_types:
            raise ValueError(f"model_type must be one of: {valid_types}")
        return v.lower()
    
    @validator('model_size')
    def validate_model_size(cls, v, values):
        # YOLOv9 has: t(tiny), s, m, c(compact), e(extended)
        # YOLOv10 has: n, s, m, b(balanced), l, x
        # Others: n, s, m, l, x
        valid_sizes = ['n', 's', 'm', 'l', 'x', 'b', 't', 'c', 'e']
        if v.lower() not in valid_sizes:
            raise ValueError(f"model_size must be one of: {valid_sizes}")
        return v.lower()
    
    @validator('test_split')
    def validate_splits(cls, v, values):
        train = values.get('train_split', 0.7)
        val = values.get('val_split', 0.2)
        total = train + val + v
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Splits must sum to 1.0, got {total}")
        return v

class TrainingJobResponse(BaseModel):
    id: str
    dataset_id: str
    name: Optional[str]
    status: str
    progress: float
    epochs_total: int
    epochs_completed: int
    current_loss: Optional[float]
    best_map50: Optional[float]
    created_at: datetime
    started_at: Optional[datetime]
    error_message: Optional[str]
    # New fields
    model_type: Optional[str] = "yolov8"
    model_size: Optional[str] = "n"
    train_split: Optional[float] = 0.7
    val_split: Optional[float] = 0.2
    test_split: Optional[float] = 0.1

class ModelResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    map50: float
    map50_95: float
    is_active: bool
    created_at: datetime
    training_images_count: Optional[int]

class HistoryEntry(BaseModel):
    id: str
    action: str
    annotation_id: Optional[str]
    created_at: datetime


# ============================================================================
# Router
# ============================================================================

def create_training_router(db_pool) -> APIRouter:
    """Create training router with database connection pool."""
    
    router = APIRouter(tags=["Training"])
    
    # ========================================================================
    # Datasets
    # ========================================================================
    
    @router.get("/datasets", response_model=List[DatasetResponse])
    async def list_datasets(status: Optional[str] = None):
        """List all datasets - с fallback на файловую систему."""
        datasets = []
        seen_ids = set()
        
        # Пробуем PostgreSQL
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    # v2.10.53: Динамический пересчёт счётчиков
                    if status:
                        rows = await conn.fetch("""
                            SELECT d.*,
                                COALESCE((
                                    SELECT COUNT(*) FROM annotations a 
                                    JOIN training_images i ON a.image_id = i.id 
                                    WHERE i.dataset_id = d.id
                                ), 0) as calc_annotations_count,
                                COALESCE((
                                    SELECT COUNT(DISTINCT i.id) FROM training_images i 
                                    JOIN annotations a ON a.image_id = i.id 
                                    WHERE i.dataset_id = d.id
                                ), 0) as calc_labeled_count
                            FROM training_datasets d
                            WHERE d.status = $1 
                            ORDER BY d.created_at DESC
                        """, status)
                    else:
                        rows = await conn.fetch("""
                            SELECT d.*,
                                COALESCE((
                                    SELECT COUNT(*) FROM annotations a 
                                    JOIN training_images i ON a.image_id = i.id 
                                    WHERE i.dataset_id = d.id
                                ), 0) as calc_annotations_count,
                                COALESCE((
                                    SELECT COUNT(DISTINCT i.id) FROM training_images i 
                                    JOIN annotations a ON a.image_id = i.id 
                                    WHERE i.dataset_id = d.id
                                ), 0) as calc_labeled_count
                            FROM training_datasets d
                            ORDER BY d.created_at DESC
                        """)
                    for r in rows:
                        # Используем пересчитанные значения
                        row_dict = dict(r)
                        row_dict['annotations_count'] = r.get('calc_annotations_count', 0) or row_dict.get('annotations_count', 0)
                        row_dict['labeled_count'] = r.get('calc_labeled_count', 0) or row_dict.get('labeled_count', 0)
                        # РЕФАКТОРИНГ: Используем единую функцию normalize_dataset
                        normalized = normalize_dataset(row_dict, source_type="postgres")
                        datasets.append(normalized)
                        seen_ids.add(normalized["id"])
                    logger.info(f"Found {len(rows)} datasets in PostgreSQL")
            except Exception as e:
                logger.warning(f"PostgreSQL unavailable for list_datasets: {e}")
        
        # Также читаем из файловой системы (датасеты из каталога)
        try:
            from pathlib import Path
            import json
            
            # Читаем из /app/datasets/ (каталог Roboflow/Kaggle)
            catalog_path = Path("/app/datasets")
            logger.info(f"Checking catalog path: {catalog_path}, exists: {catalog_path.exists()}")
            
            if catalog_path.exists():
                for dataset_dir in catalog_path.iterdir():
                    if not dataset_dir.is_dir():
                        continue
                    if dataset_dir.name in ('custom', '__pycache__'):
                        continue
                    if dataset_dir.name in seen_ids:
                        continue
                    
                    logger.info(f"Checking dataset dir: {dataset_dir}")
                    
                    metadata_file = dataset_dir / "metadata.json"
                    if metadata_file.exists():
                        try:
                            metadata = json.loads(metadata_file.read_text())
                            # РЕФАКТОРИНГ: Добавляем path и используем normalize_dataset
                            metadata['path'] = str(dataset_dir)
                            if metadata.get('id') is None:
                                metadata['id'] = dataset_dir.name
                            # Преобразуем ready_for_training в status
                            if 'status' not in metadata and metadata.get('ready_for_training'):
                                metadata['status'] = 'ready'
                            elif 'status' not in metadata:
                                metadata['status'] = 'downloaded'
                            
                            normalized = normalize_dataset(metadata, source_type="catalog")
                            if status is None or normalized.get("status") == status:
                                datasets.append(normalized)
                                seen_ids.add(normalized["id"])
                        except Exception as e:
                            logger.warning(f"Failed to read metadata from {dataset_dir}: {e}")
                    else:
                        # Проверяем наличие data.yaml (готовый датасет YOLO)
                        data_yaml = dataset_dir / "data.yaml"
                        if data_yaml.exists():
                            try:
                                import yaml
                                with open(data_yaml) as f:
                                    config = yaml.safe_load(f) or {}
                                
                                # Считаем изображения и аннотации (v2.10.67)
                                images_count = 0
                                annotations_count = 0
                                labeled_count = 0
                                for split in ['train', 'valid', 'test']:
                                    img_dir = dataset_dir / split / 'images'
                                    lbl_dir = dataset_dir / split / 'labels'
                                    if img_dir.exists():
                                        images_count += len(list(img_dir.glob('*.[jJ][pP][gG]'))) + \
                                                       len(list(img_dir.glob('*.[pP][nN][gG]')))
                                    # v2.10.67: Считаем YOLO label файлы и аннотации
                                    if lbl_dir.exists():
                                        txt_files = list(lbl_dir.glob('*.txt'))
                                        labeled_count += len(txt_files)
                                        for txt_file in txt_files:
                                            try:
                                                with open(txt_file, 'r') as lf:
                                                    lines = [l for l in lf if l.strip() and not l.startswith('#')]
                                                    annotations_count += len(lines)
                                            except Exception:
                                                pass
                                
                                classes = list(config.get('names', {}).values()) if isinstance(config.get('names'), dict) else config.get('names', [])
                                
                                # РЕФАКТОРИНГ: Используем normalize_dataset
                                yaml_data = {
                                    "id": dataset_dir.name,
                                    "name": dataset_dir.name.replace('-', ' ').replace('_', ' ').title(),
                                    "description": "YOLO dataset from catalog",
                                    "status": "ready",
                                    "images_count": images_count,
                                    "annotations_count": annotations_count,
                                    "labeled_count": labeled_count,
                                    "classes": classes,
                                    "source": "catalog",
                                    "path": str(dataset_dir)
                                }
                                normalized = normalize_dataset(yaml_data, source_type="catalog")
                                if status is None or normalized.get("status") == status:
                                    datasets.append(normalized)
                                    seen_ids.add(normalized["id"])
                            except Exception as e:
                                logger.warning(f"Failed to read data.yaml from {dataset_dir}: {e}")
            
            # Читаем из /app/datasets/custom (пользовательские датасеты)
            custom_path = Path("/app/datasets/custom")
            if custom_path.exists():
                for dataset_dir in custom_path.iterdir():
                    if not dataset_dir.is_dir():
                        continue
                    if dataset_dir.name in seen_ids:
                        continue
                        
                    metadata_file = dataset_dir / "metadata.json"
                    if metadata_file.exists():
                        try:
                            metadata = json.loads(metadata_file.read_text())
                            metadata['path'] = str(dataset_dir)  # Добавляем путь
                            if metadata.get('id') is None:
                                metadata['id'] = dataset_dir.name
                            normalized = normalize_dataset(metadata, source_type="custom")
                            if status is None or normalized.get("status") == status:
                                datasets.append(normalized)
                                seen_ids.add(normalized["id"])
                        except Exception as e:
                            logger.warning(f"Failed to read metadata from {dataset_dir}: {e}")
            
            # Добавляем скриншоты как специальный датасет
            screenshots_path = Path("/app/training_data/screenshots")
            logger.info(f"Checking screenshots path: {screenshots_path}, exists: {screenshots_path.exists()}")
            
            if screenshots_path.exists() and "screenshots" not in seen_ids:
                screenshot_files = list(screenshots_path.glob('*.jpg')) + list(screenshots_path.glob('*.png'))
                logger.info(f"Found {len(screenshot_files)} screenshot files")
                
                if screenshot_files:
                    # Используем normalize_dataset для консистентности
                    screenshots_data = normalize_dataset({
                        "id": "screenshots",
                        "name": "📷 Скриншоты с камер",
                        "description": "Снимки с камер для разметки и обучения",
                        "status": "ready",
                        "images_count": len(screenshot_files),
                        "annotations_count": 0,
                        "labeled_count": 0,
                        "created_by": None,
                        "created_at": None,
                        "classes": [],
                        "source": "screenshots",
                        "path": str(screenshots_path)
                    }, source_type="screenshots")
                    datasets.append(screenshots_data)
                    seen_ids.add("screenshots")
            
            # Сортируем по дате создания (новые первые)
            # Безопасная сортировка: датасеты с датой первыми, потом без даты
            def sort_key(x):
                created_at = x.get("created_at")
                if created_at is None:
                    return (1, "")  # Без даты - в конец
                if isinstance(created_at, datetime):
                    return (0, created_at.isoformat())
                if isinstance(created_at, str) and created_at:
                    return (0, created_at)
                return (1, "")
            
            datasets.sort(key=sort_key, reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list datasets from files: {e}", exc_info=True)
        
        logger.info(f"Returning {len(datasets)} datasets total (from DB + filesystem)")
        return datasets
    
    @router.post("/datasets", response_model=DatasetResponse)
    async def create_dataset(data: DatasetCreate):
        """Create new dataset - с fallback на файловую систему если БД недоступна."""
        dataset_id = str(uuid.uuid4())
        now = datetime.now()
        
        # Пробуем PostgreSQL
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO training_datasets (id, name, description, created_by)
                           VALUES ($1, $2, $3, $4)""",
                        dataset_id, data.name, data.description, 'admin'
                    )
                    row = await conn.fetchrow(
                        "SELECT * FROM training_datasets WHERE id = $1", dataset_id
                    )
                    # РЕФАКТОРИНГ: Используем normalize_dataset
                    return normalize_dataset(dict(row), source_type="postgres")
            except Exception as e:
                logger.warning(f"PostgreSQL unavailable, using file fallback: {e}")
        
        # Fallback: сохраняем в файл
        try:
            # Создаём директорию датасета
            dataset_path = Path("/app/datasets/custom") / dataset_id
            dataset_path.mkdir(parents=True, exist_ok=True)
            
            # Создаём метаданные
            metadata = {
                "id": dataset_id,
                "name": data.name,
                "description": data.description or None,
                "status": "created",
                "images_count": 0,
                "created_by": "admin",
                "created_at": now.isoformat(),
                "source": "user",
                "path": str(dataset_path)
            }
            
            # Сохраняем в файл
            (dataset_path / "metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2, default=str)
            )
            
            logger.info(f"Dataset {dataset_id} created via file fallback")
            
            # РЕФАКТОРИНГ: Используем normalize_dataset для ответа
            return normalize_dataset(metadata, source_type="user")
            
        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Не удалось создать датасет. Ошибка: {str(e)}"
            )
    
    @router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
    async def get_dataset(dataset_id: str):
        """Get dataset by ID."""
        # Сначала проверяем в PostgreSQL
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM training_datasets WHERE id = $1", dataset_id
                    )
                    if row:
                        # РЕФАКТОРИНГ: Используем normalize_dataset
                        return normalize_dataset(dict(row), source_type="postgres")
            except Exception as e:
                logger.warning(f"PostgreSQL unavailable for get_dataset: {e}")
        
        # Fallback: ищем в файловой системе
        # Проверяем каталог датасетов
        for base_path in [Path("/app/datasets"), Path("/app/datasets/custom")]:
            dataset_path = base_path / dataset_id
            if dataset_path.exists():
                metadata_file = dataset_path / "metadata.json"
                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text())
                    metadata['path'] = str(dataset_path)
                    if metadata.get('id') is None:
                        metadata['id'] = dataset_id
                    # РЕФАКТОРИНГ: Используем normalize_dataset
                    return normalize_dataset(metadata, source_type="catalog")
        
        # Специальный случай: screenshots
        if dataset_id == "screenshots":
            screenshots_path = Path("/app/training_data/screenshots")
            if screenshots_path.exists():
                screenshot_files = list(screenshots_path.glob('*.jpg')) + list(screenshots_path.glob('*.png'))
                # РЕФАКТОРИНГ: Используем normalize_dataset
                return normalize_dataset({
                    "id": "screenshots",
                    "name": "📷 Скриншоты с камер",
                    "description": "Снимки с камер для разметки и обучения",
                    "status": "ready",
                    "images_count": len(screenshot_files),
                    "source": "screenshots",
                    "path": str(screenshots_path)
                }, source_type="screenshots")
        
        raise HTTPException(404, "Dataset not found")
    
    @router.delete("/datasets/{dataset_id}")
    async def delete_dataset(dataset_id: str):
        """Delete dataset - с fallback на файловую систему."""
        deleted = False
        
        # Пробуем PostgreSQL
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    result = await conn.execute(
                        "DELETE FROM training_datasets WHERE id = $1", dataset_id
                    )
                    if result != "DELETE 0":
                        deleted = True
            except Exception as e:
                logger.warning(f"PostgreSQL unavailable for delete_dataset: {e}")
        
        # Также удаляем из файловой системы
        from pathlib import Path
        import shutil
        
        for base_path in [Path("/app/datasets"), Path("/app/datasets/custom")]:
            dataset_path = base_path / dataset_id
            if dataset_path.exists() and dataset_path.is_dir():
                try:
                    shutil.rmtree(dataset_path)
                    deleted = True
                    logger.info(f"Deleted dataset directory: {dataset_path}")
                except Exception as e:
                    logger.error(f"Failed to delete dataset directory: {e}")
        
        if not deleted:
            raise HTTPException(404, "Dataset not found")
        
        return {"status": "deleted"}
    
    # ========================================================================
    # Images
    # ========================================================================
    
    @router.post("/datasets/{dataset_id}/images")
    async def upload_images(
        dataset_id: str,
        files: List[UploadFile] = File(...)
    ):
        """Upload images to dataset."""
        # Verify dataset
        async with db_pool.acquire() as conn:
            dataset = await conn.fetchrow(
                "SELECT id FROM training_datasets WHERE id = $1", dataset_id
            )
            if not dataset:
                raise HTTPException(404, "Dataset not found")
        
        if len(files) > SecureImageUpload.MAX_FILES_PER_REQUEST:
            raise HTTPException(400, f"Max {SecureImageUpload.MAX_FILES_PER_REQUEST} files")
        
        uploaded = []
        errors = []
        
        async with db_pool.acquire() as conn:
            for file in files:
                try:
                    # Validate
                    info = SecureImageUpload.validate(file)
                    
                    # Check duplicate
                    existing = await conn.fetchrow(
                        """SELECT id FROM training_images 
                           WHERE dataset_id = $1 AND checksum = $2""",
                        dataset_id, info['hash']
                    )
                    if existing:
                        errors.append({'filename': file.filename, 'error': 'Duplicate'})
                        continue
                    
                    # Save file
                    storage_path = await SecureImageUpload.save(
                        info['content'], file.filename, dataset_id
                    )
                    
                    # Insert to DB
                    image_id = str(uuid.uuid4())
                    unique_filename = f"{image_id}{Path(file.filename).suffix.lower()}"
                    
                    await conn.execute(
                        """INSERT INTO training_images 
                           (id, dataset_id, filename, original_filename, file_size,
                            width, height, mime_type, storage_path, checksum, uploaded_by)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
                        image_id, dataset_id, unique_filename, file.filename,
                        info['size'], info['width'], info['height'],
                        info['mime_type'], storage_path, info['hash'], 'admin'
                    )
                    
                    uploaded.append({
                        'id': image_id,
                        'filename': file.filename,
                        'width': info['width'],
                        'height': info['height']
                    })
                    
                except ValueError as e:
                    errors.append({'filename': file.filename, 'error': str(e)})
                except Exception as e:
                    logger.error(f"Upload error: {e}")
                    errors.append({'filename': file.filename, 'error': 'Internal error'})
        
        return {
            'uploaded': uploaded,
            'errors': errors,
            'total_uploaded': len(uploaded),
            'total_errors': len(errors)
        }
    
    @router.get("/datasets/{dataset_id}/images")
    async def list_images(
        dataset_id: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
        status: Optional[str] = None
    ):
        """List images in dataset with annotations."""
        offset = (page - 1) * page_size
        
        # Проверяем, является ли dataset_id валидным UUID
        def is_valid_uuid(val: str) -> bool:
            try:
                import uuid
                uuid.UUID(val)
                return True
            except (ValueError, AttributeError):
                return False
        
        is_uuid_dataset = is_valid_uuid(dataset_id)
        
        # Для UUID датасетов пробуем из БД
        if db_pool and is_uuid_dataset:
            try:
                async with db_pool.acquire() as conn:
                    # Count
                    if status:
                        total = await conn.fetchval(
                            """SELECT COUNT(*) FROM training_images 
                               WHERE dataset_id = $1 AND status = $2""",
                            dataset_id, status
                        )
                        rows = await conn.fetch(
                            """SELECT i.*, COUNT(a.id) as annotations_count
                               FROM training_images i
                               LEFT JOIN annotations a ON i.id = a.image_id
                               WHERE i.dataset_id = $1 AND i.status = $2
                               GROUP BY i.id
                               ORDER BY i.uploaded_at DESC
                               LIMIT $3 OFFSET $4""",
                            dataset_id, status, page_size, offset
                        )
                    else:
                        total = await conn.fetchval(
                            "SELECT COUNT(*) FROM training_images WHERE dataset_id = $1",
                            dataset_id
                        )
                        rows = await conn.fetch(
                            """SELECT i.*, COUNT(a.id) as annotations_count
                               FROM training_images i
                               LEFT JOIN annotations a ON i.id = a.image_id
                               WHERE i.dataset_id = $1
                               GROUP BY i.id
                               ORDER BY i.uploaded_at DESC
                               LIMIT $2 OFFSET $3""",
                            dataset_id, page_size, offset
                        )
                    
                    # Если нашли данные в БД, используем их
                    if total > 0:
                        # Get image IDs for annotations fetch
                        image_ids = [str(r['id']) for r in rows]
                        
                        # Fetch all annotations for these images in one query
                        annotations_map = {}
                        if image_ids:
                            ann_rows = await conn.fetch(
                                """SELECT * FROM annotations WHERE image_id = ANY($1::uuid[])""",
                                image_ids
                            )
                            for ar in ann_rows:
                                img_id = str(ar['image_id'])
                                if img_id not in annotations_map:
                                    annotations_map[img_id] = []
                                annotations_map[img_id].append(AnnotationResponse(
                                    id=str(ar['id']),
                                    class_name=ar['class_name'],
                                    bbox=[ar['bbox_x1'], ar['bbox_y1'], ar['bbox_x2'], ar['bbox_y2']],
                                    confidence=ar['confidence'],
                                    created_by=ar['created_by'],
                                    created_at=ar['created_at'],
                                    verified=ar['verified']
                                ))
                        
                        items = []
                        for r in rows:
                            img_id = str(r['id'])
                            items.append(ImageResponse(
                                id=img_id,
                                filename=r['filename'],
                                original_filename=r['original_filename'],
                                url=f"/api/training/images/{img_id}",  # URL для загрузки
                                width=r['width'],
                                height=r['height'],
                                file_size=r['file_size'],
                                status=r['status'],
                                uploaded_at=r['uploaded_at'],
                                annotations_count=r['annotations_count'],
                                annotations=annotations_map.get(img_id, [])
                            ))
                        
                        # Считаем глобальное количество аннотированных изображений
                        total_annotated = await conn.fetchval(
                            """SELECT COUNT(DISTINCT i.id) FROM training_images i
                               JOIN annotations a ON i.id = a.image_id
                               WHERE i.dataset_id = $1""",
                            dataset_id
                        ) or 0
                        
                        return {
                            'items': items,
                            'total': total,
                            'total_annotated': total_annotated,
                            'page': page,
                            'page_size': page_size
                        }
            except Exception as e:
                logger.warning(f"DB query failed for list_images: {e}")
        
        # Fallback: читаем из файловой системы (или для catalog датасетов с строковым ID)
        from pathlib import Path
        import hashlib
        
        items = []
        all_images = []
        
        # Определяем путь к датасету
        if dataset_id == "screenshots":
            dataset_path = Path("/app/training_data/screenshots")
        else:
            dataset_path = Path(f"/app/datasets/{dataset_id}")
            
            # Ищем изображения в train/images, valid/images
            if not dataset_path.exists():
                return {'items': [], 'total': 0, 'page': page, 'page_size': page_size}
        
        if dataset_path.exists():
            # Собираем все изображения
            if dataset_id == "screenshots":
                image_dirs = [dataset_path]
            else:
                image_dirs = [
                    dataset_path / "train" / "images",
                    dataset_path / "valid" / "images",
                    dataset_path / "test" / "images",
                    dataset_path / "images",  # Плоская структура
                ]
            
            for img_dir in image_dirs:
                if img_dir.exists():
                    for img_file in img_dir.iterdir():
                        if img_file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp'):
                            all_images.append(img_file)
            
            # Сортируем по времени изменения (новые первые)
            all_images.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            total = len(all_images)
            
            # Пагинация
            page_images = all_images[offset:offset + page_size]
            
            # Собираем все image_id для batch-запроса аннотаций из БД
            image_id_map = {}  # img_id -> img_file
            for img_file in page_images:
                md5_hash = hashlib.md5(str(img_file).encode()).hexdigest()
                img_id = f"{md5_hash[:8]}-{md5_hash[8:12]}-{md5_hash[12:16]}-{md5_hash[16:20]}-{md5_hash[20:32]}"
                image_id_map[img_id] = img_file
            
            # Batch-запрос аннотаций из БД (v2.10.49 fix)
            annotations_map = {}
            annotations_count_map = {}
            if image_id_map:
                try:
                    async with db_pool.acquire() as conn:
                        image_ids = list(image_id_map.keys())
                        # Получаем все аннотации для этих изображений одним запросом
                        ann_rows = await conn.fetch(
                            """SELECT * FROM annotations WHERE image_id = ANY($1::uuid[])""",
                            image_ids
                        )
                        for ar in ann_rows:
                            img_id = str(ar['image_id'])
                            if img_id not in annotations_map:
                                annotations_map[img_id] = []
                            annotations_map[img_id].append(AnnotationResponse(
                                id=str(ar['id']),
                                class_name=ar['class_name'],
                                bbox=[ar['bbox_x1'], ar['bbox_y1'], ar['bbox_x2'], ar['bbox_y2']],
                                confidence=ar['confidence'],
                                created_by=ar['created_by'],
                                created_at=ar['created_at'],
                                verified=ar['verified']
                            ))
                        # Подсчёт аннотаций
                        for img_id in image_ids:
                            annotations_count_map[img_id] = len(annotations_map.get(img_id, []))
                except Exception as e:
                    logger.warning(f"Failed to fetch annotations for filesystem images: {e}")
            
            # v2.10.67: Парсим YOLO .txt label файлы для изображений без DB-аннотаций
            yolo_class_names = {}
            if dataset_id != "screenshots":
                try:
                    import yaml as _yaml
                    data_yaml_path = dataset_path / "data.yaml"
                    if data_yaml_path.exists():
                        with open(data_yaml_path) as _f:
                            _cfg = _yaml.safe_load(_f) or {}
                        names = _cfg.get('names', {})
                        if isinstance(names, dict):
                            yolo_class_names = {int(k): v for k, v in names.items()}
                        elif isinstance(names, list):
                            yolo_class_names = {i: n for i, n in enumerate(names)}
                except Exception as e:
                    logger.warning(f"Could not read data.yaml class names: {e}")
            
            for img_id, img_file in image_id_map.items():
                # Если уже есть аннотации из БД — пропускаем YOLO файл
                if annotations_count_map.get(img_id, 0) > 0:
                    continue
                
                # Ищем .txt файл в sibling labels/ директории
                labels_dir = img_file.parent.parent / 'labels'
                txt_name = img_file.stem + '.txt'
                txt_path = labels_dir / txt_name
                
                if not txt_path.exists():
                    continue
                
                try:
                    yolo_annotations = []
                    with open(txt_path, 'r') as lf:
                        for line_idx, line in enumerate(lf):
                            line = line.strip()
                            if not line or line.startswith('#'):
                                continue
                            parts = line.split()
                            if len(parts) < 5:
                                continue
                            
                            class_id = int(parts[0])
                            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                            
                            # YOLO format (cx, cy, w, h) → normalized (x1, y1, x2, y2)
                            x1 = max(0.0, cx - w / 2)
                            y1 = max(0.0, cy - h / 2)
                            x2 = min(1.0, cx + w / 2)
                            y2 = min(1.0, cy + h / 2)
                            
                            class_name = yolo_class_names.get(class_id, f"class_{class_id}")
                            
                            yolo_annotations.append(AnnotationResponse(
                                id=f"yolo-{img_id[:8]}-{line_idx}",
                                class_name=class_name,
                                bbox=[round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6)],
                                confidence=1.0,
                                created_by="dataset",
                                created_at=datetime.fromtimestamp(txt_path.stat().st_mtime),
                                verified=True
                            ))
                    
                    if yolo_annotations:
                        annotations_map[img_id] = yolo_annotations
                        annotations_count_map[img_id] = len(yolo_annotations)
                except Exception as e:
                    logger.warning(f"Failed to parse YOLO labels {txt_path}: {e}")
            
            # Формируем ответ с реальными аннотациями
            for img_id, img_file in image_id_map.items():
                # Получаем размеры изображения
                width, height = 0, 0
                try:
                    from PIL import Image
                    with Image.open(img_file) as img:
                        width, height = img.size
                except Exception:
                    pass
                
                items.append(ImageResponse(
                    id=img_id,
                    filename=img_file.name,
                    original_filename=img_file.name,
                    url=f"/api/training/datasets/{dataset_id}/file/{img_file.name}",
                    width=width,
                    height=height,
                    file_size=img_file.stat().st_size,
                    status="annotated" if annotations_count_map.get(img_id, 0) > 0 else "pending",
                    uploaded_at=datetime.fromtimestamp(img_file.stat().st_mtime),
                    annotations_count=annotations_count_map.get(img_id, 0),
                    annotations=annotations_map.get(img_id, [])
                ))
        
        # Подсчёт глобального количества аннотированных изображений для файлового датасета
        total_annotated = 0
        if all_images:
            # v2.10.67: Считаем и DB-аннотации и YOLO label файлы
            db_annotated = 0
            try:
                async with db_pool.acquire() as conn:
                    all_image_ids = []
                    for img_file in all_images:
                        md5_hash = hashlib.md5(str(img_file).encode()).hexdigest()
                        img_id = f"{md5_hash[:8]}-{md5_hash[8:12]}-{md5_hash[12:16]}-{md5_hash[16:20]}-{md5_hash[20:32]}"
                        all_image_ids.append(img_id)
                    
                    db_annotated = await conn.fetchval(
                        """SELECT COUNT(DISTINCT image_id) FROM annotations 
                           WHERE image_id = ANY($1::uuid[])""",
                        all_image_ids
                    ) or 0
            except Exception as e:
                logger.warning(f"Failed to count DB annotated images: {e}")
            
            # Считаем YOLO label файлы (быстрый подсчёт по labels/ директориям)
            yolo_labeled = 0
            if dataset_id != "screenshots":
                labeled_dirs = set()
                for img_file in all_images:
                    labels_dir = img_file.parent.parent / 'labels'
                    if labels_dir not in labeled_dirs:
                        labeled_dirs.add(labels_dir)
                
                for labels_dir in labeled_dirs:
                    if labels_dir.exists():
                        yolo_labeled += len(list(labels_dir.glob('*.txt')))
            
            total_annotated = max(db_annotated, yolo_labeled)
        
        return {
            'items': items,
            'total': len(all_images) if all_images else 0,
            'total_annotated': total_annotated,
            'page': page,
            'page_size': page_size
        }
    
    @router.get("/images/{image_id}")
    async def get_image(image_id: str):
        """Get image file."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT storage_path, mime_type FROM training_images WHERE id = $1",
                image_id
            )
            if not row:
                raise HTTPException(404, "Image not found")
        
        path = row['storage_path']
        if not os.path.exists(path):
            raise HTTPException(404, "File not found")
        
        return FileResponse(path, media_type=row['mime_type'])
    
    @router.get("/datasets/{dataset_id}/file/{filename}")
    async def get_dataset_file(dataset_id: str, filename: str):
        """Get image file from filesystem dataset (catalog/screenshots)."""
        from pathlib import Path
        import mimetypes
        
        # Защита от path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(400, "Invalid filename")
        
        # Определяем путь к датасету
        if dataset_id == "screenshots":
            dataset_path = Path("/app/training_data/screenshots")
        else:
            dataset_path = Path(f"/app/datasets/{dataset_id}")
        
        # Ищем файл в разных местах
        possible_paths = [
            dataset_path / filename,
            dataset_path / "train" / "images" / filename,
            dataset_path / "valid" / "images" / filename,
            dataset_path / "test" / "images" / filename,
            dataset_path / "images" / filename,
        ]
        
        for file_path in possible_paths:
            if file_path.exists() and file_path.is_file():
                mime_type = mimetypes.guess_type(str(file_path))[0] or "image/jpeg"
                return FileResponse(str(file_path), media_type=mime_type)
        
        raise HTTPException(404, f"File not found: {filename}")
    
    @router.delete("/images/{image_id}")
    async def delete_image(image_id: str):
        """Delete image."""
        storage_path = None
        deleted_from_db = False
        
        # Try to delete from database first
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT storage_path FROM training_images WHERE id = $1", image_id
                )
                if row:
                    storage_path = row['storage_path']
                    await conn.execute("DELETE FROM training_images WHERE id = $1", image_id)
                    deleted_from_db = True
        except Exception as e:
            logger.warning(f"DB delete failed (may be fallback mode): {e}")
        
        # If not in DB, try to find in filesystem (fallback for screenshots/imported)
        if not deleted_from_db:
            # Try screenshots folder
            screenshots_path = Path("/app/violations")
            for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                for f in screenshots_path.rglob(f"*{ext}"):
                    # Match by hash ID
                    file_hash = hashlib.md5(str(f).encode()).hexdigest()[:32]
                    if image_id == file_hash or image_id == file_hash[:16]:
                        storage_path = str(f)
                        break
                if storage_path:
                    break
            
            # Try datasets folder
            if not storage_path:
                datasets_path = Path("/app/datasets")
                for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    for f in datasets_path.rglob(f"*{ext}"):
                        file_hash = hashlib.md5(str(f).encode()).hexdigest()[:32]
                        if image_id == file_hash or image_id == file_hash[:16]:
                            storage_path = str(f)
                            break
                    if storage_path:
                        break
        
        if not storage_path:
            raise HTTPException(404, "Image not found")
        
        # Delete file
        try:
            if os.path.exists(storage_path):
                os.remove(storage_path)
                logger.info(f"Deleted image file: {storage_path}")
        except Exception as e:
            logger.error(f"Delete file error: {e}")
        
        # Clean up Redis annotations (non-critical)
        try:
            import aioredis
            redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
            redis = await aioredis.from_url(redis_url)
            cleaned_keys = []
            for prefix in ["annotations:", "auto_annotations:", "annotation_history:"]:
                for id_variant in [image_id, image_id[:16] if len(image_id) > 16 else image_id]:
                    key = f"{prefix}{id_variant}"
                    deleted_count = await redis.delete(key)
                    if deleted_count > 0:
                        cleaned_keys.append(key)
            # Also clean catalog annotations
            for id_variant in [image_id, image_id[:16] if len(image_id) > 16 else image_id]:
                cat_key = f"catalog_annotations:{id_variant}"
                deleted_count = await redis.delete(cat_key)
                if deleted_count > 0:
                    cleaned_keys.append(cat_key)
            await redis.close()
            if cleaned_keys:
                logger.info(f"Cleaned Redis keys for {image_id}: {cleaned_keys}")
        except Exception as e:
            logger.warning(f"Redis cleanup failed (non-critical): {e}")
        
        return {"status": "deleted", "source": "db" if deleted_from_db else "filesystem"}
    
    # ========================================================================
    # Annotations
    # ========================================================================
    
    @router.get("/images/{image_id}/annotations", response_model=List[AnnotationResponse])
    async def list_annotations(image_id: str):
        """Get annotations for image."""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM annotations WHERE image_id = $1 ORDER BY created_at""",
                image_id
            )
            return [
                AnnotationResponse(
                    id=str(r['id']),
                    class_name=r['class_name'],
                    bbox=[r['bbox_x1'], r['bbox_y1'], r['bbox_x2'], r['bbox_y2']],
                    confidence=r['confidence'],
                    created_by=r['created_by'],
                    created_at=r['created_at'],
                    verified=r['verified']
                )
                for r in rows
            ]
    
    @router.post("/images/{image_id}/annotations", response_model=AnnotationResponse)
    async def create_annotation(image_id: str, data: AnnotationCreate):
        """Create annotation for image (supports both DB images and catalog file-based images)."""
        annotation_id = str(uuid.uuid4())
        
        # Helper to convert MD5 hash to UUID format
        def md5_to_uuid(md5_hash: str) -> str:
            """Convert 32-char MD5 hash to UUID format (with dashes)."""
            if len(md5_hash) == 32 and all(c in '0123456789abcdef' for c in md5_hash.lower()):
                return f"{md5_hash[:8]}-{md5_hash[8:12]}-{md5_hash[12:16]}-{md5_hash[16:20]}-{md5_hash[20:]}"
            return md5_hash
        
        # Check if image_id is UUID or MD5 hash
        def is_valid_uuid(val: str) -> bool:
            try:
                uuid.UUID(val)
                return True
            except (ValueError, AttributeError):
                return False
        
        # Normalize image_id: convert MD5 hash to UUID format if needed
        normalized_image_id = image_id
        if not is_valid_uuid(image_id) and len(image_id) == 32:
            normalized_image_id = md5_to_uuid(image_id)
        
        async with db_pool.acquire() as conn:
            # Verify image exists in DB
            img = await conn.fetchrow(
                "SELECT id, dataset_id FROM training_images WHERE id = $1", normalized_image_id
            )
            
            dataset_id = img['dataset_id'] if img else None
            
            # If image not found - it might be from catalog (file-based)
            # Create a placeholder record for it
            if not img:
                try:
                    # Create placeholder image record for catalog-based images
                    await conn.execute(
                        """INSERT INTO training_images 
                           (id, dataset_id, filename, original_filename, storage_path, 
                            width, height, file_size, status, mime_type)
                           VALUES ($1, NULL, $2, $2, $3, 0, 0, 0, 'catalog', 'image/jpeg')
                           ON CONFLICT (id) DO NOTHING""",
                        normalized_image_id, 
                        f"catalog_image_{image_id[:8]}",
                        f"/catalog/{image_id}"
                    )
                    logger.info(f"Created placeholder for catalog image: {normalized_image_id}")
                except Exception as e:
                    logger.warning(f"Could not create placeholder image: {e}")
                    # Continue anyway - the annotation might still work
            
            # Insert annotation
            try:
                await conn.execute(
                    """INSERT INTO annotations 
                       (id, image_id, class_name, bbox_x1, bbox_y1, bbox_x2, bbox_y2, created_by)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    annotation_id, normalized_image_id, data.class_name,
                    data.bbox_x1, data.bbox_y1, data.bbox_x2, data.bbox_y2, 'admin'
                )
            except Exception as e:
                logger.error(f"Failed to create annotation: {e}")
                raise HTTPException(500, f"Failed to create annotation: {str(e)}")
            
            # v2.10.51: Обновляем счётчики датасета
            if dataset_id:
                try:
                    await conn.execute("""
                        UPDATE training_datasets 
                        SET annotations_count = (
                            SELECT COUNT(*) FROM annotations a 
                            JOIN training_images i ON a.image_id = i.id 
                            WHERE i.dataset_id = $1
                        ),
                        labeled_count = (
                            SELECT COUNT(DISTINCT i.id) FROM training_images i 
                            JOIN annotations a ON a.image_id = i.id 
                            WHERE i.dataset_id = $1
                        ),
                        updated_at = NOW()
                        WHERE id = $1
                    """, dataset_id)
                    logger.debug(f"Updated dataset {dataset_id} counters after annotation create")
                except Exception as e:
                    logger.warning(f"Failed to update dataset counters: {e}")
            
            row = await conn.fetchrow(
                "SELECT * FROM annotations WHERE id = $1", annotation_id
            )
            
            if not row:
                raise HTTPException(500, "Annotation created but could not be retrieved")
            
            return AnnotationResponse(
                id=str(row['id']),
                class_name=row['class_name'],
                bbox=[row['bbox_x1'], row['bbox_y1'], row['bbox_x2'], row['bbox_y2']],
                confidence=row['confidence'],
                created_by=row['created_by'],
                created_at=row['created_at'],
                verified=row['verified']
            )
    
    @router.post("/images/{image_id}/auto-annotate")
    async def auto_annotate_image(image_id: str, threshold: float = Query(0.3, ge=0.05, le=0.95)):
        """
        T04: Auto-annotate image via Celery worker (CPU-only).
        Dispatches task to Celery queue, returns task_id for polling.
        """
        from celery import Celery as CeleryApp
        import json
        
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        celery_app = CeleryApp('training_worker', broker=redis_url, backend=redis_url)
        
        # Verify image exists before dispatching
        image_found = False
        # Check DB
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT id FROM training_images WHERE id = $1", image_id
                    )
                    if row:
                        image_found = True
            except Exception:
                pass
        
        # Check filesystem if not in DB
        if not image_found:
            import hashlib
            for search_dir in ["/app/datasets", "/app/violations"]:
                if os.path.isdir(search_dir):
                    for root, dirs, files in os.walk(search_dir):
                        for f in files:
                            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                                fpath = os.path.join(root, f)
                                fhash = hashlib.md5(fpath.encode()).hexdigest()
                                if image_id in (fhash, fhash[:16]):
                                    image_found = True
                                    break
                        if image_found:
                            break
                if image_found:
                    break
        
        if not image_found:
            raise HTTPException(404, "Image not found")
        
        # Dispatch to Celery worker (CPU-only, T06 GPU guard)
        task = celery_app.send_task(
            "training.auto_annotate",
            args=[image_id, threshold]
        )
        
        logger.info(f"Auto-annotate dispatched: task_id={task.id}, image={image_id}")
        
        return {
            "task_id": task.id,
            "status": "queued",
            "image_id": image_id,
            "threshold": threshold
        }
    
    @router.delete("/annotations/{annotation_id}")
    async def delete_annotation(annotation_id: str):
        """Delete annotation."""
        async with db_pool.acquire() as conn:
            # v2.10.51: Получаем dataset_id перед удалением
            ann_row = await conn.fetchrow("""
                SELECT a.id, i.dataset_id 
                FROM annotations a 
                JOIN training_images i ON a.image_id = i.id 
                WHERE a.id = $1
            """, annotation_id)
            
            dataset_id = ann_row['dataset_id'] if ann_row else None
            
            result = await conn.execute(
                "DELETE FROM annotations WHERE id = $1", annotation_id
            )
            if result == "DELETE 0":
                raise HTTPException(404, "Annotation not found")
            
            # v2.10.51: Обновляем счётчики датасета
            if dataset_id:
                try:
                    await conn.execute("""
                        UPDATE training_datasets 
                        SET annotations_count = (
                            SELECT COUNT(*) FROM annotations a 
                            JOIN training_images i ON a.image_id = i.id 
                            WHERE i.dataset_id = $1
                        ),
                        labeled_count = (
                            SELECT COUNT(DISTINCT i.id) FROM training_images i 
                            JOIN annotations a ON a.image_id = i.id 
                            WHERE i.dataset_id = $1
                        ),
                        updated_at = NOW()
                        WHERE id = $1
                    """, dataset_id)
                    logger.debug(f"Updated dataset {dataset_id} counters after annotation delete")
                except Exception as e:
                    logger.warning(f"Failed to update dataset counters: {e}")
            
            return {"status": "deleted"}
    
    @router.put("/annotations/{annotation_id}", response_model=AnnotationResponse)
    async def update_annotation(annotation_id: str, data: AnnotationUpdate):
        """Update annotation class or bbox."""
        async with db_pool.acquire() as conn:
            # Check if annotation exists
            existing = await conn.fetchrow(
                "SELECT * FROM annotations WHERE id = $1", annotation_id
            )
            
            if not existing:
                raise HTTPException(404, "Annotation not found")
            
            # Update annotation - use existing values for None fields
            new_class = data.class_name if data.class_name is not None else existing['class_name']
            new_x1 = data.bbox_x1 if data.bbox_x1 is not None else existing['bbox_x1']
            new_y1 = data.bbox_y1 if data.bbox_y1 is not None else existing['bbox_y1']
            new_x2 = data.bbox_x2 if data.bbox_x2 is not None else existing['bbox_x2']
            new_y2 = data.bbox_y2 if data.bbox_y2 is not None else existing['bbox_y2']
            
            await conn.execute("""
                UPDATE annotations 
                SET class_name = $2, 
                    bbox_x1 = $3, bbox_y1 = $4, 
                    bbox_x2 = $5, bbox_y2 = $6
                WHERE id = $1
            """, annotation_id, new_class, new_x1, new_y1, new_x2, new_y2)
            
            # Fetch updated annotation
            row = await conn.fetchrow(
                "SELECT * FROM annotations WHERE id = $1", annotation_id
            )
            
            logger.info(f"Updated annotation {annotation_id} to class {new_class}")
            
            return AnnotationResponse(
                id=str(row['id']),
                class_name=row['class_name'],
                bbox=[row['bbox_x1'], row['bbox_y1'], row['bbox_x2'], row['bbox_y2']],
                confidence=row['confidence'],
                created_by=row['created_by'],
                created_at=row['created_at'],
                verified=row['verified']
            )
    
    # ========================================================================
    # Auto-Annotation using existing model
    # ========================================================================
    
    @router.post("/datasets/{dataset_id}/auto-annotate")
    async def auto_annotate_dataset(
        dataset_id: str,
        threshold: float = Query(0.3, ge=0.05, le=0.95),
        skip_annotated: bool = Query(True)
    ):
        """
        T05: Batch auto-annotate all images in dataset via Celery (CPU-only).
        Returns task_id for progress polling.
        """
        from celery import Celery as CeleryApp
        
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        celery_app = CeleryApp('training_worker', broker=redis_url, backend=redis_url)
        
        task = celery_app.send_task(
            "training.batch_auto_annotate",
            args=[dataset_id, threshold, skip_annotated]
        )
        
        logger.info(f"Batch auto-annotate dispatched: task_id={task.id}, dataset={dataset_id}")
        
        return {
            "task_id": task.id,
            "status": "queued",
            "dataset_id": dataset_id,
            "threshold": threshold,
            "skip_annotated": skip_annotated
        }
    
    @router.get("/auto-annotate/status/{task_id}")
    async def get_auto_annotate_status(task_id: str):
        """Poll auto-annotate task status (single or batch)."""
        from celery import Celery as CeleryApp
        
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        celery_app = CeleryApp('training_worker', broker=redis_url, backend=redis_url)
        
        result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": result.status,
        }
        
        if result.status == 'PROGRESS':
            response["progress"] = result.info
        elif result.status == 'SUCCESS':
            response["result"] = result.result
        elif result.status == 'FAILURE':
            response["error"] = str(result.result)
        
        return response
    
    @router.get("/auto-annotate/results/{image_id}")
    async def get_auto_annotate_results(image_id: str):
        """Get auto-annotation results from Redis for a specific image."""
        import aioredis
        import json
        
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        r = await aioredis.from_url(redis_url)
        
        try:
            data = await r.get(f"auto_annotations:{image_id}")
            if data:
                annotations = json.loads(data)
                return {
                    "image_id": image_id,
                    "annotations": annotations,
                    "count": len(annotations),
                    "source": "auto"
                }
            
            return {"image_id": image_id, "annotations": [], "count": 0}
        finally:
            await r.close()
    
    @router.get("/datasets/{dataset_id}/auto-annotate/progress")
    async def get_batch_progress(dataset_id: str):
        """Poll batch auto-annotate progress for a dataset."""
        import aioredis
        import json
        
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        r = await aioredis.from_url(redis_url)
        
        try:
            data = await r.get(f"autoannotate:status:{dataset_id}")
            if data:
                return json.loads(data)
            return {"status": "not_found", "dataset_id": dataset_id}
        finally:
            await r.close()
    
    # ========================================================================
    # History / Undo
    # ========================================================================
    
    @router.get("/images/{image_id}/history", response_model=List[HistoryEntry])
    async def get_history(image_id: str, limit: int = Query(50, ge=1, le=200)):
        """Get annotation history for undo."""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, action, annotation_id, created_at
                   FROM annotation_history
                   WHERE image_id = $1
                   ORDER BY created_at DESC
                   LIMIT $2""",
                image_id, limit
            )
            return [
                HistoryEntry(
                    id=str(r['id']),
                    action=r['action'],
                    annotation_id=str(r['annotation_id']) if r['annotation_id'] else None,
                    created_at=r['created_at']
                )
                for r in rows
            ]
    
    @router.post("/images/{image_id}/undo")
    async def undo_annotation(image_id: str):
        """Undo last annotation action."""
        async with db_pool.acquire() as conn:
            # Get last history
            entry = await conn.fetchrow(
                """SELECT * FROM annotation_history
                   WHERE image_id = $1
                   ORDER BY created_at DESC
                   LIMIT 1""",
                image_id
            )
            if not entry:
                raise HTTPException(404, "No history")
            
            # Perform undo
            if entry['action'] == 'create':
                await conn.execute(
                    "DELETE FROM annotations WHERE id = $1",
                    entry['annotation_id']
                )
            elif entry['action'] == 'delete' and entry['old_data']:
                old = entry['old_data']
                await conn.execute(
                    """INSERT INTO annotations 
                       (id, image_id, class_name, bbox_x1, bbox_y1, bbox_x2, bbox_y2, created_by)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    old['id'], image_id, old['class_name'],
                    old['bbox_x1'], old['bbox_y1'], old['bbox_x2'], old['bbox_y2'],
                    old['created_by']
                )
            elif entry['action'] == 'update' and entry['old_data']:
                old = entry['old_data']
                await conn.execute(
                    """UPDATE annotations 
                       SET class_name = $2, bbox_x1 = $3, bbox_y1 = $4, bbox_x2 = $5, bbox_y2 = $6
                       WHERE id = $1""",
                    entry['annotation_id'], old['class_name'],
                    old['bbox_x1'], old['bbox_y1'], old['bbox_x2'], old['bbox_y2']
                )
            
            # Remove history entry
            await conn.execute(
                "DELETE FROM annotation_history WHERE id = $1", entry['id']
            )
            
            return {"status": "undone", "action": entry['action']}
    
    # ========================================================================
    # Training Jobs
    # ========================================================================
    
    @router.get("/jobs", response_model=List[TrainingJobResponse])
    async def list_jobs(status: Optional[str] = None, limit: int = Query(20, ge=1, le=100)):
        """List training jobs."""
        async with db_pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """SELECT * FROM training_jobs 
                       WHERE status = $1 ORDER BY created_at DESC LIMIT $2""",
                    status, limit
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM training_jobs ORDER BY created_at DESC LIMIT $1",
                    limit
                )
            return [
                TrainingJobResponse(
                    id=str(r['id']),
                    dataset_id=str(r['dataset_id']),
                    name=r['name'],
                    status=r['status'],
                    progress=r['progress'] or 0,
                    epochs_total=r['epochs_total'],
                    epochs_completed=r['epochs_completed'] or 0,
                    current_loss=r['current_loss'],
                    best_map50=r['best_map50'],
                    created_at=r['created_at'],
                    started_at=r['started_at'],
                    error_message=r['error_message']
                )
                for r in rows
            ]
    
    @router.post("/jobs", response_model=TrainingJobResponse)
    async def create_job(data: TrainingJobCreate):
        """Create training job and queue it."""
        job_id = str(uuid.uuid4())
        job_name = data.name or f"Training {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Normalize model_type (yolo11 -> yolov11)
        model_type = data.model_type
        if model_type == 'yolo11':
            model_type = 'yolov11'
        
        # Helper to check if value is valid UUID
        def is_valid_uuid(val: str) -> bool:
            try:
                uuid.UUID(val)
                return True
            except (ValueError, AttributeError):
                return False
        
        dataset_id_for_job = data.dataset_id  # Will be UUID for DB storage
        is_filesystem_dataset = not is_valid_uuid(data.dataset_id)
        
        async with db_pool.acquire() as conn:
            # Handle filesystem datasets (screenshots, catalog datasets like helmetvest-v7)
            if is_filesystem_dataset:
                logger.info(f"Filesystem dataset detected: {data.dataset_id}")
                
                # Check if placeholder already exists
                existing = await conn.fetchrow(
                    """SELECT id, images_count, annotations_count FROM training_datasets 
                       WHERE name = $1 AND source = 'filesystem'""",
                    data.dataset_id
                )
                
                # v2.10.67: Always recalculate from filesystem (placeholder may be stale)
                if data.dataset_id == "screenshots":
                    dataset_path = Path("/app/training_data/screenshots")
                else:
                    dataset_path = Path(f"/app/datasets/{data.dataset_id}")
                
                if existing and existing['annotations_count'] and existing['annotations_count'] > 0:
                    # Placeholder has valid data - use it
                    dataset_id_for_job = str(existing['id'])
                    images_count = existing['images_count']
                    annotations_count = existing['annotations_count']
                    logger.info(f"Found existing placeholder with data: {dataset_id_for_job}")
                else:
                    
                    # Count images - search recursively up to 3 levels deep
                    images_count = 0
                    labels_count = 0
                    
                    def find_images_and_labels(base_path: Path, depth: int = 3):
                        """Recursively find images and labels"""
                        img_count = 0
                        lbl_count = 0
                        
                        if not base_path.exists():
                            return 0, 0
                        
                        # Count images in this directory
                        for pattern in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
                            img_count += len(list(base_path.glob(pattern)))
                        
                        # Count YOLO annotation files (.txt)
                        labels_path = base_path.parent / 'labels'
                        if labels_path.exists():
                            txt_files = list(labels_path.glob('*.txt'))
                            # Each line in txt file is one annotation
                            for txt_file in txt_files:
                                try:
                                    with open(txt_file, 'r') as f:
                                        lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
                                        lbl_count += len(lines)
                                except:
                                    pass
                        
                        # Check common YOLO subdirectories
                        if depth > 0:
                            for subdir in ['train/images', 'valid/images', 'test/images', 'images', 'train', 'valid']:
                                sub_path = base_path / subdir
                                if sub_path.exists() and sub_path.is_dir():
                                    sub_img, sub_lbl = find_images_and_labels(sub_path, depth - 1)
                                    img_count += sub_img
                                    lbl_count += sub_lbl
                            
                            # Also check for nested folder (Roboflow creates subfolder with project name)
                            try:
                                for item in base_path.iterdir():
                                    if item.is_dir() and item.name not in ['train', 'valid', 'test', 'images', 'labels']:
                                        sub_img, sub_lbl = find_images_and_labels(item, depth - 1)
                                        img_count += sub_img
                                        lbl_count += sub_lbl
                            except:
                                pass
                        
                        return img_count, lbl_count
                    
                    if dataset_path.exists():
                        images_count, labels_count = find_images_and_labels(dataset_path)
                    
                    logger.info(f"Filesystem search: images={images_count}, yolo_labels={labels_count}")
                    
                    # Count annotations from Redis for manual annotations
                    redis_annotations_count = 0
                    try:
                        redis_key = f"catalog_annotations:{data.dataset_id}"
                        if redis_client:
                            ann_data = await redis_client.hgetall(redis_key)
                            for img_annotations in ann_data.values():
                                try:
                                    import json
                                    anns = json.loads(img_annotations)
                                    redis_annotations_count += len(anns) if isinstance(anns, list) else 0
                                except:
                                    pass
                        logger.info(f"Redis annotations count for {data.dataset_id}: {redis_annotations_count}")
                    except Exception as e:
                        logger.warning(f"Could not get Redis annotations: {e}")
                    
                    # Use max of YOLO labels and Redis annotations
                    annotations_count = max(labels_count, redis_annotations_count)
                    
                    logger.info(f"Filesystem dataset stats: images={images_count}, annotations={annotations_count} (yolo={labels_count}, redis={redis_annotations_count})")
                    
                    # Create or update placeholder in training_datasets
                    if existing:
                        # v2.10.67: Update stale placeholder with recalculated stats
                        dataset_id_for_job = str(existing['id'])
                        await conn.execute(
                            """UPDATE training_datasets 
                               SET images_count = $1, annotations_count = $2
                               WHERE id = $3""",
                            images_count, annotations_count, existing['id']
                        )
                        logger.info(f"Updated stale placeholder: {dataset_id_for_job} with images={images_count}, annotations={annotations_count}")
                    else:
                        new_dataset_id = str(uuid.uuid4())
                        await conn.execute(
                            """INSERT INTO training_datasets 
                               (id, name, description, images_count, annotations_count, source, created_by)
                               VALUES ($1, $2, $3, $4, $5, 'filesystem', 'admin')
                               ON CONFLICT DO NOTHING""",
                            new_dataset_id, data.dataset_id, 
                            f"Filesystem dataset: {data.dataset_id}",
                            images_count, annotations_count
                        )
                        dataset_id_for_job = new_dataset_id
                        logger.info(f"Created placeholder dataset: {new_dataset_id} for {data.dataset_id}")
                
                stats = {'images_count': images_count, 'annotations_count': annotations_count}
            else:
                # Regular UUID dataset from database
                stats = await conn.fetchrow(
                    """SELECT images_count, annotations_count 
                       FROM training_datasets WHERE id = $1""",
                    data.dataset_id
                )
                if not stats:
                    raise HTTPException(404, "Dataset not found")
            
            # Check requirements
            if stats['images_count'] < 10:  # Reduced for testing
                raise HTTPException(400, f"Need at least 10 images (have {stats['images_count']})")
            if stats['annotations_count'] < 20:  # Reduced for testing
                raise HTTPException(400, f"Need at least 20 annotations (have {stats['annotations_count']})")
            
            # Build model name (e.g., yolov8n.pt, yolov11m.pt)
            model_name = f"{model_type}{data.model_size}.pt"
            
            await conn.execute(
                """INSERT INTO training_jobs 
                   (id, dataset_id, name, epochs_total, batch_size, learning_rate,
                    image_size, augmentation, pretrained, created_by, status,
                    model_type, model_size, train_split, val_split, test_split,
                    optimizer, patience)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'queued',
                           $11, $12, $13, $14, $15, $16, $17)""",
                job_id, dataset_id_for_job, job_name, data.epochs, data.batch_size,
                data.learning_rate, data.image_size, data.augmentation, data.pretrained, 'admin',
                model_type, data.model_size, data.train_split, data.val_split, data.test_split,
                data.optimizer, data.patience
            )
            
            row = await conn.fetchrow("SELECT * FROM training_jobs WHERE id = $1", job_id)
        
        # Queue Celery task
        try:
            from celery import Celery
            celery_app = Celery(broker=os.getenv('REDIS_URL', 'redis://redis:6379/0'))
            celery_app.send_task('training.train_model', args=[job_id])
            logger.info(f"Queued training job: {job_id} with model {model_name}")
        except Exception as e:
            logger.error(f"Failed to queue training job: {e}")
            # Update status to pending if queue fails
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE training_jobs SET status = 'pending' WHERE id = $1",
                    job_id
                )
            
        return TrainingJobResponse(
            id=str(row['id']),
            dataset_id=str(row['dataset_id']),
            name=row['name'],
            status='queued',
            progress=0,
            epochs_total=row['epochs_total'],
            epochs_completed=0,
            current_loss=None,
            best_map50=None,
            created_at=row['created_at'],
            started_at=None,
            error_message=None,
            model_type=row.get('model_type', 'yolov8'),
            model_size=row.get('model_size', 'n'),
            train_split=row.get('train_split', 0.7),
            val_split=row.get('val_split', 0.2),
            test_split=row.get('test_split', 0.1)
        )
    
    @router.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        """Cancel training job."""
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE training_jobs SET status = 'cancelled' 
                   WHERE id = $1 AND status IN ('pending', 'queued', 'running')""",
                job_id
            )
            if result == "UPDATE 0":
                raise HTTPException(400, "Job not found or cannot be cancelled")
        
        # Send cancel signal to Celery
        try:
            from celery import Celery
            celery_app = Celery(broker=os.getenv('REDIS_URL', 'redis://redis:6379/0'))
            celery_app.send_task('training.cancel_job', args=[job_id])
        except Exception as e:
            logger.error(f"Failed to send cancel signal: {e}")
        
        return {"status": "cancelled"}
    
    @router.get("/jobs/{job_id}/logs")
    async def get_training_logs(job_id: str):
        """Get training logs for charts."""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT epoch, train_loss, val_loss, map50, map50_95, 
                          learning_rate, created_at as timestamp
                   FROM training_logs
                   WHERE job_id = $1
                   ORDER BY epoch, created_at""",
                job_id
            )
            
            logs = [
                {
                    'epoch': r['epoch'],
                    'train_loss': float(r['train_loss']) if r['train_loss'] else None,
                    'val_loss': float(r['val_loss']) if r['val_loss'] else None,
                    'map50': float(r['map50']) if r['map50'] else None,
                    'map50_95': float(r['map50_95']) if r['map50_95'] else None,
                    'learning_rate': float(r['learning_rate']) if r['learning_rate'] else None,
                    'timestamp': r['timestamp'].isoformat() if r['timestamp'] else None
                }
                for r in rows
            ]
            
            return {'logs': logs}
    
    # ========================================================================
    # Models
    # ========================================================================
    
    @router.get("/models")
    async def list_models():
        """List all models with DB + filesystem fallback. Never returns 404."""
        import os
        from datetime import datetime
        
        models = []
        db_ids = set()
        
        # Step 1: Try DB (authoritative source)
        try:
            if db_pool:
                async with db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT * FROM model_versions ORDER BY created_at DESC"
                    )
                    for r in rows:
                        db_ids.add(str(r['id']))
                        models.append({
                            "id": str(r['id']),
                            "name": r['name'],
                            "description": r.get('description', ''),
                            "map50": float(r['map50']) if r.get('map50') else None,
                            "map50_95": float(r['map50_95']) if r.get('map50_95') else None,
                            "is_active": r.get('is_active', False),
                            "created_at": r['created_at'].isoformat() if r.get('created_at') else None,
                            "training_images_count": r.get('train_images_count', 0),
                            "source": "db"
                        })
        except Exception as e:
            logger.warning(f"DB query failed, falling back to filesystem: {e}")
        
        # Step 2: Scan filesystem for .pt files not in DB
        model_dirs = ["/app/training_data/models", "/app/training_data/runs"]
        for model_dir in model_dirs:
            if not os.path.isdir(model_dir):
                continue
            for root, dirs, files in os.walk(model_dir):
                for f in files:
                    if not f.endswith('.pt'):
                        continue
                    fpath = os.path.join(root, f)
                    try:
                        stat = os.stat(fpath)
                        size_mb = round(stat.st_size / (1024 * 1024), 1)
                        mtime = datetime.fromtimestamp(stat.st_mtime)
                        model_id = f.replace('.pt', '')
                        if model_id not in db_ids:
                            models.append({
                                "id": model_id,
                                "name": f,
                                "description": f"Filesystem model: {fpath}",
                                "map50": None,
                                "map50_95": None,
                                "is_active": False,
                                "created_at": mtime.isoformat(),
                                "training_images_count": 0,
                                "model_path": fpath,
                                "size_mb": size_mb,
                                "source": "filesystem"
                            })
                    except Exception:
                        pass
        
        # Sort by created_at descending
        models.sort(key=lambda m: m.get('created_at') or '', reverse=True)
        
        return {
            "models": models,
            "count": len(models),
            "db_count": len(db_ids),
            "fs_count": len(models) - len(db_ids)
        }
    
    @router.post("/models/{model_id}/activate")
    async def activate_model(model_id: str):
        """
        Activate model and deploy to detector.
        1. Mark as active in DB
        2. Copy model file to ppe_model.pt (priority name)
        3. Signal detector to reload model
        """
        import shutil
        import aioredis
        
        async with db_pool.acquire() as conn:
            # Get model info first
            row = await conn.fetchrow(
                "SELECT model_path, name FROM model_versions WHERE id = $1",
                model_id
            )
            if not row:
                raise HTTPException(404, "Model not found")
            
            model_path = row['model_path']
            if not os.path.exists(model_path):
                raise HTTPException(404, f"Model file not found: {model_path}")
            
            # Deactivate all
            await conn.execute("UPDATE model_versions SET is_active = FALSE")
            
            # Activate selected
            await conn.execute(
                """UPDATE model_versions 
                   SET is_active = TRUE, activated_at = NOW(), activated_by = $2
                   WHERE id = $1""",
                model_id, 'admin'
            )
            
            # Copy model to ppe_model.pt (highest priority name)
            models_dir = os.path.dirname(model_path)
            target_path = os.path.join(models_dir, 'ppe_model.pt')
            
            try:
                shutil.copy2(model_path, target_path)
                logger.info(f"Model copied to {target_path}")
            except Exception as e:
                logger.error(f"Failed to copy model: {e}")
            
            # Signal detector to reload model via Redis pubsub
            try:
                redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')
                redis = await aioredis.from_url(redis_url)
                await redis.publish('system:model_updated', model_id)
                await redis.close()
                logger.info(f"Model reload signal sent for {model_id}")
            except Exception as e:
                logger.warning(f"Failed to signal detector: {e}")
            
            return {
                "status": "activated", 
                "model_id": model_id,
                "deployed_to": target_path,
                "message": "Модель активирована. Перезапустите detector для применения или подождите автозагрузку."
            }
    
    @router.get("/models/{model_id}/download")
    async def download_model(model_id: str):
        """Download model file."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT model_path, name FROM model_versions WHERE id = $1",
                model_id
            )
            if not row:
                raise HTTPException(404, "Model not found")
        
        path = row['model_path']
        if not os.path.exists(path):
            raise HTTPException(404, "Model file not found")
        
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=f"{row['name']}.pt"
        )
    
    # ========================================================================
    # Stats
    # ========================================================================
    
    @router.get("/stats/overview")
    async def get_stats():
        """Get training statistics."""
        async with db_pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    (SELECT COUNT(*) FROM training_datasets) as datasets,
                    (SELECT COUNT(*) FROM training_images) as images,
                    (SELECT COUNT(*) FROM annotations) as annotations,
                    (SELECT COUNT(*) FROM training_jobs WHERE status = 'completed') as completed_jobs,
                    (SELECT COUNT(*) FROM training_jobs WHERE status = 'running') as running_jobs,
                    (SELECT COUNT(*) FROM model_versions) as models
            """)
            return dict(stats)
    
    @router.get("/stats/class-distribution")
    async def get_class_distribution(dataset_id: Optional[str] = None):
        """Get class distribution."""
        async with db_pool.acquire() as conn:
            if dataset_id:
                rows = await conn.fetch("""
                    SELECT a.class_name, COUNT(*) as count
                    FROM annotations a
                    JOIN training_images i ON a.image_id = i.id
                    WHERE i.dataset_id = $1
                    GROUP BY a.class_name
                    ORDER BY count DESC
                """, dataset_id)
            else:
                rows = await conn.fetch("""
                    SELECT class_name, COUNT(*) as count
                    FROM annotations
                    GROUP BY class_name
                    ORDER BY count DESC
                """)
            
            distribution = [dict(r) for r in rows]
            total = sum(d['count'] for d in distribution)
            
            for d in distribution:
                d['percentage'] = round(d['count'] / total * 100, 2) if total > 0 else 0
            
            return {'distribution': distribution, 'total': total}
    
    # ========================================================================
    # WebSocket for Training Progress
    # ========================================================================
    
    @router.websocket("/ws/progress/{job_id}")
    async def training_progress_ws(websocket, job_id: str):
        """WebSocket endpoint for real-time training progress."""
        import aioredis
        
        await websocket.accept()
        
        redis = await aioredis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'))
        pubsub = redis.pubsub()
        
        channel = f"training:progress:{job_id}"
        await pubsub.subscribe(channel)
        
        try:
            # Send current status first
            status = await redis.get(f"training:status:{job_id}")
            if status:
                await websocket.send_json({
                    'type': 'status',
                    'data': json.loads(status)
                })
            
            # Listen for updates
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    data = json.loads(message['data'])
                    await websocket.send_json({
                        'type': 'progress',
                        'data': data
                    })
                    
                    # Close if training finished
                    if data.get('status') in ('completed', 'failed', 'cancelled'):
                        break
                        
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await pubsub.unsubscribe(channel)
            await redis.close()
    
    # ========================================================================
    # Dataset Catalog - Готовые датасеты для быстрой загрузки
    # ========================================================================
    
    @router.get("/catalog/datasets", response_model=List[dict])
    async def get_dataset_catalog():
        """
        Получить каталог готовых PPE датасетов для загрузки.
        Аналогично каталогу моделей - выбираешь, скачиваешь, используешь.
        """
        try:
            from dataset_downloader import dataset_downloader
            return dataset_downloader.get_catalog()
        except ImportError:
            # Fallback если модуль не загружен - обновлено 2026-01-29
            return [
                {
                    "id": "coco128-demo",
                    "name": "🚀 COCO128 Demo (Быстрый старт)",
                    "description": "Демо-датасет для быстрого тестирования системы. НЕ требует API ключей!",
                    "source": "direct",
                    "url": "https://github.com/ultralytics/yolov5/releases/download/v1.0/coco128.zip",
                    "size_mb": 7,
                    "images_count": 128,
                    "classes": ["person"],
                    "format": "yolov8",
                    "license": "CC BY 4.0",
                    "is_downloaded": False,
                    "recommended_for": "Быстрый старт и тестирование"
                },
                {
                    "id": "construction-ppe-skcet",
                    "name": "⭐ Construction PPE (8845 изобр.)",
                    "description": "Каски, жилеты, ботинки, перчатки - полный набор СИЗ. Требует Roboflow API ключ.",
                    "source": "roboflow",
                    "url": "https://universe.roboflow.com/skcet-g4h72/construction-ppe-rdhzo",
                    "size_mb": 500,
                    "images_count": 8845,
                    "classes": ["Helmet", "Safety Vest", "Gloves", "Safety Boot", "Human"],
                    "format": "yolov8",
                    "license": "CC BY 4.0",
                    "is_downloaded": False,
                    "recommended_for": "Строительные площадки, производство"
                },
                {
                    "id": "helmetvest-v7",
                    "name": "Helmet & Vest Detection",
                    "description": "Каски и жилеты - 2286 изображений. Требует Roboflow API ключ.",
                    "source": "roboflow",
                    "url": "https://universe.roboflow.com/data-u4eek/helmetvest/dataset/7",
                    "size_mb": 150,
                    "images_count": 2286,
                    "classes": ["Helmet", "NoHelmet", "NoVest", "Vest"],
                    "format": "yolov8",
                    "license": "CC BY 4.0",
                    "is_downloaded": False,
                    "recommended_for": "Базовая детекция касок и жилетов"
                }
            ]
    
    @router.post("/catalog/datasets/{dataset_id}/download")
    async def download_catalog_dataset(
        dataset_id: str,
        background_tasks: BackgroundTasks,
        roboflow_api_key: Optional[str] = Query(None, description="API ключ Roboflow (если нужен)")
    ):
        """
        Скачать датасет из каталога.
        
        - Для Roboflow датасетов можно передать API ключ
        - Без ключа создаются инструкции для ручной загрузки
        - Demo датасеты скачиваются напрямую
        """
        try:
            from dataset_downloader import dataset_downloader
            import asyncio
            
            # Если API ключ не передан, пробуем загрузить из сохранённых
            effective_api_key = roboflow_api_key
            if not effective_api_key:
                try:
                    keys = _load_api_keys()
                    effective_api_key = keys.get("roboflow")
                except Exception:
                    pass
            
            # Функция для запуска в фоне
            def run_download():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        dataset_downloader.download_dataset(dataset_id, effective_api_key)
                    )
                finally:
                    loop.close()
            
            # Запускаем в фоновой задаче
            import threading
            thread = threading.Thread(target=run_download, daemon=True)
            thread.start()
            
            return {
                "status": "downloading",
                "message": f"Загрузка датасета {dataset_id} началась",
                "dataset_id": dataset_id
            }
        except Exception as e:
            logger.error(f"Failed to start dataset download: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
    
    @router.get("/catalog/datasets/{dataset_id}/status")
    async def get_dataset_download_status(dataset_id: str):
        """Получить статус загрузки датасета"""
        try:
            from dataset_downloader import dataset_downloader
            
            progress = dataset_downloader.get_progress(dataset_id)
            if progress:
                return {
                    "dataset_id": progress.dataset_id,
                    "status": progress.status.value,
                    "progress": progress.progress,
                    "message": progress.message,
                    "error": progress.error
                }
            return {
                "dataset_id": dataset_id,
                "status": "idle",
                "progress": 0,
                "message": "Загрузка не начата"
            }
        except Exception as e:
            return {
                "dataset_id": dataset_id,
                "status": "error",
                "progress": 0,
                "message": str(e)
            }
    
    @router.delete("/catalog/datasets/{dataset_id}")
    async def delete_catalog_dataset(dataset_id: str):
        """Удалить скачанный датасет"""
        try:
            from dataset_downloader import dataset_downloader
            
            if dataset_downloader.delete_dataset(dataset_id):
                return {"status": "deleted", "dataset_id": dataset_id}
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
    
    @router.post("/catalog/datasets/{dataset_id}/import")
    async def import_catalog_dataset(dataset_id: str):
        """
        Импортировать датасет из папки в систему.
        Создаёт записи в БД для всех изображений из папки.
        Используется после ручной загрузки датасета.
        """
        from pathlib import Path
        import hashlib
        
        dataset_path = Path(f"/app/datasets/{dataset_id}")
        
        if not dataset_path.exists():
            raise HTTPException(404, f"Dataset folder not found: {dataset_id}")
        
        # Собираем все изображения
        image_dirs = [
            dataset_path / "train" / "images",
            dataset_path / "valid" / "images", 
            dataset_path / "test" / "images",
            dataset_path / "images",
        ]
        
        imported = 0
        errors = []
        
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    # Создаём датасет в БД если не существует
                    existing = await conn.fetchrow(
                        "SELECT id FROM training_datasets WHERE id = $1",
                        dataset_id
                    )
                    
                    if not existing:
                        await conn.execute("""
                            INSERT INTO training_datasets (id, name, description, status, created_at, updated_at)
                            VALUES ($1, $2, $3, 'active', NOW(), NOW())
                        """, dataset_id, dataset_id.replace('-', ' ').title(), f"Imported from {dataset_id}")
                    
                    for img_dir in image_dirs:
                        if not img_dir.exists():
                            continue
                            
                        for img_file in img_dir.iterdir():
                            if img_file.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.bmp'):
                                continue
                            
                            try:
                                # Генерируем UUID из пути
                                img_hash = hashlib.md5(str(img_file).encode()).hexdigest()
                                img_id = f"{img_hash[:8]}-{img_hash[8:12]}-{img_hash[12:16]}-{img_hash[16:20]}-{img_hash[20:32]}"
                                
                                # Проверяем нет ли уже
                                exists = await conn.fetchval(
                                    "SELECT 1 FROM training_images WHERE storage_path = $1",
                                    str(img_file)
                                )
                                if exists:
                                    continue
                                
                                # Получаем размеры
                                width, height = 0, 0
                                try:
                                    from PIL import Image
                                    with Image.open(img_file) as img:
                                        width, height = img.size
                                except Exception:
                                    pass
                                
                                await conn.execute("""
                                    INSERT INTO training_images 
                                    (id, dataset_id, filename, original_filename, storage_path, 
                                     mime_type, file_size, width, height, status, uploaded_at)
                                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending', NOW())
                                    ON CONFLICT (id) DO NOTHING
                                """,
                                    img_id, dataset_id, img_file.name, img_file.name,
                                    str(img_file), 'image/jpeg', img_file.stat().st_size,
                                    width, height
                                )
                                
                                # Импортируем аннотации из label файла если есть
                                label_file = img_file.parent.parent / "labels" / (img_file.stem + ".txt")
                                if label_file.exists() and width > 0:
                                    await import_yolo_labels(conn, img_id, label_file, width, height)
                                
                                imported += 1
                                
                            except Exception as e:
                                errors.append(f"{img_file.name}: {str(e)}")
                    
                    # Обновляем счётчики датасета
                    await conn.execute("""
                        UPDATE training_datasets 
                        SET images_count = (SELECT COUNT(*) FROM training_images WHERE dataset_id = $1),
                            updated_at = NOW()
                        WHERE id = $1
                    """, dataset_id)
                    
            except Exception as e:
                logger.error(f"Import error: {e}")
                raise HTTPException(500, f"Import failed: {e}")
        
        return {
            "status": "completed",
            "dataset_id": dataset_id,
            "imported": imported,
            "errors": errors[:10] if errors else []
        }
    
    async def import_yolo_labels(conn, image_id: str, label_file, width: int, height: int):
        """Import YOLO format labels for an image"""
        try:
            with open(label_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    
                    class_id = int(parts[0])
                    x_center, y_center, w, h = map(float, parts[1:5])
                    
                    # Convert YOLO format (center, width, height) to corner format
                    bbox_x1 = x_center - w/2
                    bbox_y1 = y_center - h/2
                    bbox_x2 = x_center + w/2
                    bbox_y2 = y_center + h/2
                    
                    # Get class name from ID
                    class_names = ["Hardhat", "NO-Hardhat", "Safety Vest", "NO-Safety Vest", "Person",
                                   "helmet", "no_helmet", "vest", "no_vest", "goggles", "gloves", "mask"]
                    class_name = class_names[class_id] if class_id < len(class_names) else f"class_{class_id}"
                    
                    import uuid
                    await conn.execute("""
                        INSERT INTO annotations 
                        (id, image_id, class_name, bbox_x1, bbox_y1, bbox_x2, bbox_y2, 
                         confidence, created_by, created_at, verified)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, 1.0, 'import', NOW(), true)
                        ON CONFLICT DO NOTHING
                    """, 
                        str(uuid.uuid4()), image_id, class_name,
                        bbox_x1, bbox_y1, bbox_x2, bbox_y2
                    )
        except Exception as e:
            logger.warning(f"Failed to import labels from {label_file}: {e}")
    
    # ========================================================================
    # API Keys Management - Ключи для внешних сервисов
    # ========================================================================
    
    @router.get("/api-keys")
    async def get_api_keys():
        """
        Получить список сохранённых API ключей (маскированные).
        Возвращает типы ключей и их маскированные значения.
        """
        keys = _load_api_keys()
        result = {}
        for key_type, value in keys.items():
            if value:
                # Показываем только первые и последние символы
                masked = f"{value[:4]}...{value[-4:]}" if len(value) > 10 else "****"
                result[key_type] = {
                    "exists": True,
                    "masked": masked
                }
            else:
                result[key_type] = {"exists": False, "masked": None}
        
        # Добавляем пустые значения для известных типов
        for key_type in ["roboflow", "kaggle_username", "kaggle_key", "huggingface"]:
            if key_type not in result:
                result[key_type] = {"exists": False, "masked": None}
        
        return result
    
    @router.post("/api-keys/{key_type}")
    async def save_api_key(key_type: str, data: dict):
        """
        Сохранить API ключ.
        
        key_type: roboflow | kaggle_username | kaggle_key | huggingface
        data: { "value": "your-api-key" }
        """
        allowed_types = ["roboflow", "kaggle_username", "kaggle_key", "huggingface"]
        if key_type not in allowed_types:
            raise HTTPException(400, f"Unknown key type. Allowed: {', '.join(allowed_types)}")
        
        value = data.get("value", "").strip()
        if not value:
            raise HTTPException(400, "API key value is required")
        
        keys = _load_api_keys()
        keys[key_type] = value
        
        if _save_api_keys(keys):
            # Для Kaggle - создаём файл kaggle.json если оба ключа есть
            if key_type in ["kaggle_username", "kaggle_key"]:
                kaggle_username = keys.get("kaggle_username")
                kaggle_key = keys.get("kaggle_key")
                if kaggle_username and kaggle_key:
                    kaggle_dir = Path.home() / ".kaggle"
                    kaggle_dir.mkdir(exist_ok=True)
                    kaggle_file = kaggle_dir / "kaggle.json"
                    with open(kaggle_file, 'w') as f:
                        json.dump({"username": kaggle_username, "key": kaggle_key}, f)
                    kaggle_file.chmod(0o600)
                    logger.info("Kaggle credentials saved")
            
            return {"status": "saved", "key_type": key_type}
        else:
            raise HTTPException(500, "Failed to save API key")
    
    @router.delete("/api-keys/{key_type}")
    async def delete_api_key(key_type: str):
        """Удалить API ключ"""
        keys = _load_api_keys()
        if key_type in keys:
            del keys[key_type]
            _save_api_keys(keys)
        return {"status": "deleted", "key_type": key_type}
    
    @router.get("/api-keys/{key_type}/value")
    async def get_api_key_value(key_type: str):
        """
        Получить полное значение API ключа (для внутреннего использования).
        """
        keys = _load_api_keys()
        value = keys.get(key_type)
        if value:
            return {"key_type": key_type, "value": value}
        return {"key_type": key_type, "value": None}
    
    # Legacy endpoint для совместимости с DatasetCatalog
    @router.get("/settings/roboflow-api-key")
    async def get_roboflow_key_legacy():
        """Legacy endpoint - получить Roboflow API key"""
        keys = _load_api_keys()
        return {"api_key": keys.get("roboflow")}
    
    @router.post("/settings/roboflow-api-key")
    async def save_roboflow_key_legacy(data: dict):
        """Legacy endpoint - сохранить Roboflow API key"""
        value = data.get("api_key", "").strip()
        if not value:
            raise HTTPException(400, "API key is required")
        
        keys = _load_api_keys()
        keys["roboflow"] = value
        
        if _save_api_keys(keys):
            return {"status": "saved"}
        raise HTTPException(500, "Failed to save API key")
    
    return router
