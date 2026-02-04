#!/usr/bin/env python3
"""
Скрипт для скачивания и настройки PPE-модели.

Источники моделей:
1. Roboflow Universe (рекомендуется)
2. Hugging Face
3. Локальное обучение
"""

import os
import sys
import urllib.request
import shutil
from pathlib import Path

# Путь для моделей
MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Доступные модели
MODELS = {
    "roboflow_construction": {
        "name": "Construction Site Safety (Roboflow)",
        "description": "Hardhat, NO-Hardhat, Safety Vest, NO-Safety Vest, Person",
        "url": "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt",  # Placeholder
        "classes": ["Hardhat", "NO-Hardhat", "Safety Vest", "NO-Safety Vest", "Person"],
        "note": "Требуется ручное скачивание с Roboflow"
    },
    "yolov8n_base": {
        "name": "YOLOv8n Base (COCO)",
        "description": "Базовая модель для тестирования (только Person)",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8n.pt",
        "classes": ["person", "...80 COCO classes"],
        "note": "Для production нужна PPE-модель"
    }
}


def download_file(url: str, destination: Path, description: str = ""):
    """Скачивание файла с прогрессом."""
    print(f"\n📥 Скачивание: {description or url}")
    print(f"   Путь: {destination}")
    
    try:
        def progress_hook(count, block_size, total_size):
            percent = int(count * block_size * 100 / total_size) if total_size > 0 else 0
            bar = '█' * (percent // 2) + '░' * (50 - percent // 2)
            print(f"\r   [{bar}] {percent}%", end='', flush=True)
        
        urllib.request.urlretrieve(url, destination, progress_hook)
        print(f"\n   ✅ Скачано: {destination.stat().st_size / 1024 / 1024:.1f} MB")
        return True
    except Exception as e:
        print(f"\n   ❌ Ошибка: {e}")
        return False


def download_base_model():
    """Скачивание базовой модели YOLOv8n."""
    model_path = MODELS_DIR / "yolov8n.pt"
    
    if model_path.exists():
        print(f"✅ Базовая модель уже существует: {model_path}")
        return model_path
    
    success = download_file(
        MODELS["yolov8n_base"]["url"],
        model_path,
        "YOLOv8n Base Model"
    )
    
    return model_path if success else None


def setup_ppe_model():
    """Настройка PPE-модели."""
    ppe_model_path = MODELS_DIR / "ppe_model.pt"
    
    if ppe_model_path.exists():
        print(f"✅ PPE-модель уже существует: {ppe_model_path}")
        return ppe_model_path
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         🦺 НАСТРОЙКА PPE-МОДЕЛИ                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Для детекции СИЗ нужна специализированная модель.                          ║
║                                                                              ║
║  ВАРИАНТ 1: Скачать с Roboflow (рекомендуется)                              ║
║  ─────────────────────────────────────────────────                           ║
║  1. Откройте: https://universe.roboflow.com/roboflow-universe-projects/     ║
║               construction-site-safety                                       ║
║  2. Нажмите "Download" → Format: "YOLOv8"                                   ║
║  3. Скачайте и распакуйте архив                                              ║
║  4. Скопируйте файл best.pt в папку models/ как ppe_model.pt                ║
║                                                                              ║
║  ВАРИАНТ 2: Обучить свою модель                                              ║
║  ─────────────────────────────────────────────────                           ║
║  1. Соберите 500+ фото с ваших камер                                        ║
║  2. Разметьте в CVAT или Roboflow                                           ║
║  3. Обучите: python scripts/train_model.py                                  ║
║                                                                              ║
║  ВАРИАНТ 3: Использовать базовую модель (только для теста)                  ║
║  ─────────────────────────────────────────────────                           ║
║  Базовая модель находит только людей, НЕ определяет СИЗ                     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    print("\nВыберите действие:")
    print("  1. Скачать базовую модель (для тестирования)")
    print("  2. Я скачаю PPE-модель вручную с Roboflow")
    print("  3. Выход")
    
    choice = input("\nВаш выбор [1-3]: ").strip()
    
    if choice == "1":
        base_model = download_base_model()
        if base_model:
            # Копируем как ppe_model.pt для совместимости
            shutil.copy(base_model, ppe_model_path)
            print(f"\n⚠️  Используется базовая модель: {ppe_model_path}")
            print("   Она находит людей, но НЕ определяет каски и жилеты!")
            print("   Для production скачайте PPE-модель с Roboflow.")
            return ppe_model_path
    elif choice == "2":
        print(f"\n📂 Положите файл модели сюда: {ppe_model_path}")
        print("   После этого перезапустите систему.")
        return None
    else:
        print("\n👋 Выход")
        return None


def verify_model(model_path: Path):
    """Проверка модели."""
    print(f"\n🔍 Проверка модели: {model_path}")
    
    try:
        from ultralytics import YOLO
        model = YOLO(model_path)
        
        print(f"   ✅ Модель загружена успешно")
        print(f"   📊 Классы ({len(model.names)}):")
        
        for idx, name in model.names.items():
            # Подсвечиваем PPE-классы
            if any(ppe in name.lower() for ppe in ['hardhat', 'helmet', 'vest', 'safety']):
                print(f"      {idx}: {name} ✅ PPE")
            elif 'no-' in name.lower() or 'no_' in name.lower():
                print(f"      {idx}: {name} 🔴 Violation")
            elif name.lower() == 'person':
                print(f"      {idx}: {name} 👤")
            else:
                print(f"      {idx}: {name}")
        
        # Тестовый inference
        import numpy as np
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        results = model(dummy, verbose=False)
        print(f"   ✅ Inference работает")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   🦺  PPE DETECTION SYSTEM - Настройка модели                                ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    # Проверяем существующую модель
    ppe_model = MODELS_DIR / "ppe_model.pt"
    
    if ppe_model.exists():
        print(f"📦 Найдена модель: {ppe_model}")
        verify_model(ppe_model)
    else:
        print("⚠️  PPE-модель не найдена")
        setup_ppe_model()
        
        if ppe_model.exists():
            verify_model(ppe_model)
    
    print("\n" + "="*80)
    print("Готово!")
    print("="*80)


if __name__ == "__main__":
    main()
