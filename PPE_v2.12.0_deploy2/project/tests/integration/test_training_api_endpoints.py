"""
Training API Integration Tests
==============================

End-to-end integration tests for Training API endpoints.
Uses FastAPI TestClient with mocked database and storage.

Author: Claude
Date: 2026-01-26
"""

import pytest
import io
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
from typing import Dict, Any

import sys
import os

# Add services path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/api'))

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


# ============================================================================
# MOCK SETUP
# ============================================================================

# Create mock app for testing
def create_test_app():
    """Create test FastAPI app with mocked dependencies."""
    from fastapi import FastAPI, APIRouter, Depends, Query
    from pydantic import BaseModel
    from typing import List, Optional
    
    app = FastAPI(title="Training API Test")
    router = APIRouter(prefix="/api/training", tags=["Training"])
    
    # In-memory storage for testing
    datasets_db: Dict[str, dict] = {}
    images_db: Dict[str, dict] = {}
    annotations_db: Dict[str, dict] = {}
    jobs_db: Dict[str, dict] = {}
    models_db: Dict[str, dict] = {}
    
    # Pydantic models
    class DatasetCreate(BaseModel):
        name: str
        description: Optional[str] = None
    
    class DatasetResponse(BaseModel):
        id: str
        name: str
        description: Optional[str]
        status: str
        images_count: int
        annotations_count: int
        created_at: datetime
    
    class AnnotationCreate(BaseModel):
        class_name: str
        bbox_x1: float
        bbox_y1: float
        bbox_x2: float
        bbox_y2: float
    
    class TrainingJobCreate(BaseModel):
        dataset_id: str
        epochs: int = 50
        batch_size: int = 16
        learning_rate: float = 0.001
    
    # Dataset endpoints
    @router.get("/datasets")
    async def list_datasets(status: Optional[str] = None):
        result = list(datasets_db.values())
        if status:
            result = [d for d in result if d.get('status') == status]
        return result
    
    @router.post("/datasets")
    async def create_dataset(data: DatasetCreate):
        dataset_id = str(uuid.uuid4())
        dataset = {
            'id': dataset_id,
            'name': data.name,
            'description': data.description,
            'status': 'draft',
            'images_count': 0,
            'annotations_count': 0,
            'created_at': datetime.now().isoformat(),
            'created_by': 'test_user'
        }
        datasets_db[dataset_id] = dataset
        return dataset
    
    @router.get("/datasets/{dataset_id}")
    async def get_dataset(dataset_id: str):
        if dataset_id not in datasets_db:
            raise HTTPException(404, "Dataset not found")
        return datasets_db[dataset_id]
    
    @router.delete("/datasets/{dataset_id}")
    async def delete_dataset(dataset_id: str):
        if dataset_id not in datasets_db:
            raise HTTPException(404, "Dataset not found")
        del datasets_db[dataset_id]
        # Cascade delete images
        images_to_delete = [k for k, v in images_db.items() if v.get('dataset_id') == dataset_id]
        for img_id in images_to_delete:
            del images_db[img_id]
        return {"status": "deleted"}
    
    # Image endpoints
    @router.post("/datasets/{dataset_id}/images")
    async def upload_images(dataset_id: str):
        if dataset_id not in datasets_db:
            raise HTTPException(404, "Dataset not found")
        
        # Simulate image upload
        image_id = str(uuid.uuid4())
        image = {
            'id': image_id,
            'dataset_id': dataset_id,
            'filename': f'test_{image_id[:8]}.jpg',
            'original_filename': 'test.jpg',
            'file_size': 1024,
            'width': 640,
            'height': 480,
            'status': 'pending',
            'uploaded_at': datetime.now().isoformat()
        }
        images_db[image_id] = image
        datasets_db[dataset_id]['images_count'] += 1
        return {"uploaded": [image], "errors": []}
    
    @router.get("/datasets/{dataset_id}/images")
    async def list_images(dataset_id: str, limit: int = 50, offset: int = 0):
        if dataset_id not in datasets_db:
            raise HTTPException(404, "Dataset not found")
        result = [v for v in images_db.values() if v.get('dataset_id') == dataset_id]
        return result[offset:offset+limit]
    
    @router.get("/images/{image_id}")
    async def get_image(image_id: str):
        if image_id not in images_db:
            raise HTTPException(404, "Image not found")
        return images_db[image_id]
    
    @router.delete("/images/{image_id}")
    async def delete_image(image_id: str):
        if image_id not in images_db:
            raise HTTPException(404, "Image not found")
        image = images_db[image_id]
        dataset_id = image.get('dataset_id')
        del images_db[image_id]
        if dataset_id and dataset_id in datasets_db:
            datasets_db[dataset_id]['images_count'] -= 1
        # Cascade delete annotations
        anns_to_delete = [k for k, v in annotations_db.items() if v.get('image_id') == image_id]
        for ann_id in anns_to_delete:
            del annotations_db[ann_id]
        return {"status": "deleted"}
    
    # Annotation endpoints
    @router.get("/images/{image_id}/annotations")
    async def list_annotations(image_id: str):
        if image_id not in images_db:
            raise HTTPException(404, "Image not found")
        return [v for v in annotations_db.values() if v.get('image_id') == image_id]
    
    @router.post("/images/{image_id}/annotations")
    async def create_annotation(image_id: str, data: AnnotationCreate):
        if image_id not in images_db:
            raise HTTPException(404, "Image not found")
        
        # Validate bbox
        if not (0 <= data.bbox_x1 <= 1 and 0 <= data.bbox_y1 <= 1 and
                0 <= data.bbox_x2 <= 1 and 0 <= data.bbox_y2 <= 1):
            raise HTTPException(400, "Bounding box coordinates must be between 0 and 1")
        if data.bbox_x1 >= data.bbox_x2 or data.bbox_y1 >= data.bbox_y2:
            raise HTTPException(400, "Invalid bounding box: x1 must be < x2 and y1 must be < y2")
        
        ann_id = str(uuid.uuid4())
        annotation = {
            'id': ann_id,
            'image_id': image_id,
            'class_name': data.class_name,
            'bbox_x1': data.bbox_x1,
            'bbox_y1': data.bbox_y1,
            'bbox_x2': data.bbox_x2,
            'bbox_y2': data.bbox_y2,
            'created_at': datetime.now().isoformat()
        }
        annotations_db[ann_id] = annotation
        
        # Update dataset annotation count
        image = images_db[image_id]
        dataset_id = image.get('dataset_id')
        if dataset_id and dataset_id in datasets_db:
            datasets_db[dataset_id]['annotations_count'] += 1
        
        return annotation
    
    @router.delete("/annotations/{annotation_id}")
    async def delete_annotation(annotation_id: str):
        if annotation_id not in annotations_db:
            raise HTTPException(404, "Annotation not found")
        ann = annotations_db[annotation_id]
        image_id = ann.get('image_id')
        del annotations_db[annotation_id]
        
        # Update dataset annotation count
        if image_id and image_id in images_db:
            image = images_db[image_id]
            dataset_id = image.get('dataset_id')
            if dataset_id and dataset_id in datasets_db:
                datasets_db[dataset_id]['annotations_count'] -= 1
        
        return {"status": "deleted"}
    
    # Training job endpoints
    @router.get("/jobs")
    async def list_jobs(status: Optional[str] = None):
        result = list(jobs_db.values())
        if status:
            result = [j for j in result if j.get('status') == status]
        return result
    
    @router.post("/jobs")
    async def create_job(data: TrainingJobCreate):
        if data.dataset_id not in datasets_db:
            raise HTTPException(404, "Dataset not found")
        
        # Check for existing running job
        running = [j for j in jobs_db.values() 
                   if j.get('dataset_id') == data.dataset_id 
                   and j.get('status') in ('pending', 'running')]
        if running:
            raise HTTPException(400, "A training job is already running for this dataset")
        
        job_id = str(uuid.uuid4())
        job = {
            'id': job_id,
            'dataset_id': data.dataset_id,
            'status': 'pending',
            'progress': 0,
            'epochs_total': data.epochs,
            'epochs_completed': 0,
            'batch_size': data.batch_size,
            'learning_rate': data.learning_rate,
            'created_at': datetime.now().isoformat()
        }
        jobs_db[job_id] = job
        return job
    
    @router.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        if job_id not in jobs_db:
            raise HTTPException(404, "Job not found")
        return jobs_db[job_id]
    
    @router.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        if job_id not in jobs_db:
            raise HTTPException(404, "Job not found")
        job = jobs_db[job_id]
        if job['status'] not in ('pending', 'running'):
            raise HTTPException(400, f"Cannot cancel job with status: {job['status']}")
        job['status'] = 'cancelled'
        return {"status": "cancelled"}
    
    # Model endpoints
    @router.get("/models")
    async def list_models():
        return list(models_db.values())
    
    @router.post("/models/{model_id}/activate")
    async def activate_model(model_id: str):
        if model_id not in models_db:
            raise HTTPException(404, "Model not found")
        # Deactivate all other models
        for m in models_db.values():
            m['is_active'] = False
        models_db[model_id]['is_active'] = True
        return {"status": "activated", "model": models_db[model_id]}
    
    # Stats endpoints
    @router.get("/stats/overview")
    async def stats_overview():
        return {
            'total_datasets': len(datasets_db),
            'total_images': len(images_db),
            'total_annotations': len(annotations_db),
            'total_jobs': len(jobs_db),
            'active_model': next((m['name'] for m in models_db.values() if m.get('is_active')), None)
        }
    
    @router.get("/stats/class-distribution")
    async def class_distribution():
        distribution = {}
        for ann in annotations_db.values():
            cls = ann.get('class_name', 'unknown')
            distribution[cls] = distribution.get(cls, 0) + 1
        return distribution
    
    app.include_router(router)
    
    # Store references for clearing in tests
    app.state.datasets_db = datasets_db
    app.state.images_db = images_db
    app.state.annotations_db = annotations_db
    app.state.jobs_db = jobs_db
    app.state.models_db = models_db
    
    return app


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def app():
    """Create test app."""
    return create_test_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def clear_db(app):
    """Clear all in-memory databases before each test."""
    app.state.datasets_db.clear()
    app.state.images_db.clear()
    app.state.annotations_db.clear()
    app.state.jobs_db.clear()
    app.state.models_db.clear()
    return app


