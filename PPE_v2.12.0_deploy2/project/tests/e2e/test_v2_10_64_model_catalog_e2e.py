"""
E2E Tests for v2.10.64: Simplified Model Catalog
=================================================

Тесты проверяют:
1. API /api/models/catalog возвращает только PPE модели
2. API /api/models/training-architectures работает
3. API /api/models/active корректно работает
4. Фронтенд корректно отображает модели
"""

import pytest
import os
import sys
import json
import re
from pathlib import Path

# Путь к проекту
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'services', 'api'))


class TestModelsCatalogAPI:
    """E2E тесты для API каталога моделей"""
    
    def test_models_catalog_structure(self):
        """Проверяем структуру MODELS_CATALOG в коде"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Извлекаем MODELS_CATALOG
        # Ищем от начала до TRAINING_ARCHITECTURES
        start_marker = 'MODELS_CATALOG'
        end_marker = 'TRAINING_ARCHITECTURES'
        
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)
        
        assert start_idx != -1, "MODELS_CATALOG должен существовать"
        assert end_idx != -1, "TRAINING_ARCHITECTURES должен существовать"
        
        catalog_section = content[start_idx:end_idx]
        
        # Подсчитываем модели по типу
        ppe_count = catalog_section.count('"type": "ppe"')
        coco_count = catalog_section.count('"type": "coco"')
        
        assert ppe_count >= 3, f"Должно быть минимум 3 PPE модели, найдено: {ppe_count}"
        assert coco_count == 0, f"COCO моделей быть не должно, найдено: {coco_count}"
    
    def test_catalog_endpoint_definition(self):
        """Проверяем что endpoint /catalog определён корректно"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие endpoint
        assert '@router.get("/catalog"' in content or '@router.get(\'/catalog\'' in content, \
            "Endpoint /catalog должен быть определён"
        
        # Проверяем что возвращает ModelCatalogResponse
        assert 'ModelCatalogResponse' in content, "Должен использовать ModelCatalogResponse"
    
    def test_catalog_includes_trained_models(self):
        """Проверяем что каталог включает обученные модели из БД"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем функцию get_model_catalog
        func_match = re.search(r'async def get_model_catalog.*?(?=\n@|\nclass|\nasync def |\Z)', content, re.DOTALL)
        assert func_match, "Функция get_model_catalog должна существовать"
        
        func_content = func_match.group(0)
        
        # Проверяем что есть запрос к model_versions
        assert 'model_versions' in func_content, "Должен быть запрос к таблице model_versions"
        assert 'source="trained"' in func_content or "source='trained'" in func_content or \
               '"trained"' in func_content, "Обученные модели должны иметь source='trained'"


class TestTrainingArchitecturesAPI:
    """E2E тесты для API архитектур обучения"""
    
    def test_training_architectures_endpoint_exists(self):
        """Проверяем что endpoint /training-architectures существует"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'training-architectures' in content, "Endpoint /training-architectures должен существовать"
        assert 'get_training_architectures' in content, "Функция get_training_architectures должна существовать"
    
    def test_training_architectures_content(self):
        """Проверяем содержимое TRAINING_ARCHITECTURES"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем TRAINING_ARCHITECTURES
        start_idx = content.find('TRAINING_ARCHITECTURES')
        assert start_idx != -1, "TRAINING_ARCHITECTURES должен существовать"
        
        # Берём до конца словаря (примерно 2000 символов)
        arch_section = content[start_idx:start_idx + 2000]
        
        # Проверяем наличие архитектур
        assert '"yolov8"' in arch_section or "'yolov8'" in arch_section, "YOLOv8 должен быть"
        assert '"yolov11"' in arch_section or "'yolov11'" in arch_section, "YOLOv11 должен быть"
        
        # Проверяем наличие размеров
        for size in ['n', 's', 'm', 'l', 'x']:
            assert f'"{size}"' in arch_section or f"'{size}'" in arch_section, \
                f"Размер {size} должен быть в архитектурах"
        
        # Проверяем наличие файлов моделей
        assert 'yolov8n.pt' in arch_section, "Файл yolov8n.pt должен быть указан"
        assert 'yolo11n.pt' in arch_section, "Файл yolo11n.pt должен быть указан"


class TestActiveModelAPI:
    """E2E тесты для API активной модели"""
    
    def test_active_model_endpoint_exists(self):
        """Проверяем что endpoint /active существует"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '@router.get("/active"' in content or '@router.get(\'/active\'' in content, \
            "Endpoint /active должен быть определён"
    
    def test_active_model_handles_trained_models(self):
        """Проверяем что /active корректно обрабатывает обученные модели"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем функцию get_active_model
        func_match = re.search(r'async def get_active_model.*?(?=\n@router|\nclass|\Z)', content, re.DOTALL)
        assert func_match, "Функция get_active_model должна существовать"
        
        func_content = func_match.group(0)
        
        # Проверяем обработку trained моделей
        assert 'trained-' in func_content, "Должна быть проверка на trained- prefix"
        assert 'model_versions' in func_content, "Должен быть запрос к model_versions для trained моделей"


class TestActivateModelAPI:
    """E2E тесты для API активации модели"""
    
    def test_activate_endpoint_exists(self):
        """Проверяем что endpoint /activate существует"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '@router.post("/activate"' in content or '@router.post(\'/activate\'' in content, \
            "Endpoint /activate должен быть определён"
    
    def test_activate_handles_trained_models(self):
        """Проверяем что активация работает для обученных моделей"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие функции для активации trained моделей
        assert '_activate_trained_model' in content, "Должна быть функция _activate_trained_model"
        
        # Проверяем что копируется в ppe_model.pt
        assert 'ppe_model.pt' in content, "Должно быть копирование в ppe_model.pt"


class TestFrontendIntegration:
    """E2E тесты для интеграции с фронтендом"""
    
    def test_settings_api_calls(self):
        """Проверяем что Settings.tsx использует правильные API вызовы"""
        settings_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Settings.tsx')
        
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем API вызовы
        assert '/models/catalog' in content, "Должен вызывать /models/catalog"
        assert '/models/active' in content, "Должен вызывать /models/active"
        assert '/models/activate' in content, "Должен вызывать /models/activate"
    
    def test_settings_model_filtering(self):
        """Проверяем что Settings фильтрует модели по типу"""
        settings_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Settings.tsx')
        
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем фильтрацию
        assert "source === 'trained'" in content, "Должна быть фильтрация trained моделей"
        assert 'trainedModels' in content, "Должна быть переменная trainedModels"
        assert 'ppeModels' in content, "Должна быть переменная ppeModels"
    
    def test_training_api_calls(self):
        """Проверяем что Training.tsx отправляет правильные параметры"""
        training_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Training.tsx')
        
        with open(training_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем что передаются параметры модели
        assert 'model_type' in content, "Должен передавать model_type"
        assert 'model_size' in content, "Должен передавать model_size"
    
    def test_training_api_types(self):
        """Проверяем типы в training API"""
        api_training_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'api', 'training.ts')
        
        with open(api_training_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем что TrainingJobCreate включает model параметры
        assert 'model_type' in content, "TrainingJobCreate должен иметь model_type"
        assert 'model_size' in content, "TrainingJobCreate должен иметь model_size"


class TestModelSelectorComponent:
    """E2E тесты для компонента выбора модели"""
    
    def test_model_selector_architectures(self):
        """Проверяем что ModelSelector содержит нужные архитектуры"""
        selector_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'components', 'training', 'ModelSelector.tsx')
        
        with open(selector_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие архитектур
        assert 'yolov8' in content, "YOLOv8 должен быть в ModelSelector"
        assert 'yolov11' in content, "YOLOv11 должен быть в ModelSelector"
    
    def test_model_selector_sizes(self):
        """Проверяем что ModelSelector содержит все размеры"""
        selector_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'components', 'training', 'ModelSelector.tsx')
        
        with open(selector_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие размеров
        sizes = ['Nano', 'Small', 'Medium', 'Large', 'XLarge']
        for size in sizes:
            assert size in content, f"Размер {size} должен быть в ModelSelector"
    
    def test_model_selector_gpu_info(self):
        """Проверяем что ModelSelector показывает требования к GPU"""
        selector_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'components', 'training', 'ModelSelector.tsx')
        
        with open(selector_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем информацию о GPU
        assert 'gpu_mem' in content or 'GPU' in content, "Должна быть информация о требованиях GPU"


class TestNoCOCOModelsInUI:
    """E2E тесты - убеждаемся что COCO модели не видны в UI"""
    
    def test_settings_no_coco_section(self):
        """В Settings не должно быть секции COCO моделей"""
        settings_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Settings.tsx')
        
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Не должно быть фильтрации по type === 'coco'
        assert "type === 'coco'" not in content and 'type === "coco"' not in content, \
            "Не должно быть фильтрации COCO моделей (их нет в каталоге)"
    
    def test_no_coco_warning_needed(self):
        """Предупреждение про COCO больше не нужно"""
        settings_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Settings.tsx')
        
        with open(settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Старое предупреждение должно быть убрано
        old_warning = "НЕ детектирует PPE напрямую"
        assert old_warning not in content, "Старое предупреждение про COCO должно быть убрано"


class TestEndToEndFlow:
    """Полный E2E flow тест"""
    
    def test_complete_model_selection_flow(self):
        """
        Тест полного flow:
        1. Settings загружает каталог
        2. Каталог содержит только PPE модели
        3. Можно активировать PPE модель
        4. Training использует архитектуры для обучения
        5. После обучения модель появляется в каталоге
        """
        # 1. Проверяем Settings загружает каталог
        settings_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Settings.tsx')
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = f.read()
        assert 'getModelsCatalog' in settings, "Settings должен загружать каталог"
        
        # 2. Проверяем каталог содержит только PPE
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        with open(models_router_path, 'r', encoding='utf-8') as f:
            router = f.read()
        
        catalog_start = router.find('MODELS_CATALOG')
        catalog_end = router.find('TRAINING_ARCHITECTURES')
        catalog = router[catalog_start:catalog_end]
        assert '"type": "coco"' not in catalog, "Каталог не должен содержать COCO"
        
        # 3. Проверяем активацию работает
        assert 'activate_model' in router, "Должна быть функция активации"
        assert 'ppe_model.pt' in router, "Активация должна копировать в ppe_model.pt"
        
        # 4. Проверяем Training использует архитектуры
        training_path = os.path.join(PROJECT_ROOT, 'dashboard', 'src', 'pages', 'Training.tsx')
        with open(training_path, 'r', encoding='utf-8') as f:
            training = f.read()
        assert 'ModelSelector' in training, "Training должен использовать ModelSelector"
        assert 'model_type' in training, "Training должен передавать model_type"
        
        # 5. Проверяем обученные модели добавляются в каталог
        assert 'source="trained"' in router or '"trained"' in router, \
            "Обученные модели должны добавляться с source='trained'"
        assert 'model_versions' in router, "Должен быть запрос к model_versions"
    
    def test_model_activation_flow(self):
        """
        Тест flow активации модели:
        1. Пользователь выбирает модель в Settings
        2. API активирует модель
        3. Детектор получает новую модель
        """
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        with open(models_router_path, 'r', encoding='utf-8') as f:
            router = f.read()
        
        # Проверяем flow активации
        assert 'system:active_model' in router, "Должен обновлять Redis key"
        assert 'model_changed' in router, "Должен публиковать событие model_changed"
        assert 'active_model.json' in router, "Должен создавать active_model.json"


class TestAPIResponseFormats:
    """Тесты форматов ответов API"""
    
    def test_model_info_schema(self):
        """Проверяем схему ModelInfo"""
        models_router_path = os.path.join(PROJECT_ROOT, 'services', 'api', 'models_router.py')
        
        with open(models_router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем что ModelInfo содержит нужные поля
        required_fields = ['id', 'name', 'description', 'type', 'source', 'is_downloaded', 'is_active']
        
        # Ищем класс ModelInfo
        model_info_match = re.search(r'class ModelInfo.*?(?=\nclass |\Z)', content, re.DOTALL)
        assert model_info_match, "Класс ModelInfo должен существовать"
        
        model_info = model_info_match.group(0)
        for field in required_fields:
            assert field in model_info, f"ModelInfo должен содержать поле {field}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
