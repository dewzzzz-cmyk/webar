"""
Deploy 1 Tests — T01, T02, T03
PPE Detection System v2.12.0
"""
import os
import re
import pytest

# ============================================================
# T01: Celery workers fix (daemonic process can't spawn children)
# ============================================================

class TestT01CeleryWorkersFix:
    """workers must be 0 in train_args to avoid AssertionError."""

    def test_workers_is_zero_in_source(self):
        """Source code must have workers: 0."""
        worker_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'services', 'training', 'worker.py'
        )
        with open(worker_path, 'r') as f:
            content = f.read()
        
        # Must contain workers: 0
        assert "'workers': 0" in content or '"workers": 0' in content, \
            "worker.py must have workers=0 to prevent daemonic crash"

    def test_workers_not_four(self):
        """Regression: workers must NEVER be 4."""
        worker_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'services', 'training', 'worker.py'
        )
        with open(worker_path, 'r') as f:
            content = f.read()
        
        # Must NOT contain workers: 4 (the old broken value)
        assert "'workers': 4" not in content, \
            "REGRESSION: workers=4 causes AssertionError in Celery daemon"


# ============================================================
# T02: Models endpoint robustness (never 404)
# ============================================================

class TestT02ModelsEndpoint:
    """GET /api/training/models must never return 404."""

    def test_list_models_has_filesystem_fallback(self):
        """Source must contain filesystem scan logic."""
        router_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'services', 'api', 'training_router.py'
        )
        with open(router_path, 'r') as f:
            content = f.read()
        
        assert 'model_dirs' in content, "Must scan filesystem directories"
        assert '.pt' in content, "Must look for .pt model files"
        assert 'source' in content, "Must indicate model source (db/filesystem)"

    def test_list_models_no_response_model_constraint(self):
        """Endpoint must NOT have strict response_model=List[ModelResponse]."""
        router_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'services', 'api', 'training_router.py'
        )
        with open(router_path, 'r') as f:
            content = f.read()
        
        # Find the models endpoint line
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '@router.get("/models"' in line and 'download' not in line:
                # Must NOT have response_model=List[ModelResponse] (causes 422 on extended response)
                assert 'response_model=List[ModelResponse]' not in line, \
                    "Strict response_model blocks filesystem fallback fields"
                break

    def test_returns_dict_with_count(self):
        """Response must be dict with models/count keys, not bare list."""
        router_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'services', 'api', 'training_router.py'
        )
        with open(router_path, 'r') as f:
            content = f.read()
        
        assert '"models":' in content, "Response must have 'models' key"
        assert '"count":' in content, "Response must have 'count' key"


# ============================================================
# T03: Screenshot deletion cleans Redis
# ============================================================

class TestT03ScreenshotDeletion:
    """DELETE /api/training/images/{id} must clean Redis annotations."""

    def test_delete_image_cleans_redis(self):
        """Source must contain Redis cleanup logic."""
        router_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'services', 'api', 'training_router.py'
        )
        with open(router_path, 'r') as f:
            content = f.read()
        
        assert 'Clean up Redis' in content, "Must have Redis cleanup section"
        assert 'annotations:' in content, "Must clean annotations: keys"
        assert 'auto_annotations:' in content, "Must clean auto_annotations: keys"
        assert 'annotation_history:' in content, "Must clean annotation_history: keys"

    def test_redis_cleanup_is_non_critical(self):
        """Redis failure must NOT block image deletion."""
        router_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'services', 'api', 'training_router.py'
        )
        with open(router_path, 'r') as f:
            content = f.read()
        
        # Find the delete_image function and check it has try/except around Redis
        assert 'Redis cleanup failed (non-critical)' in content, \
            "Redis errors must be caught and logged as non-critical"

    def test_delete_returns_source_field(self):
        """Response must include source field (db/filesystem)."""
        router_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'services', 'api', 'training_router.py'
        )
        with open(router_path, 'r') as f:
            content = f.read()
        
        assert '"source"' in content and '"db"' in content and '"filesystem"' in content, \
            "delete response must indicate source: db or filesystem"

    def test_cleans_catalog_annotations_too(self):
        """Must also clean catalog_annotations: keys."""
        router_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'services', 'api', 'training_router.py'
        )
        with open(router_path, 'r') as f:
            content = f.read()
        
        assert 'catalog_annotations:' in content, \
            "Must clean catalog_annotations keys for catalog images"


# ============================================================
# Version check
# ============================================================

class TestVersion:
    def test_version_is_2_12_0(self):
        version_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'VERSION'
        )
        with open(version_path, 'r') as f:
            version = f.read().strip()
        assert version == '2.12.0', f"Expected 2.12.0, got {version}"
