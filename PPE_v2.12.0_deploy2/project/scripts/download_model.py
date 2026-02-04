#!/usr/bin/env python3
"""
Скрипт для скачивания PPE-модели.

Варианты:
1. Roboflow Universe (рекомендуется)
2. Ultralytics Hub
3. Hugging Face
"""

import os
import sys
import urllib.request
import zipfile
from pathlib import Path

MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Известные PPE модели
PPE_MODELS = {
    "roboflow_construction": {
        "name": "Construction Site Safety (Roboflow)",
        "url": "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt",
        "description": "Базовая YOLOv8n (для теста). Для PPE нужен Roboflow API.",
        "classes": ["person"]
    },
    "yolov8n_base": {
        "name": "YOLOv8n Base",
        "url": "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt",
        "description": "Базовая модель для тестирования pipeline",
        "classes": ["person", "...80 COCO classes"]
    }
}

def download_file(url: str, dest: Path, desc: str = ""):
    """Скачивание файла с прогрессом."""
    print(f"⬇️  Скачивание: {desc or url}")
    
    def progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(100, downloaded * 100 // total_size) if total_size > 0 else 0
        bar = '█' * (percent // 5) + '░' * (20 - percent // 5)
        print(f"\r   [{bar}] {percent}%", end='', flush=True)
    
    urllib.request.urlretrieve(url, dest, progress)
    print(f"\n✅ Сохранено: {dest}")

def download_from_roboflow():
    """Инструкция для скачивания с Roboflow."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    СКАЧИВАНИЕ PPE-МОДЕЛИ С ROBOFLOW                        ║
╠════════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  Roboflow предоставляет лучшие PPE-модели, но требует бесплатную          ║
║  регистрацию для скачивания.                                               ║
║                                                                            ║
║  ШАГИ:                                                                     ║
║                                                                            ║
║  1. Откройте в браузере:                                                   ║
║     https://universe.roboflow.com/roboflow-universe-projects/              ║
║     construction-site-safety                                               ║
║                                                                            ║
║  2. Нажмите "Download Dataset" → Выберите "YOLOv8"                        ║
║                                                                            ║
║  3. Зарегистрируйтесь (бесплатно) или войдите                             ║
║                                                                            ║
║  4. Скачайте модель и положите в папку:                                   ║
║     {models_dir}/ppe_model.pt                                              ║
║                                                                            ║
║  ИЛИ используйте Roboflow Python SDK:                                     ║
║                                                                            ║
║  pip install roboflow                                                      ║
║                                                                            ║
║  from roboflow import Roboflow                                            ║
║  rf = Roboflow(api_key="YOUR_API_KEY")                                    ║
║  project = rf.workspace("roboflow-universe-projects")                     ║
║             .project("construction-site-safety")                          ║
║  model = project.version(30).model                                        ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
""".format(models_dir=MODELS_DIR))

def download_base_model():
    """Скачивание базовой модели для тестирования."""
    dest = MODELS_DIR / "yolov8n.pt"
    
    if dest.exists():
        print(f"✅ Модель уже существует: {dest}")
        return dest
    
    url = "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt"
    download_file(url, dest, "YOLOv8n Base Model")
    return dest

def create_ppe_model_from_pretrained():
    """
    Создание PPE-модели путём fine-tuning.
    Это заглушка - реальное обучение требует датасет.
    """
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    ОБУЧЕНИЕ СОБСТВЕННОЙ PPE-МОДЕЛИ                         ║
╠════════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  Для обучения своей модели:                                               ║
║                                                                            ║
║  1. Соберите датасет (минимум 500 изображений с каждым классом):         ║
║     - Hardhat (каска надета)                                              ║
║     - NO-Hardhat (каска отсутствует)                                      ║
║     - Safety-Vest (жилет надет)                                           ║
║     - NO-Vest (жилет отсутствует)                                        ║
║     - Person                                                               ║
║                                                                            ║
║  2. Разметьте в CVAT, Roboflow или LabelImg                              ║
║                                                                            ║
║  3. Запустите обучение:                                                   ║
║                                                                            ║
║     from ultralytics import YOLO                                          ║
║     model = YOLO('yolov8n.pt')                                            ║
║     model.train(                                                           ║
║         data='dataset.yaml',                                               ║
║         epochs=100,                                                        ║
║         imgsz=640,                                                         ║
║         batch=16                                                           ║
║     )                                                                      ║
║                                                                            ║
║  4. Скопируйте best.pt в models/ppe_model.pt                             ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
""")

def main():
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║   🦺  PPE MODEL DOWNLOADER                                                 ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    print("Выберите действие:\n")
    print("  1. Скачать базовую модель YOLOv8n (для тестирования pipeline)")
    print("  2. Инструкция: скачать PPE-модель с Roboflow (рекомендуется)")
    print("  3. Инструкция: обучить свою модель")
    print("  4. Выход")
    print()
    
    choice = input("Введите номер [1-4]: ").strip()
    
    if choice == "1":
        print()
        model_path = download_base_model()
        
        # Создаём симлинк как ppe_model.pt
        ppe_link = MODELS_DIR / "ppe_model.pt"
        if not ppe_link.exists():
            import shutil
            shutil.copy(model_path, ppe_link)
            print(f"📎 Создана копия: {ppe_link}")
        
        print("""
✅ Базовая модель готова!

⚠️  ВАЖНО: Эта модель НЕ определяет каски и жилеты!
   Она находит только людей (класс 'person').
   
   Для реальной работы нужна PPE-модель с Roboflow.
   Запустите скрипт снова и выберите пункт 2.
""")
    
    elif choice == "2":
        download_from_roboflow()
    
    elif choice == "3":
        create_ppe_model_from_pretrained()
    
    elif choice == "4":
        print("👋 До свидания!")
        sys.exit(0)
    
    else:
        print("❌ Неверный выбор")
        sys.exit(1)

if __name__ == "__main__":
    main()
