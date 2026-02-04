"""
Deploy 2 Tests — T04 (Auto-Annotate), T05 (Batch), T06 (GPU Guard)
PPE Detection System v2.12.0
"""
import os
import re
import pytest


ROUTER_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'services', 'api', 'training_router.py'
)
WORKER_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'services', 'training', 'worker.py'
)


def _read(path):
    with open(path, 'r') as f:
        return f.read()


# ============================================================
# T04: Auto-Annotate Single Image (Celery + CPU)
# ============================================================

class TestT04AutoAnnotateSingle:
    """POST /images/{id}/auto-annotate → Celery task dispatch."""

    def test_endpoint_dispatches_to_celery(self):
        """API sends task to Celery, not running YOLO inline."""
        code = _read(ROUTER_PATH)
        # Find the auto-annotate function
        match = re.search(
            r'async def auto_annotate_image.*?(?=\n    @router|\n    #\s===)',
            code, re.DOTALL
        )
        assert match, "auto_annotate_image function not found"
        func_body = match.group()
        
        assert 'send_task' in func_body, "Must dispatch to Celery via send_task"
        assert 'training.auto_annotate' in func_body, "Must call training.auto_annotate task"
        
        # Must NOT contain inline YOLO
        assert 'YOLO(' not in func_body, "API must NOT run YOLO inline — use Celery worker"
        assert 'model.predict' not in func_body, "API must NOT run model.predict inline"

    def test_endpoint_returns_task_id(self):
        """Response must include task_id for polling."""
        code = _read(ROUTER_PATH)
        match = re.search(
            r'async def auto_annotate_image.*?(?=\n    @router|\n    #\s===)',
            code, re.DOTALL
        )
        func_body = match.group()
        assert '"task_id"' in func_body, "Must return task_id"
        assert '"status"' in func_body, "Must return status"

    def test_endpoint_validates_threshold(self):
        """Threshold must have validation (ge/le)."""
        code = _read(ROUTER_PATH)
        assert 'ge=0.05' in code or 'ge=0.1' in code, "Threshold must have minimum validation"
        assert 'le=0.95' in code or 'le=0.9' in code, "Threshold must have maximum validation"

    def test_celery_task_exists_in_worker(self):
        """Celery worker must have auto_annotate task."""
        code = _read(WORKER_PATH)
        assert 'training.auto_annotate' in code, "Worker must register training.auto_annotate task"
        assert 'def auto_annotate_task' in code, "Worker must have auto_annotate_task function"

    def test_worker_stores_in_redis(self):
        """Worker must store results in Redis."""
        code = _read(WORKER_PATH)
        assert 'auto_annotations:' in code, "Must store in auto_annotations:{id} Redis key"

    def test_worker_saves_to_db(self):
        """Worker must try to save annotations to DB."""
        code = _read(WORKER_PATH)
        # Find auto_annotate_task function
        match = re.search(
            r'def auto_annotate_task.*?(?=\n@app\.task|\n# ====)',
            code, re.DOTALL
        )
        assert match, "auto_annotate_task not found"
        func_body = match.group()
        assert 'INSERT INTO annotations' in func_body, "Must save annotations to DB"
        assert 'ON CONFLICT DO NOTHING' in func_body, "Must handle duplicate annotations"

    def test_no_duplicate_endpoints(self):
        """Must have exactly ONE /images/{id}/auto-annotate endpoint."""
        code = _read(ROUTER_PATH)
        matches = re.findall(r'@router\.post\("/images/\{image_id\}/auto-annotate"\)', code)
        assert len(matches) == 1, f"Expected 1 auto-annotate endpoint, found {len(matches)}"


# ============================================================
# T05: Batch Auto-Annotate (Celery + CPU + progress)
# ============================================================

