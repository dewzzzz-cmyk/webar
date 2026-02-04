#!/usr/bin/env python3
"""
PPE Training Worker Service v1.0
Celery worker для обучения моделей YOLOv8

Features:
- Async training job execution
- Progress reporting via Redis
- Model evaluation and metrics
- Graceful shutdown
"""

import os
import sys
import json
import shutil
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import asyncio

from celery import Celery
from celery.signals import worker_process_init, worker_shutdown
import redis
import psycopg2
from psycopg2.extras import RealDictCursor

# ============================================================================
# Configuration
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('training_worker')

# Environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://ppe:ppe_secret@postgres:5432/ppe_detection')
TRAINING_DATA_PATH = os.getenv('TRAINING_DATA_PATH', '/app/training_data')
MODELS_PATH = os.getenv('MODELS_PATH', '/app/models')

# Supported models configuration
SUPPORTED_MODELS = {
    'yolov8': {
        'sizes': ['n', 's', 'm', 'l', 'x'],
        'template': 'yolov8{size}.pt',
        'description': 'YOLOv8 - Fast and accurate, good default choice'
    },
    'yolov9': {
        'sizes': ['t', 's', 'm', 'c', 'e'],  # YOLOv9 uses t,s,m,c,e
        'template': 'yolov9{size}.pt',
        'description': 'YOLOv9 - Improved architecture with GELAN'
    },
    'yolov10': {
        'sizes': ['n', 's', 'm', 'b', 'l', 'x'],
        'template': 'yolov10{size}.pt',
        'description': 'YOLOv10 - NMS-free, faster inference'
    },
    'yolov11': {
        'sizes': ['n', 's', 'm', 'l', 'x'],
        'template': 'yolo11{size}.pt',  # Note: yolo11, not yolov11
        'description': 'YOLOv11 - Latest Ultralytics model'
    }
}

def get_model_path(model_type: str, model_size: str) -> str:
    """Get the model file path based on type and size."""
    model_type = model_type.lower()
    model_size = model_size.lower()
    
    # Handle yolo11 naming
    if model_type == 'yolo11':
        model_type = 'yolov11'
    
    if model_type not in SUPPORTED_MODELS:
        logger.warning(f"Unknown model type {model_type}, falling back to yolov8")
        model_type = 'yolov8'
    
    config = SUPPORTED_MODELS[model_type]
    
    # Map size for YOLOv9 (n->t, s->s, m->m, l->c, x->e)
    if model_type == 'yolov9' and model_size in ['n', 'l', 'x']:
        size_map = {'n': 't', 'l': 'c', 'x': 'e'}
        model_size = size_map.get(model_size, model_size)
    
    if model_size not in config['sizes']:
        logger.warning(f"Size {model_size} not available for {model_type}, using first available")
        model_size = config['sizes'][0]
    
    # Build model name
    template = config['template']
    model_name = template.format(size=model_size)
    
    logger.info(f"Selected model: {model_name} ({config['description']})")
    return model_name

# Paths
DATASETS_PATH = Path(TRAINING_DATA_PATH) / 'datasets'
RUNS_PATH = Path(TRAINING_DATA_PATH) / 'runs'
IMAGES_PATH = Path(TRAINING_DATA_PATH) / 'images'

# Create directories
for path in [DATASETS_PATH, RUNS_PATH, IMAGES_PATH, Path(MODELS_PATH)]:
    path.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Celery App
# ============================================================================

app = Celery('training_worker')
app.config_from_object({
    'broker_url': REDIS_URL,
    'result_backend': REDIS_URL,
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    'timezone': 'UTC',
    'task_track_started': True,
    'task_time_limit': 86400,  # 24 hours max
    'worker_prefetch_multiplier': 1,  # One task at a time
    'worker_concurrency': 1,  # Single worker for GPU
})

# Redis client for progress updates
redis_client: Optional[redis.Redis] = None
db_conn = None

@worker_process_init.connect
def init_worker(**kwargs):
    """Initialize worker process."""
    global redis_client, db_conn
    redis_client = redis.from_url(REDIS_URL)
    db_conn = psycopg2.connect(DATABASE_URL)
    logger.info("Training worker initialized")

@worker_shutdown.connect
def shutdown_worker(**kwargs):
    """Cleanup on shutdown."""
    global db_conn
    if db_conn:
        db_conn.close()
    logger.info("Training worker shutdown")


