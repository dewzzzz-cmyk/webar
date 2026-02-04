#!/usr/bin/env python3
"""
API Service v2.1 - Исправленная версия

Исправления:
- JWT аутентификация
- Rate limiting
- Улучшенная валидация
- Dependency Injection для Redis
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
from functools import wraps
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

import redis.asyncio as aioredis
import asyncpg
from sqlalchemy import create_engine, func, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text

# ============================================================================
# Configuration
# ============================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
logger = logging.getLogger('api')

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://ppe:ppe_secret@localhost:5432/ppe_detection')
VIOLATIONS_PATH = os.getenv('VIOLATIONS_PATH', '/app/violations')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')

# Security - NO DEFAULTS IN PRODUCTION!
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    logger.error("FATAL: JWT_SECRET environment variable is required!")
    raise RuntimeError("JWT_SECRET must be set!")
if len(JWT_SECRET) < 32:
    logger.warning("JWT_SECRET is too short! Recommended: 64+ characters")

JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', 24))

# Rate limiting
RATE_LIMIT_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', 300))
RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', 60))  # seconds

# Credentials - MUST be set via environment
DEFAULT_USERNAME = os.environ.get('API_USERNAME')
DEFAULT_PASSWORD = os.environ.get('API_PASSWORD')
if not DEFAULT_USERNAME or not DEFAULT_PASSWORD:
    logger.warning("API_USERNAME/API_PASSWORD not set, using defaults (INSECURE!)")
    DEFAULT_USERNAME = DEFAULT_USERNAME or 'admin'
    DEFAULT_PASSWORD = DEFAULT_PASSWORD or 'admin123'

# ============================================================================
# Version - читаем из файла VERSION
# ============================================================================

def get_app_version() -> str:
    """Read version from VERSION file or return default."""
    version_paths = ['/app/VERSION', './VERSION', '../VERSION', '../../VERSION']
    for path in version_paths:
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    return "2.10.46"  # Fallback

APP_VERSION = get_app_version()
logger.info(f"API Version: {APP_VERSION}")

# ============================================================================
# Database
# ============================================================================

Base = declarative_base()

class Violation(Base):
    __tablename__ = 'violations'
    
    id = Column(String(36), primary_key=True)
    timestamp = Column(DateTime, index=True)
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

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# Pydantic Schemas
# ============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class ViolationResponse(BaseModel):
    id: str
    timestamp: datetime
    camera_id: str
    zone_id: Optional[str]
    violation_type: str
    confidence: float
    person_id: Optional[int]
    bbox: List[int]
    image_path: Optional[str]
    acknowledged: bool
    
    class Config:
        from_attributes = True

class ViolationStats(BaseModel):
    total: int
    by_type: Dict[str, int]
    by_camera: Dict[str, int]
    by_hour: Dict[str, int]

class AcknowledgeRequest(BaseModel):
    acknowledged_by: str
    notes: Optional[str] = None

# ============================================================================
# Security - JWT Authentication
# ============================================================================

security = HTTPBearer(auto_error=False)

def create_token(username: str) -> str:
    """Создание JWT токена."""
    payload = {
        'sub': username,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Optional[str]:
    """Проверка JWT токена."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get('sub')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """Получение текущего пользователя из токена."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    username = verify_token(credentials.credentials)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истёкший токен",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return username

# Optional auth - для публичных endpoints
async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    if credentials is None:
        return None
    return verify_token(credentials.credentials)

# ============================================================================
# Rate Limiting
# ============================================================================

class RateLimiter:
    """Rate limiter на базе Redis."""
    
    def __init__(self, redis: aioredis.Redis, requests: int = 100, window: int = 60):
        self.redis = redis
        self.requests = requests
        self.window = window
    
    async def is_allowed(self, key: str) -> bool:
        """Проверка лимита."""
        current = await self.redis.get(f"ratelimit:{key}")
        
        if current is None:
            await self.redis.setex(f"ratelimit:{key}", self.window, 1)
            return True
        
        if int(current) >= self.requests:
            return False
        
        await self.redis.incr(f"ratelimit:{key}")
        return True
    
    async def get_remaining(self, key: str) -> int:
        """Оставшееся количество запросов."""
        current = await self.redis.get(f"ratelimit:{key}")
        if current is None:
            return self.requests
        return max(0, self.requests - int(current))

# ============================================================================
# WebSocket Manager
# ============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket подключен, всего: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket отключен, всего: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# ============================================================================
# Application State
# ============================================================================

class AppState:
    redis: Optional[aioredis.Redis] = None
    rate_limiter: Optional[RateLimiter] = None
    db_pool: Optional[asyncpg.Pool] = None

state = AppState()


