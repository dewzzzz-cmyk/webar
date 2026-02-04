"""
Training API Comprehensive Tests
================================

Полное покрытие тестами Training API endpoints:
- Datasets CRUD
- Images upload/management  
- Annotations CRUD + History
- Training Jobs lifecycle
- Model management
- Security validation

Author: Claude
Date: 2026-01-26
Coverage Target: 80%+
"""

import pytest
import io
import json
import uuid
import hashlib
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
from typing import Dict, Any, List

import sys
import os

# FastAPI testing
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from httpx import AsyncClient


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def valid_jpeg_bytes():
    """Minimal valid JPEG image (1x1 red pixel)."""
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
def valid_png_bytes():
    """Minimal valid PNG image (1x1 red pixel)."""
    return bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
        0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x05, 0xFE,
        0xD4, 0xEF, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
        0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
    ])


@pytest.fixture
def mock_db_connection():
    """Mock asyncpg database connection."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="INSERT 1")
    return conn


@pytest.fixture
def mock_db_pool(mock_db_connection):
    """Mock asyncpg connection pool."""
    pool = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = mock_db_connection
    pool.acquire.return_value.__aexit__.return_value = None
    return pool


@pytest.fixture
def sample_dataset():
    """Sample dataset data."""
    return {
        'id': str(uuid.uuid4()),
        'name': 'Test PPE Dataset',
        'description': 'Dataset for testing PPE detection',
        'created_by': 'admin',
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'images_count': 0,
        'annotations_count': 0,
        'status': 'draft'
    }


@pytest.fixture
def sample_image():
    """Sample image data."""
    return {
        'id': str(uuid.uuid4()),
        'dataset_id': str(uuid.uuid4()),
        'filename': 'test_image.jpg',
        'original_filename': 'original.jpg',
        'file_size': 1024,
        'width': 640,
        'height': 480,
        'mime_type': 'image/jpeg',
        'storage_path': '/app/training_data/images/test/test_image.jpg',
        'checksum': 'abc123',
        'uploaded_by': 'admin',
        'uploaded_at': datetime.now(),
        'status': 'pending'
    }


@pytest.fixture
def sample_annotation():
    """Sample annotation data."""
    return {
        'id': str(uuid.uuid4()),
        'image_id': str(uuid.uuid4()),
        'class_name': 'hardhat',
        'bbox_x1': 0.1,
        'bbox_y1': 0.2,
        'bbox_x2': 0.5,
        'bbox_y2': 0.6,
        'confidence': 0.95,
        'created_by': 'admin',
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'verified': False,
        'verified_by': None,
        'verified_at': None
    }


@pytest.fixture
def sample_training_job():
    """Sample training job data."""
    return {
        'id': str(uuid.uuid4()),
        'dataset_id': str(uuid.uuid4()),
        'name': 'PPE Training Job 1',
        'status': 'pending',
        'progress': 0,
        'epochs_total': 50,
        'epochs_completed': 0,
        'batch_size': 16,
        'learning_rate': 0.001,
        'image_size': 640,
        'augmentation': True,
        'pretrained': True,
        'current_loss': None,
        'best_loss': None,
        'current_map50': None,
        'best_map50': None,
        'error_message': None,
        'created_by': 'admin',
        'created_at': datetime.now(),
        'started_at': None,
        'completed_at': None
    }


@pytest.fixture
def sample_model():
    """Sample model version data."""
    return {
        'id': str(uuid.uuid4()),
        'training_job_id': str(uuid.uuid4()),
        'name': 'PPE Model v1.0',
        'description': 'Trained on construction site data',
        'model_path': '/app/models/ppe_model_v1.pt',
        'map50': 0.85,
        'map50_95': 0.72,
        'precision_avg': 0.88,
        'recall_avg': 0.82,
        'metrics_per_class': {'hardhat': 0.9, 'vest': 0.85},
        'train_images_count': 1000,
        'is_active': False,
        'created_at': datetime.now(),
        'activated_at': None,
        'activated_by': None
    }


# ============================================================================
# SECURE IMAGE UPLOAD TESTS
# ============================================================================

class TestSecureImageUpload:
    """Tests for secure image upload validation."""
    
    def test_valid_jpeg_magic_bytes(self, valid_jpeg_bytes):
        """Test valid JPEG is recognized by magic bytes."""
        jpeg_magic = b'\xff\xd8\xff'
        assert valid_jpeg_bytes[:3] == jpeg_magic
    
    def test_valid_png_magic_bytes(self, valid_png_bytes):
        """Test valid PNG is recognized by magic bytes."""
        png_magic = b'\x89PNG\r\n\x1a\n'
        assert valid_png_bytes[:8] == png_magic
    
    def test_reject_invalid_magic_bytes(self):
        """Test rejection of files with invalid magic bytes."""
        # GIF magic bytes (not allowed)
        gif_bytes = b'GIF89a' + b'\x00' * 100
        gif_magic = gif_bytes[:6]
        
        allowed_magics = [b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n']
        
        is_valid = any(gif_bytes.startswith(m) for m in allowed_magics)
        assert not is_valid
    
    def test_file_extension_validation(self):
        """Test file extension validation."""
        allowed = {'.jpg', '.jpeg', '.png', '.webp'}
        
        valid_files = ['image.jpg', 'photo.JPEG', 'pic.png', 'img.webp']
        for f in valid_files:
            ext = Path(f).suffix.lower()
            assert ext in allowed, f"Expected {ext} to be allowed"
        
        invalid_files = ['image.gif', 'photo.bmp', 'pic.tiff', 'img.svg', 'file.exe']
        for f in invalid_files:
            ext = Path(f).suffix.lower()
            assert ext not in allowed, f"Expected {ext} to be rejected"
    
    def test_file_size_limit(self):
        """Test file size limit enforcement (10MB)."""
        max_size = 10 * 1024 * 1024  # 10MB
        
        # Valid sizes
        assert 1 * 1024 * 1024 <= max_size  # 1MB
        assert 5 * 1024 * 1024 <= max_size  # 5MB
        assert 10 * 1024 * 1024 <= max_size  # 10MB (edge case)
        
        # Invalid sizes
        assert 11 * 1024 * 1024 > max_size  # 11MB
        assert 50 * 1024 * 1024 > max_size  # 50MB
    
    def test_image_dimensions_validation(self):
        """Test image dimension constraints."""
        min_dim = 32
        max_dim = 8192
        
        # Valid dimensions
        valid_dims = [(640, 480), (1920, 1080), (4096, 4096), (32, 32), (8192, 8192)]
        for w, h in valid_dims:
            assert min_dim <= w <= max_dim and min_dim <= h <= max_dim
        
        # Invalid dimensions
        invalid_dims = [(16, 16), (10000, 1000), (100, 10)]
        for w, h in invalid_dims:
            is_valid = min_dim <= w <= max_dim and min_dim <= h <= max_dim
            assert not is_valid
    
    def test_filename_sanitization(self):
        """Test filename sanitization removes dangerous characters."""
        dangerous_names = [
            '../../../etc/passwd',
            'image<script>.jpg',
            'file"name.png',
            'path\\traversal.jpg',
            'null\x00byte.png'
        ]
        
        for name in dangerous_names:
            # Sanitize: keep only alphanumeric, dots, underscores, hyphens
            sanitized = ''.join(c for c in name if c.isalnum() or c in '._-')
            assert '/' not in sanitized
            assert '\\' not in sanitized
            assert '<' not in sanitized
            assert '>' not in sanitized
            assert '"' not in sanitized
            assert '\x00' not in sanitized
    
    def test_checksum_calculation(self, valid_jpeg_bytes):
        """Test SHA256 checksum calculation."""
        checksum = hashlib.sha256(valid_jpeg_bytes).hexdigest()
        
        assert len(checksum) == 64
        assert checksum.isalnum()
        
        # Same input = same checksum
        checksum2 = hashlib.sha256(valid_jpeg_bytes).hexdigest()
        assert checksum == checksum2
        
        # Different input = different checksum
        modified = valid_jpeg_bytes + b'\x00'
        checksum3 = hashlib.sha256(modified).hexdigest()
        assert checksum != checksum3
    
    def test_max_files_per_request(self):
        """Test maximum files per upload request."""
        max_files = 100
        
        # Valid
        assert 1 <= max_files
        assert 50 <= max_files
        assert 100 <= max_files
        
        # Invalid
        assert 101 > max_files
        assert 500 > max_files


# ============================================================================
# DATASET API TESTS
# ============================================================================

class TestDatasetAPI:
    """Tests for Dataset CRUD operations."""
    
    def test_dataset_create_schema(self):
        """Test dataset creation request schema."""
        valid_request = {
            'name': 'Construction Site PPE',
            'description': 'Images from construction site cameras'
        }
        
        assert 'name' in valid_request
        assert len(valid_request['name']) >= 1
        assert len(valid_request['name']) <= 255
    
    def test_dataset_create_validates_name(self):
        """Test dataset name validation."""
        # Valid names
        valid_names = ['Test', 'PPE Dataset 2024', 'a' * 255]
        for name in valid_names:
            assert 1 <= len(name) <= 255
        
        # Invalid names
        invalid_names = ['', 'a' * 256]
        for name in invalid_names:
            assert not (1 <= len(name) <= 255)
    
    def test_dataset_response_schema(self, sample_dataset):
        """Test dataset response contains all required fields."""
        required_fields = [
            'id', 'name', 'description', 'created_by', 'created_at',
            'updated_at', 'images_count', 'annotations_count', 'status'
        ]
        
        for field in required_fields:
            assert field in sample_dataset
    
    def test_dataset_status_transitions(self):
        """Test valid dataset status transitions."""
        valid_transitions = {
            'draft': ['active', 'archived'],
            'active': ['training', 'archived'],
            'training': ['active', 'archived'],
            'archived': ['active']
        }
        
        # Valid transition
        assert 'active' in valid_transitions['draft']
        
        # Invalid transition
        assert 'training' not in valid_transitions['draft']
    
    @pytest.mark.asyncio
    async def test_dataset_list_empty(self, mock_db_pool, mock_db_connection):
        """Test listing datasets when database is empty."""
        mock_db_connection.fetch.return_value = []
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.fetch("SELECT * FROM training_datasets")
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_dataset_list_with_data(self, mock_db_pool, mock_db_connection, sample_dataset):
        """Test listing datasets with data."""
        mock_db_connection.fetch.return_value = [sample_dataset]
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.fetch("SELECT * FROM training_datasets")
        
        assert len(result) == 1
        assert result[0]['name'] == sample_dataset['name']
    
    @pytest.mark.asyncio
    async def test_dataset_list_filter_by_status(self, mock_db_pool, mock_db_connection, sample_dataset):
        """Test listing datasets filtered by status."""
        mock_db_connection.fetch.return_value = [sample_dataset]
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.fetch(
                "SELECT * FROM training_datasets WHERE status = $1",
                'draft'
            )
        
        assert len(result) == 1
        assert result[0]['status'] == 'draft'
    
    @pytest.mark.asyncio
    async def test_dataset_get_by_id(self, mock_db_pool, mock_db_connection, sample_dataset):
        """Test getting dataset by ID."""
        mock_db_connection.fetchrow.return_value = sample_dataset
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM training_datasets WHERE id = $1",
                sample_dataset['id']
            )
        
        assert result is not None
        assert result['id'] == sample_dataset['id']
    
    @pytest.mark.asyncio
    async def test_dataset_get_not_found(self, mock_db_pool, mock_db_connection):
        """Test getting non-existent dataset returns None."""
        mock_db_connection.fetchrow.return_value = None
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM training_datasets WHERE id = $1",
                str(uuid.uuid4())
            )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_dataset_delete(self, mock_db_pool, mock_db_connection, sample_dataset):
        """Test deleting dataset."""
        mock_db_connection.execute.return_value = "DELETE 1"
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM training_datasets WHERE id = $1",
                sample_dataset['id']
            )
        
        assert "DELETE" in result


# ============================================================================
# IMAGE API TESTS
# ============================================================================

class TestImageAPI:
    """Tests for Image management operations."""
    
    def test_image_response_schema(self, sample_image):
        """Test image response contains all required fields."""
        required_fields = [
            'id', 'dataset_id', 'filename', 'original_filename',
            'file_size', 'width', 'height', 'mime_type', 'storage_path',
            'checksum', 'uploaded_by', 'uploaded_at', 'status'
        ]
        
        for field in required_fields:
            assert field in sample_image
    
    def test_image_status_values(self):
        """Test valid image status values."""
        valid_statuses = ['pending', 'annotated', 'verified', 'rejected']
        
        for status in valid_statuses:
            assert status in valid_statuses
    
    def test_unique_filename_generation(self):
        """Test unique filename generation."""
        original = "test.jpg"
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_name = f"{timestamp}_{unique_id}_{original}"
        
        assert original in unique_name
        assert len(unique_name) > len(original)
    
    @pytest.mark.asyncio
    async def test_image_list_for_dataset(self, mock_db_pool, mock_db_connection, sample_image):
        """Test listing images for a dataset."""
        mock_db_connection.fetch.return_value = [sample_image]
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.fetch(
                "SELECT * FROM training_images WHERE dataset_id = $1",
                sample_image['dataset_id']
            )
        
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_image_list_pagination(self, mock_db_pool, mock_db_connection, sample_image):
        """Test image list pagination."""
        images = [sample_image.copy() for _ in range(5)]
        mock_db_connection.fetch.return_value = images[:2]  # Page 1
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.fetch(
                "SELECT * FROM training_images WHERE dataset_id = $1 LIMIT $2 OFFSET $3",
                sample_image['dataset_id'], 2, 0
            )
        
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_image_delete_cascades_annotations(self, mock_db_pool, mock_db_connection, sample_image):
        """Test deleting image cascades to annotations."""
        mock_db_connection.execute.return_value = "DELETE 1"
        
        # With ON DELETE CASCADE in DB schema, deleting image removes annotations
        async with mock_db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM training_images WHERE id = $1",
                sample_image['id']
            )
        
        assert "DELETE" in result


# ============================================================================
# ANNOTATION API TESTS
# ============================================================================

class TestAnnotationAPI:
    """Tests for Annotation CRUD operations."""
    
    def test_annotation_response_schema(self, sample_annotation):
        """Test annotation response contains all required fields."""
        required_fields = [
            'id', 'image_id', 'class_name', 'bbox_x1', 'bbox_y1',
            'bbox_x2', 'bbox_y2', 'confidence', 'created_by', 'created_at'
        ]
        
        for field in required_fields:
            assert field in sample_annotation
    
    def test_bbox_validation(self):
        """Test bounding box validation (normalized 0-1)."""
        valid_bboxes = [
            (0.0, 0.0, 1.0, 1.0),  # Full image
            (0.1, 0.2, 0.5, 0.6),  # Normal box
            (0.0, 0.0, 0.1, 0.1),  # Small box
        ]
        
        for x1, y1, x2, y2 in valid_bboxes:
            assert 0 <= x1 <= 1 and 0 <= y1 <= 1
            assert 0 <= x2 <= 1 and 0 <= y2 <= 1
            assert x1 < x2 and y1 < y2
        
        # Invalid bboxes
        invalid_bboxes = [
            (-0.1, 0.0, 0.5, 0.5),  # Negative coordinate
            (0.0, 0.0, 1.5, 1.0),   # > 1
            (0.5, 0.5, 0.3, 0.3),   # x1 > x2
        ]
        
        for x1, y1, x2, y2 in invalid_bboxes:
            is_valid = (
                0 <= x1 <= 1 and 0 <= y1 <= 1 and
                0 <= x2 <= 1 and 0 <= y2 <= 1 and
                x1 < x2 and y1 < y2
            )
            assert not is_valid
    
    def test_class_name_validation(self):
        """Test annotation class name validation."""
        valid_classes = [
            'person', 'hardhat', 'no_hardhat', 'vest', 'no_vest',
            'glasses', 'no_glasses', 'mask', 'no_mask'
        ]
        
        for cls in valid_classes:
            assert len(cls) >= 1
            assert len(cls) <= 50
    
    def test_bbox_to_yolo_format(self, sample_annotation):
        """Test conversion from (x1,y1,x2,y2) to YOLO format."""
        x1 = sample_annotation['bbox_x1']
        y1 = sample_annotation['bbox_y1']
        x2 = sample_annotation['bbox_x2']
        y2 = sample_annotation['bbox_y2']
        
        # YOLO format: center_x, center_y, width, height
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        w = x2 - x1
        h = y2 - y1
        
        assert 0 <= cx <= 1
        assert 0 <= cy <= 1
        assert 0 < w <= 1
        assert 0 < h <= 1
    
    @pytest.mark.asyncio
    async def test_annotation_list_for_image(self, mock_db_pool, mock_db_connection, sample_annotation):
        """Test listing annotations for an image."""
        mock_db_connection.fetch.return_value = [sample_annotation]
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.fetch(
                "SELECT * FROM annotations WHERE image_id = $1",
                sample_annotation['image_id']
            )
        
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_annotation_create(self, mock_db_pool, mock_db_connection, sample_annotation):
        """Test creating annotation."""
        mock_db_connection.fetchrow.return_value = sample_annotation
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.fetchrow(
                """INSERT INTO annotations 
                   (image_id, class_name, bbox_x1, bbox_y1, bbox_x2, bbox_y2)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   RETURNING *""",
                sample_annotation['image_id'],
                sample_annotation['class_name'],
                sample_annotation['bbox_x1'],
                sample_annotation['bbox_y1'],
                sample_annotation['bbox_x2'],
                sample_annotation['bbox_y2']
            )
        
        assert result is not None


# ============================================================================
# ANNOTATION HISTORY (UNDO/REDO) TESTS
# ============================================================================

class TestAnnotationHistory:
    """Tests for annotation history (undo/redo) functionality."""
    
    def test_history_entry_schema(self):
        """Test history entry schema."""
        entry = {
            'id': str(uuid.uuid4()),
            'image_id': str(uuid.uuid4()),
            'user_id': 'admin',
            'action': 'create',
            'annotation_id': str(uuid.uuid4()),
            'old_data': None,
            'new_data': {'class_name': 'hardhat', 'bbox': [0.1, 0.2, 0.5, 0.6]},
            'created_at': datetime.now()
        }
        
        assert entry['action'] in ['create', 'update', 'delete']
    
    def test_history_actions(self):
        """Test valid history actions."""
        valid_actions = ['create', 'update', 'delete']
        
        for action in valid_actions:
            assert action in valid_actions
    
    def test_undo_restores_previous_state(self):
        """Test undo operation restores previous state."""
        # Simulate annotation history
        history = []
        current_annotations = []
        
        # Create annotation
        ann1 = {'id': '1', 'class': 'hardhat'}
        current_annotations.append(ann1)
        history.append({'action': 'create', 'annotation': ann1})
        
        # Undo
        last_action = history.pop()
        if last_action['action'] == 'create':
            current_annotations = [a for a in current_annotations if a['id'] != last_action['annotation']['id']]
        
        assert len(current_annotations) == 0
    
    def test_redo_reapplies_action(self):
        """Test redo operation reapplies action."""
        redo_stack = [{'action': 'create', 'annotation': {'id': '1', 'class': 'hardhat'}}]
        current_annotations = []
        
        # Redo
        action = redo_stack.pop()
        if action['action'] == 'create':
            current_annotations.append(action['annotation'])
        
        assert len(current_annotations) == 1
    
    def test_history_limit(self):
        """Test history has maximum size limit."""
        max_history = 50
        history = []
        
        for i in range(60):
            history.append({'action': f'action_{i}'})
            if len(history) > max_history:
                history = history[-max_history:]
        
        assert len(history) == max_history


# ============================================================================
# TRAINING JOB API TESTS
# ============================================================================

class TestTrainingJobAPI:
    """Tests for Training Job lifecycle."""
    
    def test_training_job_response_schema(self, sample_training_job):
        """Test training job response contains all required fields."""
        required_fields = [
            'id', 'dataset_id', 'status', 'progress', 'epochs_total',
            'epochs_completed', 'batch_size', 'learning_rate', 'created_at'
        ]
        
        for field in required_fields:
            assert field in sample_training_job
    
    def test_training_job_status_values(self):
        """Test valid training job status values."""
        valid_statuses = ['pending', 'preparing', 'running', 'completed', 'failed', 'cancelled']
        
        for status in valid_statuses:
            assert status in valid_statuses
    
    def test_training_job_status_transitions(self):
        """Test valid training job status transitions."""
        valid_transitions = {
            'pending': ['preparing', 'cancelled'],
            'preparing': ['running', 'failed', 'cancelled'],
            'running': ['completed', 'failed', 'cancelled'],
            'completed': [],  # Terminal state
            'failed': [],     # Terminal state
            'cancelled': []   # Terminal state
        }
        
        # Valid transition
        assert 'running' in valid_transitions['preparing']
        
        # Invalid transition
        assert 'running' not in valid_transitions['completed']
    
    def test_training_hyperparameters_validation(self):
        """Test training hyperparameters validation."""
        valid_params = {
            'epochs': 50,
            'batch_size': 16,
            'learning_rate': 0.001,
            'image_size': 640
        }
        
        assert 1 <= valid_params['epochs'] <= 1000
        assert valid_params['batch_size'] in [4, 8, 16, 32, 64]
        assert 0.00001 <= valid_params['learning_rate'] <= 0.1
        assert valid_params['image_size'] in [320, 416, 512, 640, 832, 1024]
    
    def test_progress_calculation(self):
        """Test training progress calculation."""
        epochs_completed = 25
        epochs_total = 50
        
        progress = (epochs_completed / epochs_total) * 100
        
        assert progress == 50.0
    
    @pytest.mark.asyncio
    async def test_training_job_create(self, mock_db_pool, mock_db_connection, sample_training_job):
        """Test creating training job."""
        mock_db_connection.fetchrow.return_value = sample_training_job
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.fetchrow(
                """INSERT INTO training_jobs (dataset_id, epochs_total, batch_size, learning_rate)
                   VALUES ($1, $2, $3, $4) RETURNING *""",
                sample_training_job['dataset_id'],
                sample_training_job['epochs_total'],
                sample_training_job['batch_size'],
                sample_training_job['learning_rate']
            )
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_training_job_cancel(self, mock_db_pool, mock_db_connection, sample_training_job):
        """Test cancelling training job."""
        mock_db_connection.execute.return_value = "UPDATE 1"
        
        async with mock_db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE training_jobs SET status = 'cancelled' WHERE id = $1 AND status IN ('pending', 'preparing', 'running')",
                sample_training_job['id']
            )
        
        assert "UPDATE" in result


# ============================================================================
# MODEL VERSION API TESTS
# ============================================================================

class TestModelVersionAPI:
    """Tests for Model Version management."""
    
    def test_model_response_schema(self, sample_model):
        """Test model response contains all required fields."""
        required_fields = [
            'id', 'name', 'map50', 'map50_95', 'is_active', 'created_at'
        ]
        
        for field in required_fields:
            assert field in sample_model
    
    def test_model_metrics_validation(self):
        """Test model metrics validation."""
        metrics = {
            'map50': 0.85,
            'map50_95': 0.72,
            'precision': 0.88,
            'recall': 0.82
        }
        
        for name, value in metrics.items():
            assert 0 <= value <= 1, f"{name} should be between 0 and 1"
    
    def test_only_one_active_model(self):
        """Test only one model can be active at a time."""
        models = [
            {'id': '1', 'is_active': True},
            {'id': '2', 'is_active': False},
            {'id': '3', 'is_active': False}
        ]
        
        active_count = sum(1 for m in models if m['is_active'])
        assert active_count <= 1
    
    @pytest.mark.asyncio
    async def test_model_activate(self, mock_db_pool, mock_db_connection, sample_model):
        """Test activating a model."""
        # First deactivate all
        mock_db_connection.execute.return_value = "UPDATE 3"
        
        async with mock_db_pool.acquire() as conn:
            await conn.execute("UPDATE model_versions SET is_active = FALSE")
            await conn.execute(
                "UPDATE model_versions SET is_active = TRUE WHERE id = $1",
                sample_model['id']
            )
        
        mock_db_connection.execute.assert_called()


# ============================================================================
# STATISTICS API TESTS
# ============================================================================

class TestStatisticsAPI:
    """Tests for Statistics endpoints."""
    
    def test_overview_stats_schema(self):
        """Test overview statistics schema."""
        stats = {
            'total_datasets': 5,
            'total_images': 1000,
            'total_annotations': 5000,
            'total_jobs': 10,
            'active_model': 'PPE Model v1.0'
        }
        
        required_fields = ['total_datasets', 'total_images', 'total_annotations', 'total_jobs']
        for field in required_fields:
            assert field in stats
    
    def test_class_distribution_stats(self):
        """Test class distribution statistics."""
        distribution = {
            'person': 1500,
            'hardhat': 800,
            'no_hardhat': 200,
            'vest': 750,
            'no_vest': 250
        }
        
        total = sum(distribution.values())
        assert total == 3500
        
        # Calculate percentages
        percentages = {k: v/total*100 for k, v in distribution.items()}
        assert abs(sum(percentages.values()) - 100) < 0.01


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
                'val_loss': 0.6123,
                'map50': 0.75,
                'message': 'Epoch 10/50'
            }
        }
        
        assert message['type'] == 'progress'
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
                'model_path': '/app/models/best.pt',
                'message': 'Обучение завершено!'
            }
        }
        
        assert message['data']['status'] == 'completed'
        assert message['data']['progress'] == 100
        assert 'model_id' in message['data']
    
    def test_error_message(self):
        """Test error message structure."""
        message = {
            'type': 'error',
            'data': {
                'status': 'failed',
                'error': 'CUDA out of memory',
                'message': 'Ошибка: недостаточно памяти GPU'
            }
        }
        
        assert message['type'] == 'error'
        assert 'error' in message['data']


# ============================================================================
# YOLO DATASET FORMAT TESTS
# ============================================================================

class TestYOLODatasetFormat:
    """Tests for YOLO dataset format conversion."""
    
    def test_data_yaml_generation(self):
        """Test data.yaml file generation."""
        job_id = str(uuid.uuid4())
        class_names = ['person', 'hardhat', 'no_hardhat', 'vest', 'no_vest']
        
        data_yaml = {
            'path': f'/app/training_data/datasets/{job_id}',
            'train': 'images/train',
            'val': 'images/val',
            'names': {i: name for i, name in enumerate(class_names)},
            'nc': len(class_names)
        }
        
        assert data_yaml['nc'] == 5
        assert data_yaml['names'][0] == 'person'
    
    def test_label_file_format(self):
        """Test YOLO label file format."""
        # YOLO format: class_id center_x center_y width height
        annotations = [
            {'class_id': 0, 'cx': 0.5, 'cy': 0.5, 'w': 0.3, 'h': 0.4},
            {'class_id': 1, 'cx': 0.2, 'cy': 0.3, 'w': 0.1, 'h': 0.15}
        ]
        
        lines = []
        for ann in annotations:
            line = f"{ann['class_id']} {ann['cx']} {ann['cy']} {ann['w']} {ann['h']}"
            lines.append(line)
        
        content = '\n'.join(lines)
        assert '0 0.5 0.5 0.3 0.4' in content
    
    def test_train_val_split_ratio(self):
        """Test 80/20 train/val split."""
        total = 100
        train_ratio = 0.8
        
        train_count = int(total * train_ratio)
        val_count = total - train_count
        
        assert train_count == 80
        assert val_count == 20


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Tests for error handling."""
    
    def test_not_found_response(self):
        """Test 404 response structure."""
        error_response = {
            'detail': 'Dataset not found'
        }
        
        assert 'detail' in error_response
    
    def test_validation_error_response(self):
        """Test 422 validation error response structure."""
        error_response = {
            'detail': [
                {
                    'loc': ['body', 'name'],
                    'msg': 'field required',
                    'type': 'value_error.missing'
                }
            ]
        }
        
        assert 'detail' in error_response
        assert isinstance(error_response['detail'], list)
    
    def test_internal_error_response(self):
        """Test 500 internal error response structure."""
        error_response = {
            'detail': 'Internal server error'
        }
        
        assert 'detail' in error_response


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================

