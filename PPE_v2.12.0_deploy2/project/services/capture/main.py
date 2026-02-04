#!/usr/bin/env python3
"""
Capture Service - Захват видеопотока с RTSP камер.

Функции:
- Подключение к нескольким RTSP потокам
- Адаптивный FPS (настраивается для каждой камеры)
- Публикация кадров в Redis Streams
- Автоматическое переподключение при сбоях
- Health monitoring камер
"""

import os
import sys
import time
import signal
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
import queue

import cv2
import numpy as np
import redis
import yaml

# ============================================================================
# Configuration
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('capture')

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
CONFIG_PATH = os.getenv('CONFIG_PATH', '/app/configs/cameras.yaml')
MAX_FRAME_SIZE = int(os.getenv('MAX_FRAME_SIZE', 1280))  # Максимальная ширина кадра
JPEG_QUALITY = int(os.getenv('JPEG_QUALITY', 80))
RECONNECT_DELAY = int(os.getenv('RECONNECT_DELAY', 5))
STREAM_MAXLEN = int(os.getenv('STREAM_MAXLEN', 100))  # Макс. кадров в очереди


@dataclass
class CameraConfig:
    """Конфигурация камеры."""
    id: str
    name: str
    rtsp_url: str
    fps: int = 5
    zone_id: Optional[str] = None
    enabled: bool = True
    resize_width: int = 1280


@dataclass
class CameraState:
    """Состояние камеры."""
    config: CameraConfig
    is_connected: bool = False
    last_frame_time: Optional[datetime] = None
    frame_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    cap: Optional[cv2.VideoCapture] = None
    running: bool = False


# ============================================================================
# Camera Manager
# ============================================================================