async def get_camera_frame(camera_id: str) -> Optional[bytes]:
    """
    Получить кадр камеры с fallback логикой:
    1. detected:{camera_id} - обработанный кадр с детекциями (приоритет)
    2. raw:{camera_id} - сырой кадр от capture
    3. latest:{camera_id} - legacy fallback
    4. placeholder - если камера offline
    """
    # Проверяем что Redis инициализирован
    if not state.redis:
        return generate_offline_placeholder(camera_id)
    
    try:
        # Пробуем detected (с детекциями)
        frame = await state.redis.get(f"detected:{camera_id}")
        if frame:
            return frame
        
        # Пробуем raw (сырой)
        frame = await state.redis.get(f"raw:{camera_id}")
        if frame:
            return frame
        
        # Legacy fallback
        frame = await state.redis.get(f"latest:{camera_id}")
        if frame:
            return frame
    except Exception as e:
        logger.warning(f"Redis error getting frame for {camera_id}: {e}")
    
    # Генерируем placeholder если камера offline
    return generate_offline_placeholder(camera_id)


def generate_offline_placeholder(camera_id: str) -> bytes:
    """Генерирует placeholder изображение для offline камеры"""
    import cv2
    import numpy as np
    from datetime import datetime
    
    # Создаём серое изображение 640x480
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (40, 40, 40)  # Тёмно-серый фон
    
    # Добавляем текст
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # "Камера offline"
    text1 = "Camera Offline"
    text_size1 = cv2.getTextSize(text1, font, 1.2, 2)[0]
    x1 = (640 - text_size1[0]) // 2
    cv2.putText(img, text1, (x1, 200), font, 1.2, (128, 128, 128), 2)
    
    # ID камеры
    text2 = f"ID: {camera_id}"
    text_size2 = cv2.getTextSize(text2, font, 0.7, 1)[0]
    x2 = (640 - text_size2[0]) // 2
    cv2.putText(img, text2, (x2, 260), font, 0.7, (100, 100, 100), 1)
    
    # Время
    time_text = datetime.now().strftime("%H:%M:%S")
    text_size3 = cv2.getTextSize(time_text, font, 0.6, 1)[0]
    x3 = (640 - text_size3[0]) // 2
    cv2.putText(img, time_text, (x3, 300), font, 0.6, (80, 80, 80), 1)
    
    # Рисуем иконку камеры (простой прямоугольник)
    cv2.rectangle(img, (290, 100), (350, 140), (80, 80, 80), 2)
    cv2.rectangle(img, (340, 110), (360, 130), (80, 80, 80), 2)
    
    # Конвертируем в JPEG
    _, jpeg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return jpeg.tobytes()