# ============================================================================
# Database Helpers
# ============================================================================

def get_db_cursor():
    """Get database cursor."""
    global db_conn
    if db_conn.closed:
        db_conn = psycopg2.connect(DATABASE_URL)
    return db_conn.cursor(cursor_factory=RealDictCursor)


def update_job_status(job_id: str, status: str, **kwargs):
    """Update training job status in database."""
    with get_db_cursor() as cur:
        updates = ['status = %s']
        values = [status]
        
        for key, value in kwargs.items():
            updates.append(f'{key} = %s')
            values.append(value)
        
        values.append(job_id)
        
        cur.execute(
            f"UPDATE training_jobs SET {', '.join(updates)} WHERE id = %s",
            values
        )
        db_conn.commit()


def publish_progress(job_id: str, data: Dict[str, Any]):
    """Publish progress update via Redis."""
    if redis_client:
        channel = f"training:progress:{job_id}"
        redis_client.publish(channel, json.dumps(data))
        
        # Also store latest status
        redis_client.setex(
            f"training:status:{job_id}",
            3600,  # 1 hour TTL
            json.dumps(data)
        )


# ============================================================================
# Dataset Preparation
# ============================================================================

def prepare_yolo_dataset(job_id: str, dataset_id: str) -> str:
    """
    Prepare dataset in YOLO format.
    
    Structure:
    dataset/
    ├── images/
    │   ├── train/
    │   └── val/
    ├── labels/
    │   ├── train/
    │   └── val/
    └── data.yaml
    """
    logger.info(f"Preparing dataset for job {job_id}")
    
    dataset_path = DATASETS_PATH / job_id
    dataset_path.mkdir(parents=True, exist_ok=True)
    
    # Create structure
    (dataset_path / 'images' / 'train').mkdir(parents=True, exist_ok=True)
    (dataset_path / 'images' / 'val').mkdir(parents=True, exist_ok=True)
    (dataset_path / 'labels' / 'train').mkdir(parents=True, exist_ok=True)
    (dataset_path / 'labels' / 'val').mkdir(parents=True, exist_ok=True)
    
    # Get images and annotations
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT i.id, i.storage_path, i.width, i.height
            FROM training_images i
            WHERE i.dataset_id = %s AND i.status IN ('annotated', 'validated')
        """, (dataset_id,))
        images = cur.fetchall()
    
    if not images:
        raise ValueError("No annotated images in dataset")
    
    # Class mapping - extended for more PPE types
    class_names = [
        'person', 'hardhat', 'no_hardhat', 'vest', 'no_vest',
        'glasses', 'no_glasses', 'gloves', 'no_gloves', 'boots', 'no_boots',
        'mask', 'no_mask', 'helmet', 'safety_vest', 'Hardhat', 'NO-Hardhat',
        'Safety Vest', 'NO-Safety Vest', 'Person'
    ]
    class_to_idx = {name: idx for idx, name in enumerate(class_names)}
    # Also map lowercase variants
    for name in list(class_to_idx.keys()):
        class_to_idx[name.lower()] = class_to_idx[name]
        class_to_idx[name.lower().replace('-', '_')] = class_to_idx[name]
        class_to_idx[name.lower().replace(' ', '_')] = class_to_idx[name]
    
    # Get train/val split from job config
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT train_split, val_split FROM training_jobs WHERE id = %s
        """, (job_id,))
        job_config = cur.fetchone()
    
    train_ratio = float(job_config['train_split']) if job_config and job_config['train_split'] else 0.7
    val_ratio = float(job_config['val_split']) if job_config and job_config['val_split'] else 0.2
    
    # Normalize (train + val should = 1.0 for YOLO)
    total = train_ratio + val_ratio
    train_ratio = train_ratio / total
    
    import random
    random.shuffle(images)
    split_idx = int(len(images) * train_ratio)
    train_images = images[:split_idx]
    val_images = images[split_idx:]
    
    logger.info(f"Dataset split: {len(train_images)} train ({train_ratio*100:.0f}%), {len(val_images)} val ({(1-train_ratio)*100:.0f}%)")
    
    def process_images(images_list, split: str):
        for img in images_list:
            img_id = str(img['id'])
            src_path = img['storage_path']
            
            if not os.path.exists(src_path):
                logger.warning(f"Image not found: {src_path}")
                continue
            
            # Copy image
            ext = Path(src_path).suffix
            dst_img = dataset_path / 'images' / split / f"{img_id}{ext}"
            shutil.copy2(src_path, dst_img)
            
            # Get annotations
            with get_db_cursor() as cur:
                cur.execute("""
                    SELECT class_name, bbox_x1, bbox_y1, bbox_x2, bbox_y2
                    FROM annotations
                    WHERE image_id = %s
                """, (img_id,))
                annotations = cur.fetchall()
            
            # Create label file (YOLO format)
            label_path = dataset_path / 'labels' / split / f"{img_id}.txt"
            with open(label_path, 'w') as f:
                for ann in annotations:
                    if ann['class_name'] not in class_to_idx:
                        continue
                    
                    class_idx = class_to_idx[ann['class_name']]
                    
                    # Convert to YOLO format (center_x, center_y, width, height)
                    x1, y1 = ann['bbox_x1'], ann['bbox_y1']
                    x2, y2 = ann['bbox_x2'], ann['bbox_y2']
                    
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    w = x2 - x1
                    h = y2 - y1
                    
                    f.write(f"{class_idx} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
    
    process_images(train_images, 'train')
    process_images(val_images, 'val')
    
    # Create data.yaml
    data_yaml = {
        'path': str(dataset_path),
        'train': 'images/train',
        'val': 'images/val',
        'nc': len(class_names),
        'names': class_names
    }
    
    import yaml
    with open(dataset_path / 'data.yaml', 'w') as f:
        yaml.dump(data_yaml, f, default_flow_style=False)
    
    logger.info(f"Dataset prepared at {dataset_path}")
    return str(dataset_path / 'data.yaml')


# ============================================================================
# Training Task
# ============================================================================

@app.task(bind=True, name='training.train_model')
def train_model(self, job_id: str):
    """
    Main training task.
    
    1. Load job config from database
    2. Prepare YOLO dataset
    3. Run training with progress callbacks
    4. Evaluate model
    5. Save results
    """
    logger.info(f"Starting training job: {job_id}")
    
    try:
        # Get job config
        with get_db_cursor() as cur:
            cur.execute("SELECT * FROM training_jobs WHERE id = %s", (job_id,))
            job = cur.fetchone()
        
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        
        if job['status'] == 'cancelled':
            logger.info(f"Job {job_id} was cancelled")
            return {'status': 'cancelled'}
        
        # Update status
        update_job_status(
            job_id, 
            'running',
            started_at=datetime.utcnow()
        )
        
        publish_progress(job_id, {
            'status': 'running',
            'stage': 'preparing',
            'message': 'Подготовка датасета...'
        })
        
        # Prepare dataset
        data_yaml = prepare_yolo_dataset(job_id, str(job['dataset_id']))
        
        publish_progress(job_id, {
            'status': 'running',
            'stage': 'training',
            'message': 'Начало обучения...',
            'progress': 0
        })
        
        # Import YOLO (lazy import for GPU memory)
        from ultralytics import YOLO
        
        # Get model type and size from job config
        model_type = job.get('model_type', 'yolov8') or 'yolov8'
        model_size = job.get('model_size', 'n') or 'n'
        model_name = get_model_path(model_type, model_size)
        
        publish_progress(job_id, {
            'status': 'running',
            'stage': 'loading_model',
            'message': f'Загрузка модели {model_name}...',
            'progress': 0
        })
        
        # Load base model (Ultralytics will auto-download if not present)
        logger.info(f"Loading model: {model_name}")
        model = YOLO(model_name)
        
        # Training parameters from job
        epochs = job['epochs_total']
        batch_size = job['batch_size']
        lr = job['learning_rate']
        imgsz = job['image_size']
        augment = job['augmentation']
        optimizer = job.get('optimizer', 'auto') or 'auto'
        patience = job.get('patience', 50) or 50
        
        # Run path
        run_path = RUNS_PATH / job_id
        
        # Custom callback for progress
        def on_train_epoch_end(trainer):
            epoch = trainer.epoch + 1
            progress = (epoch / epochs) * 100
            
            metrics = trainer.metrics
            train_loss = float(metrics.get('train/box_loss', 0) + 
                              metrics.get('train/cls_loss', 0))
            
            # Update database
            update_job_status(
                job_id,
                'running',
                progress=progress,
                epochs_completed=epoch,
                current_loss=train_loss
            )
            
            # Publish progress
            publish_progress(job_id, {
                'status': 'running',
                'stage': 'training',
                'epoch': epoch,
                'epochs_total': epochs,
                'progress': progress,
                'train_loss': train_loss,
                'message': f'Эпоха {epoch}/{epochs}'
            })
            
            # Check for cancellation
            with get_db_cursor() as cur:
                cur.execute(
                    "SELECT status FROM training_jobs WHERE id = %s",
                    (job_id,)
                )
                current = cur.fetchone()
                if current and current['status'] == 'cancelled':
                    raise KeyboardInterrupt("Job cancelled")
        
        def on_val_end(validator):
            metrics = validator.metrics
            map50 = float(metrics.box.map50) if hasattr(metrics, 'box') else 0
            map50_95 = float(metrics.box.map) if hasattr(metrics, 'box') else 0
            
            # Update best metrics
            with get_db_cursor() as cur:
                cur.execute(
                    "SELECT best_map50 FROM training_jobs WHERE id = %s",
                    (job_id,)
                )
                current = cur.fetchone()
                
                if current and (current['best_map50'] is None or map50 > current['best_map50']):
                    update_job_status(
                        job_id,
                        'running',
                        best_map50=map50,
                        best_map50_95=map50_95
                    )
            
            publish_progress(job_id, {
                'status': 'running',
                'stage': 'validating',
                'map50': map50,
                'map50_95': map50_95,
                'message': f'Validation: mAP@50={map50:.3f}'
            })
        
        # Add callbacks
        model.add_callback('on_train_epoch_end', on_train_epoch_end)
        model.add_callback('on_val_end', on_val_end)
        
        # Detect device
        device = 0 if os.path.exists('/dev/nvidia0') else 'cpu'
        logger.info(f"Training device: {'GPU' if device == 0 else 'CPU'}")
        
        # Train
        logger.info(f"Starting {model_name} training: {epochs} epochs, batch={batch_size}, optimizer={optimizer}, patience={patience}")
        
        # Build training args
        train_args = {
            'data': data_yaml,
            'epochs': epochs,
            'batch': batch_size,
            'imgsz': imgsz,
            'lr0': lr,
            'augment': augment,
            'project': str(RUNS_PATH),
            'name': job_id,
            'exist_ok': True,
            'verbose': True,
            'device': device,
            'workers': 0,  # MUST be 0: Celery daemonic process cannot spawn children
            'patience': patience if patience > 0 else 0,  # 0 disables early stopping
            'save': True,
            'plots': True,
            'cache': True,  # Cache images for faster training
            'amp': True,  # Mixed precision for faster training on GPU
        }
        
        # Add optimizer if not auto
        if optimizer != 'auto':
            train_args['optimizer'] = optimizer
        
        results = model.train(**train_args)
        
        # Get best model path
        best_model_path = run_path / 'weights' / 'best.pt'
        
        if not best_model_path.exists():
            best_model_path = run_path / 'weights' / 'last.pt'
        
        # Final evaluation
        publish_progress(job_id, {
            'status': 'running',
            'stage': 'evaluating',
            'message': 'Финальная оценка модели...'
        })
        
        # Load best model and evaluate
        best_model = YOLO(str(best_model_path))
        val_results = best_model.val(data=data_yaml)
        
        # Extract metrics
        final_map50 = float(val_results.box.map50)
        final_map50_95 = float(val_results.box.map)
        
        # Per-class metrics
        class_names = ['person', 'hardhat', 'no_hardhat', 'vest', 'no_vest', 'glasses', 'no_glasses']
        metrics_per_class = {}
        
        if hasattr(val_results.box, 'ap50'):
            ap50_per_class = val_results.box.ap50
            for i, name in enumerate(class_names):
                if i < len(ap50_per_class):
                    metrics_per_class[name] = {
                        'ap50': float(ap50_per_class[i])
                    }
        
        # Copy model to models directory
        final_model_path = Path(MODELS_PATH) / f"ppe_custom_{job_id}.pt"
        shutil.copy2(best_model_path, final_model_path)
        
        # v2.10.54: Автоматически активируем обученную модель
        # Копируем в ppe_model.pt - детектор подхватит через hot reload
        active_model_path = Path(MODELS_PATH) / "ppe_model.pt"
        try:
            # Backup старой модели если есть
            if active_model_path.exists():
                backup_path = Path(MODELS_PATH) / f"ppe_model_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"
                shutil.copy2(active_model_path, backup_path)
                logger.info(f"Created model backup: {backup_path}")
            
            # Копируем новую обученную модель как активную
            shutil.copy2(final_model_path, active_model_path)
            logger.info(f"✓ Trained model auto-activated: {final_model_path} -> {active_model_path}")
            
            # Обновляем Redis для UI
            try:
                r = redis.from_url(REDIS_URL, decode_responses=True)
                r.set("system:active_model", f"ppe_custom_{job_id}")
                r.hset("system:active_model_info", mapping={
                    "id": f"ppe_custom_{job_id}",
                    "name": f"PPE Custom Model ({datetime.now().strftime('%Y-%m-%d')})",
                    "source": "training",
                    "activated_at": datetime.now().isoformat()
                })
            except Exception as redis_err:
                logger.warning(f"Could not update Redis: {redis_err}")
        except Exception as activate_err:
            logger.error(f"Could not auto-activate model: {activate_err}")
            # Не критично - модель всё равно сохранена
        
        # Get training stats
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as count FROM training_images
                WHERE dataset_id = %s AND status IN ('annotated', 'validated')
            """, (str(job['dataset_id']),))
            img_count = cur.fetchone()['count']
        
        # Create model version
        import uuid
        model_version_id = str(uuid.uuid4())
        
        with get_db_cursor() as cur:
            cur.execute("""
                INSERT INTO model_versions 
                (id, training_job_id, name, description, model_path,
                 map50, map50_95, metrics_per_class, train_images_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                model_version_id,
                job_id,
                f"PPE Custom Model ({datetime.now().strftime('%Y-%m-%d')})",
                f"Fine-tuned on {img_count} images, {epochs} epochs",
                str(final_model_path),
                final_map50,
                final_map50_95,
                json.dumps(metrics_per_class),
                img_count
            ))
            db_conn.commit()
        
        # Update job as completed
        update_job_status(
            job_id,
            'completed',
            progress=100,
            epochs_completed=epochs,
            best_map50=final_map50,
            best_map50_95=final_map50_95,
            completed_at=datetime.utcnow()
        )
        
        publish_progress(job_id, {
            'status': 'completed',
            'stage': 'done',
            'progress': 100,
            'map50': final_map50,
            'map50_95': final_map50_95,
            'model_id': model_version_id,
            'message': f'Обучение завершено! mAP@50={final_map50:.3f}'
        })
        
        logger.info(f"Training completed: job={job_id}, mAP@50={final_map50:.3f}")
        
        return {
            'status': 'completed',
            'job_id': job_id,
            'model_id': model_version_id,
            'map50': final_map50,
            'map50_95': final_map50_95
        }
        
    except KeyboardInterrupt:
        logger.info(f"Training cancelled: {job_id}")
        update_job_status(job_id, 'cancelled')
        publish_progress(job_id, {
            'status': 'cancelled',
            'message': 'Обучение отменено'
        })
        return {'status': 'cancelled'}
        
    except Exception as e:
        logger.error(f"Training failed: {job_id} - {e}", exc_info=True)
        update_job_status(
            job_id,
            'failed',
            error_message=str(e)
        )
        publish_progress(job_id, {
            'status': 'failed',
            'error': str(e),
            'message': f'Ошибка: {str(e)}'
        })
        raise


