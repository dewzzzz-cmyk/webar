"""
Settings API Router - Управление настройками системы
- Модели: список, скачивание, активация
- Камеры: CRUD, тестирование RTSP
- GPU: статус, настройки
"""

import os
import asyncio
import logging
import subprocess
import urllib.request
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger('settings_api')

# ============================================================================
# Configuration
# ============================================================================

MODELS_PATH = Path(os.getenv('MODELS_PATH', '/app/models'))
MODELS_PATH.mkdir(parents=True, exist_ok=True)

CAMERAS_CONFIG_PATH = Path(os.getenv('CAMERAS_CONFIG_PATH', '/app/configs/cameras.yaml'))

# Доступные модели для скачивания
AVAILABLE_MODELS = {
    "yolov8n": {
        "name": "YOLOv8 Nano",
        "description": "Быстрая модель для слабых GPU (базовая, COCO)",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8n.pt",
        "size_mb": 6.3,
        "speed": "Быстрая",
        "accuracy": "Базовая",
        "recommended_gpu": "GTX 1650+",
        "type": "base"
    },
    "yolov8s": {
        "name": "YOLOv8 Small",
        "description": "Баланс скорости и точности (базовая, COCO)",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8s.pt",
        "size_mb": 22.5,
        "speed": "Средняя",
        "accuracy": "Хорошая",
        "recommended_gpu": "RTX 2060+",
        "type": "base"
    },
    "yolov8m": {
        "name": "YOLOv8 Medium",
        "description": "Высокая точность (базовая, COCO)",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8m.pt",
        "size_mb": 52.0,
        "speed": "Средняя",
        "accuracy": "Высокая",
        "recommended_gpu": "RTX 3060+",
        "type": "base"
    },
    "yolov8l": {
        "name": "YOLOv8 Large",
        "description": "Максимальная точность (базовая, COCO)",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8l.pt",
        "size_mb": 87.7,
        "speed": "Медленная",
        "accuracy": "Очень высокая",
        "recommended_gpu": "RTX 3080+",
        "type": "base"
    },
    "yolov8x": {
        "name": "YOLOv8 XLarge",
        "description": "Максимум для RTX 4090/5090 (базовая, COCO)",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8x.pt",
        "size_mb": 136.7,
        "speed": "Медленная",
        "accuracy": "Максимальная",
        "recommended_gpu": "RTX 4080+",
        "type": "base"
    },
    "yolov11n": {
        "name": "YOLOv11 Nano (NEW)",
        "description": "Новейшая архитектура, быстрая",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt",
        "size_mb": 5.4,
        "speed": "Очень быстрая",
        "accuracy": "Хорошая",
        "recommended_gpu": "GTX 1650+",
        "type": "base"
    },
    "yolov11m": {
        "name": "YOLOv11 Medium (NEW)",
        "description": "Новейшая архитектура, баланс",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11m.pt",
        "size_mb": 38.8,
        "speed": "Средняя",
        "accuracy": "Высокая",
        "recommended_gpu": "RTX 3060+",
        "type": "base"
    },
    "yolov11x": {
        "name": "YOLOv11 XLarge (NEW)",
        "description": "Новейшая архитектура для RTX 5090",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11x.pt",
        "size_mb": 109.3,
        "speed": "Медленная",
        "accuracy": "Максимальная",
        "recommended_gpu": "RTX 4080+",
        "type": "base"
    },
}

# Состояние скачивания
download_status = {}


# ============================================================================
# Schemas
# ============================================================================

class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    size_mb: float
    speed: str
    accuracy: str
    recommended_gpu: str
    type: str
    is_downloaded: bool = False
    is_active: bool = False
    file_path: Optional[str] = None


class DownloadStatus(BaseModel):
    model_id: str
    status: str  # pending, downloading, completed, error
    progress: int = 0
    error: Optional[str] = None


class CameraCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-z0-9_]+$')
    name: str = Field(..., min_length=1, max_length=100)
    rtsp_url: str = Field(..., min_length=10)
    fps: int = Field(5, ge=1, le=30)
    zone_id: Optional[str] = None
    enabled: bool = True


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    fps: Optional[int] = Field(None, ge=1, le=30)
    zone_id: Optional[str] = None
    enabled: Optional[bool] = None


class CameraResponse(BaseModel):
    id: str
    name: str
    rtsp_url: str
    fps: int
    zone_id: Optional[str]
    enabled: bool
    status: str = "unknown"


class GPUInfo(BaseModel):
    available: bool
    name: Optional[str] = None
    memory_total_mb: Optional[int] = None
    memory_used_mb: Optional[int] = None
    memory_free_mb: Optional[int] = None
    cuda_version: Optional[str] = None
    driver_version: Optional[str] = None
    temperature: Optional[int] = None
    utilization: Optional[int] = None


class SystemSettings(BaseModel):
    confidence_threshold: float = Field(0.5, ge=0.1, le=1.0)
    iou_threshold: float = Field(0.45, ge=0.1, le=1.0)
    max_detections: int = Field(100, ge=1, le=1000)
    device: str = "auto"  # auto, cpu, cuda:0, cuda:1
    half_precision: bool = True  # FP16 для GPU
    batch_size: int = Field(1, ge=1, le=8)


# ============================================================================
# Router Factory
# ============================================================================