class CameraManager:
    """
    Управление камерами и публикация кадров в Redis.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.cameras: Dict[str, CameraState] = {}
        self.executor = ThreadPoolExecutor(max_workers=20)
        self._shutdown = False
        
    def load_config(self, config_path: str) -> List[CameraConfig]:
        """Загрузка конфигурации камер из YAML."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            cameras = []
            for cam_data in config.get('cameras', []):
                # Поддержка обоих форматов: url и rtsp_url
                rtsp_url = cam_data.get('rtsp_url') or cam_data.get('url', '')
                
                if not rtsp_url:
                    logger.warning(f"Камера {cam_data.get('id', 'unknown')} без URL, пропускаем")
                    continue
                
                cameras.append(CameraConfig(
                    id=cam_data['id'],
                    name=cam_data.get('name', cam_data['id']),
                    rtsp_url=rtsp_url,
                    fps=cam_data.get('fps', 5),
                    zone_id=cam_data.get('zone_id'),
                    enabled=cam_data.get('enabled', True),
                    resize_width=cam_data.get('resize_width', MAX_FRAME_SIZE)
                ))
            
            logger.info(f"Загружено {len(cameras)} камер из конфигурации")
            return cameras
            
        except FileNotFoundError:
            logger.warning(f"Файл конфигурации не найден: {config_path}")
            return self._get_default_cameras()
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            return self._get_default_cameras()
    
    def _get_default_cameras(self) -> List[CameraConfig]:
        """
        Дефолтная конфигурация - пустой список.
        Веб-камера больше не запускается автоматически для экономии CPU.
        Пользователь должен явно настроить камеры в cameras.yaml.
        """
        logger.warning("Нет настроенных камер. Создайте configs/cameras.yaml")
        logger.warning("Capture service работает в режиме ожидания (idle)")
        return []
    
    def add_camera(self, config: CameraConfig):
        """Добавление камеры."""
        if config.id in self.cameras:
            logger.warning(f"Камера {config.id} уже существует")
            return
        
        state = CameraState(config=config)
        self.cameras[config.id] = state
        logger.info(f"Добавлена камера: {config.id} ({config.name})")
    
    def connect_camera(self, camera_id: str) -> bool:
        """Подключение к камере."""
        if camera_id not in self.cameras:
            return False
        
        state = self.cameras[camera_id]
        config = state.config
        
        try:
            # Определяем источник
            if config.rtsp_url.isdigit():
                source = int(config.rtsp_url)  # Веб-камера
                cap = cv2.VideoCapture(source)
            else:
                # RTSP поток - используем оптимизированные настройки
                source = config.rtsp_url
                
                # Добавляем параметры для FFmpeg через environment (v2.10.49)
                # Эти опции КРИТИЧЕСКИ важны для низкой задержки RTSP
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
                    'rtsp_transport;tcp|'  # TCP вместо UDP - меньше потерь пакетов
                    'fflags;nobuffer|'     # Отключаем буферизацию FFmpeg
                    'flags;low_delay|'     # Режим низкой задержки
                    'max_delay;500000|'    # Макс задержка 500ms
                    'stimeout;5000000|'    # Таймаут подключения 5s
                    'analyzeduration;1000000|'  # Анализ потока 1s
                    'probesize;1000000'    # Размер пробы 1MB
                )
                
                cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                
                # Минимальный буфер OpenCV
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
            
            if not cap.isOpened():
                raise Exception("Не удалось открыть видеопоток")
            
            state.cap = cap
            state.is_connected = True
            state.error_count = 0
            state.last_error = None
            
            # Получаем информацию о потоке
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"[{camera_id}] Подключено: {width}x{height} @ {fps:.1f} FPS (TCP mode)")
            
            # Публикуем статус в Redis
            self._publish_status(camera_id, 'connected')
            
            return True
            
        except Exception as e:
            state.is_connected = False
            state.error_count += 1
            state.last_error = str(e)
            logger.error(f"[{camera_id}] Ошибка подключения: {e}")
            return False
    
    def disconnect_camera(self, camera_id: str):
        """Отключение камеры."""
        if camera_id not in self.cameras:
            return
        
        state = self.cameras[camera_id]
        state.running = False
        
        if state.cap:
            state.cap.release()
            state.cap = None
        
        state.is_connected = False
        logger.info(f"[{camera_id}] Отключено")
        self._publish_status(camera_id, 'disconnected')
    
    def _publish_status(self, camera_id: str, status: str):
        """Публикация статуса камеры в Redis."""
        try:
            state = self.cameras.get(camera_id)
            name = state.config.name if state else camera_id
            
            self.redis.hset(f"camera:{camera_id}", mapping={
                'status': status,
                'name': name,
                'updated_at': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Ошибка публикации статуса: {e}")
    
    def _capture_loop(self, camera_id: str):
        """Цикл захвата кадров для одной камеры с защитой от зависания."""
        state = self.cameras[camera_id]
        config = state.config
        state.running = True
        
        # v2.10.52: Подключение перенесено сюда для параллельности
        # Теперь все камеры подключаются одновременно, а не последовательно
        if not state.is_connected:
            logger.info(f"[{camera_id}] Подключение к камере...")
            if not self.connect_camera(camera_id):
                logger.error(f"[{camera_id}] Не удалось подключиться, выход из capture loop")
                state.running = False
                return
        
        frame_interval = 1.0 / config.fps
        last_capture = 0
        last_successful_read = time.time()
        READ_TIMEOUT = 10.0  # Таймаут чтения кадра
        WATCHDOG_TIMEOUT = 30.0  # Таймаут watchdog для переподключения
        
        logger.info(f"[{camera_id}] Запуск захвата ({config.fps} FPS)")
        
        # Буфер для кадров (один кадр)
        frame_queue: queue.Queue = queue.Queue(maxsize=1)
        reader_running = threading.Event()
        reader_running.set()
        
        def frame_reader():
            """Отдельный поток для чтения кадров с агрессивной очисткой буфера (v2.10.49)."""
            consecutive_errors = 0
            MAX_CONSECUTIVE_ERRORS = 10
            
            while reader_running.is_set() and state.running:
                try:
                    if state.cap is None or not state.is_connected:
                        time.sleep(0.1)
                        consecutive_errors = 0
                        continue
                    
                    # АГРЕССИВНАЯ ОЧИСТКА БУФЕРА RTSP (v2.10.49)
                    # Пропускаем несколько кадров чтобы получить самый свежий
                    # Это критически важно для RTSP потоков с буферизацией
                    frames_to_skip = 3  # Пропускаем 3 старых кадра
                    for _ in range(frames_to_skip):
                        if not state.cap.grab():
                            break
                    
                    # Читаем финальный (самый свежий) кадр
                    ret = state.cap.grab()
                    if not ret:
                        consecutive_errors += 1
                        if consecutive_errors > MAX_CONSECUTIVE_ERRORS:
                            logger.warning(f"[{camera_id}] Много ошибок чтения, пропуск...")
                            consecutive_errors = 0
                        time.sleep(0.05)
                        continue
                    
                    ret, frame = state.cap.retrieve()
                    if ret and frame is not None:
                        consecutive_errors = 0
                        # Обновляем очередь (старый кадр удаляется если есть)
                        try:
                            frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                        frame_queue.put((ret, frame))
                    else:
                        consecutive_errors += 1
                        
                except Exception as e:
                    logger.debug(f"[{camera_id}] Frame reader error: {e}")
                    consecutive_errors += 1
                    time.sleep(0.05)
        
        # Запускаем поток чтения
        reader_thread = threading.Thread(target=frame_reader, daemon=True)
        reader_thread.start()
        
        while state.running and not self._shutdown:
            try:
                # Контроль FPS
                now = time.time()
                if now - last_capture < frame_interval:
                    time.sleep(0.01)
                    continue
                
                # Проверяем подключение
                if not state.is_connected or state.cap is None:
                    logger.warning(f"[{camera_id}] Нет подключения, переподключение...")
                    time.sleep(RECONNECT_DELAY)
                    self.connect_camera(camera_id)
                    last_successful_read = time.time()  # Reset watchdog
                    continue
                
                # Watchdog: если долго нет кадров - переподключение
                if now - last_successful_read > WATCHDOG_TIMEOUT:
                    logger.error(f"[{camera_id}] Watchdog timeout ({WATCHDOG_TIMEOUT}s), переподключение...")
                    self.disconnect_camera(camera_id)
                    time.sleep(RECONNECT_DELAY)
                    self.connect_camera(camera_id)
                    last_successful_read = time.time()
                    continue
                
                # Получаем кадр из очереди с таймаутом
                try:
                    ret, frame = frame_queue.get(timeout=READ_TIMEOUT)
                except queue.Empty:
                    logger.warning(f"[{camera_id}] Таймаут чтения кадра ({READ_TIMEOUT}s)")
                    state.error_count += 1
                    
                    if state.error_count > 5:
                        logger.error(f"[{camera_id}] Слишком много таймаутов, переподключение...")
                        self.disconnect_camera(camera_id)
                        time.sleep(RECONNECT_DELAY)
                        self.connect_camera(camera_id)
                        last_successful_read = time.time()
                    continue
                
                if not ret or frame is None:
                    state.error_count += 1
                    continue
                
                # Resize если нужно
                h, w = frame.shape[:2]
                if w > config.resize_width:
                    scale = config.resize_width / w
                    frame = cv2.resize(frame, None, fx=scale, fy=scale)
                
                # Кодируем в JPEG
                _, buffer = cv2.imencode('.jpg', frame, [
                    cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY
                ])
                
                # Публикуем в Redis Stream
                self._publish_frame(camera_id, buffer.tobytes())
                
                state.frame_count += 1
                state.last_frame_time = datetime.now()
                state.error_count = 0
                last_capture = now
                last_successful_read = now  # Reset watchdog
                
                if state.frame_count % 100 == 0:
                    logger.debug(f"[{camera_id}] Отправлено {state.frame_count} кадров")
                
            except Exception as e:
                logger.error(f"[{camera_id}] Ошибка захвата: {e}")
                state.error_count += 1
                time.sleep(1)
        
        # Останавливаем поток чтения
        reader_running.clear()
        logger.info(f"[{camera_id}] Захват остановлен")
    
    def _publish_frame(self, camera_id: str, frame_data: bytes):
        """Публикация кадра в Redis Stream и сохранение последнего кадра."""
        try:
            stream_key = f"frames:{camera_id}"
            
            # Добавляем в stream для детектора
            self.redis.xadd(
                stream_key,
                {
                    'frame': frame_data,
                    'timestamp': datetime.now().isoformat(),
                    'camera_id': camera_id
                },
                maxlen=STREAM_MAXLEN
            )
            
            # Сохраняем RAW кадр (без детекций) - для fallback
            self.redis.set(f"raw:{camera_id}", frame_data)
            
            # latest будет перезаписан detector'ом с детекциями
            # Если детектор не работает, API будет брать raw
            
        except Exception as e:
            logger.error(f"Ошибка публикации кадра: {e}")
    
    def start_capture(self, camera_id: str):
        """Запуск захвата для камеры в отдельном потоке.
        
        v2.10.52: Подключение перенесено в _capture_loop для параллельности.
        Раньше connect_camera() блокировал запуск остальных камер.
        """
        if camera_id not in self.cameras:
            return
        
        state = self.cameras[camera_id]
        
        if state.running:
            logger.warning(f"[{camera_id}] Захват уже запущен")
            return
        
        # НЕ подключаемся здесь! Подключение будет в _capture_loop (параллельно)
        # Это позволяет всем камерам стартовать одновременно
        
        # Запускаем в потоке
        self.executor.submit(self._capture_loop, camera_id)
    
    def start_all(self):
        """Запуск захвата для всех камер."""
        for camera_id, state in self.cameras.items():
            if state.config.enabled:
                self.start_capture(camera_id)
    
    def stop_all(self):
        """Остановка всех камер."""
        self._shutdown = True
        
        for camera_id in self.cameras:
            self.disconnect_camera(camera_id)
        
        self.executor.shutdown(wait=True)
        logger.info("Все камеры остановлены")
    
    def get_status(self) -> Dict:
        """Получение статуса всех камер."""
        status = {}
        for camera_id, state in self.cameras.items():
            status[camera_id] = {
                'name': state.config.name,
                'connected': state.is_connected,
                'running': state.running,
                'frame_count': state.frame_count,
                'last_frame': state.last_frame_time.isoformat() if state.last_frame_time else None,
                'error_count': state.error_count,
                'last_error': state.last_error
            }
        return status
    
    def reload_cameras(self, config_path: str):
        """Перезагрузка конфигурации камер."""
        logger.info("Перезагрузка конфигурации камер...")
        
        # Останавливаем текущие камеры
        for camera_id in list(self.cameras.keys()):
            self.disconnect_camera(camera_id)
        
        self.cameras.clear()
        
        # Загружаем новую конфигурацию
        cameras = self.load_config(config_path)
        
        for cam_config in cameras:
            self.add_camera(cam_config)
        
        # Запускаем enabled камеры
        self._shutdown = False
        self.start_all()
        
        logger.info(f"Перезагружено {len(cameras)} камер")


# ============================================================================
# Main
# ============================================================================

def main():
    logger.info("="*60)
    logger.info("  CAPTURE SERVICE - Запуск")
    logger.info("="*60)
    
    # Подключение к Redis
    logger.info(f"Подключение к Redis: {REDIS_URL}")
    redis_client = redis.from_url(REDIS_URL, decode_responses=False)
    
    try:
        redis_client.ping()
        logger.info("Redis подключен")
    except Exception as e:
        logger.error(f"Ошибка подключения к Redis: {e}")
        sys.exit(1)
    
    # Инициализация менеджера камер
    manager = CameraManager(redis_client)
    
    # Загрузка конфигурации
    cameras = manager.load_config(CONFIG_PATH)
    
    for cam_config in cameras:
        manager.add_camera(cam_config)
    
    # Обработка сигналов
    def shutdown_handler(signum, frame):
        logger.info("Получен сигнал завершения...")
        manager.stop_all()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    # Запуск захвата
    manager.start_all()
    
    # Подписываемся на обновления конфигурации
    pubsub = redis_client.pubsub()
    pubsub.subscribe('system:cameras_updated')
    
    last_status_time = time.time()
    
    # Основной цикл (публикация статуса + обработка обновлений)
    while True:
        try:
            # Проверяем сообщения pubsub каждую секунду
            message = pubsub.get_message(timeout=1)
            if message and message['type'] == 'message':
                logger.info("Получена команда обновления камер")
                manager.reload_cameras(CONFIG_PATH)
            
            # Публикуем статус каждые 30 секунд
            if time.time() - last_status_time >= 30:
                status = manager.get_status()
                redis_client.set('capture:status', str(status))
                
                # Логируем статус
                connected = sum(1 for s in status.values() if s['connected'])
                total_frames = sum(s['frame_count'] for s in status.values())
                logger.info(f"Статус: {connected}/{len(status)} камер, {total_frames} кадров")
                last_status_time = time.time()
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}")
            time.sleep(5)
    
    manager.stop_all()


if __name__ == '__main__':
    main()