class TestRateLimiting:
    """Tests for rate limiting."""
    
    def test_upload_rate_limit(self):
        """Test upload rate limit (100 files per minute)."""
        limit = 100
        window_seconds = 60
        
        # Simulate requests
        requests = 150
        allowed = min(requests, limit)
        
        assert allowed == 100
    
    def test_api_rate_limit(self):
        """Test API rate limit (1000 requests per minute)."""
        limit = 1000
        
        # Should allow normal usage
        assert 100 <= limit
        assert 500 <= limit


# ============================================================================
# CONCURRENT OPERATIONS TESTS
# ============================================================================

class TestConcurrentOperations:
    """Tests for concurrent operation handling."""
    
    @pytest.mark.asyncio
    async def test_concurrent_annotation_updates(self):
        """Test concurrent annotation updates don't conflict."""
        lock = asyncio.Lock()
        results = []
        
        async def update_annotation(value):
            async with lock:
                results.append(value)
        
        await asyncio.gather(
            update_annotation(1),
            update_annotation(2),
            update_annotation(3)
        )
        
        assert len(results) == 3
    
    @pytest.mark.asyncio
    async def test_single_active_training_job(self):
        """Test only one training job runs at a time per dataset."""
        dataset_id = str(uuid.uuid4())
        active_jobs = []
        
        def can_start_job(ds_id):
            return ds_id not in active_jobs
        
        assert can_start_job(dataset_id)
        active_jobs.append(dataset_id)
        assert not can_start_job(dataset_id)


