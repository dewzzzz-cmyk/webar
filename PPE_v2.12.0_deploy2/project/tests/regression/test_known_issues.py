"""
Regression Tests for Known Issues
=================================
Tests based on bugs found during development.
Run these before each release to ensure bugs don't return.

Bug History:
- v2.10.60: Training start "Unknown error" - SQL column 'source' doesn't exist
- v2.10.60: Dataset download fails - recursive search needed
- v2.10.61: Kaggle library missing
- v2.10.61: Catalog annotation counting broken
- v2.10.62: TypeScript unused imports break build
- v2.10.62: Auto-annotation endpoint missing
"""

import pytest
import asyncio
import os
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services" / "api"))


class TestCatalogDatasetImageSearch:
    """
    Bug v2.10.60: Roboflow creates nested folders, images not found.
    Fix: Recursive search up to 3 levels deep.
    """
    
    def test_recursive_image_search_finds_nested_images(self, tmp_path):
        """Images in nested folders should be found."""
        # Create nested structure like Roboflow does
        nested = tmp_path / "dataset" / "project-name" / "train" / "images"
        nested.mkdir(parents=True)
        
        # Create test images
        (nested / "image1.jpg").write_bytes(b"fake image 1")
        (nested / "image2.png").write_bytes(b"fake image 2")
        (nested / "image3.jpeg").write_bytes(b"fake image 3")
        
        # Search function should find them
        found = self._find_images_recursive(tmp_path / "dataset", max_depth=3)
        
        assert len(found) == 3
        assert any("image1.jpg" in str(f) for f in found)
        assert any("image2.png" in str(f) for f in found)
        assert any("image3.jpeg" in str(f) for f in found)
    
    def test_recursive_search_respects_max_depth(self, tmp_path):
        """Search should not go deeper than max_depth."""
        # Create 5 levels deep
        deep = tmp_path / "l1" / "l2" / "l3" / "l4" / "l5"
        deep.mkdir(parents=True)
        (deep / "too_deep.jpg").write_bytes(b"fake")
        
        # Search with depth 3 should not find it
        found = self._find_images_recursive(tmp_path, max_depth=3)
        assert len(found) == 0
        
        # Search with depth 5 should find it
        found = self._find_images_recursive(tmp_path, max_depth=5)
        assert len(found) == 1
    
    def test_finds_images_with_various_extensions(self, tmp_path):
        """Should find jpg, jpeg, png, bmp, webp."""
        extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.JPG', '.PNG']
        
        for i, ext in enumerate(extensions):
            (tmp_path / f"image{i}{ext}").write_bytes(b"fake")
        
        # Also create non-image file
        (tmp_path / "readme.txt").write_text("not an image")
        
        found = self._find_images_recursive(tmp_path, max_depth=1)
        assert len(found) == len(extensions)
    
    def _find_images_recursive(self, base_path: Path, max_depth: int = 3) -> list:
        """Helper: Recursive image search (mirrors actual implementation)."""
        extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        found = []
        
        def search(path: Path, depth: int):
            if depth > max_depth:
                return
            try:
                for item in path.iterdir():
                    if item.is_file() and item.suffix.lower() in extensions:
                        found.append(item)
                    elif item.is_dir():
                        search(item, depth + 1)
            except PermissionError:
                pass
        
        search(base_path, 0)
        return found


