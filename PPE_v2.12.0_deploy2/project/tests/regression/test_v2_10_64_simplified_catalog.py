"""
Tests for v2.10.64: Simplified Model Catalog
============================================

Проверяем что:
1. COCO модели убраны из каталога
2. Остались только PPE модели
3. TRAINING_ARCHITECTURES содержит все нужные архитектуры
4. Settings.tsx корректно группирует модели
5. Training.tsx имеет правильные заголовки
"""

import pytest
import os
import re
import json

# Путь к проекту
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestModelCatalogSimplification:
    """Тесты для упрощённого каталога моделей"""
    
    def test_no_coco_models_in_catalog(self):
        """COCO модели должны быть убраны из MODELS_CATALOG"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем MODELS_CATALOG
        catalog_match = re.search(r'MODELS_CATALOG\s*[:\[=].*?\]', content, re.DOTALL)
        assert catalog_match, "MODELS_CATALOG должен существовать"
        
        catalog_content = catalog_match.group(0)
        
        # Проверяем что нет COCO моделей
        coco_patterns = [
            'yolov8n-coco',
            'yolov8s-coco', 
            'yolov8m-coco',
            'yolov11n',  # Базовые yolov11 - это COCO
            'yolov11s',
            'yolov11m',
            'yolov11l',
            'yolov11x',
            '"type": "coco"',
        ]
        
        for pattern in coco_patterns:
            assert pattern not in catalog_content, f"COCO модель '{pattern}' не должна быть в MODELS_CATALOG"
    
    def test_ppe_models_present(self):
        """PPE модели должны быть в каталоге"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие PPE моделей
        ppe_patterns = [
            'keremberke-hardhat-n',
            'keremberke-hardhat-s',
            'keremberke-hardhat-m',
        ]
        
        for pattern in ppe_patterns:
            assert pattern in content, f"PPE модель '{pattern}' должна быть в MODELS_CATALOG"
    
    def test_training_architectures_exist(self):
        """TRAINING_ARCHITECTURES должен содержать архитектуры для обучения"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие TRAINING_ARCHITECTURES
        assert 'TRAINING_ARCHITECTURES' in content, "TRAINING_ARCHITECTURES должен существовать"
        
        # Проверяем содержит yolov8 и yolov11
        assert '"yolov8"' in content or "'yolov8'" in content, "yolov8 должен быть в TRAINING_ARCHITECTURES"
        assert '"yolov11"' in content or "'yolov11'" in content, "yolov11 должен быть в TRAINING_ARCHITECTURES"
    
    def test_training_architectures_have_sizes(self):
        """Каждая архитектура должна иметь размеры n, s, m, l, x"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем секцию TRAINING_ARCHITECTURES
        arch_match = re.search(r'TRAINING_ARCHITECTURES\s*=\s*\{.*?\n\}', content, re.DOTALL)
        assert arch_match, "TRAINING_ARCHITECTURES должен быть словарём"
        
        arch_content = arch_match.group(0)
        
        # Проверяем наличие размеров
        sizes = ['"n"', '"s"', '"m"', '"l"', '"x"']
        for size in sizes:
            assert size in arch_content, f"Размер {size} должен быть в TRAINING_ARCHITECTURES"


class TestTrainingArchitecturesEndpoint:
    """Тесты для нового endpoint /api/models/training-architectures"""
    
    def test_endpoint_exists(self):
        """Endpoint для архитектур должен существовать"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '/training-architectures' in content or 'training-architectures' in content, \
            "Endpoint /training-architectures должен существовать"
    
    def test_endpoint_returns_architectures(self):
        """Endpoint должен возвращать TRAINING_ARCHITECTURES"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем функцию endpoint
        assert 'get_training_architectures' in content or 'TRAINING_ARCHITECTURES' in content


class TestSettingsUIGrouping:
    """Тесты для группировки моделей в Settings.tsx"""
    
    def test_model_grouping_code_exists(self):
        """Код группировки моделей должен существовать"""
        settings_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Settings.tsx')
        
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие группировки
        assert "source === 'trained'" in content, "Должна быть фильтрация обученных моделей"
        assert "trainedModels" in content, "Должна быть переменная trainedModels"
        assert "ppeModels" in content, "Должна быть переменная ppeModels"
    
    def test_trained_models_section_header(self):
        """Должен быть заголовок для обученных моделей"""
        settings_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Settings.tsx')
        
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "обученн" in content.lower(), "Должен быть заголовок для обученных моделей"
    
    def test_ppe_models_section_header(self):
        """Должен быть заголовок для PPE моделей"""
        settings_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Settings.tsx')
        
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "PPE" in content or "ppe" in content.lower(), "Должен быть заголовок для PPE моделей"
    
    def test_no_coco_warning_text(self):
        """Старое предупреждение про COCO должно быть убрано"""
        settings_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Settings.tsx')
        
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Старый текст про COCO не должен быть в секции каталога
        old_warning = "Стандартные модели YOLO (v8, v11) обучены на COCO датасете"
        assert old_warning not in content, "Старое предупреждение про COCO должно быть убрано"


class TestTrainingUISimplification:
    """Тесты для упрощения UI обучения"""
    
    def test_training_header_updated(self):
        """Заголовок в Training.tsx должен быть обновлён"""
        training_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Training.tsx')
        
        with open(training_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Должен быть новый заголовок
        assert "Архитектура для обучения" in content or "архитектура" in content.lower(), \
            "Должен быть заголовок про архитектуру"
    
    def test_training_info_about_activation(self):
        """Должна быть подсказка про активацию после обучения"""
        training_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Training.tsx')
        
        with open(training_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие информации про активацию
        assert "Настройки" in content or "настройк" in content.lower() or "активир" in content.lower(), \
            "Должна быть информация про активацию в настройках"


class TestModelCatalogCount:
    """Тест на количество моделей в каталоге"""
    
    def test_catalog_has_reasonable_count(self):
        """В каталоге должно быть 3-5 PPE моделей (не 15+)"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Считаем количество "id": в MODELS_CATALOG
        catalog_start = content.find('MODELS_CATALOG')
        catalog_end = content.find('TRAINING_ARCHITECTURES')
        
        if catalog_start != -1 and catalog_end != -1:
            catalog_section = content[catalog_start:catalog_end]
            id_count = catalog_section.count('"id":')
            
            assert id_count <= 6, f"В каталоге должно быть ≤6 моделей, найдено: {id_count}"
            assert id_count >= 2, f"В каталоге должно быть ≥2 моделей, найдено: {id_count}"


class TestActiveModelQuery:
    """Тесты для улучшенного get_active_model"""
    
    def test_active_model_queries_trained_models(self):
        """get_active_model должен искать обученные модели в БД"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем функцию get_active_model
        func_match = re.search(r'async def get_active_model.*?(?=\n@|\nclass|\ndef |\Z)', content, re.DOTALL)
        assert func_match, "Функция get_active_model должна существовать"
        
        func_content = func_match.group(0)
        
        # Проверяем что есть поиск в БД для trained моделей
        assert "trained-" in func_content, "Должна быть проверка на trained- модели"
        assert "model_versions" in func_content, "Должен быть запрос к model_versions"


class TestVersionUpdate:
    """Проверка версии"""
    
    def test_version_is_2_10_64(self):
        """Версия должна быть 2.10.64"""
        version_path = os.path.join(PROJECT_ROOT, 'VERSION')
        
        with open(version_path, 'r') as f:
            version = f.read().strip()
        
        assert version == '2.10.64', f"Версия должна быть 2.10.64, найдена: {version}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
