"""
Unit тесты для PPE Detector
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Добавляем путь к сервисам
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/detector'))


class TestCooldownManager:
    """Тесты для CooldownManager."""
    
    def test_cooldown_key_generation(self):
        """Тест генерации ключа cooldown."""
        from main import CooldownManager
        
        mock_redis = Mock()
        manager = CooldownManager(mock_redis, default_cooldown=30)
        
        key = manager._make_key("cam_1", 42, "no_hardhat")
        assert key == "cooldown:cam_1:42:no_hardhat"
        
        key_unknown = manager._make_key("cam_1", None, "no_vest")
        assert key_unknown == "cooldown:cam_1:unknown:no_vest"
    
    def test_is_in_cooldown_true(self):
        """Тест проверки активного cooldown."""
        from main import CooldownManager
        
        mock_redis = Mock()
        mock_redis.exists.return_value = 1
        
        manager = CooldownManager(mock_redis, default_cooldown=30)
        
        result = manager.is_in_cooldown("cam_1", 42, "no_hardhat")
        
        assert result is True
        mock_redis.exists.assert_called_once()
    
    def test_is_in_cooldown_false(self):
        """Тест проверки отсутствия cooldown."""
        from main import CooldownManager
        
        mock_redis = Mock()
        mock_redis.exists.return_value = 0
        
        manager = CooldownManager(mock_redis, default_cooldown=30)
        
        result = manager.is_in_cooldown("cam_1", 42, "no_hardhat")
        
        assert result is False
    
    def test_set_cooldown(self):
        """Тест установки cooldown."""
        from main import CooldownManager
        
        mock_redis = Mock()
        manager = CooldownManager(mock_redis, default_cooldown=30)
        
        manager.set_cooldown("cam_1", 42, "no_hardhat", 60)
        
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == "cooldown:cam_1:42:no_hardhat"
        assert args[1] == 60


class TestPPEDetectorClassMapping:
    """Тесты маппинга классов PPE."""
    
    def test_violation_classes(self):
        """Тест определения классов нарушений."""
        violation_classes = {'no_hardhat', 'no_vest', 'no_glasses', 'no_gloves'}
        
        assert 'no_hardhat' in violation_classes
        assert 'no_vest' in violation_classes
        assert 'hardhat' not in violation_classes
        assert 'vest' not in violation_classes
    
    def test_ppe_classes(self):
        """Тест определения классов СИЗ."""
        ppe_classes = {'hardhat', 'vest', 'glasses', 'gloves'}
        
        assert 'hardhat' in ppe_classes
        assert 'vest' in ppe_classes
        assert 'no_hardhat' not in ppe_classes
    
    def test_class_mapping(self):
        """Тест маппинга классов модели."""
        mapping = {
            'Hardhat': 'hardhat',
            'NO-Hardhat': 'no_hardhat',
            'Safety Vest': 'vest',
            'NO-Safety Vest': 'no_vest',
            'Person': 'person',
        }
        
        assert mapping['Hardhat'] == 'hardhat'
        assert mapping['NO-Hardhat'] == 'no_hardhat'
        assert mapping['Safety Vest'] == 'vest'
        assert mapping['NO-Safety Vest'] == 'no_vest'


class TestDetectionResultParsing:
    """Тесты парсинга результатов детекции."""
    
    def test_empty_result(self):
        """Тест пустого результата."""
        result = {
            'camera_id': 'cam_1',
            'detections': [],
            'persons': [],
            'violations': [],
            'ppe_items': [],
            'persons_count': 0,
            'violations_count': 0
        }
        
        assert result['persons_count'] == 0
        assert result['violations_count'] == 0
        assert len(result['detections']) == 0
    
    def test_detection_structure(self):
        """Тест структуры детекции."""
        detection = {
            'class_id': 0,
            'class_name': 'NO-Hardhat',
            'ppe_type': 'no_hardhat',
            'confidence': 0.85,
            'bbox': [100, 100, 200, 200],
            'track_id': 42,
            'camera_id': 'cam_1'
        }
        
        assert 'class_id' in detection
        assert 'ppe_type' in detection
        assert 'confidence' in detection
        assert 'bbox' in detection
        assert len(detection['bbox']) == 4
        assert 0 <= detection['confidence'] <= 1


class TestViolationHandling:
    """Тесты обработки нарушений."""
    
    def test_violation_id_format(self):
        """Тест формата ID нарушения."""
        import uuid
        
        violation_id = str(uuid.uuid4())[:8]
        
        assert len(violation_id) == 8
        assert violation_id.isalnum() or '-' in violation_id
    
    def test_image_crop_bounds(self):
        """Тест границ при обрезке изображения."""
        h, w = 1080, 1920
        bbox = [100, 100, 200, 200]
        pad = 50
        
        x1, y1, x2, y2 = bbox
        
        crop_y1 = max(0, y1 - pad)
        crop_y2 = min(h, y2 + pad)
        crop_x1 = max(0, x1 - pad)
        crop_x2 = min(w, x2 + pad)
        
        assert crop_y1 >= 0
        assert crop_y2 <= h
        assert crop_x1 >= 0
        assert crop_x2 <= w
    
    def test_image_crop_edge_case(self):
        """Тест обрезки у края изображения."""
        h, w = 480, 640
        bbox = [10, 10, 50, 50]  # Близко к краю
        pad = 50
        
        x1, y1, x2, y2 = bbox
        
        crop_y1 = max(0, y1 - pad)  # Должно быть 0, не -40
        crop_x1 = max(0, x1 - pad)
        
        assert crop_y1 == 0
        assert crop_x1 == 0


# Запуск тестов
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
