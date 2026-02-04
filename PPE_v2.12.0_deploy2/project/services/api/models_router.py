#!/usr/bin/env python3
"""
Models Router v2.10.46

HuggingFace model catalog, download, and activation API.
Allows switching between pre-trained PPE detection models.
"""

import os
import json
import logging
import threading
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
import redis

# Optional: HuggingFace Hub for downloading models
try:
    from huggingface_hub import hf_hub_download
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    logger_temp = logging.getLogger('api.models')
    logger_temp.warning("huggingface_hub not installed. HuggingFace model downloads will fail.")

# ============================================================================
# Configuration
# ============================================================================

logger = logging.getLogger('api.models')

REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
MODELS_DIR = os.getenv('MODELS_PATH', '/app/models')

# Download status tracking
download_status: Dict[str, Dict[str, Any]] = {}

# ============================================================================
# Model Catalog v2.10.64
# ТОЛЬКО PPE модели - COCO модели убраны из UI (используются автоматически при обучении)
# ============================================================================

MODELS_CATALOG: List[Dict[str, Any]] = [
    # ==========================================================================
    # PPE модели от HuggingFace (готовы к детекции)
    # ==========================================================================
    {
        "id": "keremberke-hardhat-n",
        "name": "PPE Hard Hat (Nano)",
        "description": "Быстрая модель для детекции касок. GTX 1650+",
        "type": "ppe",
        "source": "huggingface",
        "repo": "keremberke/yolov8n-hard-hat-detection",
        "file": "best.pt",
        "size_mb": 6,
        "classes": ["hardhat", "no-hardhat"],
        "recommended": True,
        "speed": "fast",
        "accuracy": "good"
    },
    {
        "id": "keremberke-hardhat-s",
        "name": "PPE Hard Hat (Small)",
        "description": "Баланс скорости и точности. RTX 3060+",
        "type": "ppe",
        "source": "huggingface",
        "repo": "keremberke/yolov8s-hard-hat-detection",
        "file": "best.pt",
        "size_mb": 22,
        "classes": ["hardhat", "no-hardhat"],
        "recommended": True,
        "speed": "medium",
        "accuracy": "better"
    },
    {
        "id": "keremberke-hardhat-m",
        "name": "PPE Hard Hat (Medium)",
        "description": "Высокая точность детекции касок. RTX 4060+",
        "type": "ppe",
        "source": "huggingface",
        "repo": "keremberke/yolov8m-hard-hat-detection",
        "file": "best.pt",
        "size_mb": 50,
        "classes": ["hardhat", "no-hardhat"],
        "recommended": False,
        "speed": "slow",
        "accuracy": "best"
    },
    # ==========================================================================
    # Примечание: Обученные модели добавляются динамически из БД (model_versions)
    # с source="trained" в get_model_catalog()
    # ==========================================================================
]

# ==========================================================================
# Архитектуры для обучения (НЕ показываются в UI Настроек)
# Используются автоматически при запуске обучения
# ==========================================================================
TRAINING_ARCHITECTURES = {
    "yolov8": {
        "name": "YOLOv8",
        "sizes": {
            "n": {"name": "Nano", "file": "yolov8n.pt", "size_mb": 6, "gpu": "GTX 1650+"},
            "s": {"name": "Small", "file": "yolov8s.pt", "size_mb": 22, "gpu": "RTX 3060+"},
            "m": {"name": "Medium", "file": "yolov8m.pt", "size_mb": 50, "gpu": "RTX 4060+"},
            "l": {"name": "Large", "file": "yolov8l.pt", "size_mb": 83, "gpu": "RTX 4080+"},
            "x": {"name": "XLarge", "file": "yolov8x.pt", "size_mb": 130, "gpu": "RTX 4090+"},
        }
    },
    "yolov11": {
        "name": "YOLOv11 (2024)",
        "sizes": {
            "n": {"name": "Nano", "file": "yolo11n.pt", "size_mb": 5, "gpu": "GTX 1650+"},
            "s": {"name": "Small", "file": "yolo11s.pt", "size_mb": 18, "gpu": "RTX 3060+"},
            "m": {"name": "Medium", "file": "yolo11m.pt", "size_mb": 38, "gpu": "RTX 4060+"},
            "l": {"name": "Large", "file": "yolo11l.pt", "size_mb": 49, "gpu": "RTX 4080+"},
            "x": {"name": "XLarge", "file": "yolo11x.pt", "size_mb": 109, "gpu": "RTX 4090+"},
        }
    }
}

