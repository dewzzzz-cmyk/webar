#!/usr/bin/env python3
"""
Alerter Service v2.1 - Исправленная версия

Исправления:
- Cooldown в Redis (не в памяти)
- Retry с exponential backoff для Telegram
- Очередь алертов для надёжности
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

import redis.asyncio as aioredis
import httpx

# ============================================================================
# Configuration
# ============================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
logger = logging.getLogger('alerter')

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
VIOLATIONS_PATH = os.getenv('VIOLATIONS_PATH', '/app/violations')
ALERT_COOLDOWN = int(os.getenv('ALERT_COOLDOWN', 30))

# Retry settings
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', 5))

VIOLATION_NAMES = {
    'no_hardhat': '🪖 Без каски',
    'no_vest': '🦺 Без жилета',
    'no_glasses': '🥽 Без очков',
    'no_gloves': '🧤 Без перчаток',
}

# ============================================================================
# Cooldown Manager (Redis-based) - ИСПРАВЛЕНИЕ
# ============================================================================

class CooldownManager:
    """Cooldown в Redis - переживает рестарты."""
    
    def __init__(self, redis: aioredis.Redis, default_cooldown: int = 30):
        self.redis = redis
        self.default_cooldown = default_cooldown
        self.prefix = "alert_cooldown:"
    
    async def is_in_cooldown(self, key: str) -> bool:
        """Проверка cooldown."""
        return await self.redis.exists(f"{self.prefix}{key}") > 0
    
    async def set_cooldown(self, key: str, seconds: Optional[int] = None):
        """Установка cooldown."""
        ttl = seconds or self.default_cooldown
        await self.redis.setex(f"{self.prefix}{key}", ttl, "1")

# ============================================================================
# Telegram Client with Retry - ИСПРАВЛЕНИЕ
# ============================================================================

class TelegramClient:
    """Клиент Telegram с retry логикой."""
    
    def __init__(self, bot_token: str, chat_id: str, max_retries: int = 3, retry_delay: int = 5):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def _send_with_retry(self, method: str, **kwargs) -> bool:
        """Отправка с retry и exponential backoff."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram не настроен")
            return False
        
        for attempt in range(self.max_retries):
            try:
                if method == 'sendMessage':
                    response = await self.client.post(
                        f"{self.base_url}/sendMessage",
                        json={"chat_id": self.chat_id, **kwargs}
                    )
                elif method == 'sendPhoto':
                    files = kwargs.pop('files', None)
                    data = {"chat_id": self.chat_id, **kwargs}
                    response = await self.client.post(
                        f"{self.base_url}/sendPhoto",
                        data=data,
                        files=files
                    )
                else:
                    return False
                
                if response.status_code == 200:
                    logger.info(f"Telegram: {method} успешно (попытка {attempt + 1})")
                    return True
                elif response.status_code == 429:
                    # Rate limited - ждём дольше
                    retry_after = int(response.headers.get('Retry-After', self.retry_delay * 2))
                    logger.warning(f"Telegram rate limit, ждём {retry_after}с")
                    await asyncio.sleep(retry_after)
                else:
                    logger.error(f"Telegram ошибка {response.status_code}: {response.text}")
                    
            except httpx.TimeoutException:
                logger.warning(f"Telegram timeout (попытка {attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.error(f"Telegram ошибка: {e}")
            
            # Exponential backoff
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)
                logger.info(f"Retry через {delay}с...")
                await asyncio.sleep(delay)
        
        logger.error(f"Telegram: не удалось отправить после {self.max_retries} попыток")
        return False
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        return await self._send_with_retry('sendMessage', text=text, parse_mode=parse_mode)
    
    async def send_photo(self, photo_path: str, caption: str, parse_mode: str = "HTML") -> bool:
        if not os.path.exists(photo_path):
            logger.warning(f"Фото не найдено: {photo_path}")
            return await self.send_message(caption, parse_mode)
        
        try:
            with open(photo_path, 'rb') as photo:
                return await self._send_with_retry(
                    'sendPhoto',
                    caption=caption,
                    parse_mode=parse_mode,
                    files={"photo": photo}
                )
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            return await self.send_message(caption, parse_mode)
    
    async def close(self):
        await self.client.aclose()

# ============================================================================
# Alert Queue - ИСПРАВЛЕНИЕ: очередь для надёжности
# ============================================================================

class AlertQueue:
    """Очередь алертов в Redis для надёжной доставки."""
    
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.queue_key = "alerts:queue"
        self.failed_key = "alerts:failed"
    
    async def push(self, alert: Dict):
        """Добавить алерт в очередь."""
        await self.redis.lpush(self.queue_key, json.dumps(alert))
    
    async def pop(self) -> Optional[Dict]:
        """Получить алерт из очереди."""
        data = await self.redis.rpop(self.queue_key)
        if data:
            return json.loads(data)
        return None
    
    async def push_failed(self, alert: Dict):
        """Сохранить неудачный алерт."""
        await self.redis.lpush(self.failed_key, json.dumps(alert))
    
    async def get_queue_length(self) -> int:
        """Длина очереди."""
        return await self.redis.llen(self.queue_key)

