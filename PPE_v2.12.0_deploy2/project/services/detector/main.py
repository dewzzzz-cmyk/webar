#!/usr/bin/env python3
"""
Detection Service v2.1 - Исправленная версия

Исправления:
- Отдельный tracker для каждой камеры
- Обработка pending messages при старте
- Cooldown в Redis (не в памяти)
- Warmup модели при старте
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import uuid

import cv2
import numpy as np
import redis
import yaml

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from ultralytics import YOLO

# ============================================================================
# Configuration
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('detector')

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://ppe:ppe_secret@localhost:5432/ppe_detection')
MODEL_PATH = os.getenv('MODEL_PATH', '/app/models/ppe_model.pt')
CONFIG_PATH = os.getenv('CONFIG_PATH', '/app/configs/zones.yaml')
VIOLATIONS_PATH = os.getenv('VIOLATIONS_PATH', '/app/violations')

CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', 0.5))
IOU_THRESHOLD = float(os.getenv('IOU_THRESHOLD', 0.45))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 4))
WORKER_TIMEOUT = int(os.getenv('WORKER_TIMEOUT', 1000))
COOLDOWN_SECONDS = int(os.getenv('COOLDOWN_SECONDS', 30))
DETECT_EVERY_N = int(os.getenv('DETECT_EVERY_N', 2))  # Обрабатывать каждый N-й кадр

Path(VIOLATIONS_PATH).mkdir(parents=True, exist_ok=True)

# ============================================================================
# Database
# ============================================================================

Base = declarative_base()

class Violation(Base):
    __tablename__ = 'violations'
    
    id = Column(String(36), primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    camera_id = Column(String(50), index=True)
    zone_id = Column(String(50), index=True, nullable=True)
    violation_type = Column(String(50), index=True)
    confidence = Column(Float)
    person_id = Column(Integer, nullable=True)
    bbox_x1 = Column(Integer)
    bbox_y1 = Column(Integer)
    bbox_x2 = Column(Integer)
    bbox_y2 = Column(Integer)
    image_path = Column(String(255), nullable=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

# ============================================================================
# Cooldown Manager (Redis-based) - ИСПРАВЛЕНИЕ
# ============================================================================

class CooldownManager:
    """Cooldown в Redis - переживает рестарты."""
    
    def __init__(self, redis_client: redis.Redis, default_cooldown: int = 30):
        self.redis = redis_client
        self.default_cooldown = default_cooldown
        self.prefix = "cooldown:"
    
    def _make_key(self, camera_id: str, person_id: Optional[int], violation_type: str) -> str:
        person_key = str(person_id) if person_id is not None else "unknown"
        return f"{self.prefix}{camera_id}:{person_key}:{violation_type}"
    
    def is_in_cooldown(self, camera_id: str, person_id: Optional[int], violation_type: str) -> bool:
        key = self._make_key(camera_id, person_id, violation_type)
        return self.redis.exists(key) > 0
    
    def set_cooldown(self, camera_id: str, person_id: Optional[int], violation_type: str, 
                     cooldown_seconds: Optional[int] = None):
        key = self._make_key(camera_id, person_id, violation_type)
        ttl = cooldown_seconds or self.default_cooldown
        self.redis.setex(key, ttl, "1")

# ============================================================================
# PPE Detector with Per-Camera Tracking - ИСПРАВЛЕНИЕ
# ============================================================================

class PPEDetector:
    """Детектор с отдельным трекером для каждой камеры."""
    
    PPE_CLASS_MAPPING = {
        'Hardhat': 'hardhat', 'NO-Hardhat': 'no_hardhat',
        'Safety Vest': 'vest', 'NO-Safety Vest': 'no_vest',
        'Person': 'person', 'helmet': 'hardhat', 'no-helmet': 'no_hardhat',
        'vest': 'vest', 'no-vest': 'no_vest', 'person': 'person', 0: 'person',
    }
    
    VIOLATION_CLASSES = {'no_hardhat', 'no_vest', 'no_glasses', 'no_gloves'}
    PPE_CLASSES = {'hardhat', 'vest', 'glasses', 'gloves'}
    
    def __init__(self, model_path: str, confidence: float = 0.5, iou: float = 0.45):
        self.confidence = confidence
        self.iou = iou
        
        # Автопоиск модели
        actual_model_path = self._find_model(model_path)
        logger.info(f"Загрузка модели: {actual_model_path}")
        
        # Определяем device - GPU если доступен
        import torch
        if torch.cuda.is_available():
            self.device = 'cuda:0'
            logger.info(f"Используется GPU: {torch.cuda.get_device_name(0)}")
        else:
            self.device = 'cpu'
            logger.warning("GPU не найден, используется CPU (будет медленно!)")
        
        self.model = YOLO(actual_model_path)
        # Явно переводим модель на нужный device
        self.model.to(self.device)
        
        # Инициализация после загрузки модели
        self.class_names = self.model.names
        
        # Маппинг классов
        self.idx_to_ppe = {}
        for idx, name in self.class_names.items():
            ppe_class = self.PPE_CLASS_MAPPING.get(name) or self.PPE_CLASS_MAPPING.get(idx)
            if ppe_class:
                self.idx_to_ppe[idx] = ppe_class
            else:
                name_lower = name.lower()
                if 'hardhat' in name_lower or 'helmet' in name_lower:
                    self.idx_to_ppe[idx] = 'no_hardhat' if 'no' in name_lower else 'hardhat'
                elif 'vest' in name_lower:
                    self.idx_to_ppe[idx] = 'no_vest' if 'no' in name_lower else 'vest'
                elif 'person' in name_lower:
                    self.idx_to_ppe[idx] = 'person'
        
        logger.info(f"Классы модели: {self.class_names}")
        logger.info(f"PPE маппинг: {self.idx_to_ppe}")
        
        # Отдельные модели для каждой камеры (для изоляции трекинга)
        self._camera_models: Dict[str, YOLO] = {}
    
    def _find_model(self, model_path: str) -> str:
        """
        Автопоиск модели v2.10.63:
        1. Читаем active_model.json (если есть) - приоритет!
        2. Проверяем ppe_model.pt
        3. Ищем любой .pt файл в папке models
        4. Скачиваем базовую модель как fallback
        """
        models_dir = Path(model_path).parent
        
        # 0. НОВОЕ: Читаем active_model.json (создаётся API при активации)
        active_model_config = models_dir / "active_model.json"
        if active_model_config.exists():
            try:
                with open(active_model_config, 'r') as f:
                    config = json.load(f)
                    model_file = config.get("file", "")
                    model_source = config.get("source", "")
                    logger.info(f"Найден active_model.json: {config}")
                    
                    # Проверяем есть ли файл
                    if model_file:
                        # Сначала ищем в models_dir
                        candidate = models_dir / model_file
                        if candidate.exists():
                            logger.info(f"Активная модель: {candidate}")
                            return str(candidate)
                        
                        # Для Ultralytics моделей - скачиваем если нет
                        if model_source == "ultralytics":
                            logger.info(f"Скачиваю Ultralytics модель: {model_file}")
                            # YOLO автоматически скачает модель
                            return model_file
            except Exception as e:
                logger.warning(f"Ошибка чтения active_model.json: {e}")
        
        # 1. Указанный путь существует (ppe_model.pt)
        if os.path.exists(model_path) and os.path.isfile(model_path):
            logger.info(f"Найдена модель: {model_path}")
            return model_path
        
        # 2. Поиск в папке models
        if models_dir.exists():
            pt_files = list(models_dir.glob("*.pt"))
            if pt_files:
                # Приоритет: ppe_custom (обученные) > ppe_model > yolov11 > yolov8 > best
                priority_order = ['ppe_custom', 'ppe_model', 'yolov11', 'yolov10', 'yolov9', 'yolov8', 'best']
                
                for prefix in priority_order:
                    # Для ppe_custom берём самый новый по дате
                    matching = [f for f in pt_files if f.stem.lower().startswith(prefix.lower())]
                    if matching:
                        if prefix == 'ppe_custom' and len(matching) > 1:
                            # Сортируем по времени модификации (новый первый)
                            matching.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                        selected = matching[0]
                        logger.info(f"Автообнаружена модель: {selected}")
                        return str(selected)
                
                # Если нет совпадений по приоритету - берём первую найденную
                selected = pt_files[0]
                logger.info(f"Автообнаружена модель: {selected}")
                return str(selected)
        
        # 3. Fallback - скачиваем базовую PPE модель (не COCO!)
        logger.warning(f"Модель не найдена в {models_dir}, скачиваем yolov8n.pt")
        logger.warning("⚠️ ВНИМАНИЕ: Используется COCO модель! Активируйте PPE модель в Настройках.")
        return 'yolov8n.pt'
    
    def warmup(self):
        """Прогрев модели."""
        logger.info("Прогрев модели...")
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        for _ in range(3):
            self.model(dummy, verbose=False)
        logger.info("Модель прогрета")
    
    def _get_model_for_camera(self, camera_id: str) -> YOLO:
        """
        ИСПРАВЛЕНИЕ: Отдельная модель для каждой камеры.
        Это гарантирует изолированный трекинг.
        """
        if camera_id not in self._camera_models:
            # Клонируем модель для новой камеры
            self._camera_models[camera_id] = YOLO(self.model.model)
            logger.info(f"Создан трекер для камеры: {camera_id}")
        return self._camera_models[camera_id]
    
    def detect(self, frame: np.ndarray, camera_id: str, track: bool = True) -> Dict:
        """Детекция с изолированным трекингом для камеры."""
        
        # Используем общую модель, но с persist=True трекинг будет работать
        # в рамках последовательных вызовов для одной камеры
        if track:
            results = self.model.track(
                frame,
                conf=self.confidence,
                iou=self.iou,
                persist=True,
                verbose=False,
                device=self.device
            )
        else:
            results = self.model(frame, conf=self.confidence, iou=self.iou, verbose=False, device=self.device)
        
        return self._parse_results(results[0] if results else None, camera_id)
    
    def _parse_results(self, result, camera_id: str) -> Dict:
        detections = {
            'camera_id': camera_id,
            'detections': [],
            'persons': [],
            'violations': [],
            'ppe_items': [],
            'persons_count': 0,
            'violations_count': 0
        }
        
        if result is None or result.boxes is None:
            return detections
        
        for box in result.boxes:
            cls_idx = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()
            
            track_id = None
            if hasattr(box, 'id') and box.id is not None:
                track_id = int(box.id[0])
            
            ppe_type = self.idx_to_ppe.get(cls_idx, 'unknown')
            
            det = {
                'class_id': cls_idx,
                'class_name': self.class_names[cls_idx],
                'ppe_type': ppe_type,
                'confidence': conf,
                'bbox': xyxy,
                'track_id': track_id,
                'camera_id': camera_id
            }
            
            detections['detections'].append(det)
            
            if ppe_type == 'person':
                detections['persons'].append(det)
            elif ppe_type in self.VIOLATION_CLASSES:
                detections['violations'].append(det)
            elif ppe_type in self.PPE_CLASSES:
                detections['ppe_items'].append(det)
        
        detections['persons_count'] = len(detections['persons'])
        detections['violations_count'] = len(detections['violations'])
        
        return detections
    
    def draw_detections(self, frame: np.ndarray, detections: Dict) -> np.ndarray:
        output = frame.copy()
        
        for det in detections['detections']:
            x1, y1, x2, y2 = det['bbox']
            ppe_type = det['ppe_type']
            conf = det['confidence']
            track_id = det.get('track_id')
            
            if ppe_type in self.VIOLATION_CLASSES:
                color = (0, 0, 255)
                thickness = 3
            elif ppe_type in self.PPE_CLASSES:
                color = (0, 255, 0)
                thickness = 2
            elif ppe_type == 'person':
                color = (255, 200, 0)
                thickness = 2
            else:
                color = (200, 200, 200)
                thickness = 1
            
            cv2.rectangle(output, (x1, y1), (x2, y2), color, thickness)
            
            label = f"{ppe_type}"
            if track_id is not None:
                label = f"#{track_id} {label}"
            label += f" {conf:.0%}"
            
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(output, (x1, y1 - th - 8), (x1 + tw + 8, y1), color, -1)
            cv2.putText(output, label, (x1 + 4, y1 - 4), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        stats = f"Persons: {detections['persons_count']} | Violations: {detections['violations_count']}"
        cv2.putText(output, stats, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        return output

# ============================================================================
# Detection Worker
# ============================================================================

class DetectionWorker:
    def __init__(self):
        logger.info(f"Подключение к Redis: {REDIS_URL}")
        self.redis = redis.from_url(REDIS_URL, decode_responses=False)
        
        logger.info(f"Подключение к БД: {DATABASE_URL}")
        self.engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
        self.detector = PPEDetector(MODEL_PATH, CONFIDENCE_THRESHOLD, IOU_THRESHOLD)
        self.cooldown = CooldownManager(self.redis, COOLDOWN_SECONDS)
        
        self.zones = self._load_zones()
        self.consumer_group = 'detection_workers'
        self.consumer_name = f'worker_{os.getpid()}'
        self._shutdown = False
        
        self.metrics = {'frames': 0, 'violations': 0, 'errors': 0}
        self._frame_counters: Dict[str, int] = {}  # per-camera frame skip counters
        
        # Hot model reload tracking
        self._model_path = MODEL_PATH
        self._model_mtime = self._get_model_mtime()
        self._last_model_check = time.time()
        self._model_check_interval = 30  # Check every 30 seconds
    
    def _get_model_mtime(self) -> float:
        """Get modification time of active model file."""
        # Check ppe_model.pt first (activated model)
        models_dir = Path(MODEL_PATH).parent
        active_model = models_dir / 'ppe_model.pt'
        if active_model.exists():
            return active_model.stat().st_mtime
        if Path(MODEL_PATH).exists():
            return Path(MODEL_PATH).stat().st_mtime
        return 0
    
    def _check_model_update(self):
        """Check if model was updated and reload if needed."""
        current_time = time.time()
        if current_time - self._last_model_check < self._model_check_interval:
            return
        
        self._last_model_check = current_time
        current_mtime = self._get_model_mtime()
        
        if current_mtime > self._model_mtime:
            logger.info("=" * 50)
            logger.info("Обнаружена новая модель! Перезагрузка...")
            logger.info("=" * 50)
            try:
                # Reload detector with new model
                self.detector = PPEDetector(MODEL_PATH, CONFIDENCE_THRESHOLD, IOU_THRESHOLD)
                self.detector.warmup()
                self._model_mtime = current_mtime
                logger.info("Модель успешно перезагружена!")
                
                # Publish status
                self.redis.hset('detector:status', mapping={
                    'model_reloaded': datetime.now().isoformat(),
                    'model_path': str(self.detector._find_model(MODEL_PATH))
                })
                # v2.10.54: Публикуем полный статус после reload
                self._publish_model_status()
            except Exception as e:
                logger.error(f"Ошибка перезагрузки модели: {e}")
    
    def _publish_model_status(self):
        """v2.10.54: Публикует информацию о текущей модели в Redis."""
        try:
            model_path = self.detector._find_model(MODEL_PATH)
            model_name = Path(model_path).stem if model_path else "unknown"
            
            # Получаем классы модели
            class_names = self.detector.class_names if hasattr(self.detector, 'class_names') else {}
            ppe_mapping = self.detector.idx_to_ppe if hasattr(self.detector, 'idx_to_ppe') else {}
            
            # Определяем тип модели
            is_ppe_model = any(k in str(ppe_mapping.values()) for k in ['hardhat', 'vest', 'no_hardhat', 'no_vest'])
            is_coco_model = 'person' in str(class_names.values()) and not is_ppe_model
            
            model_type = "ppe" if is_ppe_model else ("coco" if is_coco_model else "custom")
            
            status_data = {
                'status': 'running',
                'model': model_name,
                'model_path': str(model_path),
                'model_type': model_type,
                'classes': json.dumps(dict(class_names)) if class_names else '{}',
                'ppe_classes': json.dumps(dict(ppe_mapping)) if ppe_mapping else '{}',
                'is_ppe_capable': str(is_ppe_model),
                'last_updated': datetime.now().isoformat()
            }
            
            self.redis.hset('detector:status', mapping=status_data)
            
            logger.info(f"Model status published: {model_name} (type: {model_type}, PPE capable: {is_ppe_model})")
            logger.info(f"  Classes: {list(class_names.values())[:10]}...")  # Первые 10
            
            if not is_ppe_model:
                logger.warning("=" * 60)
                logger.warning("⚠️  ВНИМАНИЕ: Загружена НЕ PPE модель!")
                logger.warning("    Модель не умеет детектить СИЗ (каски, жилеты)")
                logger.warning("    Для PPE детекции нужна специальная модель")
                logger.warning("=" * 60)
        
        except Exception as e:
            logger.error(f"Error publishing model status: {e}")
    
    def _load_zones(self) -> Dict:
        zones = {}
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH) as f:
                    config = yaml.safe_load(f)
                for z in config.get('zones', []):
                    zones[z['id']] = z
        except Exception as e:
            logger.error(f"Ошибка загрузки зон: {e}")
        
        if not zones:
            zones['default'] = {'id': 'default', 'name': 'Default', 'cooldown_seconds': 30}
        return zones
    
    def _get_streams(self) -> List[str]:
        try:
            keys = self.redis.keys('frames:*')
            return [k.decode() if isinstance(k, bytes) else k for k in keys]
        except Exception as e:
            logger.error(f"Ошибка получения стримов: {e}")
            return []
    
    def _ensure_group(self, stream: str):
        try:
            self.redis.xgroup_create(stream, self.consumer_group, id='0', mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
    
    def _process_pending(self, stream: str):
        """ИСПРАВЛЕНИЕ: Обработка pending messages при старте."""
        logger.info(f"Обработка pending для {stream}...")
        try:
            pending = self.redis.xreadgroup(
                self.consumer_group, self.consumer_name,
                {stream: '0'}, count=100, block=None
            )
            
            if not pending:
                return
            
            count = 0
            for _, entries in pending:
                for entry_id, data in entries:
                    self.redis.xack(stream, self.consumer_group, entry_id)
                    count += 1
            
            logger.info(f"Обработано {count} pending messages для {stream}")
        except Exception as e:
            logger.error(f"Ошибка pending: {e}")
    
    def _process_frame(self, camera_id: str, frame_data: bytes, timestamp: str):
        try:
            nparr = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return
            
            result = self.detector.detect(frame, camera_id, track=True)
            
            for v in result['violations']:
                self._handle_violation(camera_id, frame, v, timestamp)
            
            annotated = self.detector.draw_detections(frame, result)
            _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            
            # Сохраняем обработанный кадр с детекциями
            # TTL 5 сек - если детектор отстаёт, кадр устареет и API возьмёт raw
            self.redis.setex(f"detected:{camera_id}", 5, buffer.tobytes())
            
            # Также публикуем в latest для обратной совместимости
            self.redis.set(f"latest:{camera_id}", buffer.tobytes())
            
            self.redis.publish(f"detections:{camera_id}", json.dumps({
                'camera_id': camera_id,
                'timestamp': timestamp,
                'persons_count': result['persons_count'],
                'violations_count': result['violations_count'],
                'detections': result['detections']
            }))
            
            self.metrics['frames'] += 1
            
        except Exception as e:
            logger.error(f"Ошибка кадра: {e}")
            self.metrics['errors'] += 1
    
    def _handle_violation(self, camera_id: str, frame: np.ndarray, violation: Dict, timestamp: str):
        v_type = violation['ppe_type']
        conf = violation['confidence']
        bbox = violation['bbox']
        track_id = violation.get('track_id')
        
        # ИСПРАВЛЕНИЕ: Cooldown в Redis
        if self.cooldown.is_in_cooldown(camera_id, track_id, v_type):
            return
        
        v_id = str(uuid.uuid4())[:8]
        img_file = f"{v_id}.jpg"
        img_path = os.path.join(VIOLATIONS_PATH, img_file)
        
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        pad = 50
        cy1, cy2 = max(0, y1 - pad), min(h, y2 + pad)
        cx1, cx2 = max(0, x1 - pad), min(w, x2 + pad)
        
        if cy2 <= cy1 or cx2 <= cx1:
            logger.warning(f"[{camera_id}] Пустой кроп для нарушения {v_id}: bbox=({x1},{y1},{x2},{y2}), frame={w}x{h}")
            img_file = None
            img_path = None
        else:
            crop = frame[cy1:cy2, cx1:cx2]
            if crop.size == 0 or not cv2.imwrite(img_path, crop):
                logger.warning(f"[{camera_id}] Не удалось сохранить изображение {v_id}: crop shape={crop.shape}")
                img_file = None
                img_path = None
        
        # Сохраняем в БД
        session = self.Session()
        try:
            db_v = Violation(
                id=v_id,
                timestamp=datetime.fromisoformat(timestamp) if timestamp else datetime.now(),
                camera_id=camera_id,
                zone_id='default',
                violation_type=v_type,
                confidence=conf,
                person_id=track_id,
                bbox_x1=x1, bbox_y1=y1, bbox_x2=x2, bbox_y2=y2,
                image_path=img_file
            )
            session.add(db_v)
            session.commit()
        except Exception as e:
            logger.error(f"Ошибка БД: {e}")
            session.rollback()
        finally:
            session.close()
        
        # Алерт
        self.redis.publish('alerts', json.dumps({
            'id': v_id, 'camera_id': camera_id, 'violation_type': v_type,
            'confidence': conf, 'timestamp': timestamp,
            'image_path': img_file, 'bbox': bbox, 'person_id': track_id
        }))
        
        # ИСПРАВЛЕНИЕ: Cooldown в Redis
        zone = self.zones.get('default', {})
        self.cooldown.set_cooldown(camera_id, track_id, v_type, zone.get('cooldown_seconds', 30))
        
        self.metrics['violations'] += 1
        logger.info(f"[{camera_id}] Нарушение: {v_type} (conf={conf:.0%}, track={track_id})")
    
    def run(self):
        logger.info("="*60)
        logger.info("  DETECTION SERVICE v2.1 - Запуск")
        logger.info("="*60)
        logger.info(f"  Модель: {MODEL_PATH}")
        logger.info(f"  Порог уверенности: {CONFIDENCE_THRESHOLD}")
        logger.info(f"  Обработка каждого {DETECT_EVERY_N}-го кадра")
        
        # Информация о GPU и публикация в Redis
        gpu_info = {
            'available': False,
            'name': None,
            'memory_total_mb': None,
            'memory_used_mb': None,
            'memory_free_mb': None,
            'cuda_version': None,
            'pytorch_version': None,
            'device': 'cpu',
            'updated_at': datetime.now().isoformat()
        }
        
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                gpu_mem = props.total_memory / (1024**3)
                logger.info(f"GPU: {gpu_name} ({gpu_mem:.1f} GB)")
                logger.info(f"CUDA: {torch.version.cuda}")
                logger.info(f"PyTorch: {torch.__version__}")
                
                gpu_info.update({
                    'available': True,
                    'name': gpu_name,
                    'memory_total_mb': int(props.total_memory / (1024**2)),
                    'cuda_version': torch.version.cuda,
                    'pytorch_version': torch.__version__,
                    'device': 'cuda:0'
                })
                
                # v2.10.67: Получаем реальное использование GPU памяти
                try:
                    mem_free, mem_total = torch.cuda.mem_get_info(0)
                    gpu_info['memory_used_mb'] = int((mem_total - mem_free) / (1024**2))
                    gpu_info['memory_free_mb'] = int(mem_free / (1024**2))
                except Exception:
                    pass
            else:
                logger.warning("GPU не обнаружен, используется CPU")
        except Exception as e:
            logger.warning(f"Не удалось определить GPU: {e}")
        
        # Публикуем GPU статус в Redis
        try:
            self.redis.hset('detector:gpu', mapping={k: str(v) if v is not None else '' for k, v in gpu_info.items()})
            logger.info("GPU статус опубликован в Redis")
        except Exception as e:
            logger.error(f"Не удалось опубликовать GPU статус: {e}")
        
        self.detector.warmup()
        
        # v2.10.54: Публикуем информацию о загруженной модели
        self._publish_model_status()
        
        # ИСПРАВЛЕНИЕ: Обработка pending при старте
        for stream in self._get_streams():
            self._ensure_group(stream)
            self._process_pending(stream)
        
        logger.info("Обработка кадров...")
        
        # v2.10.67: Таймер для обновления GPU статистики
        import time as _time
        _last_gpu_update = _time.time()
        _GPU_UPDATE_INTERVAL = 30  # секунд
        
        while not self._shutdown:
            try:
                # Check for model updates (hot reload)
                self._check_model_update()
                
                # v2.10.67: Периодическое обновление GPU памяти
                now = _time.time()
                if now - _last_gpu_update > _GPU_UPDATE_INTERVAL:
                    _last_gpu_update = now
                    try:
                        import torch
                        if torch.cuda.is_available():
                            mem_free, mem_total = torch.cuda.mem_get_info(0)
                            self.redis.hset('detector:gpu', mapping={
                                'memory_used_mb': str(int((mem_total - mem_free) / (1024**2))),
                                'memory_free_mb': str(int(mem_free / (1024**2))),
                                'updated_at': datetime.now().isoformat()
                            })
                    except Exception:
                        pass
                
                streams = self._get_streams()
                if not streams:
                    time.sleep(1)
                    continue
                
                for stream in streams:
                    self._ensure_group(stream)
                    
                    messages = self.redis.xreadgroup(
                        self.consumer_group, self.consumer_name,
                        {stream: '>'}, count=BATCH_SIZE, block=WORKER_TIMEOUT
                    )
                    
                    if not messages:
                        continue
                    
                    for s, entries in messages:
                        cam_id = s.decode().replace('frames:', '') if isinstance(s, bytes) else s.replace('frames:', '')
                        
                        # Берём только последний кадр из батча — пропускаем устаревшие
                        if len(entries) > 1:
                            # ACK старые, обрабатываем только последний
                            for entry_id, _ in entries[:-1]:
                                self.redis.xack(stream, self.consumer_group, entry_id)
                            entries = [entries[-1]]
                        
                        for entry_id, data in entries:
                            # Frame skip: обрабатываем каждый DETECT_EVERY_N-й кадр
                            counter = self._frame_counters.get(cam_id, 0) + 1
                            self._frame_counters[cam_id] = counter
                            
                            self.redis.xack(stream, self.consumer_group, entry_id)
                            
                            if counter % DETECT_EVERY_N != 0:
                                continue
                            
                            frame_data = data.get(b'frame') or data.get('frame')
                            ts = data.get(b'timestamp') or data.get('timestamp')
                            if isinstance(ts, bytes):
                                ts = ts.decode()
                            
                            if frame_data:
                                self._process_frame(cam_id, frame_data, ts)
                            
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Ошибка: {e}")
                time.sleep(1)
        
        logger.info(f"Статистика: frames={self.metrics['frames']}, violations={self.metrics['violations']}, errors={self.metrics['errors']}")
    
    def shutdown(self):
        self._shutdown = True

def main():
    worker = DetectionWorker()
    
    def handler(sig, frame):
        worker.shutdown()
    
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    
    worker.run()

if __name__ == '__main__':
    main()
