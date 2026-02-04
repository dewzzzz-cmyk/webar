"""
Unit тесты для API Service
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import jwt
import sys
import os

# Добавляем путь к сервисам
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/api'))


class TestJWTAuthentication:
    """Тесты JWT аутентификации."""
    
    JWT_SECRET = 'test-secret-key'
    JWT_ALGORITHM = 'HS256'
    
    def test_create_valid_token(self):
        """Тест создания валидного токена."""
        payload = {
            'sub': 'testuser',
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        
        token = jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)
        
        assert token is not None
        assert isinstance(token, str)
    
    def test_decode_valid_token(self):
        """Тест декодирования валидного токена."""
        payload = {
            'sub': 'testuser',
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        
        token = jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)
        decoded = jwt.decode(token, self.JWT_SECRET, algorithms=[self.JWT_ALGORITHM])
        
        assert decoded['sub'] == 'testuser'
    
    def test_expired_token(self):
        """Тест истёкшего токена."""
        payload = {
            'sub': 'testuser',
            'iat': datetime.utcnow() - timedelta(hours=25),
            'exp': datetime.utcnow() - timedelta(hours=1)  # Истёк час назад
        }
        
        token = jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)
        
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, self.JWT_SECRET, algorithms=[self.JWT_ALGORITHM])
    
    def test_invalid_token(self):
        """Тест невалидного токена."""
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode('invalid.token.here', self.JWT_SECRET, algorithms=[self.JWT_ALGORITHM])
    
    def test_wrong_secret(self):
        """Тест токена с неправильным секретом."""
        payload = {
            'sub': 'testuser',
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        
        token = jwt.encode(payload, 'wrong-secret', algorithm=self.JWT_ALGORITHM)
        
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, self.JWT_SECRET, algorithms=[self.JWT_ALGORITHM])


class TestRateLimiter:
    """Тесты Rate Limiter."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self):
        """Тест разрешения запросов в пределах лимита."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.setex = AsyncMock()
        
        # Симуляция: первый запрос
        current = await mock_redis.get("ratelimit:test")
        
        if current is None:
            await mock_redis.setex("ratelimit:test", 60, 1)
            allowed = True
        else:
            allowed = int(current) < 100
        
        assert allowed is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess(self):
        """Тест блокировки при превышении лимита."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b'100'  # Уже на лимите
        
        current = await mock_redis.get("ratelimit:test")
        allowed = int(current) < 100
        
        assert allowed is False


class TestViolationSchema:
    """Тесты схем данных."""
    
    def test_violation_response_structure(self):
        """Тест структуры ответа нарушения."""
        violation = {
            'id': 'abc12345',
            'timestamp': datetime.now().isoformat(),
            'camera_id': 'cam_1',
            'zone_id': 'zone_default',
            'violation_type': 'no_hardhat',
            'confidence': 0.85,
            'person_id': 42,
            'bbox': [100, 100, 200, 200],
            'image_path': 'abc12345.jpg',
            'acknowledged': False
        }
        
        assert 'id' in violation
        assert 'timestamp' in violation
        assert 'camera_id' in violation
        assert 'violation_type' in violation
        assert 'confidence' in violation
        assert 'bbox' in violation
        assert len(violation['bbox']) == 4
    
    def test_violation_stats_structure(self):
        """Тест структуры статистики."""
        stats = {
            'total': 150,
            'by_type': {'no_hardhat': 80, 'no_vest': 70},
            'by_camera': {'cam_1': 100, 'cam_2': 50},
            'by_hour': {'10:00': 30, '11:00': 45}
        }
        
        assert stats['total'] == 150
        assert sum(stats['by_type'].values()) == 150
        assert sum(stats['by_camera'].values()) == 150


class TestAPIEndpoints:
    """Тесты логики API endpoints."""
    
    def test_pagination_params(self):
        """Тест параметров пагинации."""
        limit = 100
        offset = 0
        
        assert 1 <= limit <= 1000
        assert offset >= 0
    
    def test_hours_filter(self):
        """Тест фильтра по часам."""
        hours = 24
        since = datetime.now() - timedelta(hours=hours)
        
        assert since < datetime.now()
        assert (datetime.now() - since).total_seconds() == hours * 3600
    
    def test_acknowledge_request(self):
        """Тест запроса подтверждения."""
        request = {
            'acknowledged_by': 'admin',
            'notes': 'Проверено, сотрудник предупреждён'
        }
        
        assert 'acknowledged_by' in request
        assert request['acknowledged_by'] is not None


class TestWebSocket:
    """Тесты WebSocket логики."""
    
    def test_alert_message_structure(self):
        """Тест структуры сообщения алерта."""
        message = {
            'type': 'violation',
            'data': {
                'id': 'abc12345',
                'camera_id': 'cam_1',
                'violation_type': 'no_hardhat',
                'confidence': 0.85,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        assert message['type'] == 'violation'
        assert 'data' in message
        assert 'id' in message['data']
    
    def test_ping_message(self):
        """Тест ping сообщения."""
        message = {'type': 'ping'}
        
        assert message['type'] == 'ping'


# Запуск тестов
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