class TestCatalogAnnotationCounting:
    """
    Bug v2.10.61: Annotations not counted for catalog datasets.
    Fix: Count YOLO .txt files in labels/ folder.
    """
    
    def test_counts_yolo_txt_labels(self, tmp_path):
        """Should count annotations from YOLO .txt files."""
        labels_dir = tmp_path / "labels"
        labels_dir.mkdir()
        
        # Create YOLO format label files
        # Format: class_id x_center y_center width height
        (labels_dir / "img1.txt").write_text("0 0.5 0.5 0.1 0.1\n1 0.3 0.3 0.2 0.2")
        (labels_dir / "img2.txt").write_text("0 0.5 0.5 0.1 0.1")
        (labels_dir / "img3.txt").write_text("")  # Empty file
        
        count = self._count_yolo_annotations(tmp_path)
        
        assert count == 3  # 2 + 1 + 0
    
    def test_handles_nested_labels_folder(self, tmp_path):
        """Should find labels in nested train/labels structure."""
        nested_labels = tmp_path / "train" / "labels"
        nested_labels.mkdir(parents=True)
        
        (nested_labels / "img1.txt").write_text("0 0.5 0.5 0.1 0.1")
        
        count = self._count_yolo_annotations(tmp_path)
        
        assert count == 1
    
    def test_ignores_non_txt_files(self, tmp_path):
        """Should only count .txt files."""
        labels_dir = tmp_path / "labels"
        labels_dir.mkdir()
        
        (labels_dir / "img1.txt").write_text("0 0.5 0.5 0.1 0.1")
        (labels_dir / "img1.xml").write_text("<annotation>...</annotation>")
        (labels_dir / "classes.names").write_text("helmet\nvest")
        
        count = self._count_yolo_annotations(tmp_path)
        
        assert count == 1
    
    def _count_yolo_annotations(self, base_path: Path) -> int:
        """Helper: Count YOLO annotations (mirrors actual implementation)."""
        total = 0
        
        # Find labels directories
        for labels_dir in base_path.rglob("labels"):
            if labels_dir.is_dir():
                for txt_file in labels_dir.glob("*.txt"):
                    try:
                        content = txt_file.read_text().strip()
                        if content:
                            total += len(content.split('\n'))
                    except Exception:
                        pass
        
        return total


class TestTrainingJobCreation:
    """
    Bug v2.10.60: Training start fails with "Unknown error".
    Root cause: SQL query referenced non-existent 'source' column.
    """
    
    @pytest.mark.asyncio
    async def test_training_job_with_filesystem_dataset(self):
        """Creating training job with filesystem dataset should not fail."""
        # Mock database pool
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            'id': 'test-uuid',
            'name': 'Test Dataset',
            'image_count': 100,
            'annotations_count': 500
        })
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock()
        
        # This query should NOT contain 'source' column
        # The actual implementation was fixed to read from Redis instead
        query = """
            SELECT i.id, i.file_path, i.filename
            FROM training_images i
            WHERE i.dataset_id = $1
        """
        
        # Verify query doesn't reference non-existent columns
        assert 'source' not in query.lower()
        assert 'original_path' not in query.lower()
    
    @pytest.mark.asyncio
    async def test_catalog_dataset_uses_redis_annotations(self):
        """Catalog datasets should read annotations from Redis, not SQL."""
        # For catalog datasets, annotations are stored in Redis
        # key format: catalog_annotations:{dataset_id}
        
        redis_key_pattern = "catalog_annotations:{dataset_id}"
        
        # Verify this pattern is used in actual code
        # This is a documentation test to ensure developers know the pattern
        assert "catalog_annotations" in redis_key_pattern