# ============================================================================
# Pydantic Models
# ============================================================================

class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    type: str
    source: str
    size_mb: Optional[int] = None
    classes: Optional[Any] = None
    warning: Optional[str] = None
    recommended: bool = False
    is_downloaded: bool = False
    is_active: bool = False

class ModelCatalogResponse(BaseModel):
    models: List[ModelInfo]
    total: int
    active_model_id: Optional[str] = None

class ActiveModelResponse(BaseModel):
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    status: str
    last_updated: Optional[str] = None
    detector_status: Optional[Dict[str, Any]] = None

class ActivateModelRequest(BaseModel):
    model_id: str

class ActivateModelResponse(BaseModel):
    success: bool
    message: str
    model_id: str
    model_name: str

class DownloadStatusResponse(BaseModel):
    model_id: str
    status: str  # pending, downloading, completed, error
    progress: int = 0
    error: Optional[str] = None

# ============================================================================
# Redis Connection
# ============================================================================

def get_redis_client() -> redis.Redis:
    """Get synchronous Redis client."""
    return redis.from_url(REDIS_URL, decode_responses=True)

# ============================================================================
# Router
# ============================================================================

router = APIRouter(prefix="/api/models", tags=["models"])

@router.get("/catalog", response_model=ModelCatalogResponse)
async def get_model_catalog():
    """
    Получить каталог доступных моделей.
    
    Включает:
    - Предустановленные модели HuggingFace
    - COCO модели для тестирования/дообучения
    - Локально обученные модели (из model_versions)
    """
    try:
        r = get_redis_client()
        active_model_id = r.get("system:active_model")
        
        models_dir = Path(MODELS_DIR)
        
        models = []
        
        # 1. Модели из каталога (PPE, COCO)
        for catalog_entry in MODELS_CATALOG:
            size_mb = catalog_entry.get("size_mb")
            is_downloaded = False
            
            # Check if model file exists locally and get size
            if catalog_entry["source"] == "local":
                model_file = models_dir / catalog_entry["file"]
                is_downloaded = model_file.exists()
                # Dynamically get file size for local models
                if is_downloaded and size_mb is None:
                    try:
                        size_mb = round(model_file.stat().st_size / (1024 * 1024), 1)
                    except Exception:
                        pass
            elif catalog_entry["source"] == "ultralytics":
                # COCO model auto-downloads
                is_downloaded = True
            else:
                # Check HuggingFace cache
                model_file = models_dir / f"{catalog_entry['id']}.pt"
                is_downloaded = model_file.exists()
                # Get actual size if downloaded
                if is_downloaded and size_mb is None:
                    try:
                        size_mb = round(model_file.stat().st_size / (1024 * 1024), 1)
                    except Exception:
                        pass
            
            model_info = ModelInfo(
                id=catalog_entry["id"],
                name=catalog_entry["name"],
                description=catalog_entry["description"],
                type=catalog_entry["type"],
                source=catalog_entry["source"],
                size_mb=size_mb,
                classes=catalog_entry.get("classes"),
                warning=catalog_entry.get("warning"),
                recommended=catalog_entry.get("recommended", False),
                is_downloaded=is_downloaded,
                is_active=(active_model_id == catalog_entry["id"])
            )
            
            models.append(model_info)
        
        # 2. v2.10.63: Добавляем ОБУЧЕННЫЕ модели из БД
        try:
            import asyncpg
            db_url = os.getenv('DATABASE_URL', 'postgresql://ppe:ppe_secret@postgres:5432/ppe_detection')
            conn = await asyncpg.connect(db_url)
            try:
                trained_models = await conn.fetch(
                    """SELECT id, name, description, model_path, map50, map50_95, 
                              train_images_count, is_active, created_at
                       FROM model_versions 
                       ORDER BY created_at DESC"""
                )
                
                for row in trained_models:
                    model_id = f"trained-{row['id']}"
                    file_path = row['model_path']
                    
                    # Проверяем существует ли файл
                    is_downloaded = file_path and os.path.exists(file_path)
                    size_mb = None
                    if is_downloaded:
                        try:
                            size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 1)
                        except:
                            pass
                    
                    # Формируем описание с метриками
                    description = row['description'] or ''
                    if row['map50']:
                        description = f"mAP@50: {row['map50']:.1f}% | mAP@50-95: {row['map50_95']:.1f}% | {row['train_images_count'] or 0} изображений"
                    
                    model_info = ModelInfo(
                        id=model_id,
                        name=row['name'] or "Обученная модель (YOLO)",
                        description=description,
                        type="ppe",  # Обученные модели всегда PPE
                        source="trained",
                        size_mb=size_mb,
                        classes=None,
                        warning=None,
                        recommended=row['is_active'],  # Помечаем активную как рекомендованную
                        is_downloaded=is_downloaded,
                        is_active=(active_model_id == model_id) or row['is_active']
                    )
                    models.append(model_info)
                    
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"Could not fetch trained models: {e}")
        
        return ModelCatalogResponse(
            models=models,
            total=len(models),
            active_model_id=active_model_id
        )
    
    except Exception as e:
        logger.error(f"Error fetching model catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", response_model=ActiveModelResponse)