# ============================================================================
# Application
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("="*60)
    logger.info("  API SERVICE v2.10.68 - Запуск (с Training Module)")
    logger.info("  FIX: Training Router retry + db_pool race condition")
    logger.info("="*60)
    
    # Redis connection
    state.redis = await aioredis.from_url(REDIS_URL)
    state.rate_limiter = RateLimiter(state.redis, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)
    logger.info(f"Redis подключен")
    
    # Connect settings router FIRST (doesn't require DB)
    try:
        from settings_router import create_settings_router
        settings_router = create_settings_router(state.redis)
        app.include_router(settings_router, prefix="/api/settings", tags=["Settings"])
        logger.info("Settings Router подключен")
    except Exception as e:
        logger.error(f"Settings router ошибка: {e}")
    
    # AsyncPG pool for training module (with retry for startup race condition)
    max_retries = 5
    retry_delay = 3  # seconds
    for attempt in range(1, max_retries + 1):
        try:
            state.db_pool = await asyncpg.create_pool(
                DATABASE_URL.replace('postgresql://', 'postgres://'),
                min_size=2,
                max_size=10,
                command_timeout=10
            )
            logger.info(f"AsyncPG pool создан для Training API (попытка {attempt}/{max_retries})")
            break
        except Exception as pool_err:
            if attempt < max_retries:
                logger.warning(f"PostgreSQL не готов (попытка {attempt}/{max_retries}): {pool_err}")
                logger.info(f"Повторная попытка через {retry_delay}с...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Не удалось подключиться к PostgreSQL после {max_retries} попыток: {pool_err}")
                raise
    
    try:
        logger.info("AsyncPG pool создан, создаю таблицы...")
        
        # Verify connection is alive
        async with state.db_pool.acquire() as test_conn:
            ver = await test_conn.fetchval("SELECT version()")
            logger.info(f"PostgreSQL connected: {ver[:50]}...")
        
        # Auto-migrate: Create training tables if not exist
        async with state.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE EXTENSION IF NOT EXISTS "pgcrypto";
                
                CREATE TABLE IF NOT EXISTS training_datasets (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    created_by VARCHAR(100) NOT NULL DEFAULT 'system',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    images_count INTEGER DEFAULT 0,
                    annotations_count INTEGER DEFAULT 0,
                    labeled_count INTEGER DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'draft',
                    source VARCHAR(50) DEFAULT 'user',
                    path VARCHAR(500),
                    classes JSONB DEFAULT '[]'::jsonb
                );
                
                -- Миграция для существующих баз данных (добавление новых колонок)
                DO $$ 
                BEGIN
                    BEGIN ALTER TABLE training_datasets ADD COLUMN labeled_count INTEGER DEFAULT 0; EXCEPTION WHEN duplicate_column THEN NULL; END;
                    BEGIN ALTER TABLE training_datasets ADD COLUMN source VARCHAR(50) DEFAULT 'user'; EXCEPTION WHEN duplicate_column THEN NULL; END;
                    BEGIN ALTER TABLE training_datasets ADD COLUMN path VARCHAR(500); EXCEPTION WHEN duplicate_column THEN NULL; END;
                    BEGIN ALTER TABLE training_datasets ADD COLUMN classes JSONB DEFAULT '[]'::jsonb; EXCEPTION WHEN duplicate_column THEN NULL; END;
                END $$;
                
                CREATE TABLE IF NOT EXISTS training_images (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    dataset_id UUID REFERENCES training_datasets(id) ON DELETE CASCADE,
                    filename VARCHAR(255) NOT NULL,
                    original_filename VARCHAR(255) NOT NULL,
                    file_size INTEGER NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    mime_type VARCHAR(50) DEFAULT 'image/jpeg',
                    storage_path VARCHAR(500) NOT NULL,
                    checksum VARCHAR(64),
                    uploaded_by VARCHAR(100) NOT NULL DEFAULT 'admin',
                    uploaded_at TIMESTAMP DEFAULT NOW(),
                    status VARCHAR(20) DEFAULT 'pending'
                );
                
                CREATE TABLE IF NOT EXISTS annotations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    image_id UUID REFERENCES training_images(id) ON DELETE CASCADE,
                    class_name VARCHAR(50) NOT NULL,
                    bbox_x1 FLOAT NOT NULL,
                    bbox_y1 FLOAT NOT NULL,
                    bbox_x2 FLOAT NOT NULL,
                    bbox_y2 FLOAT NOT NULL,
                    confidence FLOAT,
                    created_by VARCHAR(100) NOT NULL DEFAULT 'admin',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    verified BOOLEAN DEFAULT FALSE,
                    verified_by VARCHAR(100),
                    verified_at TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS training_jobs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    dataset_id UUID REFERENCES training_datasets(id),
                    name VARCHAR(255),
                    status VARCHAR(20) DEFAULT 'pending',
                    progress FLOAT DEFAULT 0,
                    epochs_total INTEGER NOT NULL DEFAULT 50,
                    epochs_completed INTEGER DEFAULT 0,
                    batch_size INTEGER DEFAULT 16,
                    learning_rate FLOAT DEFAULT 0.001,
                    image_size INTEGER DEFAULT 640,
                    augmentation BOOLEAN DEFAULT TRUE,
                    pretrained BOOLEAN DEFAULT TRUE,
                    current_loss FLOAT,
                    best_loss FLOAT,
                    map50 FLOAT,
                    map50_95 FLOAT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    error_message TEXT,
                    model_path VARCHAR(500),
                    -- New fields for model selection
                    model_type VARCHAR(20) DEFAULT 'yolov8',
                    model_size VARCHAR(5) DEFAULT 'n',
                    train_split FLOAT DEFAULT 0.7,
                    val_split FLOAT DEFAULT 0.2,
                    test_split FLOAT DEFAULT 0.1,
                    optimizer VARCHAR(20) DEFAULT 'auto',
                    patience INTEGER DEFAULT 50,
                    created_by VARCHAR(100) DEFAULT 'admin'
                );
                
                -- Add columns if they don't exist (for existing databases)
                DO $$ 
                BEGIN
                    BEGIN ALTER TABLE training_jobs ADD COLUMN model_type VARCHAR(20) DEFAULT 'yolov8'; EXCEPTION WHEN duplicate_column THEN NULL; END;
                    BEGIN ALTER TABLE training_jobs ADD COLUMN model_size VARCHAR(5) DEFAULT 'n'; EXCEPTION WHEN duplicate_column THEN NULL; END;
                    BEGIN ALTER TABLE training_jobs ADD COLUMN train_split FLOAT DEFAULT 0.7; EXCEPTION WHEN duplicate_column THEN NULL; END;
                    BEGIN ALTER TABLE training_jobs ADD COLUMN val_split FLOAT DEFAULT 0.2; EXCEPTION WHEN duplicate_column THEN NULL; END;
                    BEGIN ALTER TABLE training_jobs ADD COLUMN test_split FLOAT DEFAULT 0.1; EXCEPTION WHEN duplicate_column THEN NULL; END;
                    BEGIN ALTER TABLE training_jobs ADD COLUMN optimizer VARCHAR(20) DEFAULT 'auto'; EXCEPTION WHEN duplicate_column THEN NULL; END;
                    BEGIN ALTER TABLE training_jobs ADD COLUMN patience INTEGER DEFAULT 50; EXCEPTION WHEN duplicate_column THEN NULL; END;
                    BEGIN ALTER TABLE training_jobs ADD COLUMN created_by VARCHAR(100) DEFAULT 'admin'; EXCEPTION WHEN duplicate_column THEN NULL; END;
                END $$;
                
                CREATE TABLE IF NOT EXISTS model_versions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    training_job_id UUID REFERENCES training_jobs(id),
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    model_path VARCHAR(500) NOT NULL,
                    map50 DOUBLE PRECISION NOT NULL DEFAULT 0,
                    map50_95 DOUBLE PRECISION NOT NULL DEFAULT 0,
                    precision_avg DOUBLE PRECISION,
                    recall_avg DOUBLE PRECISION,
                    metrics_per_class JSONB,
                    train_images_count INTEGER,
                    is_active BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    activated_at TIMESTAMP,
                    activated_by VARCHAR(100)
                );
                
                CREATE TABLE IF NOT EXISTS annotation_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    image_id UUID REFERENCES training_images(id) ON DELETE CASCADE,
                    action VARCHAR(20) NOT NULL,
                    annotation_data JSONB,
                    created_by VARCHAR(100) NOT NULL DEFAULT 'admin',
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            logger.info("Training tables: auto-migration completed")
        
        # Connect training router (requires DB)
        from training_router import create_training_router
        training_router = create_training_router(state.db_pool)
        app.include_router(training_router, prefix="/api/training")
        logger.info("Training Router подключен")
    except Exception as e:
        import traceback
        logger.error(f"Training module недоступен: {e}")
        logger.error(f"Training module traceback:\n{traceback.format_exc()}")
        logger.warning("Training API endpoints будут недоступны (404)")
    
    # Connect models router (v2.10.40 - HuggingFace catalog)
    try:
        from models_router import router as models_router
        app.include_router(models_router)
        logger.info("Models Router подключен (HuggingFace catalog)")
    except Exception as e:
        logger.warning(f"Models router недоступен: {e}")
    
    # Start alert subscriber
    asyncio.create_task(alert_subscriber())
    
    yield
    
    # Cleanup
    if state.db_pool:
        await state.db_pool.close()
    if state.redis:
        await state.redis.close()
    logger.info("API Service остановлен")