# ============================================================================
# Evaluation Task
# ============================================================================

@app.task(name='training.evaluate_model')
def evaluate_model(model_id: str, dataset_id: str):
    """Evaluate a model on a dataset."""
    logger.info(f"Evaluating model {model_id} on dataset {dataset_id}")
    
    try:
        # Get model path
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT model_path FROM model_versions WHERE id = %s",
                (model_id,)
            )
            model = cur.fetchone()
        
        if not model:
            raise ValueError(f"Model not found: {model_id}")
        
        # Prepare temp dataset
        temp_job_id = f"eval_{model_id}"
        data_yaml = prepare_yolo_dataset(temp_job_id, dataset_id)
        
        # Load and evaluate
        from ultralytics import YOLO
        yolo = YOLO(model['model_path'])
        results = yolo.val(data=data_yaml)
        
        # Cleanup temp dataset
        shutil.rmtree(DATASETS_PATH / temp_job_id, ignore_errors=True)
        
        return {
            'model_id': model_id,
            'map50': float(results.box.map50),
            'map50_95': float(results.box.map)
        }
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        raise


# ============================================================================
# Cleanup Task
# ============================================================================

@app.task(name='training.cleanup_old_runs')
def cleanup_old_runs(days: int = 7):
    """Clean up old training runs."""
    import time
    
    now = time.time()
    cutoff = now - (days * 86400)
    
    for run_dir in RUNS_PATH.iterdir():
        if run_dir.is_dir():
            mtime = run_dir.stat().st_mtime
            if mtime < cutoff:
                logger.info(f"Cleaning up old run: {run_dir}")
                shutil.rmtree(run_dir, ignore_errors=True)


