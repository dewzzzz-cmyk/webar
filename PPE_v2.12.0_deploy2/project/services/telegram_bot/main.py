"""
PPE Detection - Telegram Bot with Commands
Полноценный бот с командами: /status, /stats, /cameras, /help
"""

import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
from typing import Optional
import aiohttp
import redis.asyncio as redis
import asyncpg

# Telegram Bot API
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ALLOWED_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", TELEGRAM_CHAT_ID).split(",")

# Services
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ppe:ppe_secret@postgres:5432/ppe_detection")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PPETelegramBot:
    """Telegram bot for PPE Detection System."""
    
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis: Optional[redis.Redis] = None
        self.last_update_id = 0
        self.running = False
        
        # Command handlers
        self.commands = {
            "/start": self.cmd_start,
            "/help": self.cmd_help,
            "/status": self.cmd_status,
            "/stats": self.cmd_stats,
            "/cameras": self.cmd_cameras,
            "/violations": self.cmd_violations,
            "/mute": self.cmd_mute,
            "/unmute": self.cmd_unmute,
        }
    
    async def init(self):
        """Initialize connections."""
        try:
            self.db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
            self.redis = redis.from_url(REDIS_URL, decode_responses=True)
            logger.info("✅ Bot initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            raise
    
    async def close(self):
        """Close connections."""
        if self.db_pool:
            await self.db_pool.close()
        if self.redis:
            await self.redis.close()
    
    # =========================================================================
    # TELEGRAM API
    # =========================================================================
    
    async def send_message(
        self, 
        chat_id: str, 
        text: str, 
        parse_mode: str = "HTML",
        reply_markup: Optional[dict] = None
    ) -> bool:
        """Send message to Telegram."""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode
                }
                if reply_markup:
                    payload["reply_markup"] = json.dumps(reply_markup)
                
                async with session.post(
                    f"{self.base_url}/sendMessage",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    async def get_updates(self, offset: int = 0) -> list:
        """Get updates from Telegram."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                    timeout=aiohttp.ClientTimeout(total=35)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("result", [])
        except Exception as e:
            logger.error(f"Failed to get updates: {e}")
        return []
    
    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================
    
    async def cmd_start(self, chat_id: str, args: list):
        """Handle /start command."""
        text = """
🦺 <b>PPE Detection System Bot</b>

Добро пожаловать! Этот бот отправляет уведомления о нарушениях СИЗ и позволяет контролировать систему.

<b>Доступные команды:</b>
/status - Статус системы
/stats - Статистика нарушений
/cameras - Список камер
/violations - Последние нарушения
/mute [мин] - Отключить уведомления
/unmute - Включить уведомления
/help - Справка

🔔 Уведомления включены
        """
        await self.send_message(chat_id, text.strip())
    
    async def cmd_help(self, chat_id: str, args: list):
        """Handle /help command."""
        text = """
📖 <b>Справка по командам</b>

<b>/status</b>
Показывает текущий статус системы: количество активных камер, состояние сервисов, загрузку.

<b>/stats</b> [период]
Статистика нарушений. Периоды:
• /stats - за сегодня
• /stats week - за неделю
• /stats month - за месяц

<b>/cameras</b>
Список камер и их статус (online/offline).

<b>/violations</b> [кол-во]
Последние нарушения. По умолчанию 5.
• /violations 10 - последние 10

<b>/mute</b> [минуты]
Отключить уведомления на указанное время.
• /mute - на 30 минут
• /mute 60 - на 1 час

<b>/unmute</b>
Включить уведомления.

💡 <i>Бот отправляет уведомления о нарушениях СИЗ в реальном времени</i>
        """
        await self.send_message(chat_id, text.strip())
    
    async def cmd_status(self, chat_id: str, args: list):
        """Handle /status command."""
        try:
            # Get system status
            status = {
                "cameras_online": 0,
                "cameras_total": 0,
                "violations_today": 0,
                "db_status": "❓",
                "redis_status": "❓",
                "detector_fps": 0
            }
            
            # Check database
            try:
                async with self.db_pool.acquire() as conn:
                    # Count violations today
                    status["violations_today"] = await conn.fetchval("""
                        SELECT COUNT(*) FROM violations 
                        WHERE timestamp >= CURRENT_DATE
                    """) or 0
                    status["db_status"] = "✅"
            except Exception:
                status["db_status"] = "❌"
            
            # Check Redis
            try:
                await self.redis.ping()
                status["redis_status"] = "✅"
                
                # Get camera statuses from Redis
                keys = await self.redis.keys("camera:status:*")
                status["cameras_total"] = len(keys)
                
                for key in keys:
                    data = await self.redis.get(key)
                    if data:
                        cam_status = json.loads(data)
                        if cam_status.get("online"):
                            status["cameras_online"] += 1
                
                # Get detector FPS
                fps = await self.redis.get("detector:fps")
                status["detector_fps"] = float(fps) if fps else 0
            except Exception:
                status["redis_status"] = "❌"
            
            # Check mute status
            muted_until = await self.redis.get(f"bot:muted:{chat_id}")
            mute_status = ""
            if muted_until:
                mute_status = f"\n🔇 <i>Уведомления отключены до {muted_until}</i>"
            
            text = f"""
📊 <b>Статус системы</b>

<b>Камеры:</b> {status["cameras_online"]}/{status["cameras_total"]} online
<b>Нарушений сегодня:</b> {status["violations_today"]}
<b>Детектор FPS:</b> {status["detector_fps"]:.1f}

<b>Сервисы:</b>
• База данных: {status["db_status"]}
• Redis: {status["redis_status"]}
{mute_status}

🕐 <i>{datetime.now().strftime("%H:%M:%S %d.%m.%Y")}</i>
            """
            await self.send_message(chat_id, text.strip())
            
        except Exception as e:
            logger.error(f"Error in /status: {e}")
            await self.send_message(chat_id, f"❌ Ошибка получения статуса: {e}")
    
    async def cmd_stats(self, chat_id: str, args: list):
        """Handle /stats command."""
        try:
            # Parse period
            period = args[0] if args else "today"
            
            if period == "week":
                date_filter = "timestamp >= CURRENT_DATE - INTERVAL '7 days'"
                period_name = "за неделю"
            elif period == "month":
                date_filter = "timestamp >= CURRENT_DATE - INTERVAL '30 days'"
                period_name = "за месяц"
            else:
                date_filter = "timestamp >= CURRENT_DATE"
                period_name = "за сегодня"
            
            async with self.db_pool.acquire() as conn:
                # Total violations
                total = await conn.fetchval(f"""
                    SELECT COUNT(*) FROM violations WHERE {date_filter}
                """) or 0
                
                # By type
                by_type = await conn.fetch(f"""
                    SELECT violation_type, COUNT(*) as count
                    FROM violations WHERE {date_filter}
                    GROUP BY violation_type
                    ORDER BY count DESC
                """)
                
                # By camera
                by_camera = await conn.fetch(f"""
                    SELECT camera_id, COUNT(*) as count
                    FROM violations WHERE {date_filter}
                    GROUP BY camera_id
                    ORDER BY count DESC
                    LIMIT 5
                """)
                
                # Acknowledged
                acknowledged = await conn.fetchval(f"""
                    SELECT COUNT(*) FROM violations 
                    WHERE {date_filter} AND acknowledged = true
                """) or 0
            
            # Format types
            types_text = ""
            type_emoji = {
                "no_hardhat": "🪖",
                "no_vest": "🦺",
                "no_glasses": "🥽",
                "no_mask": "😷"
            }
            for row in by_type:
                emoji = type_emoji.get(row["violation_type"], "⚠️")
                types_text += f"\n  {emoji} {row['violation_type']}: {row['count']}"
            
            # Format cameras
            cameras_text = ""
            for row in by_camera:
                cameras_text += f"\n  📹 {row['camera_id']}: {row['count']}"
            
            text = f"""
📈 <b>Статистика {period_name}</b>

<b>Всего нарушений:</b> {total}
<b>Подтверждено:</b> {acknowledged} ({100*acknowledged//max(total,1)}%)

<b>По типам:</b>{types_text or " нет данных"}

<b>Топ камер:</b>{cameras_text or " нет данных"}

🕐 <i>{datetime.now().strftime("%H:%M:%S")}</i>
            """
            await self.send_message(chat_id, text.strip())
            
        except Exception as e:
            logger.error(f"Error in /stats: {e}")
            await self.send_message(chat_id, f"❌ Ошибка: {e}")
    
    async def cmd_cameras(self, chat_id: str, args: list):
        """Handle /cameras command."""
        try:
            cameras_text = ""
            
            # Get from Redis
            keys = await self.redis.keys("camera:status:*")
            
            if not keys:
                cameras_text = "<i>Нет данных о камерах</i>"
            else:
                for key in sorted(keys):
                    camera_id = key.split(":")[-1]
                    data = await self.redis.get(key)
                    
                    if data:
                        status = json.loads(data)
                        online = status.get("online", False)
                        fps = status.get("fps", 0)
                        emoji = "🟢" if online else "🔴"
                        status_text = f"{fps:.1f} FPS" if online else "offline"
                        cameras_text += f"\n{emoji} <b>{camera_id}</b>: {status_text}"
                    else:
                        cameras_text += f"\n⚪ <b>{camera_id}</b>: нет данных"
            
            text = f"""
📹 <b>Камеры</b>

{cameras_text}

🟢 online  🔴 offline

🕐 <i>{datetime.now().strftime("%H:%M:%S")}</i>
            """
            await self.send_message(chat_id, text.strip())
            
        except Exception as e:
            logger.error(f"Error in /cameras: {e}")
            await self.send_message(chat_id, f"❌ Ошибка: {e}")
    
    async def cmd_violations(self, chat_id: str, args: list):
        """Handle /violations command."""
        try:
            limit = int(args[0]) if args else 5
            limit = min(max(limit, 1), 20)  # Between 1 and 20
            
            async with self.db_pool.acquire() as conn:
                violations = await conn.fetch("""
                    SELECT id, camera_id, violation_type, confidence, 
                           timestamp, acknowledged
                    FROM violations
                    ORDER BY timestamp DESC
                    LIMIT $1
                """, limit)
            
            if not violations:
                await self.send_message(chat_id, "📋 Нарушений пока нет")
                return
            
            text = f"📋 <b>Последние {len(violations)} нарушений</b>\n"
            
            type_emoji = {
                "no_hardhat": "🪖",
                "no_vest": "🦺",
                "no_glasses": "🥽",
                "no_mask": "😷"
            }
            
            for v in violations:
                emoji = type_emoji.get(v["violation_type"], "⚠️")
                time_str = v["timestamp"].strftime("%H:%M:%S")
                ack = "✓" if v["acknowledged"] else ""
                
                text += f"\n{emoji} <b>{v['violation_type']}</b> {ack}"
                text += f"\n   📹 {v['camera_id']} | {time_str} | {v['confidence']*100:.0f}%\n"
            
            await self.send_message(chat_id, text.strip())
            
        except Exception as e:
            logger.error(f"Error in /violations: {e}")
            await self.send_message(chat_id, f"❌ Ошибка: {e}")
    
    async def cmd_mute(self, chat_id: str, args: list):
        """Handle /mute command."""
        try:
            minutes = int(args[0]) if args else 30
            minutes = min(max(minutes, 5), 1440)  # Between 5 min and 24 hours
            
            until = datetime.now() + timedelta(minutes=minutes)
            until_str = until.strftime("%H:%M")
            
            await self.redis.setex(
                f"bot:muted:{chat_id}",
                minutes * 60,
                until_str
            )
            
            await self.send_message(
                chat_id,
                f"🔇 Уведомления отключены на {minutes} мин (до {until_str})"
            )
        except Exception as e:
            logger.error(f"Error in /mute: {e}")
            await self.send_message(chat_id, f"❌ Ошибка: {e}")
    
    async def cmd_unmute(self, chat_id: str, args: list):
        """Handle /unmute command."""
        try:
            await self.redis.delete(f"bot:muted:{chat_id}")
            await self.send_message(chat_id, "🔔 Уведомления включены")
        except Exception as e:
            logger.error(f"Error in /unmute: {e}")
            await self.send_message(chat_id, f"❌ Ошибка: {e}")
    
    # =========================================================================
    # MESSAGE PROCESSING
    # =========================================================================
    
    async def process_message(self, message: dict):
        """Process incoming message."""
        try:
            chat_id = str(message["chat"]["id"])
            text = message.get("text", "")
            
            # Check if chat is allowed
            if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
                logger.warning(f"Unauthorized chat: {chat_id}")
                await self.send_message(
                    chat_id, 
                    "⛔ Доступ запрещён. Обратитесь к администратору."
                )
                return
            
            # Parse command
            if text.startswith("/"):
                parts = text.split()
                command = parts[0].split("@")[0].lower()  # Handle @botname
                args = parts[1:]
                
                handler = self.commands.get(command)
                if handler:
                    await handler(chat_id, args)
                else:
                    await self.send_message(
                        chat_id, 
                        f"❓ Неизвестная команда: {command}\n/help - список команд"
                    )
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    
    async def run(self):
        """Main bot loop."""
        logger.info("🤖 Starting Telegram bot...")
        await self.init()
        self.running = True
        
        while self.running:
            try:
                updates = await self.get_updates(self.last_update_id + 1)
                
                for update in updates:
                    self.last_update_id = update["update_id"]
                    
                    if "message" in update:
                        await self.process_message(update["message"])
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)
        
        await self.close()
        logger.info("Bot stopped")
    
    def stop(self):
        """Stop the bot."""
        self.running = False


# =============================================================================
# ALERT SENDER (для интеграции с Alerter сервисом)
# =============================================================================

class AlertSender:
    """Send violation alerts via Telegram."""
    
    def __init__(self, bot_token: str, chat_id: str, redis_client: redis.Redis):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.redis = redis_client
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def is_muted(self) -> bool:
        """Check if notifications are muted."""
        return await self.redis.exists(f"bot:muted:{self.chat_id}") > 0
    
    async def send_violation_alert(
        self,
        camera_id: str,
        violation_type: str,
        confidence: float,
        image_path: Optional[str] = None,
        zone_name: Optional[str] = None
    ) -> bool:
        """Send violation alert."""
        
        # Check mute
        if await self.is_muted():
            logger.info("Notifications muted, skipping alert")
            return True
        
        # Format message
        type_emoji = {
            "no_hardhat": "🪖",
            "no_vest": "🦺",
            "no_glasses": "🥽",
            "no_mask": "😷"
        }
        emoji = type_emoji.get(violation_type, "⚠️")
        
        type_names = {
            "no_hardhat": "Без каски",
            "no_vest": "Без жилета",
            "no_glasses": "Без очков",
            "no_mask": "Без маски"
        }
        type_name = type_names.get(violation_type, violation_type)
        
        text = f"""
{emoji} <b>Нарушение СИЗ</b>

<b>Тип:</b> {type_name}
<b>Камера:</b> {camera_id}
<b>Уверенность:</b> {confidence*100:.0f}%
<b>Время:</b> {datetime.now().strftime("%H:%M:%S")}
        """
        
        if zone_name:
            text += f"\n<b>Зона:</b> {zone_name}"
        
        try:
            async with aiohttp.ClientSession() as session:
                if image_path and os.path.exists(image_path):
                    # Send with photo
                    with open(image_path, "rb") as photo:
                        form = aiohttp.FormData()
                        form.add_field("chat_id", self.chat_id)
                        form.add_field("caption", text.strip())
                        form.add_field("parse_mode", "HTML")
                        form.add_field("photo", photo, filename="violation.jpg")
                        
                        async with session.post(
                            f"{self.base_url}/sendPhoto",
                            data=form
                        ) as response:
                            return response.status == 200
                else:
                    # Send text only
                    async with session.post(
                        f"{self.base_url}/sendMessage",
                        json={
                            "chat_id": self.chat_id,
                            "text": text.strip(),
                            "parse_mode": "HTML"
                        }
                    ) as response:
                        return response.status == 200
                        
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Main entry point."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN not set! Bot is disabled.")
        logger.info("To enable the bot, set TELEGRAM_BOT_TOKEN in .env file")
        # Вместо exit - спим, чтобы не рестартовать бесконечно
        while True:
            await asyncio.sleep(3600)  # Спать час
    
    bot = PPETelegramBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