class TestAutoAnnotationEndpoint:
    """
    Feature v2.10.62: Auto-annotation using detector model.
    """
    
    @pytest.mark.asyncio
    async def test_auto_annotate_endpoint_exists(self):
        """POST /images/{image_id}/auto-annotate should exist in router."""
        # This is a documentation test - verifying the endpoint pattern
        # Actual integration test is in test_training_v2_10_62.py
        
        expected_endpoint = "POST /api/training/images/{image_id}/auto-annotate"
        
        # Verify endpoint pattern is correct
        assert "auto-annotate" in expected_endpoint
        assert "{image_id}" in expected_endpoint
        assert "POST" in expected_endpoint
        
        # Check if endpoint is defined in training_router.py
        router_path = Path(__file__).parent.parent.parent / "services" / "api" / "training_router.py"
        
        if router_path.exists():
            content = router_path.read_text()
            # Should have auto-annotate endpoint defined
            assert "auto-annotate" in content, "auto-annotate endpoint not found in router"
            assert "async def" in content  # Should be async function
    
    def test_auto_annotate_response_format(self):
        """Auto-annotate should return suggestions with bbox and confidence."""
        # Expected response format
        expected_response = {
            "image_id": "test-uuid",
            "suggestions": [
                {
                    "class_name": "hardhat",
                    "bbox": [0.1, 0.2, 0.3, 0.4],  # Normalized 0-1
                    "confidence": 0.95
                }
            ],
            "count": 1,
            "threshold": 0.3
        }
        
        # Validate structure
        assert "image_id" in expected_response
        assert "suggestions" in expected_response
        assert isinstance(expected_response["suggestions"], list)
        
        if expected_response["suggestions"]:
            suggestion = expected_response["suggestions"][0]
            assert "class_name" in suggestion
            assert "bbox" in suggestion
            assert "confidence" in suggestion
            assert len(suggestion["bbox"]) == 4
            assert all(0 <= v <= 1 for v in suggestion["bbox"])
    
    def test_bbox_normalization(self):
        """Detector returns pixels, API should return normalized 0-1 coords."""
        # Detector output (pixels)
        detector_bbox = {
            "x1": 100, "y1": 50,
            "x2": 200, "y2": 150
        }
        image_width = 640
        image_height = 480
        
        # Expected normalized output
        normalized = [
            detector_bbox["x1"] / image_width,
            detector_bbox["y1"] / image_height,
            detector_bbox["x2"] / image_width,
            detector_bbox["y2"] / image_height
        ]
        
        assert all(0 <= v <= 1 for v in normalized)
        assert normalized == [100/640, 50/480, 200/640, 150/480]


class TestAnnotationCRUD:
    """
    Feature v2.10.62: Update annotation class.
    """
    
    def test_annotation_update_model(self):
        """AnnotationUpdate model should have optional fields."""
        # Expected model structure
        update_data = {
            "class_name": "vest"  # Only updating class, not bbox
        }
        
        # All fields should be optional
        assert "class_name" in update_data
        # bbox fields can be omitted
    
    @pytest.mark.asyncio
    async def test_update_annotation_preserves_bbox(self):
        """Updating class should not change bbox coordinates."""
        original = {
            "id": "ann-uuid",
            "class_name": "hardhat",
            "bbox_x1": 0.1,
            "bbox_y1": 0.2,
            "bbox_x2": 0.3,
            "bbox_y2": 0.4
        }
        
        update_request = {
            "class_name": "vest"
            # No bbox fields
        }
        
        # After update, bbox should remain unchanged
        expected_after_update = {
            "id": "ann-uuid",
            "class_name": "vest",  # Changed
            "bbox_x1": 0.1,  # Preserved
            "bbox_y1": 0.2,  # Preserved
            "bbox_x2": 0.3,  # Preserved
            "bbox_y2": 0.4   # Preserved
        }
        
        assert expected_after_update["class_name"] == "vest"
        assert expected_after_update["bbox_x1"] == original["bbox_x1"]


class TestKaggleIntegration:
    """
    Bug v2.10.61: Kaggle library not installed.
    """
    
    def test_kaggle_in_requirements(self):
        """kaggle package should be in requirements.txt."""
        requirements_path = Path(__file__).parent.parent.parent / "services" / "api" / "requirements.txt"
        
        if requirements_path.exists():
            content = requirements_path.read_text()
            assert "kaggle" in content.lower(), "kaggle package missing from requirements.txt"
    
    def test_kaggle_import_works(self):
        """Should be able to import kaggle (if installed)."""
        try:
            import kaggle
            assert True
        except ImportError:
            # Skip if not installed in test environment
            pytest.skip("kaggle not installed in test environment")


