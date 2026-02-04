"""
Integration Tests for Training API v2.10.62
============================================
Tests for auto-annotation, annotation CRUD, and catalog datasets.
"""

import pytest
import httpx
import asyncio
import os
from typing import Optional

# API base URL from environment or default
API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")


class TestAutoAnnotationAPI:
    """Integration tests for auto-annotation endpoint."""
    
    @pytest.fixture
    def api_client(self):
        """HTTP client for API calls."""
        return httpx.Client(base_url=API_BASE_URL, timeout=30.0)
    
    def test_auto_annotate_endpoint_exists(self, api_client):
        """POST /api/training/images/{id}/auto-annotate should return valid response."""
        # Use a fake image ID - should return 404 (not 405 Method Not Allowed)
        response = api_client.post(
            "/api/training/images/00000000-0000-0000-0000-000000000000/auto-annotate",
            params={"threshold": 0.3}
        )
        
        # 404 = endpoint exists, image not found
        # 405 = endpoint doesn't exist
        # 503 = detector not running (expected in test environment)
        assert response.status_code in [404, 503, 500], \
            f"Unexpected status {response.status_code}: {response.text}"
    
    def test_auto_annotate_with_threshold(self, api_client):
        """Auto-annotate should accept threshold parameter."""
        response = api_client.post(
            "/api/training/images/test-id/auto-annotate",
            params={"threshold": 0.5}
        )
        
        # Should not fail on parameter parsing
        assert response.status_code != 422, "Threshold parameter should be accepted"
    
    def test_auto_annotate_default_threshold(self, api_client):
        """Auto-annotate should work without threshold (use default)."""
        response = api_client.post(
            "/api/training/images/test-id/auto-annotate"
        )
        
        # Should use default threshold 0.3
        assert response.status_code in [404, 503, 500]


class TestAnnotationUpdateAPI:
    """Integration tests for annotation update endpoint."""
    
    @pytest.fixture
    def api_client(self):
        return httpx.Client(base_url=API_BASE_URL, timeout=30.0)
    
    def test_update_annotation_endpoint_exists(self, api_client):
        """PUT /api/training/annotations/{id} should exist."""
        response = api_client.put(
            "/api/training/annotations/00000000-0000-0000-0000-000000000000",
            json={"class_name": "hardhat"}
        )
        
        # 404 = endpoint exists, annotation not found
        # 405 = endpoint doesn't exist
        assert response.status_code == 404, \
            f"Expected 404 for non-existent annotation, got {response.status_code}"
    
    def test_update_annotation_partial_update(self, api_client):
        """Should allow updating only class_name without bbox."""
        response = api_client.put(
            "/api/training/annotations/test-id",
            json={"class_name": "vest"}  # Only class_name, no bbox
        )
        
        # Should not fail validation
        assert response.status_code != 422, \
            "Partial update (class_name only) should be allowed"
    
    def test_update_annotation_validates_class_name(self, api_client):
        """Empty class_name should be rejected."""
        response = api_client.put(
            "/api/training/annotations/test-id",
            json={"class_name": ""}
        )
        
        # Should fail validation
        assert response.status_code == 422, \
            "Empty class_name should be rejected"


class TestCatalogDatasetsAPI:
    """Integration tests for catalog dataset operations."""
    
    @pytest.fixture
    def api_client(self):
        return httpx.Client(base_url=API_BASE_URL, timeout=30.0)
    
    def test_list_catalog_datasets(self, api_client):
        """GET /api/training/catalog/datasets should return list."""
        response = api_client.get("/api/training/catalog/datasets")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # Each dataset should have required fields
        if data:
            dataset = data[0]
            assert "id" in dataset
            assert "name" in dataset
    
    def test_catalog_dataset_status(self, api_client):
        """GET /api/training/catalog/datasets/{id}/status should return status."""
        # First get list of datasets
        response = api_client.get("/api/training/catalog/datasets")
        if response.status_code != 200:
            pytest.skip("Catalog datasets endpoint not available")
        
        datasets = response.json()
        if not datasets:
            pytest.skip("No catalog datasets configured")
        
        dataset_id = datasets[0]["id"]
        
        # Get status
        response = api_client.get(f"/api/training/catalog/datasets/{dataset_id}/status")
        
        assert response.status_code == 200
        status = response.json()
        
        assert "downloaded" in status
        assert "image_count" in status