# ============================================================================
# T04: Auto-Annotate Single Image (Celery + CPU)
# T06: GPU Guard — all auto-annotate uses device="cpu"
# ============================================================================

def _resolve_image_path(image_id: str) -> Optional[str]:
    """Resolve image path from DB or filesystem by ID/hash."""
    import hashlib
    
    # Try DB first
    try:
        if db_conn:
            with db_conn.cursor() as cur:
                cur.execute(
                    "SELECT storage_path FROM training_images WHERE id = %s", (image_id,)
                )
                row = cur.fetchone()
                if row and row[0] and os.path.exists(row[0]):
                    return row[0]
    except Exception as e:
        logger.warning(f"DB lookup failed for {image_id}: {e}")
        try:
            db_conn.rollback()
        except Exception:
            pass
    
    # Try filesystem scan (catalog/screenshots)
    search_dirs = ["/app/datasets", "/app/violations", "/app/training_data/images"]
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for root, dirs, files in os.walk(search_dir):
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    fpath = os.path.join(root, f)
                    file_hash = hashlib.md5(fpath.encode()).hexdigest()
                    if image_id == file_hash or image_id == file_hash[:16]:
                        return fpath
                    # Also try content hash
                    try:
                        content_hash = hashlib.md5(open(fpath, 'rb').read()).hexdigest()
                        if image_id == content_hash or image_id == content_hash[:32]:
                            return fpath
                    except Exception:
                        pass
    
    return None


