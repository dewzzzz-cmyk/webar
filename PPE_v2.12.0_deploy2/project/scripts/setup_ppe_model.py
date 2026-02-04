#!/usr/bin/env python3
"""
🧠 PPE Model Setup Script
Скачивает и настраивает модель для PPE Detection System

Использование:
    python setup_ppe_model.py [--model MODEL_TYPE]

Типы моделей:
    yolov8n     - Базовая YOLOv8 nano (6 MB) - быстрая, для тестирования
    yolov8s     - YOLOv8 small (22 MB) - баланс скорости и точности
    ppe-custom  - Попытка скачать PPE-специфичную модель
"""

import os
import sys
import json
import urllib.request
from pathlib import Path


MODELS_DIR = Path(__file__).parent.parent / "models"

MODELS = {
    "yolov8n": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt",
        "size_mb": 6.2,
        "description": "YOLOv8 Nano - быстрая, для тестирования",
    },
    "yolov8s": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s.pt",
        "size_mb": 22.5,
        "description": "YOLOv8 Small - баланс скорости и точности",
    },
    "yolov8m": {
        "url": "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8m.pt",
        "size_mb": 52.0,
        "description": "YOLOv8 Medium - высокая точность",
    },
}

# PPE-специфичные классы для маппинга
PPE_CLASS_MAPPING = {
    # Стандартный COCO person class
    "coco_person": {
        0: "person"
    },
    # PPE датасет (Roboflow Construction Site Safety)
    "ppe_roboflow": {
        0: "Hardhat",
        1: "Mask", 
        2: "NO-Hardhat",
        3: "NO-Mask",
        4: "NO-Safety Vest",
        5: "Person",
        6: "Safety Cone",
        7: "Safety Vest",
        8: "machinery",
        9: "vehicle"
    },
    # Маппинг для нашей системы
    "ppe_system": {
        "violation_classes": ["NO-Hardhat", "NO-Mask", "NO-Safety Vest", "no_hardhat", "no_vest", "no_mask"],
        "ppe_classes": ["Hardhat", "Mask", "Safety Vest", "hardhat", "vest", "mask"],
        "person_class": ["Person", "person"],
        "ignore_classes": ["Safety Cone", "machinery", "vehicle"]
    }
}


def download_with_progress(url: str, dest: Path) -> bool:
    """Скачать файл с прогрессом."""
    try:
        print(f"📥 Загрузка: {url}")
        
        def progress(block_num, block_size, total_size):
            if total_size > 0:
                percent = min(100, block_num * block_size * 100 / total_size)
                bar_len = 40
                filled = int(bar_len * percent / 100)
                bar = "█" * filled + "░" * (bar_len - filled)
                print(f"\r   [{bar}] {percent:.1f}%", end="", flush=True)
        
        urllib.request.urlretrieve(url, dest, progress)
        print()
        return True
    except Exception as e:
        print(f"\n❌ Ошибка загрузки: {e}")
        return False


def create_model_config(model_name: str, model_path: Path):
    """Создать конфигурацию для модели."""
    config = {
        "model_name": model_name,
        "model_path": str(model_path),
        "class_mapping": PPE_CLASS_MAPPING,
        "confidence_threshold": 0.5,
        "iou_threshold": 0.45,
        "notes": "Базовая COCO модель детектит только 'person'. Для полной PPE детекции нужна специализированная модель."
    }
    
    config_path = MODELS_DIR / "model_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"📝 Конфигурация сохранена: {config_path}")
    return config_path


def verify_model(model_path: Path) -> bool:
    """Проверить модель."""
    try:
        from ultralytics import YOLO
        print("🔍 Проверка модели...")
        model = YOLO(str(model_path))
        
        # Тестовый inference
        import numpy as np
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        results = model(dummy, verbose=False)
        
        print(f"✅ Модель работает!")
        print(f"   Классы: {len(model.names)}")
        print(f"   Примеры: {list(model.names.values())[:5]}")
        return True
    except ImportError:
        print("⚠️  ultralytics не установлен, пропускаем проверку")
        print("   Установите: pip install ultralytics")
        return True
    except Exception as e:
        print(f"❌ Ошибка проверки: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="PPE Model Setup")
    parser.add_argument("--model", "-m", default="yolov8n", 
                       choices=list(MODELS.keys()),
                       help="Тип модели")
    parser.add_argument("--skip-verify", action="store_true",
                       help="Пропустить проверку модели")
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧠 PPE DETECTION - MODEL SETUP")
    print("=" * 60)
    
    # Создаём директорию
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    
    model_config = MODELS[args.model]
    model_path = MODELS_DIR / f"{args.model}.pt"
    ppe_model_link = MODELS_DIR / "ppe_model.pt"
    
    print(f"\n📦 Модель: {args.model}")
    print(f"   {model_config['description']}")
    print(f"   Размер: ~{model_config['size_mb']} MB\n")
    
    # Проверяем, есть ли уже
    if model_path.exists():
        size = model_path.stat().st_size / (1024 * 1024)
        print(f"✅ Модель уже существует: {model_path} ({size:.1f} MB)")
    else:
        # Скачиваем
        if not download_with_progress(model_config["url"], model_path):
            print("\n" + "=" * 60)
            print("📋 АЛЬТЕРНАТИВНЫЕ СПОСОБЫ ПОЛУЧЕНИЯ МОДЕЛИ:")
            print("=" * 60)
            print("""
1. Скачать вручную:
   wget https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
   mv yolov8n.pt models/

2. Через Python:
   from ultralytics import YOLO
   model = YOLO('yolov8n.pt')  # автоматически скачает
   
3. Использовать Roboflow PPE модель:
   - Зайти на https://universe.roboflow.com/search?q=ppe
   - Скачать модель в формате YOLOv8
   - Положить в models/ppe_model.pt

4. Обучить свою модель:
   - См. docs/MODELS_GUIDE.md
""")
            sys.exit(1)
    
    # Создаём симлинк ppe_model.pt -> выбранная модель
    if ppe_model_link.exists() or ppe_model_link.is_symlink():
        ppe_model_link.unlink()
    
    # На Windows симлинк может не работать, копируем
    try:
        ppe_model_link.symlink_to(model_path.name)
        print(f"🔗 Создан симлинк: ppe_model.pt -> {model_path.name}")
    except OSError:
        import shutil
        shutil.copy(model_path, ppe_model_link)
        print(f"📋 Скопировано: {model_path.name} -> ppe_model.pt")
    
    # Создаём конфигурацию
    create_model_config(args.model, ppe_model_link)
    
    # Проверяем
    if not args.skip_verify:
        verify_model(model_path)
    
    print("\n" + "=" * 60)
    print("✅ ГОТОВО!")
    print("=" * 60)
    print(f"""
Модель установлена: models/ppe_model.pt

⚠️  ВАЖНО: Базовая YOLOv8 детектит только класс 'person'.
   Для полной PPE детекции (каски, жилеты) нужна специализированная модель.
   
   Варианты:
   1. Скачать готовую PPE модель с Roboflow
   2. Дообучить базовую модель на PPE датасете
   
   См. docs/MODELS_GUIDE.md для инструкций.

Следующий шаг:
   docker-compose --profile cpu up -d
""")


if __name__ == "__main__":
    main()