def create_settings_router(redis_client=None):
    """Create settings router with optional Redis client."""
    
    router = APIRouter()
    
    # ========================================================================
    # Models API
    # ========================================================================
    
    @router.get("/models", response_model=List[ModelInfo])
    async def list_models():
        """Список доступных моделей."""
        models = []
        
        # Получаем активную модель
        active_model_path = MODELS_PATH / "ppe_model.pt"
        active_model_real = None
        if active_model_path.is_symlink():
            active_model_real = active_model_path.resolve().name
        elif active_model_path.exists():
            active_model_real = "ppe_model.pt"
        
        for model_id, info in AVAILABLE_MODELS.items():
            file_path = MODELS_PATH / f"{model_id}.pt"
            is_downloaded = file_path.exists()
            is_active = active_model_real == f"{model_id}.pt"
            
            models.append(ModelInfo(
                id=model_id,
                name=info["name"],
                description=info["description"],
                size_mb=info["size_mb"],
                speed=info["speed"],
                accuracy=info["accuracy"],
                recommended_gpu=info["recommended_gpu"],
                type=info["type"],
                is_downloaded=is_downloaded,
                is_active=is_active,
                file_path=str(file_path) if is_downloaded else None
            ))
        
        # Добавляем кастомные модели из папки
        for pt_file in MODELS_PATH.glob("*.pt"):
            if pt_file.stem not in AVAILABLE_MODELS and pt_file.stem != "ppe_model":
                models.append(ModelInfo(
                    id=pt_file.stem,
                    name=f"Custom: {pt_file.stem}",
                    description="Пользовательская модель",
                    size_mb=pt_file.stat().st_size / 1024 / 1024,
                    speed="Неизвестно",
                    accuracy="Неизвестно",
                    recommended_gpu="Неизвестно",
                    type="custom",
                    is_downloaded=True,
                    is_active=active_model_real == pt_file.name,
                    file_path=str(pt_file)
                ))
        
        return models
    
    @router.post("/models/{model_id}/download")
    async def download_model(model_id: str, background_tasks: BackgroundTasks):
        """Скачать модель."""
        if model_id not in AVAILABLE_MODELS:
            raise HTTPException(404, f"Модель {model_id} не найдена в каталоге")
        
        if model_id in download_status and download_status[model_id]["status"] == "downloading":
            raise HTTPException(400, "Скачивание уже выполняется")
        
        file_path = MODELS_PATH / f"{model_id}.pt"
        if file_path.exists():
            raise HTTPException(400, "Модель уже скачана")
        
        # Инициализируем статус
        download_status[model_id] = {
            "status": "pending",
            "progress": 0,
            "error": None
        }
        
        # Запускаем скачивание в фоне
        background_tasks.add_task(download_model_task, model_id)
        
        return {"status": "started", "model_id": model_id}
    
    @router.get("/models/{model_id}/download-status", response_model=DownloadStatus)
    async def get_download_status(model_id: str):
        """Статус скачивания модели."""
        if model_id not in download_status:
            file_path = MODELS_PATH / f"{model_id}.pt"
            if file_path.exists():
                return DownloadStatus(model_id=model_id, status="completed", progress=100)
            return DownloadStatus(model_id=model_id, status="not_started", progress=0)
        
        status = download_status[model_id]
        return DownloadStatus(
            model_id=model_id,
            status=status["status"],
            progress=status["progress"],
            error=status.get("error")
        )
    
    @router.post("/models/{model_id}/activate")
    async def activate_model(model_id: str):
        """Активировать модель (сделать текущей)."""
        file_path = MODELS_PATH / f"{model_id}.pt"
        
        if not file_path.exists():
            raise HTTPException(404, f"Модель {model_id} не скачана")
        
        # Создаём симлинк ppe_model.pt -> выбранная модель
        active_path = MODELS_PATH / "ppe_model.pt"
        
        # Удаляем старый симлинк/файл
        if active_path.exists() or active_path.is_symlink():
            active_path.unlink()
        
        # Создаём новый симлинк
        active_path.symlink_to(file_path.name)
        
        logger.info(f"Activated model: {model_id}")
        
        # Уведомляем detector о смене модели через Redis
        if redis_client:
            await redis_client.publish("system:model_changed", model_id)
        
        return {"status": "activated", "model_id": model_id}
    
    @router.delete("/models/{model_id}")
    async def delete_model(model_id: str):
        """Удалить скачанную модель."""
        file_path = MODELS_PATH / f"{model_id}.pt"
        
        if not file_path.exists():
            raise HTTPException(404, f"Модель {model_id} не найдена")
        
        # Проверяем, не активна ли модель
        active_path = MODELS_PATH / "ppe_model.pt"
        if active_path.is_symlink() and active_path.resolve() == file_path:
            raise HTTPException(400, "Нельзя удалить активную модель")
        
        file_path.unlink()
        logger.info(f"Deleted model: {model_id}")
        
        return {"status": "deleted", "model_id": model_id}
    
    # ========================================================================
    # GPU API
    # ========================================================================
    
    @router.get("/gpu", response_model=GPUInfo)
    async def get_gpu_info():
        """Информация о GPU (читаем из Redis - публикуется detector'ом)."""
        try:
            # Сначала пробуем получить из Redis (публикуется detector'ом)
            if redis_client:
                try:
                    gpu_data = await redis_client.hgetall('detector:gpu')
                    if gpu_data:
                        # Преобразуем bytes ключи в строки
                        gpu_data = {
                            (k.decode() if isinstance(k, bytes) else k): 
                            (v.decode() if isinstance(v, bytes) else v) 
                            for k, v in gpu_data.items()
                        }
                        
                        if gpu_data.get('available') == 'True':
                            return GPUInfo(
                                available=True,
                                name=gpu_data.get('name') or None,
                                memory_total_mb=int(gpu_data['memory_total_mb']) if gpu_data.get('memory_total_mb') else None,
                                memory_used_mb=int(gpu_data['memory_used_mb']) if gpu_data.get('memory_used_mb') else None,
                                memory_free_mb=int(gpu_data['memory_free_mb']) if gpu_data.get('memory_free_mb') else None,
                                cuda_version=gpu_data.get('cuda_version') or None,
                                driver_version=gpu_data.get('pytorch_version') or None,  # показываем PyTorch версию
                                temperature=None,
                                utilization=None
                            )
                except Exception as e:
                    logger.debug(f"Redis GPU info not available: {e}")
            
            # Fallback: пробуем nvidia-smi напрямую (если API контейнер имеет доступ)
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,driver_version,temperature.gpu,utilization.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                logger.debug(f"nvidia-smi failed: {result.stderr}")
                return GPUInfo(available=False)
            
            parts = [p.strip() for p in result.stdout.strip().split(', ')]
            if len(parts) >= 7:
                cuda_result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=compute_cap', '--format=csv,noheader'],
                    capture_output=True, text=True, timeout=5
                )
                cuda_version = None
                if cuda_result.returncode == 0:
                    cuda_version = f"CC {cuda_result.stdout.strip()}"
                
                return GPUInfo(
                    available=True,
                    name=parts[0],
                    memory_total_mb=int(float(parts[1])),
                    memory_used_mb=int(float(parts[2])),
                    memory_free_mb=int(float(parts[3])),
                    driver_version=parts[4],
                    temperature=int(float(parts[5])) if parts[5] else None,
                    utilization=int(float(parts[6])) if parts[6] else None,
                    cuda_version=cuda_version
                )
            
            return GPUInfo(available=False)
            
        except FileNotFoundError:
            logger.debug("nvidia-smi not found")
            return GPUInfo(available=False)
        except Exception as e:
            logger.error(f"Error getting GPU info: {e}")
            return GPUInfo(available=False)
    
    # ========================================================================
    # Roboflow API Key Management
    # ========================================================================
    
    ROBOFLOW_KEY_FILE = Path(os.getenv('CONFIG_PATH', '/app/configs')) / 'roboflow_api_key.txt'
    
    @router.get("/roboflow-api-key")
    async def get_roboflow_api_key():
        """Получить API ключ Roboflow (маскированный)."""
        try:
            if ROBOFLOW_KEY_FILE.exists():
                api_key = ROBOFLOW_KEY_FILE.read_text().strip()
                if api_key:
                    return {
                        "api_key": api_key,
                        "masked": f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
                    }
            return {"api_key": None, "masked": None}
        except Exception as e:
            logger.error(f"Error reading Roboflow API key: {e}")
            return {"api_key": None, "masked": None}
    
    @router.post("/roboflow-api-key")
    async def save_roboflow_api_key(data: dict):
        """Сохранить API ключ Roboflow."""
        api_key = data.get("api_key", "").strip()
        
        if not api_key:
            raise HTTPException(400, "API ключ не может быть пустым")
        
        try:
            ROBOFLOW_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            ROBOFLOW_KEY_FILE.write_text(api_key)
            logger.info("Roboflow API key saved")
            return {"status": "saved", "masked": f"{api_key[:8]}...{api_key[-4:]}"}
        except Exception as e:
            logger.error(f"Error saving Roboflow API key: {e}")
            raise HTTPException(500, f"Ошибка сохранения: {e}")
    
    @router.delete("/roboflow-api-key")
    async def delete_roboflow_api_key():
        """Удалить API ключ Roboflow."""
        try:
            if ROBOFLOW_KEY_FILE.exists():
                ROBOFLOW_KEY_FILE.unlink()
                logger.info("Roboflow API key deleted")
            return {"status": "deleted"}
        except Exception as e:
            logger.error(f"Error deleting Roboflow API key: {e}")
            raise HTTPException(500, f"Ошибка удаления: {e}")
    
    # ========================================================================
    # Cameras API
    # ========================================================================
    
    @router.get("/cameras", response_model=List[CameraResponse])
    async def list_cameras():
        """Список камер."""
        cameras = load_cameras_config()
        return cameras
    
    @router.post("/cameras", response_model=CameraResponse)
    async def create_camera(camera: CameraCreate):
        """Добавить камеру."""
        cameras = load_cameras_config()
        
        # Проверяем уникальность ID
        if any(c["id"] == camera.id for c in cameras):
            raise HTTPException(400, f"Камера с ID {camera.id} уже существует")
        
        # Максимум 8 камер
        if len(cameras) >= 8:
            raise HTTPException(400, "Достигнут лимит в 8 камер")
        
        new_camera = camera.model_dump()
        new_camera["status"] = "unknown"
        cameras.append(new_camera)
        
        save_cameras_config(cameras)
        
        # Уведомляем capture сервис
        if redis_client:
            await redis_client.publish("system:cameras_updated", "reload")
        
        return CameraResponse(**new_camera)
    
    @router.put("/cameras/{camera_id}", response_model=CameraResponse)
    async def update_camera(camera_id: str, update: CameraUpdate):
        """Обновить камеру."""
        cameras = load_cameras_config()
        
        camera_idx = next((i for i, c in enumerate(cameras) if c["id"] == camera_id), None)
        if camera_idx is None:
            raise HTTPException(404, f"Камера {camera_id} не найдена")
        
        # Обновляем только переданные поля
        update_data = update.model_dump(exclude_unset=True)
        cameras[camera_idx].update(update_data)
        
        save_cameras_config(cameras)
        
        if redis_client:
            await redis_client.publish("system:cameras_updated", "reload")
        
        return CameraResponse(**cameras[camera_idx])
    
    @router.delete("/cameras/{camera_id}")
    async def delete_camera(camera_id: str):
        """Удалить камеру."""
        cameras = load_cameras_config()
        
        camera_idx = next((i for i, c in enumerate(cameras) if c["id"] == camera_id), None)
        if camera_idx is None:
            raise HTTPException(404, f"Камера {camera_id} не найдена")
        
        del cameras[camera_idx]
        save_cameras_config(cameras)
        
        if redis_client:
            await redis_client.publish("system:cameras_updated", "reload")
        
        return {"status": "deleted", "camera_id": camera_id}
    
    @router.post("/cameras/{camera_id}/toggle")
    async def toggle_camera(camera_id: str):
        """Включить/выключить камеру (quick toggle)."""
        cameras = load_cameras_config()
        
        camera_idx = next((i for i, c in enumerate(cameras) if c["id"] == camera_id), None)
        if camera_idx is None:
            raise HTTPException(404, f"Камера {camera_id} не найдена")
        
        # Toggle enabled state
        cameras[camera_idx]["enabled"] = not cameras[camera_idx].get("enabled", True)
        save_cameras_config(cameras)
        
        if redis_client:
            await redis_client.publish("system:cameras_updated", "reload")
        
        return {
            "status": "toggled",
            "camera_id": camera_id,
            "enabled": cameras[camera_idx]["enabled"]
        }

    @router.post("/cameras/{camera_id}/test")
    async def test_camera(camera_id: str):
        """Тестировать подключение к камере."""
        cameras = load_cameras_config()
        
        camera = next((c for c in cameras if c["id"] == camera_id), None)
        if not camera:
            raise HTTPException(404, f"Камера {camera_id} не найдена")
        
        rtsp_url = camera.get("rtsp_url") or camera.get("url", "")
        if not rtsp_url:
            return {"status": "error", "message": "URL камеры не указан"}
        
        cap = None
        try:
            import cv2
            cap = cv2.VideoCapture(rtsp_url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Таймаут 10 секунд
            start = datetime.now()
            success = False
            frame_info = None
            
            while (datetime.now() - start).seconds < 10:
                ret, frame = cap.read()
                if ret:
                    success = True
                    frame_info = {
                        "width": frame.shape[1],
                        "height": frame.shape[0],
                        "channels": frame.shape[2] if len(frame.shape) > 2 else 1
                    }
                    break
            
            if success:
                return {
                    "status": "success",
                    "message": "Подключение успешно",
                    "frame_info": frame_info
                }
            else:
                return {
                    "status": "error",
                    "message": "Не удалось получить кадр (таймаут 10 сек)"
                }
                
        except ImportError:
            return {
                "status": "error", 
                "message": "OpenCV не установлен"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            if cap is not None:
                cap.release()
    
    # ========================================================================
    # System Settings API
    # ========================================================================
    
    @router.get("/system", response_model=SystemSettings)
    async def get_system_settings():
        """Получить системные настройки."""
        # TODO: Загружать из Redis/DB
        return SystemSettings()
    
    @router.put("/system", response_model=SystemSettings)
    async def update_system_settings(settings: SystemSettings):
        """Обновить системные настройки."""
        # TODO: Сохранять в Redis/DB
        
        if redis_client:
            import json
            await redis_client.set("system:settings", json.dumps(settings.model_dump()))
            await redis_client.publish("system:settings_updated", "reload")
        
        return settings
    
    return router


# ============================================================================
# Helper Functions
# ============================================================================

def download_model_task(model_id: str):
    """Background task для скачивания модели."""
    global download_status
    
    try:
        download_status[model_id] = {"status": "downloading", "progress": 0, "error": None}
        
        model_info = AVAILABLE_MODELS[model_id]
        url = model_info["url"]
        file_path = MODELS_PATH / f"{model_id}.pt"
        temp_path = MODELS_PATH / f"{model_id}.pt.tmp"
        
        def progress_hook(count, block_size, total_size):
            if total_size > 0:
                progress = int(count * block_size * 100 / total_size)
                download_status[model_id]["progress"] = min(progress, 99)
        
        urllib.request.urlretrieve(url, temp_path, progress_hook)
        
        # Переименовываем после успешного скачивания
        shutil.move(temp_path, file_path)
        
        download_status[model_id] = {"status": "completed", "progress": 100, "error": None}
        logger.info(f"Model {model_id} downloaded successfully")
        
    except Exception as e:
        download_status[model_id] = {"status": "error", "progress": 0, "error": str(e)}
        logger.error(f"Error downloading model {model_id}: {e}")
        
        # Удаляем временный файл
        temp_path = MODELS_PATH / f"{model_id}.pt.tmp"
        if temp_path.exists():
            temp_path.unlink()


def load_cameras_config() -> List[dict]:
    """Загрузить конфигурацию камер из YAML."""
    import yaml
    
    if not CAMERAS_CONFIG_PATH.exists():
        return []
    
    try:
        with open(CAMERAS_CONFIG_PATH) as f:
            config = yaml.safe_load(f) or {}
        
        cameras = config.get("cameras", [])
        
        # Нормализуем поля для соответствия модели CameraResponse
        normalized = []
        for cam in cameras:
            if not isinstance(cam, dict):
                continue
            if not cam.get("id"):
                continue
            
            normalized.append({
                "id": cam.get("id"),
                "name": cam.get("name", cam.get("id")),
                "rtsp_url": cam.get("rtsp_url") or cam.get("url", ""),
                "fps": cam.get("fps", 5),
                "zone_id": cam.get("zone_id"),
                "enabled": cam.get("enabled", True),
                "status": cam.get("status", "unknown")
            })
        
        return normalized
    except Exception as e:
        logger.error(f"Error loading cameras config: {e}")
        return []


def save_cameras_config(cameras: List[dict]):
    """Сохранить конфигурацию камер в YAML."""
    import yaml
    
    # Нормализуем для YAML (используем url для совместимости с capture сервисом)
    yaml_cameras = []
    for cam in cameras:
        yaml_cam = {
            "id": cam.get("id"),
            "name": cam.get("name"),
            "url": cam.get("rtsp_url") or cam.get("url", ""),
            "fps": cam.get("fps", 5),
            "enabled": cam.get("enabled", True)
        }
        if cam.get("zone_id"):
            yaml_cam["zone_id"] = cam["zone_id"]
        yaml_cameras.append(yaml_cam)
    
    config = {"cameras": yaml_cameras}
    
    CAMERAS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with open(CAMERAS_CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    logger.info(f"Saved {len(cameras)} cameras to config")