# ============================================================================
# Alerter Service
# ============================================================================

class AlerterService:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.telegram: Optional[TelegramClient] = None
        self.cooldown: Optional[CooldownManager] = None
        self.queue: Optional[AlertQueue] = None
        self._shutdown = False
    
    async def start(self):
        logger.info("="*60)
        logger.info("  ALERTER SERVICE v2.1 - Запуск")
        logger.info("="*60)
        
        self.redis = await aioredis.from_url(REDIS_URL)
        self.cooldown = CooldownManager(self.redis, ALERT_COOLDOWN)
        self.queue = AlertQueue(self.redis)
        
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            self.telegram = TelegramClient(
                TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
                max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY
            )
            logger.info("Telegram клиент инициализирован")
            
            await self.telegram.send_message(
                "🟢 <b>PPE Detection System v2.1</b>\n\n"
                "Система контроля СИЗ запущена.\n"
                f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            )
        else:
            logger.warning("Telegram не настроен")
        
        # Запускаем обработчики
        await asyncio.gather(
            self.subscribe_alerts(),
            self.process_queue()
        )
    
    async def subscribe_alerts(self):
        """Подписка на алерты из Redis Pub/Sub."""
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe('alerts')
            logger.info("Подписка на 'alerts' активна")
            
            async for message in pubsub.listen():
                if self._shutdown:
                    break
                
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        # Добавляем в очередь для надёжной обработки
                        await self.queue.push(data)
                    except Exception as e:
                        logger.error(f"Ошибка парсинга: {e}")
                        
        except Exception as e:
            logger.error(f"Ошибка подписки: {e}")
    
    async def process_queue(self):
        """Обработка очереди алертов."""
        logger.info("Обработчик очереди запущен")
        
        while not self._shutdown:
            try:
                alert = await self.queue.pop()
                
                if alert is None:
                    await asyncio.sleep(0.1)
                    continue
                
                success = await self.handle_alert(alert)
                
                if not success:
                    # Сохраняем неудачный алерт
                    await self.queue.push_failed(alert)
                    
            except Exception as e:
                logger.error(f"Ошибка очереди: {e}")
                await asyncio.sleep(1)
    
    async def handle_alert(self, alert: Dict) -> bool:
        """Обработка алерта."""
        camera_id = alert.get('camera_id')
        violation_type = alert.get('violation_type')
        confidence = alert.get('confidence', 0)
        timestamp = alert.get('timestamp')
        image_path = alert.get('image_path')
        person_id = alert.get('person_id')
        violation_id = alert.get('id')
        
        # ИСПРАВЛЕНИЕ: Cooldown в Redis
        cooldown_key = f"{camera_id}:{person_id or 'unknown'}:{violation_type}"
        
        if await self.cooldown.is_in_cooldown(cooldown_key):
            logger.debug(f"Cooldown: {cooldown_key}")
            return True  # Считаем успехом, просто пропускаем
        
        # Формируем сообщение
        violation_name = VIOLATION_NAMES.get(violation_type, violation_type)
        
        message = (
            f"⚠️ <b>НАРУШЕНИЕ СИЗ</b>\n\n"
            f"📋 <b>Тип:</b> {violation_name}\n"
            f"📹 <b>Камера:</b> {camera_id}\n"
            f"🎯 <b>Уверенность:</b> {confidence:.0%}\n"
            f"🕐 <b>Время:</b> {timestamp}\n"
        )
        
        if person_id:
            message += f"👤 <b>ID:</b> #{person_id}\n"
        
        message += f"\n🔗 <code>{violation_id}</code>"
        
        # Отправляем
        success = False
        if self.telegram:
            if image_path:
                full_path = os.path.join(VIOLATIONS_PATH, image_path)
                success = await self.telegram.send_photo(full_path, message)
            else:
                success = await self.telegram.send_message(message)
        else:
            # Если Telegram не настроен, просто логируем
            logger.info(f"Алерт (без Telegram): {violation_type} @ {camera_id}")
            success = True
        
        if success:
            # ИСПРАВЛЕНИЕ: Cooldown в Redis
            await self.cooldown.set_cooldown(cooldown_key)
            logger.info(f"Алерт отправлен: {violation_type} @ {camera_id}")
        
        return success
    
    async def stop(self):
        self._shutdown = True
        
        if self.telegram:
            await self.telegram.send_message(
                "🔴 <b>PPE Detection System</b>\n\nСистема остановлена."
            )
            await self.telegram.close()
        
        if self.redis:
            await self.redis.close()
        
        logger.info("Alerter Service остановлен")

async def main():
    service = AlerterService()
    
    try:
        await service.start()
    except KeyboardInterrupt:
        pass
    finally:
        await service.stop()

if __name__ == '__main__':
    asyncio.run(main())