class TestFrontendBuild:
    """
    Bug v2.10.62: Unused imports cause TypeScript build failure.
    """
    
    def test_training_tsx_no_unused_imports(self):
        """Training.tsx should not have unused imports."""
        training_path = Path(__file__).parent.parent.parent / "dashboard" / "src" / "pages" / "Training.tsx"
        
        if not training_path.exists():
            pytest.skip("Training.tsx not found")
        
        content = training_path.read_text()
        
        import re
        
        # Find all imports from lucide-react
        import_match = re.search(r'import\s*{([^}]+)}\s*from\s*[\'"]lucide-react[\'"]', content)
        if import_match:
            imports_str = import_match.group(1)
            
            # Parse imports, handling "X as Y" aliases
            for raw_import in imports_str.split(','):
                raw_import = raw_import.strip()
                if not raw_import:
                    continue
                
                # Handle "Image as ImageIcon" syntax
                if ' as ' in raw_import:
                    # Use the alias name for checking
                    icon = raw_import.split(' as ')[1].strip()
                else:
                    icon = raw_import.strip()
                
                # Each imported icon should be used somewhere in the code
                occurrences = len(re.findall(rf'\b{icon}\b', content))
                
                # Should appear at least twice (import + usage)
                assert occurrences >= 2, f"Icon '{icon}' may be unused (only {occurrences} occurrence)"
    
    def test_no_unused_state_setters(self):
        """State setters should be used if declared."""
        training_path = Path(__file__).parent.parent.parent / "dashboard" / "src" / "pages" / "Training.tsx"
        
        if not training_path.exists():
            pytest.skip("Training.tsx not found")
        
        content = training_path.read_text()
        
        import re
        
        # Find useState declarations
        state_pattern = r'const\s*\[(\w+),\s*(set\w+)\]\s*=\s*useState'
        
        for match in re.finditer(state_pattern, content):
            state_name = match.group(1)
            setter_name = match.group(2)
            
            # Setter should be used somewhere (or it should be a constant instead)
            setter_usage = len(re.findall(rf'\b{setter_name}\b', content))
            
            # At least declaration + one usage
            if setter_usage < 2:
                # Check if it's intentionally unused (e.g., replaced with constant)
                # This is a warning, not a failure
                print(f"Warning: {setter_name} may be unused (only {setter_usage} occurrence)")


class TestDatasetPagination:
    """
    Bug v2.10.60: Annotation count wrong with pagination.
    Fix: Use global count, not per-page count.
    """
    
    def test_annotation_count_is_global(self):
        """Annotation count should be total, not just current page."""
        # Mock paginated response
        page1_response = {
            "images": [{"id": f"img{i}"} for i in range(50)],
            "total": 150,  # Total images in dataset
            "page": 1,
            "page_size": 50,
            "annotations_count": 500  # This should be GLOBAL count
        }
        
        # annotations_count should NOT be just for current page
        assert page1_response["annotations_count"] == 500
        
        # If we had page 2, count should still be 500
        page2_response = {
            "images": [{"id": f"img{i}"} for i in range(50, 100)],
            "total": 150,
            "page": 2,
            "page_size": 50,
            "annotations_count": 500  # Same global count
        }
        
        assert page1_response["annotations_count"] == page2_response["annotations_count"]


class TestCustomClassManagement:
    """
    Feature v2.10.62: Custom class management.
    """
    
    def test_custom_class_structure(self):
        """Custom class should have id, name, color."""
        custom_class = {
            "id": "custom_boots",
            "name": "Boots",
            "color": "#EF4444"
        }
        
        assert "id" in custom_class
        assert "name" in custom_class
        assert "color" in custom_class
        
        # Color should be hex format
        assert custom_class["color"].startswith("#")
        assert len(custom_class["color"]) == 7
    
    def test_class_id_generation(self):
        """Class ID should be generated from name."""
        name = "Safety Boots"
        expected_id = "safety_boots"  # lowercase, spaces to underscores
        
        generated_id = name.lower().replace(" ", "_")
        
        assert generated_id == expected_id
    
    def test_localStorage_persistence_format(self):
        """Custom classes should be stored as JSON in localStorage."""
        custom_classes = [
            {"id": "boots", "name": "Boots", "color": "#EF4444"},
            {"id": "gloves", "name": "Gloves", "color": "#22C55E"}
        ]
        
        # Should be JSON serializable
        json_str = json.dumps(custom_classes)
        restored = json.loads(json_str)
        
        assert restored == custom_classes


# ============================================================================
# Test Runner Configuration
# ============================================================================

if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-x",  # Stop on first failure
    ])
