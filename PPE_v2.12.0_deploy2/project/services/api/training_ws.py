"""
Training WebSocket Handler
Real-time training progress via WebSocket + Redis Pub/Sub
"""

import asyncio
import json
import logging
from typing import Set, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
import aioredis

logger = logging.getLogger('training_ws')

class TrainingProgressManager:
    """Manages WebSocket connections for training progress."""
    
    def __init__(self, redis_url: str = 'redis://redis:6379'):
        self.redis_url = redis_url
        self.active_connections: Dict[str, Set[WebSocket]] = {}  # job_id -> connections
        self.redis = None
        self.pubsub = None
        self._listener_task = None
    
    async def connect(self):
        """Initialize Redis connection."""
        if not self.redis:
            self.redis = await aioredis.from_url(self.redis_url)
    
    async def subscribe(self, websocket: WebSocket, job_id: str):
        """Subscribe to training progress for a job."""
        await websocket.accept()
        
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        
        self.active_connections[job_id].add(websocket)
        logger.info(f"Client subscribed to job {job_id}. Total: {len(self.active_connections[job_id])}")
        
        # Send current state
        await self._send_current_state(websocket, job_id)
        
        # Start listener if needed
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._listen_redis())
    
    async def disconnect(self, websocket: WebSocket, job_id: str):
        """Unsubscribe from training progress."""
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
        logger.info(f"Client disconnected from job {job_id}")
    
    async def _send_current_state(self, websocket: WebSocket, job_id: str):
        """Send current training state to new connection."""
        try:
            await self.connect()
            state = await self.redis.hgetall(f"training:state:{job_id}")
            
            if state:
                # Convert bytes to strings
                state_dict = {k.decode() if isinstance(k, bytes) else k: 
                             v.decode() if isinstance(v, bytes) else v 
                             for k, v in state.items()}
                
                await websocket.send_json({
                    'type': 'state',
                    'job_id': job_id,
                    'data': state_dict
                })
        except Exception as e:
            logger.error(f"Failed to send current state: {e}")
    
    async def _listen_redis(self):
        """Listen to Redis Pub/Sub for training updates."""
        try:
            await self.connect()
            pubsub = self.redis.pubsub()
            
            # Subscribe to all training channels
            await pubsub.psubscribe('training:progress:*')
            
            logger.info("Started listening to training progress channels")
            
            async for message in pubsub.listen():
                if message['type'] == 'pmessage':
                    try:
                        channel = message['channel']
                        if isinstance(channel, bytes):
                            channel = channel.decode()
                        
                        # Extract job_id from channel
                        job_id = channel.split(':')[-1]
                        
                        data = message['data']
                        if isinstance(data, bytes):
                            data = data.decode()
                        
                        progress_data = json.loads(data)
                        
                        # Broadcast to subscribers
                        await self._broadcast(job_id, progress_data)
                        
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        
        except asyncio.CancelledError:
            logger.info("Redis listener cancelled")
        except Exception as e:
            logger.error(f"Redis listener error: {e}")
    
    async def _broadcast(self, job_id: str, data: Dict[str, Any]):
        """Broadcast progress to all subscribers of a job."""
        if job_id not in self.active_connections:
            return
        
        dead_connections = set()
        
        for websocket in self.active_connections[job_id]:
            try:
                await websocket.send_json({
                    'type': 'progress',
                    'job_id': job_id,
                    'data': data
                })
            except Exception as e:
                logger.error(f"Failed to send to websocket: {e}")
                dead_connections.add(websocket)
        
        # Remove dead connections
        for ws in dead_connections:
            self.active_connections[job_id].discard(ws)


# Singleton instance
progress_manager = TrainingProgressManager()


async def training_progress_websocket(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for training progress.
    
    Usage:
        ws://host/api/training/ws/progress/{job_id}
    
    Messages:
        {
            "type": "progress",
            "job_id": "...",
            "data": {
                "status": "running",
                "event": "epoch_end",
                "epoch": 10,
                "progress": 20.0,
                "train_loss": 0.5,
                "map50": 0.75
            }
        }
    """
    try:
        await progress_manager.subscribe(websocket, job_id)
        
        # Keep connection alive
        while True:
            try:
                # Wait for client messages (ping/pong)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                # Handle ping
                if data == 'ping':
                    await websocket.send_text('pong')
                    
            except asyncio.TimeoutError:
                # Send ping to check connection
                try:
                    await websocket.send_text('ping')
                except Exception:
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await progress_manager.disconnect(websocket, job_id)


# ============================================================================
# Training Logs API
# ============================================================================

async def get_training_logs(job_id: str, db_pool) -> list:
    """Get training logs for charts."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT epoch, train_loss, val_loss, map50, map50_95, learning_rate, created_at
               FROM training_logs
               WHERE job_id = $1
               ORDER BY epoch, created_at""",
            job_id
        )
        
        return [
            {
                'epoch': r['epoch'],
                'train_loss': r['train_loss'],
                'val_loss': r['val_loss'],
                'map50': r['map50'],
                'map50_95': r['map50_95'],
                'learning_rate': r['learning_rate'],
                'timestamp': r['created_at'].isoformat() if r['created_at'] else None
            }
            for r in rows
        ]