async def get_active_model():
    """
    Получить информацию о текущей активной модели.
    """
    try:
        r = get_redis_client()
        
        model_id = r.get("system:active_model")
        detector_status = r.hgetall("detector:status")
        
        model_name = None
        if model_id:
            # Сначала ищем в каталоге PPE
            for entry in MODELS_CATALOG:
                if entry["id"] == model_id:
                    model_name = entry["name"]
                    break
            
            # Если не нашли - проверяем обученные модели
            if not model_name and model_id.startswith("trained-"):
                try:
                    import asyncpg
                    db_url = os.getenv('DATABASE_URL', 'postgresql://ppe:ppe_secret@postgres:5432/ppe_detection')
                    conn = await asyncpg.connect(db_url)
                    try:
                        db_id = model_id.replace("trained-", "")
                        row = await conn.fetchrow(
                            "SELECT name FROM model_versions WHERE id = $1",
                            db_id
                        )
                        if row:
                            model_name = row['name'] or "Обученная модель (YOLO)"
                    finally:
                        await conn.close()
                except Exception as e:
                    logger.warning(f"Could not fetch trained model info: {e}")
        
        # Determine status
        if not model_id:
            status = "waiting"
        elif detector_status and detector_status.get("status") == "running":
            status = "active"
        else:
            status = "loading"
        
        return ActiveModelResponse(
            model_id=model_id,
            model_name=model_name,
            status=status,
            last_updated=detector_status.get("last_updated") if detector_status else None,
            detector_status=detector_status if detector_status else None
        )
    
    except Exception as e:
        logger.error(f"Error fetching active model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training-architectures")
async def get_training_architectures():
    """
    v2.10.64: Получить архитектуры для обучения.
    COCO модели используются ТОЛЬКО для обучения, не для детекции.
    """
    return {
        "architectures": TRAINING_ARCHITECTURES,
        "note": "Эти модели скачиваются автоматически при обучении"
    }