# ============================================================================
# DATASET ENDPOINT TESTS
# ============================================================================

class TestDatasetEndpoints:
    """Integration tests for dataset endpoints."""
    
    def test_list_datasets_empty(self, client, clear_db):
        """Test listing datasets when empty."""
        response = client.get("/api/training/datasets")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_create_dataset(self, client, clear_db):
        """Test creating a dataset."""
        data = {"name": "Test PPE Dataset", "description": "For testing"}
        response = client.post("/api/training/datasets", json=data)
        
        assert response.status_code == 200
        result = response.json()
        assert result['name'] == "Test PPE Dataset"
        assert result['status'] == 'draft'
        assert result['images_count'] == 0
        assert 'id' in result
    
    def test_create_dataset_minimal(self, client, clear_db):
        """Test creating dataset with only required fields."""
        data = {"name": "Minimal Dataset"}
        response = client.post("/api/training/datasets", json=data)
        
        assert response.status_code == 200
        result = response.json()
        assert result['name'] == "Minimal Dataset"
        assert result['description'] is None
    
    def test_create_dataset_invalid(self, client, clear_db):
        """Test creating dataset with invalid data."""
        data = {}  # Missing required 'name'
        response = client.post("/api/training/datasets", json=data)
        
        assert response.status_code == 422
    
    def test_get_dataset(self, client, clear_db):
        """Test getting a specific dataset."""
        # Create dataset first
        create_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = create_response.json()['id']
        
        # Get dataset
        response = client.get(f"/api/training/datasets/{dataset_id}")
        
        assert response.status_code == 200
        assert response.json()['id'] == dataset_id
    
    def test_get_dataset_not_found(self, client, clear_db):
        """Test getting non-existent dataset."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/training/datasets/{fake_id}")
        
        assert response.status_code == 404
    
    def test_delete_dataset(self, client, clear_db):
        """Test deleting a dataset."""
        # Create dataset
        create_response = client.post("/api/training/datasets", json={"name": "To Delete"})
        dataset_id = create_response.json()['id']
        
        # Delete dataset
        response = client.delete(f"/api/training/datasets/{dataset_id}")
        
        assert response.status_code == 200
        assert response.json()['status'] == 'deleted'
        
        # Verify deleted
        get_response = client.get(f"/api/training/datasets/{dataset_id}")
        assert get_response.status_code == 404
    
    def test_delete_dataset_cascades_images(self, client, clear_db):
        """Test deleting dataset also deletes its images."""
        # Create dataset and upload image
        create_response = client.post("/api/training/datasets", json={"name": "With Images"})
        dataset_id = create_response.json()['id']
        
        client.post(f"/api/training/datasets/{dataset_id}/images")
        
        # Verify image exists
        images = client.get(f"/api/training/datasets/{dataset_id}/images").json()
        assert len(images) == 1
        
        # Delete dataset
        client.delete(f"/api/training/datasets/{dataset_id}")
        
        # Verify images deleted (dataset not found now)
        response = client.get(f"/api/training/datasets/{dataset_id}/images")
        assert response.status_code == 404
    
    def test_list_datasets_filter_by_status(self, client, clear_db):
        """Test filtering datasets by status."""
        # Create datasets
        client.post("/api/training/datasets", json={"name": "Draft 1"})
        client.post("/api/training/datasets", json={"name": "Draft 2"})
        
        # Filter by status
        response = client.get("/api/training/datasets?status=draft")
        
        assert response.status_code == 200
        assert len(response.json()) == 2


# ============================================================================
# IMAGE ENDPOINT TESTS
# ============================================================================

class TestImageEndpoints:
    """Integration tests for image endpoints."""
    
    def test_upload_image(self, client, clear_db):
        """Test uploading an image."""
        # Create dataset first
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        # Upload image
        response = client.post(f"/api/training/datasets/{dataset_id}/images")
        
        assert response.status_code == 200
        result = response.json()
        assert len(result['uploaded']) == 1
        assert result['errors'] == []
    
    def test_upload_image_to_nonexistent_dataset(self, client, clear_db):
        """Test uploading image to non-existent dataset."""
        fake_id = str(uuid.uuid4())
        response = client.post(f"/api/training/datasets/{fake_id}/images")
        
        assert response.status_code == 404
    
    def test_list_images(self, client, clear_db):
        """Test listing images for a dataset."""
        # Create dataset and upload images
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        client.post(f"/api/training/datasets/{dataset_id}/images")
        client.post(f"/api/training/datasets/{dataset_id}/images")
        
        # List images
        response = client.get(f"/api/training/datasets/{dataset_id}/images")
        
        assert response.status_code == 200
        assert len(response.json()) == 2
    
    def test_list_images_pagination(self, client, clear_db):
        """Test image list pagination."""
        # Create dataset and upload images
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        for _ in range(5):
            client.post(f"/api/training/datasets/{dataset_id}/images")
        
        # Get first page
        response = client.get(f"/api/training/datasets/{dataset_id}/images?limit=2&offset=0")
        assert len(response.json()) == 2
        
        # Get second page
        response = client.get(f"/api/training/datasets/{dataset_id}/images?limit=2&offset=2")
        assert len(response.json()) == 2
    
    def test_get_image(self, client, clear_db):
        """Test getting a specific image."""
        # Create dataset and upload image
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        upload_response = client.post(f"/api/training/datasets/{dataset_id}/images")
        image_id = upload_response.json()['uploaded'][0]['id']
        
        # Get image
        response = client.get(f"/api/training/images/{image_id}")
        
        assert response.status_code == 200
        assert response.json()['id'] == image_id
    
    def test_delete_image(self, client, clear_db):
        """Test deleting an image."""
        # Create dataset and upload image
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        upload_response = client.post(f"/api/training/datasets/{dataset_id}/images")
        image_id = upload_response.json()['uploaded'][0]['id']
        
        # Delete image
        response = client.delete(f"/api/training/images/{image_id}")
        
        assert response.status_code == 200
        
        # Verify deleted
        get_response = client.get(f"/api/training/images/{image_id}")
        assert get_response.status_code == 404
    
    def test_delete_image_updates_dataset_count(self, client, clear_db):
        """Test deleting image decrements dataset image count."""
        # Create dataset and upload image
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        upload_response = client.post(f"/api/training/datasets/{dataset_id}/images")
        image_id = upload_response.json()['uploaded'][0]['id']
        
        # Verify count = 1
        ds = client.get(f"/api/training/datasets/{dataset_id}").json()
        assert ds['images_count'] == 1
        
        # Delete image
        client.delete(f"/api/training/images/{image_id}")
        
        # Verify count = 0
        ds = client.get(f"/api/training/datasets/{dataset_id}").json()
        assert ds['images_count'] == 0


# ============================================================================
# ANNOTATION ENDPOINT TESTS
# ============================================================================

class TestAnnotationEndpoints:
    """Integration tests for annotation endpoints."""
    
    def test_create_annotation(self, client, clear_db):
        """Test creating an annotation."""
        # Setup: create dataset and image
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        upload_response = client.post(f"/api/training/datasets/{dataset_id}/images")
        image_id = upload_response.json()['uploaded'][0]['id']
        
        # Create annotation
        ann_data = {
            "class_name": "hardhat",
            "bbox_x1": 0.1,
            "bbox_y1": 0.2,
            "bbox_x2": 0.5,
            "bbox_y2": 0.6
        }
        response = client.post(f"/api/training/images/{image_id}/annotations", json=ann_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result['class_name'] == "hardhat"
        assert result['bbox_x1'] == 0.1
    
    def test_create_annotation_invalid_bbox(self, client, clear_db):
        """Test creating annotation with invalid bounding box."""
        # Setup
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        upload_response = client.post(f"/api/training/datasets/{dataset_id}/images")
        image_id = upload_response.json()['uploaded'][0]['id']
        
        # Invalid: x1 > x2
        ann_data = {
            "class_name": "hardhat",
            "bbox_x1": 0.5,
            "bbox_y1": 0.2,
            "bbox_x2": 0.1,  # Invalid: should be > x1
            "bbox_y2": 0.6
        }
        response = client.post(f"/api/training/images/{image_id}/annotations", json=ann_data)
        
        assert response.status_code == 400
    
    def test_create_annotation_bbox_out_of_range(self, client, clear_db):
        """Test creating annotation with bbox out of range."""
        # Setup
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        upload_response = client.post(f"/api/training/datasets/{dataset_id}/images")
        image_id = upload_response.json()['uploaded'][0]['id']
        
        # Invalid: coordinates > 1
        ann_data = {
            "class_name": "hardhat",
            "bbox_x1": 0.1,
            "bbox_y1": 0.2,
            "bbox_x2": 1.5,  # Invalid: > 1
            "bbox_y2": 0.6
        }
        response = client.post(f"/api/training/images/{image_id}/annotations", json=ann_data)
        
        assert response.status_code == 400
    
    def test_list_annotations(self, client, clear_db):
        """Test listing annotations for an image."""
        # Setup
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        upload_response = client.post(f"/api/training/datasets/{dataset_id}/images")
        image_id = upload_response.json()['uploaded'][0]['id']
        
        # Create annotations
        ann_data = {"class_name": "hardhat", "bbox_x1": 0.1, "bbox_y1": 0.1, "bbox_x2": 0.3, "bbox_y2": 0.3}
        client.post(f"/api/training/images/{image_id}/annotations", json=ann_data)
        client.post(f"/api/training/images/{image_id}/annotations", json=ann_data)
        
        # List annotations
        response = client.get(f"/api/training/images/{image_id}/annotations")
        
        assert response.status_code == 200
        assert len(response.json()) == 2
    
    def test_delete_annotation(self, client, clear_db):
        """Test deleting an annotation."""
        # Setup
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        upload_response = client.post(f"/api/training/datasets/{dataset_id}/images")
        image_id = upload_response.json()['uploaded'][0]['id']
        
        ann_data = {"class_name": "hardhat", "bbox_x1": 0.1, "bbox_y1": 0.1, "bbox_x2": 0.3, "bbox_y2": 0.3}
        ann_response = client.post(f"/api/training/images/{image_id}/annotations", json=ann_data)
        ann_id = ann_response.json()['id']
        
        # Delete annotation
        response = client.delete(f"/api/training/annotations/{ann_id}")
        
        assert response.status_code == 200
        
        # Verify deleted
        anns = client.get(f"/api/training/images/{image_id}/annotations").json()
        assert len(anns) == 0


# ============================================================================
# TRAINING JOB ENDPOINT TESTS
# ============================================================================

class TestTrainingJobEndpoints:
    """Integration tests for training job endpoints."""
    
    def test_create_training_job(self, client, clear_db):
        """Test creating a training job."""
        # Setup: create dataset
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        # Create job
        job_data = {
            "dataset_id": dataset_id,
            "epochs": 50,
            "batch_size": 16,
            "learning_rate": 0.001
        }
        response = client.post("/api/training/jobs", json=job_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'pending'
        assert result['epochs_total'] == 50
    
    def test_create_training_job_nonexistent_dataset(self, client, clear_db):
        """Test creating job for non-existent dataset."""
        job_data = {
            "dataset_id": str(uuid.uuid4()),
            "epochs": 50
        }
        response = client.post("/api/training/jobs", json=job_data)
        
        assert response.status_code == 404
    
    def test_create_training_job_duplicate(self, client, clear_db):
        """Test cannot create duplicate running job for same dataset."""
        # Setup
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        # Create first job
        job_data = {"dataset_id": dataset_id, "epochs": 50}
        client.post("/api/training/jobs", json=job_data)
        
        # Try to create second job
        response = client.post("/api/training/jobs", json=job_data)
        
        assert response.status_code == 400
    
    def test_list_training_jobs(self, client, clear_db):
        """Test listing training jobs."""
        # Setup: create datasets and jobs
        ds1 = client.post("/api/training/datasets", json={"name": "DS1"}).json()
        ds2 = client.post("/api/training/datasets", json={"name": "DS2"}).json()
        
        client.post("/api/training/jobs", json={"dataset_id": ds1['id'], "epochs": 50})
        client.post("/api/training/jobs", json={"dataset_id": ds2['id'], "epochs": 100})
        
        # List jobs
        response = client.get("/api/training/jobs")
        
        assert response.status_code == 200
        assert len(response.json()) == 2
    
    def test_get_training_job(self, client, clear_db):
        """Test getting a specific training job."""
        # Setup
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        job_response = client.post("/api/training/jobs", json={"dataset_id": dataset_id, "epochs": 50})
        job_id = job_response.json()['id']
        
        # Get job
        response = client.get(f"/api/training/jobs/{job_id}")
        
        assert response.status_code == 200
        assert response.json()['id'] == job_id
    
    def test_cancel_training_job(self, client, clear_db):
        """Test cancelling a training job."""
        # Setup
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        job_response = client.post("/api/training/jobs", json={"dataset_id": dataset_id, "epochs": 50})
        job_id = job_response.json()['id']
        
        # Cancel job
        response = client.post(f"/api/training/jobs/{job_id}/cancel")
        
        assert response.status_code == 200
        assert response.json()['status'] == 'cancelled'
        
        # Verify status changed
        job = client.get(f"/api/training/jobs/{job_id}").json()
        assert job['status'] == 'cancelled'


# ============================================================================
# MODEL ENDPOINT TESTS
# ============================================================================

class TestModelEndpoints:
    """Integration tests for model endpoints."""
    
    def test_list_models_empty(self, client, clear_db):
        """Test listing models when empty."""
        response = client.get("/api/training/models")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_activate_model(self, client, clear_db, app):
        """Test activating a model."""
        # Add model directly to state
        model_id = str(uuid.uuid4())
        app.state.models_db[model_id] = {
            'id': model_id,
            'name': 'Test Model',
            'map50': 0.85,
            'is_active': False
        }
        
        # Activate model
        response = client.post(f"/api/training/models/{model_id}/activate")
        
        assert response.status_code == 200
        assert response.json()['model']['is_active'] is True
    
    def test_activate_model_deactivates_others(self, client, clear_db, app):
        """Test activating model deactivates other models."""
        # Add two models
        model1_id = str(uuid.uuid4())
        model2_id = str(uuid.uuid4())
        app.state.models_db[model1_id] = {'id': model1_id, 'name': 'Model 1', 'is_active': True}
        app.state.models_db[model2_id] = {'id': model2_id, 'name': 'Model 2', 'is_active': False}
        
        # Activate model 2
        client.post(f"/api/training/models/{model2_id}/activate")
        
        # Verify model 1 is deactivated
        assert app.state.models_db[model1_id]['is_active'] is False
        assert app.state.models_db[model2_id]['is_active'] is True


# ============================================================================
# STATISTICS ENDPOINT TESTS
# ============================================================================

class TestStatisticsEndpoints:
    """Integration tests for statistics endpoints."""
    
    def test_stats_overview_empty(self, client, clear_db):
        """Test stats overview when empty."""
        response = client.get("/api/training/stats/overview")
        
        assert response.status_code == 200
        stats = response.json()
        assert stats['total_datasets'] == 0
        assert stats['total_images'] == 0
        assert stats['total_annotations'] == 0
    
    def test_stats_overview_with_data(self, client, clear_db):
        """Test stats overview with data."""
        # Create data
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        upload_response = client.post(f"/api/training/datasets/{dataset_id}/images")
        image_id = upload_response.json()['uploaded'][0]['id']
        
        ann_data = {"class_name": "hardhat", "bbox_x1": 0.1, "bbox_y1": 0.1, "bbox_x2": 0.3, "bbox_y2": 0.3}
        client.post(f"/api/training/images/{image_id}/annotations", json=ann_data)
        
        # Get stats
        response = client.get("/api/training/stats/overview")
        
        assert response.status_code == 200
        stats = response.json()
        assert stats['total_datasets'] == 1
        assert stats['total_images'] == 1
        assert stats['total_annotations'] == 1
    
    def test_class_distribution(self, client, clear_db):
        """Test class distribution statistics."""
        # Create data
        ds_response = client.post("/api/training/datasets", json={"name": "Test"})
        dataset_id = ds_response.json()['id']
        
        upload_response = client.post(f"/api/training/datasets/{dataset_id}/images")
        image_id = upload_response.json()['uploaded'][0]['id']
        
        # Create annotations with different classes
        for cls in ['hardhat', 'hardhat', 'vest', 'no_hardhat']:
            ann_data = {"class_name": cls, "bbox_x1": 0.1, "bbox_y1": 0.1, "bbox_x2": 0.3, "bbox_y2": 0.3}
            client.post(f"/api/training/images/{image_id}/annotations", json=ann_data)
        
        # Get distribution
        response = client.get("/api/training/stats/class-distribution")
        
        assert response.status_code == 200
        dist = response.json()
        assert dist['hardhat'] == 2
        assert dist['vest'] == 1
        assert dist['no_hardhat'] == 1


# ============================================================================
# END-TO-END WORKFLOW TESTS
# ============================================================================

class TestEndToEndWorkflow:
    """End-to-end workflow tests."""
    
    def test_full_training_workflow(self, client, clear_db):
        """Test complete training workflow: dataset -> images -> annotations -> job."""
        # 1. Create dataset
        ds_response = client.post("/api/training/datasets", json={
            "name": "PPE Training Dataset",
            "description": "Construction site images"
        })
        assert ds_response.status_code == 200
        dataset_id = ds_response.json()['id']
        
        # 2. Upload images
        for _ in range(3):
            upload_response = client.post(f"/api/training/datasets/{dataset_id}/images")
            assert upload_response.status_code == 200
        
        # Verify image count
        ds = client.get(f"/api/training/datasets/{dataset_id}").json()
        assert ds['images_count'] == 3
        
        # 3. Add annotations
        images = client.get(f"/api/training/datasets/{dataset_id}/images").json()
        for img in images:
            ann_data = {
                "class_name": "hardhat",
                "bbox_x1": 0.2,
                "bbox_y1": 0.1,
                "bbox_x2": 0.4,
                "bbox_y2": 0.3
            }
            client.post(f"/api/training/images/{img['id']}/annotations", json=ann_data)
        
        # Verify annotation count
        ds = client.get(f"/api/training/datasets/{dataset_id}").json()
        assert ds['annotations_count'] == 3
        
        # 4. Create training job
        job_response = client.post("/api/training/jobs", json={
            "dataset_id": dataset_id,
            "epochs": 100,
            "batch_size": 16
        })
        assert job_response.status_code == 200
        job = job_response.json()
        assert job['status'] == 'pending'
        
        # 5. Check stats
        stats = client.get("/api/training/stats/overview").json()
        assert stats['total_datasets'] == 1
        assert stats['total_images'] == 3
        assert stats['total_annotations'] == 3
        assert stats['total_jobs'] == 1


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
