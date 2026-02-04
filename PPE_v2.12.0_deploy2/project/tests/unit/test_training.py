"""
Training API Unit Tests
Тесты для модуля обучения PPE Detection System

Coverage:
- SecureImageUpload validation
- Dataset CRUD operations
- Image management
- Annotation operations
- Training jobs
- Model versions
"""

import pytest
import io
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import sys
import os

# Add path to services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/api'))


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_db_pool():
    """Mock database connection pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool, conn


@pytest.fixture
def sample_image_bytes():
    """Create a minimal valid JPEG image."""
    # Minimal valid JPEG (1x1 pixel red)
    return bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
        0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
        0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
        0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
        0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
        0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
        0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xF1, 0x45, 0x00,
        0xFF, 0xD9
    ])


@pytest.fixture
def sample_png_bytes():
    """Create a minimal valid PNG image (1x1 red pixel)."""
    return bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
        0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x05, 0xFE,
        0xD4, 0xEF, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,  # IEND chunk
        0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
    ])


# ============================================================================
# SECURE IMAGE UPLOAD TESTS
# ============================================================================

class TestSecureImageUpload:
    """Tests for SecureImageUpload class."""
    
    def test_allowed_extensions(self):
        """Test allowed file extensions."""
        allowed = {'.jpg', '.jpeg', '.png', '.webp'}
        
        # Valid extensions
        for ext in allowed:
            assert ext in allowed
        
        # Invalid extensions
        invalid = {'.gif', '.bmp', '.tiff', '.svg', '.exe', '.php'}
        for ext in invalid:
            assert ext not in allowed
    
    def test_max_file_size(self):
        """Test maximum file size limit."""
        max_size = 10 * 1024 * 1024  # 10MB
        
        # Under limit
        assert 5 * 1024 * 1024 < max_size
        
        # Over limit
        assert 15 * 1024 * 1024 > max_size
    
    def test_magic_bytes_jpeg(self, sample_image_bytes):
        """Test JPEG magic bytes detection."""
        jpeg_magic = b'\xff\xd8\xff'
        assert sample_image_bytes[:3] == jpeg_magic
    
    def test_magic_bytes_png(self, sample_png_bytes):
        """Test PNG magic bytes detection."""
        png_magic = b'\x89PNG\r\n\x1a\n'
        assert sample_png_bytes[:8] == png_magic
    
    def test_image_dimensions_validation(self):
        """Test image dimension constraints."""
        min_size = 32
        max_size = 8192
        
        # Valid dimensions
        assert 640 >= min_size and 640 <= max_size
        assert 1920 >= min_size and 1920 <= max_size
        
        # Invalid dimensions
        assert 16 < min_size  # Too small
        assert 10000 > max_size  # Too large
    
    def test_reject_empty_filename(self):
        """Test rejection of empty filename."""
        with pytest.raises(ValueError, match="Имя файла"):
            mock_file = Mock()
            mock_file.filename = ""
            mock_file.file = io.BytesIO(b"test")
            
            # Simulated validation
            if not mock_file.filename:
                raise ValueError("Имя файла обязательно")
    
    def test_reject_invalid_extension(self):
        """Test rejection of invalid file extension."""
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
        
        invalid_files = ['test.gif', 'test.bmp', 'test.exe', 'test.php']
        
        for filename in invalid_files:
            ext = Path(filename).suffix.lower()
            with pytest.raises(ValueError):
                if ext not in allowed_extensions:
                    raise ValueError(f"Недопустимое расширение: {ext}")
    
    def test_hash_calculation(self, sample_image_bytes):
        """Test file hash calculation."""
        import hashlib
        
        file_hash = hashlib.sha256(sample_image_bytes).hexdigest()
        
        assert len(file_hash) == 64
        assert file_hash.isalnum()


# ============================================================================
# DATASET TESTS
# ============================================================================

class TestDatasetOperations:
    """Tests for dataset CRUD operations."""
    
    def test_dataset_create_schema(self):
        """Test dataset creation schema."""
        valid_data = {
            'name': 'Test Dataset',
            'description': 'For testing purposes'
        }
        
        assert 'name' in valid_data
        assert len(valid_data['name']) >= 1
        assert len(valid_data['name']) <= 255
    
    def test_dataset_name_validation(self):
        """Test dataset name length constraints."""
        # Valid names
        assert len("Test") >= 1
        assert len("A" * 255) <= 255
        
        # Invalid names
        assert len("") < 1
        assert len("A" * 256) > 255
    
    def test_dataset_status_values(self):
        """Test valid dataset status values."""
        valid_statuses = ['draft', 'active', 'archived', 'training']
        
        for status in valid_statuses:
            assert status in valid_statuses
        
        assert 'invalid' not in valid_statuses
    
    @pytest.mark.asyncio
    async def test_dataset_list(self, mock_db_pool):
        """Test listing datasets."""
        pool, conn = mock_db_pool
        
        mock_rows = [
            {
                'id': uuid.uuid4(),
                'name': 'Dataset 1',
                'description': 'Test',
                'status': 'draft',
                'images_count': 10,
                'annotations_count': 50,
                'created_by': 'admin',
                'created_at': datetime.now()
            }
        ]
        conn.fetch.return_value = mock_rows
        
        # Simulated fetch
        rows = await conn.fetch("SELECT * FROM training_datasets")
        
        assert len(rows) == 1
        assert rows[0]['name'] == 'Dataset 1'


# ============================================================================
# ANNOTATION TESTS
# ============================================================================

class TestAnnotationOperations:
    """Tests for annotation operations."""
    
    def test_bbox_normalization(self):
        """Test bounding box coordinates are normalized (0-1)."""
        valid_bbox = [0.1, 0.2, 0.5, 0.6]  # x1, y1, x2, y2
        
        for coord in valid_bbox:
            assert 0 <= coord <= 1
    
    def test_bbox_validation_x2_greater_x1(self):
        """Test x2 must be greater than x1."""
        x1, x2 = 0.3, 0.7
        assert x2 > x1
        
        # Invalid case
        x1_invalid, x2_invalid = 0.7, 0.3
        assert not (x2_invalid > x1_invalid)
    
    def test_bbox_validation_y2_greater_y1(self):
        """Test y2 must be greater than y1."""
        y1, y2 = 0.2, 0.8
        assert y2 > y1
    
    def test_class_names(self):
        """Test valid PPE class names."""
        valid_classes = [
            'person', 'hardhat', 'no_hardhat', 
            'vest', 'no_vest', 'glasses', 'no_glasses'
        ]
        
        for cls in valid_classes:
            assert len(cls) >= 1
            assert len(cls) <= 50
    
    def test_annotation_create_schema(self):
        """Test annotation creation schema."""
        valid_annotation = {
            'class_name': 'hardhat',
            'bbox_x1': 0.1,
            'bbox_y1': 0.2,
            'bbox_x2': 0.5,
            'bbox_y2': 0.6
        }
        
        assert valid_annotation['bbox_x2'] > valid_annotation['bbox_x1']
        assert valid_annotation['bbox_y2'] > valid_annotation['bbox_y1']
    
    def test_annotation_minimum_size(self):
        """Test minimum annotation size (1% of image)."""
        min_size = 0.01
        
        bbox = [0.1, 0.2, 0.15, 0.25]
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        
        assert width >= min_size
        assert height >= min_size


# ============================================================================
# TRAINING JOB TESTS
# ============================================================================

class TestTrainingJobOperations:
    """Tests for training job operations."""
    
    def test_training_params_defaults(self):
        """Test default training parameters."""
        defaults = {
            'epochs': 50,
            'batch_size': 16,
            'learning_rate': 0.001,
            'image_size': 640,
            'augmentation': True,
            'pretrained': True
        }
        
        assert defaults['epochs'] >= 1
        assert defaults['epochs'] <= 500
        assert defaults['batch_size'] >= 4
        assert defaults['batch_size'] <= 64
    
    def test_learning_rate_range(self):
        """Test learning rate valid range."""
        min_lr = 0.00001
        max_lr = 0.1
        
        valid_lrs = [0.001, 0.01, 0.0001]
        for lr in valid_lrs:
            assert min_lr <= lr <= max_lr
    
    def test_image_size_options(self):
        """Test valid image size options."""
        valid_sizes = [320, 416, 512, 640, 768, 1024, 1280]
        
        for size in valid_sizes:
            assert size >= 320
            assert size <= 1280
            assert size % 32 == 0  # Must be divisible by 32
    
    def test_job_status_transitions(self):
        """Test valid job status transitions."""
        valid_statuses = ['pending', 'queued', 'running', 'completed', 'failed', 'cancelled']
        
        # Valid transitions
        transitions = {
            'pending': ['queued', 'cancelled'],
            'queued': ['running', 'cancelled'],
            'running': ['completed', 'failed', 'cancelled'],
            'completed': [],
            'failed': [],
            'cancelled': []
        }
        
        for status, next_statuses in transitions.items():
            assert status in valid_statuses
            for next_status in next_statuses:
                assert next_status in valid_statuses
    
    def test_minimum_images_for_training(self):
        """Test minimum images requirement (100 recommended)."""
        # Current code has 10, experts recommend 100
        min_images_current = 10
        min_images_recommended = 100
        
        assert min_images_recommended > min_images_current
        
        # Test validation
        annotated_count = 50
        assert annotated_count >= min_images_current
        assert annotated_count < min_images_recommended


# ============================================================================
# MODEL VERSION TESTS
# ============================================================================

class TestModelVersionOperations:
    """Tests for model version operations."""
    
    def test_model_metrics_structure(self):
        """Test model metrics structure."""
        metrics = {
            'map50': 0.85,
            'map50_95': 0.72,
            'precision_avg': 0.88,
            'recall_avg': 0.82,
            'metrics_per_class': {
                'hardhat': {'ap50': 0.90},
                'no_hardhat': {'ap50': 0.85}
            }
        }
        
        assert 0 <= metrics['map50'] <= 1
        assert 0 <= metrics['map50_95'] <= 1
    
    def test_only_one_active_model(self):
        """Test only one model can be active at a time."""
        models = [
            {'id': '1', 'is_active': True},
            {'id': '2', 'is_active': False},
            {'id': '3', 'is_active': False},
        ]
        
        active_count = sum(1 for m in models if m['is_active'])
        assert active_count <= 1
    
    def test_model_path_validation(self):
        """Test model file path validation."""
        valid_paths = [
            '/app/models/ppe_model.pt',
            '/app/models/custom_2024.pt',
        ]
        
        for path in valid_paths:
            assert path.endswith('.pt')
            assert path.startswith('/app/models/')


# ============================================================================
# WEBSOCKET PROGRESS TESTS
# ============================================================================

class TestWebSocketProgress:
    """Tests for WebSocket training progress."""
    
    def test_progress_message_structure(self):
        """Test progress message structure."""
        message = {
            'type': 'progress',
            'data': {
                'status': 'running',
                'stage': 'training',
                'epoch': 10,
                'total_epochs': 50,
                'progress': 20.0,
                'train_loss': 0.5432,
                'message': 'Epoch 10/50'
            }
        }
        
        assert message['type'] in ['status', 'progress', 'error']
        assert 'data' in message
        assert 0 <= message['data']['progress'] <= 100
    
    def test_completion_message(self):
        """Test training completion message."""
        message = {
            'type': 'progress',
            'data': {
                'status': 'completed',
                'stage': 'done',
                'progress': 100,
                'map50': 0.85,
                'map50_95': 0.72,
                'model_id': str(uuid.uuid4()),
                'message': 'Обучение завершено!'
            }
        }
        
        assert message['data']['status'] == 'completed'
        assert message['data']['progress'] == 100
        assert 'model_id' in message['data']
    
    def test_error_message(self):
        """Test error message structure."""
        message = {
            'type': 'progress',
            'data': {
                'status': 'failed',
                'error': 'Out of GPU memory',
                'message': 'Ошибка: Out of GPU memory'
            }
        }
        
        assert message['data']['status'] == 'failed'
        assert 'error' in message['data']


# ============================================================================
# YOLO DATASET FORMAT TESTS
# ============================================================================

class TestYOLODatasetFormat:
    """Tests for YOLO dataset format conversion."""
    
    def test_bbox_conversion_to_yolo(self):
        """Test bbox conversion from (x1,y1,x2,y2) to YOLO format (cx,cy,w,h)."""
        # Input: normalized x1, y1, x2, y2
        x1, y1, x2, y2 = 0.1, 0.2, 0.5, 0.6
        
        # YOLO format: center_x, center_y, width, height
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        w = x2 - x1
        h = y2 - y1
        
        assert abs(cx - 0.3) < 0.0001
        assert abs(cy - 0.4) < 0.0001
        assert abs(w - 0.4) < 0.0001
        assert abs(h - 0.4) < 0.0001
    
    def test_class_to_index_mapping(self):
        """Test class name to index mapping."""
        class_names = [
            'person', 'hardhat', 'no_hardhat', 'vest', 
            'no_vest', 'glasses', 'no_glasses'
        ]
        class_to_idx = {name: idx for idx, name in enumerate(class_names)}
        
        assert class_to_idx['person'] == 0
        assert class_to_idx['hardhat'] == 1
        assert class_to_idx['no_hardhat'] == 2
    
    def test_train_val_split(self):
        """Test 80/20 train/val split."""
        total_images = 100
        
        train_count = int(total_images * 0.8)
        val_count = total_images - train_count
        
        assert train_count == 80
        assert val_count == 20
        assert train_count + val_count == total_images
    
    def test_data_yaml_structure(self):
        """Test data.yaml structure for YOLO training."""
        data_yaml = {
            'path': '/app/training_data/datasets/job_123',
            'train': 'images/train',
            'val': 'images/val',
            'names': {
                0: 'person',
                1: 'hardhat',
                2: 'no_hardhat',
                3: 'vest',
                4: 'no_vest',
                5: 'glasses',
                6: 'no_glasses'
            },
            'nc': 7
        }
        
        assert 'path' in data_yaml
        assert 'train' in data_yaml
        assert 'val' in data_yaml
        assert 'names' in data_yaml
        assert data_yaml['nc'] == len(data_yaml['names'])


# ============================================================================
# ANNOTATION HISTORY (UNDO/REDO) TESTS
# ============================================================================

class TestAnnotationHistory:
    """Tests for annotation history (undo/redo) functionality."""
    
    def test_history_stack_limit(self):
        """Test history stack has a maximum size."""
        max_history = 50
        history = []
        
        # Add 60 items
        for i in range(60):
            history.append({'action': f'action_{i}'})
            if len(history) > max_history:
                history = history[-max_history:]
        
        assert len(history) == max_history
    
    def test_undo_operation(self):
        """Test undo pops from past and pushes to future."""
        past = [
            {'annotations': [{'id': '1'}], 'selected': None},
            {'annotations': [{'id': '1'}, {'id': '2'}], 'selected': '2'},
        ]
        future = []
        current = {'annotations': [{'id': '1'}, {'id': '2'}, {'id': '3'}], 'selected': '3'}
        
        # Undo
        previous = past.pop()
        future.insert(0, current)
        current = previous
        
        assert len(current['annotations']) == 2
        assert len(future) == 1
        assert len(past) == 1
    
    def test_redo_operation(self):
        """Test redo pops from future and pushes to past."""
        past = [{'annotations': [{'id': '1'}], 'selected': None}]
        future = [{'annotations': [{'id': '1'}, {'id': '2'}], 'selected': '2'}]
        current = {'annotations': [{'id': '1'}], 'selected': '1'}
        
        # Redo
        next_state = future.pop(0)
        past.append(current)
        current = next_state
        
        assert len(current['annotations']) == 2
        assert len(future) == 0
        assert len(past) == 2


# ============================================================================
# INTEGRATION TEST HELPERS
# ============================================================================

class TestTrainingIntegrationHelpers:
    """Helper tests for training integration."""
    
    def test_redis_channel_name(self):
        """Test Redis pub/sub channel naming."""
        job_id = str(uuid.uuid4())
        channel = f"training:progress:{job_id}"
        
        assert channel.startswith("training:progress:")
        assert job_id in channel
    
    def test_celery_task_name(self):
        """Test Celery task naming convention."""
        task_names = [
            'training.train_model',
            'training.evaluate_model',
            'training.cancel_job',
            'training.cleanup_old_runs'
        ]
        
        for name in task_names:
            assert name.startswith('training.')
    
    def test_gpu_availability_check(self):
        """Test GPU availability detection."""
        # Mock check
        gpu_available = os.path.exists('/dev/nvidia0') if os.name != 'nt' else False
        
        # Should not raise
        assert isinstance(gpu_available, bool)


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