@router.post("/activate", response_model=ActivateModelResponse)
async def activate_model(request: ActivateModelRequest, background_tasks: BackgroundTasks):
    """
    Активировать модель для детекции.
    
    v2.10.63: Поддержка обученных моделей (trained-*) и Ultralytics
    """
    model_id = request.model_id
    models_dir = Path(MODELS_DIR)
    target_path = models_dir / "ppe_model.pt"
    
    # v2.10.63: Проверяем если это обученная модель
    if model_id.startswith("trained-"):
        return await _activate_trained_model(model_id, models_dir, target_path)
    
    # Ищем модель в каталоге
    model_entry = None
    for entry in MODELS_CATALOG:
        if entry["id"] == model_id:
            model_entry = entry
            break
    
    if not model_entry:
        raise HTTPException(
            status_code=404, 
            detail=f"Модель '{model_id}' не найдена в каталоге"
        )
    
    # Определяем исходный файл модели
    source_path = None
    source_file = model_entry.get("file", "")
    
    if source_file:
        candidate = models_dir / source_file
        if candidate.exists():
            source_path = candidate
    
    if not source_path:
        for ext in [".pt", ""]:
            candidate = models_dir / f"{model_id}{ext}"
            if candidate.exists():
                source_path = candidate
                break
    
    if not source_path:
        for pt_file in models_dir.glob("*.pt"):
            if model_id.replace("-", "").lower() in pt_file.stem.replace("-", "").lower():
                source_path = pt_file
                break
    
    try:
        r = get_redis_client()
        activation_method = "unknown"
        
        if source_path and source_path.exists():
            # Создаём backup
            if target_path.exists():
                backup_path = models_dir / f"ppe_model_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"
                try:
                    shutil.copy2(target_path, backup_path)
                    logger.info(f"Created backup: {backup_path}")
                except Exception as e:
                    logger.warning(f"Could not create backup: {e}")
            
            shutil.copy2(source_path, target_path)
            logger.info(f"✓ Model copied: {source_path} -> {target_path}")
            activation_method = "file_copy"
            
        elif model_entry.get("source") == "ultralytics":
            # Для Ultralytics - скачиваем и копируем
            logger.info(f"Скачиваю Ultralytics модель: {source_file}")
            try:
                from ultralytics import YOLO
                temp_model = YOLO(source_file)
                
                # Находим скачанный файл
                ultralytics_cache = Path.home() / ".cache" / "ultralytics"
                downloaded_path = None
                
                for cache_file in ultralytics_cache.rglob(source_file):
                    downloaded_path = cache_file
                    break
                
                if not downloaded_path and Path(source_file).exists():
                    downloaded_path = Path(source_file)
                
                if downloaded_path and downloaded_path.exists():
                    if target_path.exists():
                        backup_path = models_dir / f"ppe_model_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"
                        shutil.copy2(target_path, backup_path)
                    
                    shutil.copy2(downloaded_path, target_path)
                    logger.info(f"✓ Ultralytics model copied: {downloaded_path} -> {target_path}")
                    activation_method = "ultralytics_download"
                else:
                    # Fallback - маркер
                    marker_path = models_dir / "active_model.json"
                    with open(marker_path, 'w') as f:
                        json.dump({
                            "model_id": model_id,
                            "file": source_file,
                            "source": "ultralytics",
                            "activated_at": datetime.now().isoformat()
                        }, f)
                    activation_method = "ultralytics_marker"
                    
            except Exception as e:
                logger.error(f"Error downloading Ultralytics model: {e}")
                marker_path = models_dir / "active_model.json"
                with open(marker_path, 'w') as f:
                    json.dump({
                        "model_id": model_id,
                        "file": source_file,
                        "source": "ultralytics",
                        "activated_at": datetime.now().isoformat()
                    }, f)
                activation_method = "ultralytics_marker"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Файл модели не найден. Сначала скачайте модель '{model_entry['name']}'"
            )
        
        # Создаём active_model.json
        marker_path = models_dir / "active_model.json"
        with open(marker_path, 'w') as f:
            json.dump({
                "model_id": model_id,
                "file": source_file or model_id + ".pt",
                "source": model_entry.get("source", "unknown"),
                "name": model_entry["name"],
                "type": model_entry.get("type", "unknown"),
                "activated_at": datetime.now().isoformat(),
                "activation_method": activation_method
            }, f)
        
        # Сохраняем в Redis
        r.set("system:active_model", model_id)
        r.hset("system:active_model_info", mapping={
            "id": model_id,
            "name": model_entry["name"],
            "source": model_entry["source"],
            "type": model_entry.get("type", "unknown"),
            "activated_at": datetime.now().isoformat(),
            "activation_method": activation_method
        })
        
        r.publish("system:model_changed", json.dumps({
            "model_id": model_id,
            "source": model_entry["source"],
            "file": str(target_path),
            "timestamp": datetime.now().isoformat()
        }))
        
        logger.info(f"✓ Model activated: {model_id} ({model_entry['name']})")
        
        return ActivateModelResponse(
            success=True,
            message=f"Модель '{model_entry['name']}' активирована! Детектор переключится в течение 30 секунд.",
            model_id=model_id,
            model_name=model_entry["name"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _activate_trained_model(model_id: str, models_dir: Path, target_path: Path):
    """
    v2.10.63: Активировать обученную модель из БД.
    """
    import asyncpg
    
    # Извлекаем ID модели из trained-{id}
    db_model_id = model_id.replace("trained-", "")
    
    try:
        db_url = os.getenv('DATABASE_URL', 'postgresql://ppe:ppe_secret@postgres:5432/ppe_detection')
        conn = await asyncpg.connect(db_url)
        
        try:
            # Получаем информацию о модели
            row = await conn.fetchrow(
                """SELECT id, name, model_path, map50, map50_95
                   FROM model_versions WHERE id = $1""",
                db_model_id
            )
            
            if not row:
                raise HTTPException(404, f"Обученная модель не найдена: {db_model_id}")
            
            source_path = row['model_path']
            if not source_path or not os.path.exists(source_path):
                raise HTTPException(404, f"Файл модели не найден: {source_path}")
            
            # Деактивируем все модели в БД
            await conn.execute("UPDATE model_versions SET is_active = FALSE")
            
            # Активируем выбранную
            await conn.execute(
                "UPDATE model_versions SET is_active = TRUE WHERE id = $1",
                db_model_id
            )
            
            # Создаём backup
            if target_path.exists():
                backup_path = models_dir / f"ppe_model_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"
                try:
                    shutil.copy2(target_path, backup_path)
                    logger.info(f"Created backup: {backup_path}")
                except Exception as e:
                    logger.warning(f"Could not create backup: {e}")
            
            # Копируем модель
            shutil.copy2(source_path, target_path)
            logger.info(f"✓ Trained model copied: {source_path} -> {target_path}")
            
            # Создаём active_model.json
            model_name = row['name'] or "Обученная модель (YOLO)"
            marker_path = models_dir / "active_model.json"
            with open(marker_path, 'w') as f:
                json.dump({
                    "model_id": model_id,
                    "db_id": db_model_id,
                    "file": os.path.basename(source_path),
                    "source": "trained",
                    "name": model_name,
                    "type": "ppe",
                    "map50": float(row['map50']) if row['map50'] else None,
                    "map50_95": float(row['map50_95']) if row['map50_95'] else None,
                    "activated_at": datetime.now().isoformat(),
                    "activation_method": "trained_model"
                }, f)
            
            # Сохраняем в Redis
            r = get_redis_client()
            r.set("system:active_model", model_id)
            r.hset("system:active_model_info", mapping={
                "id": model_id,
                "db_id": db_model_id,
                "name": model_name,
                "source": "trained",
                "type": "ppe",
                "map50": str(row['map50'] or ""),
                "map50_95": str(row['map50_95'] or ""),
                "activated_at": datetime.now().isoformat()
            })
            
            r.publish("system:model_changed", json.dumps({
                "model_id": model_id,
                "source": "trained",
                "file": str(target_path),
                "timestamp": datetime.now().isoformat()
            }))
            
            logger.info(f"✓ Trained model activated: {model_id} ({model_name})")
            
            return ActivateModelResponse(
                success=True,
                message=f"Модель '{model_name}' активирована! Детектор переключится в течение 30 секунд.",
                model_id=model_id,
                model_name=model_name
            )
            
        finally:
            await conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating trained model: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        logger.error(f"Error activating model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detector/status")
async def get_detector_status():
    """
    Получить статус детектора.
    """
    try:
        r = get_redis_client()
        
        status = r.hgetall("detector:status")
        
        if not status:
            return {
                "status": "unknown",
                "message": "Детектор не отвечает или не запущен"
            }
        
        return {
            "status": status.get("status", "unknown"),
            "model": status.get("model", "unknown"),
            "fps": float(status.get("fps", 0)),
            "gpu": status.get("gpu", "unknown"),
            "last_updated": status.get("last_updated"),
            "frames_processed": int(status.get("frames_processed", 0)),
            "violations_detected": int(status.get("violations_detected", 0))
        }
    
    except Exception as e:
        logger.error(f"Error fetching detector status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detector/reload")
async def reload_detector():
    """
    Отправить команду перезагрузки детектору.
    """
    try:
        r = get_redis_client()
        
        r.publish("system:detector_reload", json.dumps({
            "command": "reload",
            "timestamp": datetime.now().isoformat()
        }))
        
        return {
            "success": True,
            "message": "Команда перезагрузки отправлена детектору"
        }
    
    except Exception as e:
        logger.error(f"Error sending reload command: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Model Download Endpoints (v2.10.46)
# ============================================================================

def download_model_task(model_id: str, model_entry: Dict[str, Any]):
    """Background task to download model from HuggingFace."""
    models_dir = Path(MODELS_DIR)
    models_dir.mkdir(parents=True, exist_ok=True)
    
    target_file = models_dir / f"{model_id}.pt"
    
    try:
        download_status[model_id] = {
            "status": "downloading",
            "progress": 10,
            "error": None
        }
        
        source = model_entry.get("source", "")
        
        if source == "huggingface":
            if not HF_AVAILABLE:
                raise Exception("huggingface_hub not installed. Run: pip install huggingface_hub")
            
            repo = model_entry.get("repo", "")
            filename = model_entry.get("file", "best.pt")
            
            if not repo:
                raise Exception(f"No repo specified for model {model_id}")
            
            logger.info(f"Downloading {model_id} from HuggingFace: {repo}/{filename}")
            
            download_status[model_id]["progress"] = 30
            
            # Download from HuggingFace
            downloaded_path = hf_hub_download(
                repo_id=repo,
                filename=filename,
                cache_dir=str(models_dir / ".hf_cache")
            )
            
            download_status[model_id]["progress"] = 80
            
            # Copy to target location
            shutil.copy(downloaded_path, target_file)
            
            download_status[model_id] = {
                "status": "completed",
                "progress": 100,
                "error": None
            }
            
            logger.info(f"Successfully downloaded model {model_id} to {target_file}")
            
        elif source == "ultralytics":
            # Ultralytics models auto-download via YOLO
            download_status[model_id] = {
                "status": "completed",
                "progress": 100,
                "error": None
            }
            logger.info(f"Ultralytics model {model_id} will auto-download on first use")
            
        elif source == "local":
            download_status[model_id] = {
                "status": "error",
                "progress": 0,
                "error": "Локальные модели создаются через Training UI"
            }
            
        else:
            raise Exception(f"Unknown source type: {source}")
            
    except Exception as e:
        logger.error(f"Error downloading model {model_id}: {e}")
        download_status[model_id] = {
            "status": "error",
            "progress": 0,
            "error": str(e)
        }


@router.post("/{model_id}/download")
async def download_model(model_id: str, background_tasks: BackgroundTasks):
    """
    Скачать модель из каталога.
    
    Поддерживает HuggingFace и Ultralytics модели.
    """
    # Find model in catalog
    model_entry = None
    for entry in MODELS_CATALOG:
        if entry["id"] == model_id:
            model_entry = entry
            break
    
    if not model_entry:
        raise HTTPException(
            status_code=404,
            detail=f"Модель '{model_id}' не найдена в каталоге"
        )
    
    # Check if already downloading
    if model_id in download_status and download_status[model_id].get("status") == "downloading":
        raise HTTPException(
            status_code=400,
            detail="Скачивание уже выполняется"
        )
    
    # Check if already downloaded
    models_dir = Path(MODELS_DIR)
    target_file = models_dir / f"{model_id}.pt"
    
    if target_file.exists():
        raise HTTPException(
            status_code=400,
            detail="Модель уже скачана"
        )
    
    # Start download in background
    download_status[model_id] = {
        "status": "pending",
        "progress": 0,
        "error": None
    }
    
    background_tasks.add_task(download_model_task, model_id, model_entry)
    
    return {"status": "started", "model_id": model_id}


@router.get("/{model_id}/download-status", response_model=DownloadStatusResponse)
async def get_download_status(model_id: str):
    """
    Получить статус скачивания модели.
    """
    if model_id not in download_status:
        # Check if model file exists
        models_dir = Path(MODELS_DIR)
        target_file = models_dir / f"{model_id}.pt"
        
        if target_file.exists():
            return DownloadStatusResponse(
                model_id=model_id,
                status="completed",
                progress=100
            )
        
        return DownloadStatusResponse(
            model_id=model_id,
            status="not_started",
            progress=0
        )
    
    status = download_status[model_id]
    return DownloadStatusResponse(
        model_id=model_id,
        status=status.get("status", "unknown"),
        progress=status.get("progress", 0),
        error=status.get("error")
    )


@router.delete("/{model_id}")
async def delete_model(model_id: str):
    """
    Удалить скачанную модель.
    """
    models_dir = Path(MODELS_DIR)
    target_file = models_dir / f"{model_id}.pt"
    
    if not target_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Модель '{model_id}' не найдена"
        )
    
    # Check if model is active
    try:
        r = get_redis_client()
        active_model = r.get("system:active_model")
        if active_model == model_id:
            raise HTTPException(
                status_code=400,
                detail="Нельзя удалить активную модель"
            )
    except redis.RedisError:
        pass  # Proceed if Redis not available
    
    target_file.unlink()
    
    # Clear download status
    if model_id in download_status:
        del download_status[model_id]
    
    logger.info(f"Deleted model: {model_id}")
    
    return {"status": "deleted", "model_id": model_id}