def _get_active_model_path() -> str:
    """Get path to active YOLO model for auto-annotation."""
    candidates = [
        "/app/models/ppe_model.pt",
        "/app/models/best.pt",
    ]
    # Also check DB for active model
    try:
        if db_conn:
            with db_conn.cursor() as cur:
                cur.execute(
                    "SELECT model_path FROM model_versions WHERE is_active = TRUE LIMIT 1"
                )
                row = cur.fetchone()
                if row and row[0]:
                    candidates.insert(0, row[0])
    except Exception as e:
        logger.warning(f"DB model lookup failed: {e}")
        try:
            db_conn.rollback()
        except Exception:
            pass
    
    # Check runs directory for latest best.pt
    runs_best = sorted(RUNS_PATH.glob("*/weights/best.pt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if runs_best:
        candidates.insert(1, str(runs_best[0]))
    
    for path in candidates:
        if os.path.exists(path):
            return path
    
    # Fallback: base yolov8n
    return "yolov8n.pt"


# PPE class mapping (YOLO class -> our class)
PPE_CLASS_MAPPING = {
    'person': 'person',
    'hardhat': 'hardhat',
    'no-hardhat': 'no_hardhat',
    'no_hardhat': 'no_hardhat',
    'vest': 'vest',
    'no-vest': 'no_vest',
    'no_vest': 'no_vest',
    'safety-vest': 'vest',
    'goggles': 'goggles',
    'no-goggles': 'no_goggles',
    'no_goggles': 'no_goggles',
    'mask': 'mask',
    'no-mask': 'no_mask',
    'gloves': 'gloves',
    'no-gloves': 'no_gloves',
    'helmet': 'hardhat',
    'head': 'no_hardhat',
}


@app.task(bind=True, name='training.auto_annotate')
def auto_annotate_task(self, image_id: str, threshold: float = 0.3):
    """
    T04: Auto-annotate single image using YOLO on CPU.
    T06 GPU Guard: model.to("cpu") + device="cpu" — never touches GPU.
    Results stored in Redis.
    """
    from ultralytics import YOLO
    import json
    
    logger.info(f"[auto_annotate] Starting for image {image_id}, threshold={threshold}")
    
    # Resolve image path
    image_path = _resolve_image_path(image_id)
    if not image_path:
        raise ValueError(f"Image not found: {image_id}")
    
    # Load model — CPU ONLY (GPU guard T06)
    model_path = _get_active_model_path()
    model = YOLO(model_path)
    model.to("cpu")  # T06: GPU guard — force CPU
    
    logger.info(f"[auto_annotate] Model: {model_path}, device=cpu")
    
    # Run inference on CPU
    results = model.predict(
        source=image_path,
        conf=threshold,
        device="cpu",  # T06: GPU guard — explicit CPU
        verbose=False
    )
    
    annotations = []
    if results and len(results) > 0:
        result = results[0]
        if result.boxes is not None:
            # Get image dimensions
            img_h, img_w = result.orig_shape
            
            for box in result.boxes:
                cls_id = int(box.cls[0])
                cls_name = model.names.get(cls_id, f'class_{cls_id}')
                mapped_class = PPE_CLASS_MAPPING.get(cls_name.lower(), cls_name)
                
                # Normalized bbox (xyxy -> x1,y1,x2,y2 in 0-1)
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                annotations.append({
                    "class_id": cls_id,
                    "class_name": mapped_class,
                    "bbox": [x1 / img_w, y1 / img_h, x2 / img_w, y2 / img_h],
                    "confidence": round(float(box.conf[0]), 4),
                    "source": "auto"
                })
    
    # Store in Redis
    if redis_client:
        redis_client.set(
            f"auto_annotations:{image_id}",
            json.dumps(annotations),
            ex=86400  # 24h TTL
        )
        logger.info(f"[auto_annotate] Stored {len(annotations)} annotations in Redis for {image_id}")
    
    # Also try to save to DB
    try:
        if db_conn:
            import uuid
            with db_conn.cursor() as cur:
                for ann in annotations:
                    ann_id = str(uuid.uuid4())
                    cur.execute(
                        """INSERT INTO annotations 
                           (id, image_id, class_name, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, created_by)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT DO NOTHING""",
                        (ann_id, image_id, ann["class_name"],
                         ann["bbox"][0], ann["bbox"][1], ann["bbox"][2], ann["bbox"][3],
                         ann["confidence"], "auto")
                    )
            db_conn.commit()
    except Exception as e:
        logger.warning(f"[auto_annotate] DB save failed (non-critical): {e}")
        try:
            db_conn.rollback()
        except Exception:
            pass
    
    result = {
        "image_id": image_id,
        "annotations": annotations,
        "count": len(annotations),
        "model": model_path,
        "device": "cpu"
    }
    logger.info(f"[auto_annotate] Done: {len(annotations)} annotations for {image_id}")
    return result


# ============================================================================
# T05: Batch Auto-Annotate (Celery + CPU + progress)
# ============================================================================

@app.task(bind=True, name='training.batch_auto_annotate')
def batch_auto_annotate_task(self, dataset_id: str, threshold: float = 0.3, skip_annotated: bool = True):
    """
    T05: Batch auto-annotate all images in dataset.
    Runs on CPU (GPU guard T06), reports progress via Redis pub/sub.
    """
    from ultralytics import YOLO
    import json
    
    logger.info(f"[batch_auto_annotate] Starting for dataset {dataset_id}, threshold={threshold}")
    
    # Get images list
    images = []
    try:
        if db_conn:
            with db_conn.cursor() as cur:
                if skip_annotated:
                    cur.execute(
                        """SELECT ti.id, ti.storage_path FROM training_images ti
                           LEFT JOIN annotations a ON ti.id::text = a.image_id
                           WHERE ti.dataset_id = %s
                           GROUP BY ti.id, ti.storage_path
                           HAVING COUNT(a.id) = 0""",
                        (dataset_id,)
                    )
                else:
                    cur.execute(
                        "SELECT id, storage_path FROM training_images WHERE dataset_id = %s",
                        (dataset_id,)
                    )
                images = [(str(r[0]), r[1]) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"[batch_auto_annotate] DB query failed: {e}")
        try:
            db_conn.rollback()
        except Exception:
            pass
    
    # Also scan filesystem if dataset_id looks like a directory name
    if not images:
        dataset_dirs = [
            f"/app/datasets/{dataset_id}",
            f"/app/training_data/images/{dataset_id}",
        ]
        import hashlib
        for ddir in dataset_dirs:
            if os.path.isdir(ddir):
                for root, dirs, files in os.walk(ddir):
                    for f in files:
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                            fpath = os.path.join(root, f)
                            fhash = hashlib.md5(fpath.encode()).hexdigest()
                            images.append((fhash, fpath))
    
    if not images:
        logger.warning(f"[batch_auto_annotate] No images found for dataset {dataset_id}")
        return {"dataset_id": dataset_id, "annotated": 0, "total": 0, "errors": 0}
    
    # Load model once — CPU ONLY (GPU guard T06)
    model_path = _get_active_model_path()
    model = YOLO(model_path)
    model.to("cpu")  # T06: GPU guard
    
    logger.info(f"[batch_auto_annotate] Model: {model_path}, images: {len(images)}, device=cpu")
    
    total = len(images)
    annotated = 0
    total_annotations = 0
    errors = 0
    
    for i, (image_id, image_path) in enumerate(images):
        try:
            if not image_path or not os.path.exists(image_path):
                errors += 1
                continue
            
            # Run inference on CPU
            results = model.predict(
                source=image_path,
                conf=threshold,
                device="cpu",  # T06: GPU guard
                verbose=False
            )
            
            annotations = []
            if results and len(results) > 0 and results[0].boxes is not None:
                result = results[0]
                img_h, img_w = result.orig_shape
                
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = model.names.get(cls_id, f'class_{cls_id}')
                    mapped_class = PPE_CLASS_MAPPING.get(cls_name.lower(), cls_name)
                    
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    annotations.append({
                        "class_id": cls_id,
                        "class_name": mapped_class,
                        "bbox": [x1 / img_w, y1 / img_h, x2 / img_w, y2 / img_h],
                        "confidence": round(float(box.conf[0]), 4),
                        "source": "auto"
                    })
            
            # Store in Redis
            if redis_client and annotations:
                redis_client.set(
                    f"auto_annotations:{image_id}",
                    json.dumps(annotations),
                    ex=86400
                )
            
            # Save to DB
            try:
                if db_conn and annotations:
                    import uuid
                    with db_conn.cursor() as cur:
                        for ann in annotations:
                            ann_id = str(uuid.uuid4())
                            cur.execute(
                                """INSERT INTO annotations 
                                   (id, image_id, class_name, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, created_by)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                   ON CONFLICT DO NOTHING""",
                                (ann_id, image_id, ann["class_name"],
                                 ann["bbox"][0], ann["bbox"][1], ann["bbox"][2], ann["bbox"][3],
                                 ann["confidence"], "auto")
                            )
                    db_conn.commit()
            except Exception as e:
                logger.warning(f"[batch] DB save failed for {image_id}: {e}")
                try:
                    db_conn.rollback()
                except Exception:
                    pass
            
            annotated += 1
            total_annotations += len(annotations)
            
        except Exception as e:
            logger.error(f"[batch] Error processing {image_id}: {e}")
            errors += 1
        
        # Publish progress via Redis
        if redis_client:
            progress = {
                "current": i + 1,
                "total": total,
                "progress_pct": round((i + 1) / total * 100),
                "annotated": annotated,
                "errors": errors,
                "total_annotations": total_annotations,
                "status": "processing"
            }
            redis_client.publish(
                f"autoannotate:progress:{dataset_id}",
                json.dumps(progress)
            )
            # Also set key for polling
            redis_client.set(
                f"autoannotate:status:{dataset_id}",
                json.dumps(progress),
                ex=3600
            )
        
        # Update Celery task state
        self.update_state(
            state='PROGRESS',
            meta={'current': i + 1, 'total': total, 'pct': round((i + 1) / total * 100)}
        )
    
    # Final status
    final_result = {
        "dataset_id": dataset_id,
        "annotated": annotated,
        "total": total,
        "total_annotations": total_annotations,
        "errors": errors,
        "model": model_path,
        "device": "cpu",
        "status": "completed"
    }
    
    if redis_client:
        redis_client.set(
            f"autoannotate:status:{dataset_id}",
            json.dumps(final_result),
            ex=3600
        )
    
    logger.info(f"[batch_auto_annotate] Done: {annotated}/{total} images, {total_annotations} annotations, {errors} errors")
    return final_result


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    app.start()