class TestTrainingJobsAPI:
    """Integration tests for training job creation."""
    
    @pytest.fixture
    def api_client(self):
        return httpx.Client(base_url=API_BASE_URL, timeout=30.0)
    
    def test_create_job_validates_dataset(self, api_client):
        """Creating job with non-existent dataset should fail."""
        response = api_client.post(
            "/api/training/jobs",
            json={
                "dataset_id": "non-existent-dataset-id",
                "model_type": "yolov8n",
                "epochs": 10
            }
        )
        
        # Should return 400 or 404, not 500 (internal error)
        assert response.status_code in [400, 404], \
            f"Expected 400/404 for invalid dataset, got {response.status_code}: {response.text}"
    
    def test_create_job_with_filesystem_dataset(self, api_client):
        """Creating job with filesystem dataset should not cause SQL errors."""
        # Get available datasets
        response = api_client.get("/api/training/datasets")
        if response.status_code != 200:
            pytest.skip("Datasets endpoint not available")
        
        datasets = response.json()
        
        # Find a filesystem dataset (not from PostgreSQL)
        filesystem_datasets = [d for d in datasets if d.get("source") == "filesystem"]
        
        if not filesystem_datasets:
            pytest.skip("No filesystem datasets available")
        
        dataset_id = filesystem_datasets[0]["id"]
        
        # Try to create job
        response = api_client.post(
            "/api/training/jobs",
            json={
                "dataset_id": dataset_id,
                "model_type": "yolov8n",
                "epochs": 1
            }
        )
        
        # Should not return 500 (which would indicate SQL error)
        assert response.status_code != 500, \
            f"Internal error creating job: {response.text}"


class TestDatasetImagesAPI:
    """Integration tests for dataset images with pagination."""
    
    @pytest.fixture
    def api_client(self):
        return httpx.Client(base_url=API_BASE_URL, timeout=30.0)
    
    def test_images_pagination(self, api_client):
        """Images endpoint should support pagination."""
        # Get datasets first
        response = api_client.get("/api/training/datasets")
        if response.status_code != 200:
            pytest.skip("Datasets endpoint not available")
        
        datasets = response.json()
        if not datasets:
            pytest.skip("No datasets available")
        
        dataset_id = datasets[0]["id"]
        
        # Get page 1
        response = api_client.get(
            f"/api/training/datasets/{dataset_id}/images",
            params={"page": 1, "page_size": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have pagination fields
        assert "total" in data
        assert "page" in data
        assert "images" in data
    
    def test_annotations_count_is_global(self, api_client):
        """Annotation count should be total for dataset, not just current page."""
        # Get datasets
        response = api_client.get("/api/training/datasets")
        if response.status_code != 200:
            pytest.skip("Datasets endpoint not available")
        
        datasets = response.json()
        if not datasets:
            pytest.skip("No datasets available")
        
        dataset_id = datasets[0]["id"]
        
        # Get page 1 with small page size
        response1 = api_client.get(
            f"/api/training/datasets/{dataset_id}/images",
            params={"page": 1, "page_size": 5}
        )
        
        # Get page 2
        response2 = api_client.get(
            f"/api/training/datasets/{dataset_id}/images",
            params={"page": 2, "page_size": 5}
        )
        
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.json()
            data2 = response2.json()
            
            # Total count should be same on both pages
            if "total" in data1 and "total" in data2:
                assert data1["total"] == data2["total"], \
                    "Total count should be same across pages"


class TestHealthEndpoints:
    """Test health and status endpoints."""
    
    @pytest.fixture
    def api_client(self):
        return httpx.Client(base_url=API_BASE_URL, timeout=10.0)
    
    def test_health_endpoint(self, api_client):
        """GET /health should return OK."""
        response = api_client.get("/health")
        
        assert response.status_code == 200
    
    def test_api_version(self, api_client):
        """API should return version info."""
        response = api_client.get("/api/version")
        
        if response.status_code == 200:
            data = response.json()
            assert "version" in data
            # Should be semver format
            assert data["version"].count(".") >= 2


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
    ])
