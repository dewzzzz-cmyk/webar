#!/usr/bin/env python3
"""
PPE Model Downloader - скачивание и настройка модели детекции СИЗ.
"""

import os
import sys
import urllib.request
import json
from pathlib import Path

# Директории
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
MODELS_DIR = PROJECT_DIR / "models"

# Доступные модели
MODELS = {
    "yolov8n": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt",
        "size": "6.2 MB",
        "description": "Базовая YOLOv8n - для тестирования системы",
        "note": "Детектирует person из COCO. PPE-классы нужно дообучить."
    },
    "yolov8s": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s.pt",
        "size": "22 MB",
        "description": "YOLOv8s - более точная базовая модель",
        "note": "Больше параметров, выше точность, медленнее."
    }
}

# Маппинг классов для PPE
PPE_CLASS_MAPPING = {
    "description": "Маппинг классов модели на нарушения СИЗ",
    "note": "Для базовой YOLOv8 (COCO) используем только person. Для полноценной PPE-модели нужно дообучение.",
    
    # Для базовой COCO модели
    "coco_person_class": 0,
    
    # Для PPE-модели (после дообучения)
    "ppe_classes": {
        "Hardhat": {"type": "ppe", "label": "Каска"},
        "NO-Hardhat": {"type": "violation", "label": "Без каски", "alert": "no_hardhat"},
        "Safety Vest": {"type": "ppe", "label": "Жилет"},
        "NO-Safety Vest": {"type": "violation", "label": "Без жилета", "alert": "no_vest"},
        "Mask": {"type": "ppe", "label": "Маска"},
        "NO-Mask": {"type": "violation", "label": "Без маски", "alert": "no_mask"},
        "Safety Glasses": {"type": "ppe", "label": "Очки"},
        "NO-Safety Glasses": {"type": "violation", "label": "Без очков", "alert": "no_glasses"},
        "Gloves": {"type": "ppe", "label": "Перчатки"},
        "NO-Gloves": {"type": "violation", "label": "Без перчаток", "alert": "no_gloves"},
        "Person": {"type": "person", "label": "Человек"}
    },
    
    # Violation types для системы
    "violation_types": ["no_hardhat", "no_vest", "no_mask", "no_glasses", "no_gloves"]
}


def download_with_progress(url: str, dest: Path) -> bool:
    """Скачивание файла с прогресс-баром."""
    try:
        print(f"📥 Скачивание: {url}")
        print(f"📁 Сохранение: {dest}")
        
        def progress_hook(block_num, block_size, total_size):
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, downloaded * 100 // total_size)
                bar_len = 40
                filled = int(bar_len * percent / 100)
                bar = '█' * filled + '░' * (bar_len - filled)
                size_mb = downloaded / (1024 * 1024)
                total_mb = total_size / (1024 * 1024)
                print(f"\r   [{bar}] {percent}% ({size_mb:.1f}/{total_mb:.1f} MB)", end='', flush=True)
        
        urllib.request.urlretrieve(url, dest, progress_hook)
        print("\n✅ Загрузка завершена!")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка загрузки: {e}")
        return False


def verify_model(model_path: Path) -> bool:
    """Проверка модели."""
    if not model_path.exists():
        return False
    
    size_mb = model_path.stat().st_size / (1024 * 1024)
    print(f"📊 Размер файла: {size_mb:.2f} MB")
    
    if size_mb < 1:
        print("⚠️  Файл слишком маленький, возможно повреждён")
        return False
    
    # Пробуем загрузить (если ultralytics установлен)
    try:
        from ultralytics import YOLO
        model = YOLO(str(model_path))
        print(f"✅ Модель валидна")
        print(f"   Классы: {len(model.names)}")
        return True
    except ImportError:
        print("ℹ️  ultralytics не установлен, пропускаем глубокую проверку")
        return True
    except Exception as e:
        print(f"⚠️  Ошибка проверки: {e}")
        return False


def create_config_files():
    """Создание конфигурационных файлов."""
    
    # class_mapping.json
    mapping_path = MODELS_DIR / "class_mapping.json"
    with open(mapping_path, 'w', encoding='utf-8') as f:
        json.dump(PPE_CLASS_MAPPING, f, indent=2, ensure_ascii=False)
    print(f"📝 Создан: {mapping_path}")
    
    # model_config.json
    config = {
        "model_path": "models/ppe_model.pt",
        "confidence_threshold": 0.5,
        "iou_threshold": 0.45,
        "max_detections": 100,
        "input_size": 640,
        "device": "auto",
        "half_precision": False,
        "tracking": {
            "enabled": True,
            "tracker": "bytetrack",
            "persist": True
        }
    }
    config_path = MODELS_DIR / "model_config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    print(f"📝 Создан: {config_path}")


def main():
    print("=" * 60)
    print("🦺 PPE MODEL DOWNLOADER")
    print("=" * 60)
    
    # Создаём директорию
    MODELS_DIR.mkdir(exist_ok=True)
    
    # Показываем доступные модели
    print("\n📦 Доступные модели:\n")
    for key, info in MODELS.items():
        print(f"  [{key}]")
        print(f"    {info['description']}")
        print(f"    Размер: {info['size']}")
        print(f"    ℹ️  {info['note']}")
        print()
    
    # Выбор модели
    model_key = "yolov8n"  # По умолчанию
    if len(sys.argv) > 1:
        if sys.argv[1] in MODELS:
            model_key = sys.argv[1]
        elif sys.argv[1] in ['--help', '-h']:
            print("Использование: python setup_and_download.py [model_key]")
            print(f"Доступные модели: {', '.join(MODELS.keys())}")
            return
    
    model_info = MODELS[model_key]
    model_path = MODELS_DIR / "ppe_model.pt"
    
    print(f"\n🎯 Выбрана модель: {model_key}")
    print(f"   {model_info['description']}")
    
    # Проверяем существующую модель
    if model_path.exists():
        print(f"\n📁 Модель уже существует: {model_path}")
        if verify_model(model_path):
            print("✅ Модель готова к использованию")
        else:
            print("⚠️  Модель повреждена, удаляем...")
            model_path.unlink()
    
    # Скачиваем если нужно
    if not model_path.exists():
        print("\n" + "─" * 60)
        if download_with_progress(model_info['url'], model_path):
            verify_model(model_path)
        else:
            print("❌ Не удалось скачать модель")
            return
    
    # Создаём конфиги
    print("\n" + "─" * 60)
    print("📝 Создание конфигурационных файлов...")
    create_config_files()
    
    # Итог
    print("\n" + "=" * 60)
    print("✅ НАСТРОЙКА ЗАВЕРШЕНА!")
    print("=" * 60)
    print(f"""
📁 Структура models/:
   ├── ppe_model.pt        - Модель детекции
   ├── class_mapping.json  - Маппинг классов
   └── model_config.json   - Конфигурация

⚠️  ВАЖНО: Базовая YOLOv8 детектирует только 'person'.
   Для полноценной PPE-детекции нужно:
   1. Собрать датасет с ваших камер (500+ изображений)
   2. Разметить в CVAT или Roboflow
   3. Дообучить модель (см. docs/MODELS_GUIDE.md)

🚀 Следующий шаг:
   docker-compose --profile cpu up -d
""")


if __name__ == "__main__":
    main()