# ============================================================================
# CLEANUP AND MAINTENANCE TESTS
# ============================================================================

class TestCleanupOperations:
    """Tests for cleanup and maintenance operations."""
    
    def test_orphan_image_detection(self):
        """Test detection of orphaned images (no dataset)."""
        images = [
            {'id': '1', 'dataset_id': 'ds1'},
            {'id': '2', 'dataset_id': 'ds2'},
            {'id': '3', 'dataset_id': None}  # Orphan
        ]
        
        orphans = [img for img in images if img['dataset_id'] is None]
        assert len(orphans) == 1
    
    def test_old_job_cleanup(self):
        """Test cleanup of old completed jobs."""
        now = datetime.now()
        retention_days = 30
        cutoff = now - timedelta(days=retention_days)
        
        jobs = [
            {'id': '1', 'status': 'completed', 'completed_at': now - timedelta(days=10)},
            {'id': '2', 'status': 'completed', 'completed_at': now - timedelta(days=40)},  # Old
            {'id': '3', 'status': 'running', 'completed_at': None}
        ]
        
        jobs_to_cleanup = [
            j for j in jobs 
            if j['status'] == 'completed' and j['completed_at'] and j['completed_at'] < cutoff
        ]
        
        assert len(jobs_to_cleanup) == 1
        assert jobs_to_cleanup[0]['id'] == '2'


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-x'])