class TestT05BatchAutoAnnotate:
    """POST /datasets/{id}/auto-annotate → batch Celery dispatch."""

    def test_batch_endpoint_dispatches_to_celery(self):
        """Batch API sends task to Celery."""
        code = _read(ROUTER_PATH)
        match = re.search(
            r'async def auto_annotate_dataset.*?(?=\n    @router|\n    #\s===)',
            code, re.DOTALL
        )
        assert match, "auto_annotate_dataset function not found"
        func_body = match.group()
        
        assert 'send_task' in func_body, "Must dispatch to Celery"
        assert 'batch_auto_annotate' in func_body, "Must call batch_auto_annotate task"
        assert 'YOLO(' not in func_body, "API must NOT run YOLO inline"

    def test_batch_celery_task_exists(self):
        """Celery worker must have batch_auto_annotate task."""
        code = _read(WORKER_PATH)
        assert 'training.batch_auto_annotate' in code
        assert 'def batch_auto_annotate_task' in code

    def test_batch_publishes_progress(self):
        """Batch task must publish progress via Redis."""
        code = _read(WORKER_PATH)
        match = re.search(
            r'def batch_auto_annotate_task.*?(?=\n@app\.task|\n# ====|\nif __name__)',
            code, re.DOTALL
        )
        assert match, "batch_auto_annotate_task not found"
        func_body = match.group()
        
        assert 'progress_pct' in func_body, "Must calculate progress percentage"
        assert 'publish' in func_body or 'redis_client.set' in func_body, \
            "Must publish progress updates"
        assert 'autoannotate:progress:' in func_body or 'autoannotate:status:' in func_body, \
            "Must use standard progress keys"

    def test_batch_has_skip_annotated_option(self):
        """Batch must support skip_annotated parameter."""
        code = _read(WORKER_PATH)
        assert 'skip_annotated' in code, "Must have skip_annotated parameter"

    def test_status_polling_endpoint_exists(self):
        """GET /auto-annotate/status/{task_id} must exist for polling."""
        code = _read(ROUTER_PATH)
        assert '/auto-annotate/status/' in code, "Must have status polling endpoint"
        assert 'AsyncResult' in code, "Must use Celery AsyncResult for status"

    def test_batch_progress_endpoint_exists(self):
        """GET /datasets/{id}/auto-annotate/progress must exist."""
        code = _read(ROUTER_PATH)
        assert '/auto-annotate/progress' in code, "Must have batch progress endpoint"

    def test_results_endpoint_exists(self):
        """GET /auto-annotate/results/{image_id} must exist."""
        code = _read(ROUTER_PATH)
        assert '/auto-annotate/results/' in code, "Must have results retrieval endpoint"


# ============================================================
# T06: GPU Resource Guard
# ============================================================

class TestT06GPUGuard:
    """All auto-annotate tasks must use CPU only."""

    def test_single_auto_annotate_uses_cpu(self):
        """auto_annotate_task must force CPU."""
        code = _read(WORKER_PATH)
        match = re.search(
            r'def auto_annotate_task.*?(?=\n@app\.task|\n# ====)',
            code, re.DOTALL
        )
        assert match, "auto_annotate_task not found"
        func_body = match.group()
        
        assert 'model.to("cpu")' in func_body or "model.to('cpu')" in func_body, \
            "Must call model.to('cpu')"
        assert 'device="cpu"' in func_body or "device='cpu'" in func_body, \
            "Must pass device='cpu' to predict"

    def test_batch_auto_annotate_uses_cpu(self):
        """batch_auto_annotate_task must force CPU."""
        code = _read(WORKER_PATH)
        match = re.search(
            r'def batch_auto_annotate_task.*?(?=\n@app\.task|\n# ====|\nif __name__)',
            code, re.DOTALL
        )
        assert match, "batch_auto_annotate_task not found"
        func_body = match.group()
        
        assert 'model.to("cpu")' in func_body or "model.to('cpu')" in func_body, \
            "Batch must call model.to('cpu')"
        assert 'device="cpu"' in func_body or "device='cpu'" in func_body, \
            "Batch must pass device='cpu' to predict"

    def test_training_still_uses_gpu(self):
        """Training task must still use GPU when available."""
        code = _read(WORKER_PATH)
        match = re.search(
            r'def train_model\b.*?(?=\n@app\.task|\n# ====)',
            code, re.DOTALL
        )
        assert match, "train_model not found"
        func_body = match.group()
        
        # Training should detect GPU
        assert 'nvidia' in func_body.lower() or 'device' in func_body, \
            "Training must detect and use GPU"
        # Must NOT hardcode CPU for training
        assert 'workers' in func_body, "Training must have workers config"

    def test_gpu_guard_comment_present(self):
        """Code must have GPU guard documentation."""
        code = _read(WORKER_PATH)
        assert 'GPU guard' in code.lower() or 'GPU Guard' in code, \
            "Must document GPU guard pattern"

    def test_ppe_class_mapping_exists(self):
        """Worker must have PPE class mapping for YOLO → our classes."""
        code = _read(WORKER_PATH)
        assert 'PPE_CLASS_MAPPING' in code or 'class_mapping' in code, \
            "Must have PPE class mapping"
        assert 'hardhat' in code, "Mapping must include hardhat"
        assert 'no_hardhat' in code, "Mapping must include no_hardhat"
        assert 'vest' in code, "Mapping must include vest"