app = FastAPI(
    title="PPE Detection API",
    description="API для системы контроля СИЗ (с аутентификацией и модулем обучения)",
    version=APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Rate Limit Middleware
# ============================================================================

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Middleware для rate limiting."""
    # Пропускаем health check, login, docs, и основные API endpoints
    whitelist_prefixes = [
        "/health", 
        "/api/auth/login", 
        "/docs", 
        "/openapi.json",
        "/api/settings",  # Настройки - частые запросы при загрузке страницы
        "/api/training",  # Training module
        "/api/cameras",   # Камеры
        "/ws",            # WebSocket
    ]
    
    path = request.url.path
    if any(path.startswith(prefix) for prefix in whitelist_prefixes):
        return await call_next(request)
    
    if state.rate_limiter:
        client_ip = request.client.host if request.client else "unknown"
        
        if not await state.rate_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Слишком много запросов. Попробуйте позже."}
            )
        
        response = await call_next(request)
        remaining = await state.rate_limiter.get_remaining(client_ip)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS)
        return response
    
    return await call_next(request)

# ============================================================================
# Alert Subscriber
# ============================================================================

async def alert_subscriber():
    try:
        pubsub = state.redis.pubsub()
        await pubsub.subscribe('alerts')
        logger.info("Подписка на алерты активна")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    await manager.broadcast({'type': 'violation', 'data': data})
                except Exception as e:
                    logger.error(f"Ошибка алерта: {e}")
    except Exception as e:
        logger.error(f"Ошибка подписки: {e}")

# ============================================================================
# Auth Endpoints
# ============================================================================

@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(request: LoginRequest):
    """Аутентификация и получение JWT токена."""
    # Простая проверка (в production используйте базу данных!)
    if request.username == DEFAULT_USERNAME and request.password == DEFAULT_PASSWORD:
        token = create_token(request.username)
        return TokenResponse(
            access_token=token,
            expires_in=JWT_EXPIRATION_HOURS * 3600
        )
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверный логин или пароль"
    )

@app.post("/api/auth/refresh", response_model=TokenResponse, tags=["Auth"])
async def refresh_token(username: str = Depends(get_current_user)):
    """Обновление JWT токена (refresh)."""
    token = create_token(username)
    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRATION_HOURS * 3600
    )

@app.get("/api/auth/me", tags=["Auth"])
async def get_me(username: str = Depends(get_current_user)):
    """Информация о текущем пользователе."""
    return {"username": username}

# ============================================================================
# Health Check (без аутентификации)
# ============================================================================

@app.get("/health", tags=["System"])
@app.get("/api/health", tags=["System"])
async def health_check():
    """Health check с информацией о подключенных роутерах."""
    routes_info = []
    for route in app.routes:
        if hasattr(route, 'path'):
            routes_info.append(route.path)
    
    settings_routes = [r for r in routes_info if '/settings' in r]
    training_routes = [r for r in routes_info if '/training' in r]
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": APP_VERSION,
        "routers": {
            "settings": len(settings_routes) > 0,
            "settings_routes_count": len(settings_routes),
            "training": len(training_routes) > 0,
            "training_routes_count": len(training_routes),
        },
        "db_pool": state.db_pool is not None,
        "redis": state.redis is not None,
    }

@app.get("/api/debug/routes", tags=["System"])
async def debug_routes():
    """Список всех зарегистрированных роутов (для отладки)."""
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else []
            })
    return {"routes": routes, "total": len(routes)}

# ============================================================================
# Violations API (с аутентификацией)
# ============================================================================

@app.get("/api/violations", response_model=List[ViolationResponse], tags=["Violations"])
async def get_violations(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    camera_id: Optional[str] = Query(None, max_length=50),
    violation_type: Optional[str] = Query(None, max_length=50),
    acknowledged: Optional[bool] = None,
    hours: Optional[int] = Query(None, ge=1, le=168),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """Получение списка нарушений (требуется аутентификация)."""
    query = db.query(Violation)
    
    if camera_id:
        query = query.filter(Violation.camera_id == camera_id)
    if violation_type:
        query = query.filter(Violation.violation_type == violation_type)
    if acknowledged is not None:
        query = query.filter(Violation.acknowledged == acknowledged)
    if hours:
        since = datetime.now() - timedelta(hours=hours)
        query = query.filter(Violation.timestamp >= since)
    
    violations = query.order_by(desc(Violation.timestamp)).offset(offset).limit(limit).all()
    
    return [
        ViolationResponse(
            id=v.id, timestamp=v.timestamp, camera_id=v.camera_id,
            zone_id=v.zone_id, violation_type=v.violation_type,
            confidence=v.confidence, person_id=v.person_id,
            bbox=[v.bbox_x1, v.bbox_y1, v.bbox_x2, v.bbox_y2],
            image_path=v.image_path, acknowledged=v.acknowledged
        )
        for v in violations
    ]

@app.get("/api/violations/{violation_id}", response_model=ViolationResponse, tags=["Violations"])
async def get_violation(
    violation_id: str,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """Получение конкретного нарушения."""
    violation = db.query(Violation).filter(Violation.id == violation_id).first()
    
    if not violation:
        raise HTTPException(status_code=404, detail="Нарушение не найдено")
    
    return ViolationResponse(
        id=violation.id, timestamp=violation.timestamp,
        camera_id=violation.camera_id, zone_id=violation.zone_id,
        violation_type=violation.violation_type, confidence=violation.confidence,
        person_id=violation.person_id,
        bbox=[violation.bbox_x1, violation.bbox_y1, violation.bbox_x2, violation.bbox_y2],
        image_path=violation.image_path, acknowledged=violation.acknowledged
    )

@app.get("/api/violations/{violation_id}/image", tags=["Violations"])
async def get_violation_image(
    violation_id: str,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """Получение изображения нарушения."""
    violation = db.query(Violation).filter(Violation.id == violation_id).first()
    
    if not violation or not violation.image_path:
        raise HTTPException(status_code=404, detail="Изображение не найдено")
    
    # SECURITY FIX: Prevent path traversal
    from pathlib import Path
    safe_filename = Path(violation.image_path).name  # Extract filename only
    image_path = os.path.join(VIOLATIONS_PATH, safe_filename)
    
    # Additional check: ensure path is within VIOLATIONS_PATH
    real_path = os.path.realpath(image_path)
    real_violations_path = os.path.realpath(VIOLATIONS_PATH)
    if not real_path.startswith(real_violations_path):
        logger.warning(f"Path traversal attempt blocked: {violation.image_path}")
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    return FileResponse(image_path, media_type="image/jpeg")

@app.post("/api/violations/{violation_id}/acknowledge", tags=["Violations"])
async def acknowledge_violation(
    violation_id: str,
    request: AcknowledgeRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """Подтверждение нарушения."""
    violation = db.query(Violation).filter(Violation.id == violation_id).first()
    
    if not violation:
        raise HTTPException(status_code=404, detail="Нарушение не найдено")
    
    violation.acknowledged = True
    violation.acknowledged_by = request.acknowledged_by or user
    violation.acknowledged_at = datetime.now()
    violation.notes = request.notes
    
    db.commit()
    
    return {"status": "acknowledged", "by": violation.acknowledged_by}

# ============================================================================
# Statistics API
# ============================================================================

@app.get("/api/statistics", response_model=ViolationStats, tags=["Statistics"])
async def get_statistics(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user)
):
    """Статистика нарушений."""
    since = datetime.now() - timedelta(hours=hours)
    
    total = db.query(func.count(Violation.id)).filter(Violation.timestamp >= since).scalar() or 0
    
    by_type_q = db.query(Violation.violation_type, func.count(Violation.id))\
        .filter(Violation.timestamp >= since).group_by(Violation.violation_type).all()
    by_type = {r[0]: r[1] for r in by_type_q}
    
    by_camera_q = db.query(Violation.camera_id, func.count(Violation.id))\
        .filter(Violation.timestamp >= since).group_by(Violation.camera_id).all()
    by_camera = {r[0]: r[1] for r in by_camera_q}
    
    by_hour = {}
    for h in range(min(hours, 24)):
        hour_start = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=h)
        hour_end = hour_start + timedelta(hours=1)
        count = db.query(func.count(Violation.id)).filter(
            Violation.timestamp >= hour_start, Violation.timestamp < hour_end
        ).scalar() or 0
        by_hour[hour_start.strftime('%H:00')] = count
    
    return ViolationStats(total=total, by_type=by_type, by_camera=by_camera, by_hour=by_hour)

# ============================================================================
# Cameras API
# ============================================================================

@app.get("/api/cameras", tags=["Cameras"])
async def get_cameras(user: str = Depends(get_current_user)):
    """Список камер из конфигурации + статус из Redis."""
    import yaml
    from pathlib import Path
    
    cameras = []
    
    # Читаем конфигурацию камер из файла
    config_path = Path(os.getenv('CAMERAS_CONFIG_PATH', '/app/configs/cameras.yaml'))
    
    try:
        if not config_path.exists():
            logger.warning(f"Cameras config not found at {config_path}")
            return []
        
        with open(config_path, 'r') as f:
            content = f.read()
            config = yaml.safe_load(content) or {}
        
        logger.info(f"Loaded cameras config: {type(config)}, keys: {config.keys() if isinstance(config, dict) else 'N/A'}")
        
        # Извлекаем список камер из конфигурации
        if isinstance(config, dict):
            camera_list = config.get('cameras', [])
        elif isinstance(config, list):
            camera_list = config
        else:
            camera_list = []
        
        if not camera_list:
            logger.info("No cameras in config")
            return []
            
        for cam in camera_list:
            if not isinstance(cam, dict):
                logger.warning(f"Skipping non-dict camera entry: {cam}")
                continue
                
            cam_id = cam.get('id', '')
            if not cam_id:
                logger.warning(f"Skipping camera without id: {cam}")
                continue
            
            # Проверяем статус в Redis (есть ли свежий кадр)
            status = 'disconnected'
            
            # Безопасная проверка Redis
            if state.redis:
                try:
                    has_raw = await state.redis.exists(f"raw:{cam_id}")
                    has_detected = await state.redis.exists(f"detected:{cam_id}")
                    
                    if has_raw or has_detected:
                        status = 'connected'
                    else:
                        # Проверяем статус из camera:{id}
                        cam_data = await state.redis.hgetall(f"camera:{cam_id}")
                        if cam_data:
                            status_val = cam_data.get(b'status', cam_data.get('status', b''))
                            status = status_val.decode() if isinstance(status_val, bytes) else status_val or 'unknown'
                except Exception as e:
                    logger.warning(f"Redis status check failed for {cam_id}: {e}")
            
            cameras.append({
                'id': cam_id,
                'name': cam.get('name', cam_id),
                'url': cam.get('url') or cam.get('rtsp_url', ''),
                'status': status,
                'enabled': cam.get('enabled', True)
            })
        
        logger.info(f"Returning {len(cameras)} cameras")
        return cameras
                
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка парсинга конфигурации: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка загрузки камер: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки камер: {str(e)}")

@app.get("/api/cameras/{camera_id}/stream", tags=["Cameras"])
async def get_camera_stream(camera_id: str, user: str = Depends(get_current_user)):
    """Последний кадр с камеры."""
    frame_data = await get_camera_frame(camera_id)
    if not frame_data:
        raise HTTPException(status_code=404, detail="Нет данных")
    return StreamingResponse(iter([frame_data]), media_type="image/jpeg")

# ============================================================================
# WebSocket (с опциональной аутентификацией через query param)
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    """WebSocket для real-time обновлений."""
    # Проверяем токен если передан
    if token:
        user = verify_token(token)
        if not user:
            await websocket.close(code=4001)
            return
    
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break  # Connection closed
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)

@app.websocket("/ws/camera/{camera_id}")
async def websocket_camera(websocket: WebSocket, camera_id: str, token: Optional[str] = Query(None)):
    """WebSocket стрим камеры - оптимизированный для плавности (v2.10.49)."""
    if token:
        user = verify_token(token)
        if not user:
            await websocket.close(code=4001)
            return
    
    await websocket.accept()
    
    # Настройки производительности v2.10.49
    FRAME_INTERVAL = 0.08  # ~12 FPS для плавного UI
    MAX_FRAME_SIZE = 120000  # ~120KB для быстрой передачи
    SKIP_SAME_FRAME = False  # Не пропускаем одинаковые кадры - это вызывает рывки
    is_connected = True
    frames_sent = 0
    
    async def safe_send(data: dict) -> bool:
        """Safely send data, return False if connection closed."""
        nonlocal is_connected
        if not is_connected:
            return False
        try:
            await asyncio.wait_for(websocket.send_json(data), timeout=1.0)
            return True
        except Exception:
            is_connected = False
            return False
    
    try:
        pubsub = state.redis.pubsub()
        await pubsub.subscribe(f'detections:{camera_id}')
        
        last_frame_time = 0
        
        while is_connected:
            current_time = asyncio.get_event_loop().time()
            
            # Проверяем детекции (приоритет)
            message = await pubsub.get_message(timeout=0.02)
            
            if message and message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    # При детекции отправляем сразу с кадром
                    frame = await get_camera_frame(camera_id)
                    if frame:
                        import base64
                        # Ограничиваем размер кадра
                        if len(frame) > MAX_FRAME_SIZE:
                            # Перекодируем с меньшим качеством
                            import cv2
                            import numpy as np
                            nparr = np.frombuffer(frame, np.uint8)
                            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                            if img is not None:
                                _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 60])
                                frame = buffer.tobytes()
                        data['image'] = base64.b64encode(frame).decode()
                    if not await safe_send(data):
                        break
                    last_frame_time = current_time
                    frames_sent += 1
                except json.JSONDecodeError:
                    pass
            
            # Отправляем кадр с интервалом (без детекций)
            elif current_time - last_frame_time >= FRAME_INTERVAL:
                frame = await get_camera_frame(camera_id)
                if frame:
                    import base64
                    # Ограничиваем размер кадра для быстрой передачи
                    if len(frame) > MAX_FRAME_SIZE:
                        import cv2
                        import numpy as np
                        nparr = np.frombuffer(frame, np.uint8)
                        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if img is not None:
                            _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 65])
                            frame = buffer.tobytes()
                    
                    if not await safe_send({
                        'image': base64.b64encode(frame).decode(),
                        'detections': [],
                        'camera_id': camera_id
                    }):
                        break
                    
                    frames_sent += 1
                last_frame_time = current_time
            
            await asyncio.sleep(0.01)  # 100 проверок в секунду
            
    except WebSocketDisconnect:
        pass
    finally:
        is_connected = False
        logger.debug(f"WebSocket camera {camera_id} disconnected after {frames_sent} frames")
        try:
            await pubsub.unsubscribe(f'detections:{camera_id}')
        except Exception:
            pass

# ============================================================================
# Screenshots API - Снимки с камер для обучения
# ============================================================================

@app.post("/api/screenshots/capture", tags=["Screenshots"])
async def capture_screenshots(user: str = Depends(get_current_user)):
    """Сделать снимки со всех камер для датасета."""
    import base64
    from pathlib import Path
    import aiofiles
    
    screenshots_dir = Path("/app/training_data/screenshots")
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    saved = []
    errors = []
    
    try:
        # Собираем все camera_id из разных ключей
        camera_ids = set()
        
        # Ищем raw ключи (от capture)
        raw_keys = await state.redis.keys('raw:*')
        for key in (raw_keys or []):
            key_str = key.decode() if isinstance(key, bytes) else key
            camera_ids.add(key_str.replace('raw:', ''))
        
        # Ищем detected ключи (от detector)
        detected_keys = await state.redis.keys('detected:*')
        for key in (detected_keys or []):
            key_str = key.decode() if isinstance(key, bytes) else key
            camera_ids.add(key_str.replace('detected:', ''))
        
        # Legacy fallback
        latest_keys = await state.redis.keys('latest:*')
        for key in (latest_keys or []):
            key_str = key.decode() if isinstance(key, bytes) else key
            camera_ids.add(key_str.replace('latest:', ''))
        
        logger.info(f"Найдено камер в Redis: {len(camera_ids)}")
        
        if not camera_ids:
            logger.warning("Нет доступных кадров с камер - capture сервис не публикует кадры")
            return {
                'status': 'warning',
                'message': 'Нет доступных кадров с камер. Проверьте что capture сервис работает и камеры подключены.',
                'saved': [],
                'errors': [],
                'total': 0,
                'hint': 'Выполните: docker logs ppe_capture --tail 20'
            }
        
        for cam_id in camera_ids:
            try:
                frame = await get_camera_frame(cam_id)
                if frame:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # миллисекунды
                    filename = f"{cam_id}_{timestamp}.jpg"
                    filepath = screenshots_dir / filename
                    
                    # Async запись файла
                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(frame)
                    
                    saved.append({
                        'camera_id': cam_id,
                        'filename': filename,
                        'size': len(frame),
                        'path': str(filepath)
                    })
                    logger.info(f"Снимок сохранён: {filename} ({len(frame)} bytes)")
                else:
                    errors.append({'camera_id': cam_id, 'error': 'Пустой кадр'})
            except Exception as e:
                errors.append({'camera_id': cam_id, 'error': str(e)})
                logger.error(f"Ошибка снимка {cam_id}: {e}")
        
        return {
            'status': 'success' if saved else 'error',
            'saved': saved,
            'errors': errors,
            'total': len(saved),
            'path': str(screenshots_dir)
        }
        
    except Exception as e:
        logger.error(f"Ошибка снимков: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка: {e}")

@app.post("/api/screenshots/camera/{camera_id}", tags=["Screenshots"])
async def capture_single_screenshot(camera_id: str, user: str = Depends(get_current_user)):
    """Сделать снимок с одной камеры."""
    import base64
    from pathlib import Path
    import aiofiles
    
    screenshots_dir = Path("/app/training_data/screenshots")
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        frame = await get_camera_frame(camera_id)
        if not frame:
            logger.warning(f"Нет кадра с камеры {camera_id} в Redis")
            raise HTTPException(404, f"Нет кадра с камеры {camera_id}. Проверьте что capture сервис работает.")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{camera_id}_{timestamp}.jpg"
        filepath = screenshots_dir / filename
        
        # Async запись файла
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(frame)
        
        logger.info(f"Снимок камеры {camera_id} сохранён: {filename} ({len(frame)} bytes)")
        
        return {
            'status': 'success',
            'camera_id': camera_id,
            'filename': filename,
            'size': len(frame),
            'path': str(filepath),
            'base64': base64.b64encode(frame).decode()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка снимка: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка: {e}")

# ============================================================================
# Detection Settings API - Настройки детекции
# ============================================================================

# Хранилище настроек (в Redis)
DETECTION_SETTINGS_KEY = "detection:settings"

@app.get("/api/settings/detection", tags=["Settings"])
async def get_detection_settings(user: str = Depends(get_current_user)):
    """Получить настройки детекции."""
    try:
        settings = await state.redis.hgetall(DETECTION_SETTINGS_KEY)
        
        if not settings:
            # Дефолтные настройки
            return {
                'confidence_threshold': 0.5,
                'device': 'auto',
                'fp16': True,
                'nms_threshold': 0.45
            }
        
        def decode_val(v):
            if isinstance(v, bytes):
                v = v.decode()
            if v == 'true':
                return True
            if v == 'false':
                return False
            try:
                return float(v)
            except (ValueError, TypeError):
                return v
        
        return {k.decode() if isinstance(k, bytes) else k: decode_val(v) for k, v in settings.items()}
        
    except Exception as e:
        logger.error(f"Ошибка настроек: {e}")
        return {'confidence_threshold': 0.5, 'device': 'auto', 'fp16': True}

@app.put("/api/settings/detection", tags=["Settings"])
async def update_detection_settings(
    confidence_threshold: float = 0.5,
    device: str = 'auto',
    fp16: bool = True,
    user: str = Depends(get_current_user)
):
    """Обновить настройки детекции."""
    try:
        settings = {
            'confidence_threshold': str(confidence_threshold),
            'device': device,
            'fp16': 'true' if fp16 else 'false'
        }
        
        await state.redis.hset(DETECTION_SETTINGS_KEY, mapping=settings)
        
        # Уведомляем detector о изменении настроек
        await state.redis.publish("system:settings_updated", "detection")
        
        return {'status': 'success', 'settings': settings}
        
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        raise HTTPException(500, f"Ошибка: {e}")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
