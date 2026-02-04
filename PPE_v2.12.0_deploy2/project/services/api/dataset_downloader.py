"""
Dataset Downloader
==================

Автоматическая загрузка и настройка готовых PPE датасетов.
Аналогично загрузке моделей - выбрал, нажал, использовал.
"""

import os
import asyncio
import aiohttp
import zipfile
import shutil
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# Dataset Catalog - Готовые датасеты для загрузки
# =============================================================================

@dataclass
class DatasetInfo:
    """Информация о датасете в каталоге"""
    id: str
    name: str
    description: str
    source: str  # roboflow, kaggle, custom
    url: str
    size_mb: float
    images_count: int
    classes: List[str]
    format: str  # yolo, coco, voc
    license: str
    recommended_for: str
    is_downloaded: bool = False
    local_path: Optional[str] = None


# Каталог готовых датасетов - ОБНОВЛЕНО v2.10.53
# Удалены: COCO128 Demo (не PPE), PPE Detection v2 (битая ссылка)
DATASET_CATALOG: List[DatasetInfo] = [
    # =========================================================================
    # ROBOFLOW - PPE датасеты (требуют API ключ)
    # Формат URL: workspace/project с опциональной версией
    # =========================================================================
    DatasetInfo(
        id="helmetvest-v7",
        name="Helmet & Vest Detection",
        description="Каски и жилеты - 3202 изображений с качественной разметкой. Требует Roboflow API ключ.",
        source="roboflow",
        # Формат: workspace/project/dataset/version
        url="https://universe.roboflow.com/data-u4eek/helmetvest/dataset/7",
        size_mb=150,
        images_count=3202,
        classes=["Helmet", "NoHelmet", "NoVest", "Vest"],
        format="yolov8",
        license="CC BY 4.0",
        recommended_for="Базовая детекция касок и жилетов",
    ),
    DatasetInfo(
        id="construction-site-safety",
        name="⭐ Construction PPE (8845 изобр.)",
        description="Каски, жилеты, маски - полный набор СИЗ для строек. Требует Roboflow API ключ.",
        source="roboflow",
        # Проект от roboflow-universe-projects
        url="https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety/dataset/30",
        size_mb=500,
        images_count=8845,
        classes=["Hardhat", "Mask", "NO-Hardhat", "NO-Mask", "NO-Safety Vest", "Person", "Safety Cone", "Safety Vest", "machinery", "vehicle"],
        format="yolov8",
        license="CC BY 4.0",
        recommended_for="Строительные площадки, производство",
    ),
    DatasetInfo(
        id="ppe-siabar",
        name="PPE Workplace Safety",
        description="Датасет для безопасности рабочих мест. Требует Roboflow API ключ.",
        source="roboflow",
        url="https://universe.roboflow.com/siabar/ppe-dataset-for-workplace-safety/dataset/2",
        size_mb=200,
        images_count=3000,
        classes=["Boots", "Helmet", "Person", "Vest"],
        format="yolov8",
        license="CC BY 4.0",
        recommended_for="Производство, склады",
    ),
    
    # =========================================================================
    # KAGGLE - Требуют Kaggle API (username + key)
    # =========================================================================
    DatasetInfo(
        id="safety-helmet-jacket-kaggle",
        name="Safety Helmet & Jacket (Kaggle)",
        description="Каски и жилеты для строительства. Требует Kaggle API (username + key).",
        source="kaggle",
        url="https://www.kaggle.com/datasets/niravnaik/safety-helmet-and-reflective-jacket",
        size_mb=250,
        images_count=5000,
        classes=["helmet", "no_helmet", "jacket", "no_jacket", "person"],
        format="yolov8",
        license="CC0",
        recommended_for="Строительство, дорожные работы",
    ),
    DatasetInfo(
        id="hardhat-workers-kaggle",
        name="Hard Hat Workers (Kaggle)",
        description="Фокус на касках - 7000+ изображений рабочих. Требует Kaggle API.",
        source="kaggle",
        url="https://www.kaggle.com/datasets/andrewmvd/hard-hat-detection",
        size_mb=280,
        images_count=7035,
        classes=["helmet", "head", "person"],
        format="voc",
        license="CC0",
        recommended_for="Простая детекция касок",
    ),
]


class DownloadStatus(Enum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    CONVERTING = "converting"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class DownloadProgress:
    dataset_id: str
    status: DownloadStatus
    progress: float  # 0-100
    message: str
    error: Optional[str] = None


class DatasetDownloader:
    """Загрузчик датасетов с прогрессом"""
    
    def __init__(self, base_path: str = "/app/datasets"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._progress: Dict[str, DownloadProgress] = {}
    
    def get_catalog(self) -> List[Dict[str, Any]]:
        """Получить каталог датасетов с актуальным статусом"""
        result = []
        for ds in DATASET_CATALOG:
            info = asdict(ds)
            # Проверяем, скачан ли датасет РЕАЛЬНО (есть изображения, не только data.yaml)
            local_path = self.base_path / ds.id
            is_downloaded = False
            images_count = 0
            
            if local_path.exists():
                # Проверяем наличие train/images или valid/images с реальными файлами
                train_images = local_path / 'train' / 'images'
                valid_images = local_path / 'valid' / 'images'
                
                if train_images.exists():
                    images_count += len([f for f in train_images.iterdir() if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp')])
                if valid_images.exists():
                    images_count += len([f for f in valid_images.iterdir() if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp')])
                
                # Считаем загруженным только если есть хотя бы 10 изображений
                is_downloaded = images_count >= 10
                
                # Также проверяем наличие README_DOWNLOAD.md - значит только инструкции
                has_instructions_only = (local_path / 'README_DOWNLOAD.md').exists() and not is_downloaded
                
                if has_instructions_only:
                    info['status'] = 'instructions_only'
                    info['message'] = 'Требуется ручная загрузка'
            
            info['is_downloaded'] = is_downloaded
            info['images_found'] = images_count
            if is_downloaded:
                info['local_path'] = str(local_path)
            result.append(info)
        return result
    
    def get_progress(self, dataset_id: str) -> Optional[DownloadProgress]:
        """Получить прогресс загрузки"""
        return self._progress.get(dataset_id)
    
    def _get_api_key(self, key_type: str, provided_key: Optional[str] = None) -> Optional[str]:
        """Получить API ключ из разных источников"""
        # 1. Явно переданный ключ имеет приоритет
        if provided_key:
            return provided_key
        
        # 2. Из JSON файла конфигурации (новый формат)
        json_file = Path(os.getenv('CONFIG_PATH', '/app/configs')) / 'api_keys.json'
        try:
            if json_file.exists():
                import json
                with open(json_file, 'r') as f:
                    keys = json.load(f)
                if keys.get(key_type):
                    logger.info(f"Using {key_type} API key from config file")
                    return keys[key_type]
        except Exception as e:
            logger.warning(f"Failed to read API key from JSON: {e}")
        
        # 3. Из старого текстового файла (для совместимости)
        if key_type == "roboflow":
            key_file = Path(os.getenv('CONFIG_PATH', '/app/configs')) / 'roboflow_api_key.txt'
            try:
                if key_file.exists():
                    api_key = key_file.read_text().strip()
                    if api_key:
                        logger.info(f"Using {key_type} API key from legacy config file")
                        return api_key
            except Exception as e:
                logger.warning(f"Failed to read API key from legacy file: {e}")
        
        # 4. Из переменных окружения
        env_map = {
            "roboflow": "ROBOFLOW_API_KEY",
            "kaggle_username": "KAGGLE_USERNAME",
            "kaggle_key": "KAGGLE_KEY",
            "huggingface": "HUGGINGFACE_TOKEN"
        }
        env_var = env_map.get(key_type)
        if env_var:
            env_key = os.getenv(env_var)
            if env_key:
                logger.info(f"Using {key_type} API key from environment")
                return env_key
        
        return None
    
    def _get_roboflow_api_key(self, provided_key: Optional[str] = None) -> Optional[str]:
        """Получить API ключ Roboflow (для совместимости)"""
        return self._get_api_key("roboflow", provided_key)
    
    def _get_kaggle_credentials(self) -> tuple[Optional[str], Optional[str]]:
        """Получить Kaggle credentials"""
        username = self._get_api_key("kaggle_username")
        key = self._get_api_key("kaggle_key")
        return username, key
    
    async def download_dataset(self, dataset_id: str, roboflow_api_key: Optional[str] = None) -> bool:
        """
        Скачать и настроить датасет
        
        Args:
            dataset_id: ID датасета из каталога
            roboflow_api_key: API ключ Roboflow (если нужен)
        """
        # Найти датасет в каталоге
        dataset = next((d for d in DATASET_CATALOG if d.id == dataset_id), None)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found in catalog")
        
        # Получаем API ключ из всех источников
        effective_api_key = self._get_roboflow_api_key(roboflow_api_key)
        
        dest_path = self.base_path / dataset_id
        
        try:
            # Инициализируем прогресс
            self._progress[dataset_id] = DownloadProgress(
                dataset_id=dataset_id,
                status=DownloadStatus.DOWNLOADING,
                progress=0,
                message="Начало загрузки..."
            )
            
            # Загрузка в зависимости от источника
            if dataset.source == "roboflow":
                await self._download_roboflow(dataset, dest_path, effective_api_key)
            elif dataset.source == "kaggle":
                await self._download_kaggle(dataset, dest_path)
            else:
                await self._download_direct(dataset, dest_path)
            
            # Конвертация если нужно
            self._progress[dataset_id].status = DownloadStatus.CONVERTING
            self._progress[dataset_id].message = "Конвертация в формат системы..."
            self._progress[dataset_id].progress = 80
            
            await self._convert_to_system_format(dest_path, dataset)
            
            # Готово
            self._progress[dataset_id] = DownloadProgress(
                dataset_id=dataset_id,
                status=DownloadStatus.COMPLETED,
                progress=100,
                message="Датасет готов к использованию!"
            )
            
            logger.info(f"Dataset {dataset_id} downloaded successfully to {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download dataset {dataset_id}: {e}")
            self._progress[dataset_id] = DownloadProgress(
                dataset_id=dataset_id,
                status=DownloadStatus.ERROR,
                progress=0,
                message="Ошибка загрузки",
                error=str(e)
            )
            return False
    
    async def _download_roboflow(
        self, 
        dataset: DatasetInfo, 
        dest_path: Path,
        api_key: Optional[str]
    ):
        """Загрузка с Roboflow"""
        self._progress[dataset.id].message = "Загрузка с Roboflow..."
        
        if api_key:
            # Используем Roboflow API
            try:
                from roboflow import Roboflow
                rf = Roboflow(api_key=api_key)
                
                # Парсим URL для получения workspace/project/version
                # Поддерживаемые форматы URL:
                # 1. https://universe.roboflow.com/workspace/project/dataset/version
                # 2. https://universe.roboflow.com/workspace/project
                # 3. https://universe.roboflow.com/workspace/project/version (без dataset)
                
                url = dataset.url.rstrip('/')
                parts = url.split('/')
                
                # Находим индекс universe.roboflow.com
                try:
                    base_idx = parts.index('universe.roboflow.com')
                except ValueError:
                    # Fallback для других URL
                    base_idx = 2
                
                workspace = None
                project = None
                version = None
                
                # Парсим после base_idx
                remaining = parts[base_idx + 1:]
                logger.info(f"Parsing Roboflow URL parts: {remaining}")
                
                if 'dataset' in remaining:
                    # Формат: workspace/project/dataset/version
                    dataset_idx = remaining.index('dataset')
                    workspace = remaining[dataset_idx - 2] if dataset_idx >= 2 else remaining[0]
                    project = remaining[dataset_idx - 1] if dataset_idx >= 1 else remaining[1] if len(remaining) > 1 else None
                    version = int(remaining[dataset_idx + 1]) if dataset_idx + 1 < len(remaining) else 1
                elif len(remaining) >= 3:
                    # Формат: workspace/project/version
                    workspace = remaining[0]
                    project = remaining[1]
                    try:
                        version = int(remaining[2])
                    except ValueError:
                        version = 1
                elif len(remaining) >= 2:
                    # Формат: workspace/project (берём последнюю версию)
                    workspace = remaining[0]
                    project = remaining[1]
                    version = 1
                else:
                    raise ValueError(f"Cannot parse Roboflow URL: {url}")
                
                logger.info(f"Roboflow download: workspace={workspace}, project={project}, version={version}")
                
                # Подключаемся к проекту
                proj = rf.workspace(workspace).project(project)
                ver = proj.version(version)
                
                # Скачиваем в формате yolov8
                self._progress[dataset.id].message = f"Скачивание датасета из Roboflow ({dataset.size_mb} MB)..."
                self._progress[dataset.id].progress = 20
                
                ver.download("yolov8", location=str(dest_path))
                
                self._progress[dataset.id].progress = 70
                logger.info(f"Roboflow dataset downloaded to {dest_path}")
                
                # Log what was actually created
                if dest_path.exists():
                    contents = list(dest_path.iterdir())
                    logger.info(f"Downloaded contents: {[str(c.name) for c in contents]}")
                    # Check for nested folder created by Roboflow
                    for item in contents:
                        if item.is_dir():
                            subcontents = list(item.iterdir())
                            logger.info(f"  Subfolder {item.name}: {[str(s.name) for s in subcontents]}")
                
            except ImportError as e:
                logger.error(f"Roboflow library not installed: {e}")
                self._progress[dataset.id].message = "Библиотека Roboflow не установлена"
                await self._create_manual_instructions(dataset, dest_path)
            except Exception as e:
                logger.error(f"Roboflow API error: {type(e).__name__}: {e}")
                self._progress[dataset.id].message = f"Ошибка Roboflow: {str(e)[:100]}"
                # Попробуем создать инструкции вместо полной ошибки
                await self._create_manual_instructions(dataset, dest_path)
        else:
            logger.warning("No Roboflow API key provided, creating manual instructions")
            self._progress[dataset.id].message = "API ключ не указан"
            # Создаём инструкции для ручной загрузки
            await self._create_manual_instructions(dataset, dest_path)
    
    async def _download_kaggle(self, dataset: DatasetInfo, dest_path: Path):
        """Загрузка с Kaggle"""
        self._progress[dataset.id].message = "Подготовка загрузки с Kaggle..."
        
        try:
            import kaggle
            
            # Парсим dataset path из URL
            # URL формат: https://www.kaggle.com/datasets/username/dataset-name
            parts = dataset.url.split('/')
            dataset_path = f"{parts[-2]}/{parts[-1]}"
            
            dest_path.mkdir(parents=True, exist_ok=True)
            kaggle.api.dataset_download_files(dataset_path, path=str(dest_path), unzip=True)
            
            self._progress[dataset.id].progress = 70
            
        except Exception as e:
            logger.warning(f"Kaggle download failed: {e}, creating manual instructions")
            await self._create_manual_instructions(dataset, dest_path)
    
    async def _download_direct(self, dataset: DatasetInfo, dest_path: Path):
        """Прямая загрузка по URL"""
        self._progress[dataset.id].message = f"Загрузка {dataset.size_mb} MB..."
        
        dest_path.mkdir(parents=True, exist_ok=True)
        zip_path = dest_path / "dataset.zip"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(dataset.url) as response:
                if response.status != 200:
                    raise Exception(f"Download failed: HTTP {response.status}")
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(zip_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 60  # 0-60%
                            self._progress[dataset.id].progress = progress
        
        # Распаковка
        self._progress[dataset.id].status = DownloadStatus.EXTRACTING
        self._progress[dataset.id].message = "Распаковка архива..."
        self._progress[dataset.id].progress = 65
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(dest_path)
        
        zip_path.unlink()  # Удаляем архив
        self._progress[dataset.id].progress = 75
    
    async def _create_manual_instructions(self, dataset: DatasetInfo, dest_path: Path):
        """Создать инструкции для ручной загрузки"""
        dest_path.mkdir(parents=True, exist_ok=True)
        
        instructions = f"""# Инструкция по загрузке датасета

## {dataset.name}

{dataset.description}

### Шаг 1: Скачайте датасет

1. Перейдите по ссылке: {dataset.url}
2. Нажмите "Download" → выберите формат "YOLOv8"
3. Скачайте архив на компьютер

### Шаг 2: Распакуйте в эту папку

Путь: `{dest_path}`

Структура должна быть:
```
{dataset.id}/
├── data.yaml
├── train/
│   ├── images/
│   └── labels/
└── valid/
    ├── images/
    └── labels/
```

### Шаг 3: Перезагрузите страницу

После копирования файлов обновите страницу в Dashboard.

---

**Классы в датасете:** {', '.join(dataset.classes)}
**Размер:** {dataset.size_mb} MB
**Изображений:** {dataset.images_count}
**Лицензия:** {dataset.license}
"""
        
        (dest_path / "README_DOWNLOAD.md").write_text(instructions, encoding='utf-8')
        
        self._progress[dataset.id].progress = 70
        self._progress[dataset.id].message = "Созданы инструкции для ручной загрузки"
    
    async def _convert_to_system_format(self, path: Path, dataset: DatasetInfo):
        """Конвертация в формат системы"""
        
        # Ищем изображения в разных возможных структурах
        possible_image_dirs = [
            path / 'train' / 'images',
            path / 'valid' / 'images',
            path / 'images' / 'train',
            path / 'images' / 'val',
            path / 'images',
        ]
        
        # Roboflow создаёт подпапку с именем проекта - ищем на 2 уровня вглубь
        def find_subdirs(base: Path, depth: int = 2):
            """Рекурсивный поиск подпапок"""
            result = []
            if not base.exists() or not base.is_dir():
                return result
            try:
                for item in base.iterdir():
                    if item.is_dir():
                        result.append(item)
                        if depth > 0:
                            result.extend(find_subdirs(item, depth - 1))
            except PermissionError:
                pass
            return result
        
        # Добавляем все подпапки
        for subdir in find_subdirs(path, 2):
            possible_image_dirs.extend([
                subdir / 'train' / 'images',
                subdir / 'valid' / 'images', 
                subdir / 'images' / 'train',
                subdir / 'images' / 'val',
                subdir / 'images',
                subdir,  # Иногда изображения лежат прямо в папке
            ])
        
        # Находим папку с изображениями
        images_found = []
        source_images_dir = None
        source_labels_dir = None
        
        for img_dir in possible_image_dirs:
            if img_dir.exists():
                files = [f for f in img_dir.iterdir() if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp')]
                if len(files) > len(images_found):
                    images_found = files
                    source_images_dir = img_dir
                    # Ищем соответствующую папку labels
                    possible_labels = [
                        img_dir.parent / 'labels',
                        img_dir.parent.parent / 'labels' / img_dir.name,
                        img_dir.parent.parent / 'labels',
                    ]
                    for lbl_dir in possible_labels:
                        if lbl_dir.exists():
                            source_labels_dir = lbl_dir
                            break
        
        if not images_found:
            logger.warning(f"No images found in {path}")
            return
        
        logger.info(f"Found {len(images_found)} images in {source_images_dir}")
        
        # Создаём стандартную структуру train/valid
        train_images = path / 'train' / 'images'
        train_labels = path / 'train' / 'labels'
        valid_images = path / 'valid' / 'images'
        valid_labels = path / 'valid' / 'labels'
        
        train_images.mkdir(parents=True, exist_ok=True)
        train_labels.mkdir(parents=True, exist_ok=True)
        valid_images.mkdir(parents=True, exist_ok=True)
        valid_labels.mkdir(parents=True, exist_ok=True)
        
        # Если изображения не в train/images, копируем/перемещаем
        if source_images_dir != train_images and source_images_dir != valid_images:
            # Разделяем 80/20 на train/valid
            import random
            random.shuffle(images_found)
            split_idx = int(len(images_found) * 0.8)
            train_imgs = images_found[:split_idx]
            valid_imgs = images_found[split_idx:]
            
            for img in train_imgs:
                dest = train_images / img.name
                if not dest.exists():
                    shutil.copy2(img, dest)
                # Копируем label если есть
                if source_labels_dir:
                    label_file = source_labels_dir / (img.stem + '.txt')
                    if label_file.exists():
                        shutil.copy2(label_file, train_labels / label_file.name)
            
            for img in valid_imgs:
                dest = valid_images / img.name
                if not dest.exists():
                    shutil.copy2(img, dest)
                if source_labels_dir:
                    label_file = source_labels_dir / (img.stem + '.txt')
                    if label_file.exists():
                        shutil.copy2(label_file, valid_labels / label_file.name)
            
            logger.info(f"Organized {len(train_imgs)} train + {len(valid_imgs)} valid images")
        
        # Создаём data.yaml
        data_yaml = path / "data.yaml"
        
        # Проверяем есть ли существующий data.yaml
        existing_config = {}
        if data_yaml.exists():
            try:
                with open(data_yaml) as f:
                    existing_config = yaml.safe_load(f) or {}
            except Exception:
                pass
        
        # Также ищем в подпапках
        for subdir in path.iterdir():
            if subdir.is_dir():
                candidate = subdir / "data.yaml"
                if candidate.exists():
                    try:
                        with open(candidate) as f:
                            existing_config = yaml.safe_load(f) or {}
                        # Перемещаем содержимое на уровень выше если нужно
                        break
                    except Exception:
                        pass
        
        # Обновляем конфигурацию
        config = existing_config.copy()
        config['path'] = str(path)
        config['train'] = 'train/images'
        config['val'] = 'valid/images'
        
        # Классы
        if 'names' not in config:
            config['names'] = {i: c for i, c in enumerate(dataset.classes)}
        config['nc'] = len(config.get('names', dataset.classes))
        
        with open(data_yaml, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        # Создаём метаданные для системы
        total_images = len(list(train_images.iterdir())) + len(list(valid_images.iterdir()))
        metadata = {
            "id": dataset.id,
            "name": dataset.name,
            "source": dataset.source,
            "classes": dataset.classes,
            "images_count": total_images,
            "format": "yolov8",
            "ready_for_training": True
        }
        
        with open(path / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Dataset {dataset.id} converted successfully with {total_images} images")
    
    def delete_dataset(self, dataset_id: str) -> bool:
        """Удалить скачанный датасет"""
        path = self.base_path / dataset_id
        if path.exists():
            shutil.rmtree(path)
            logger.info(f"Dataset {dataset_id} deleted")
            return True
        return False


# Глобальный экземпляр
dataset_downloader = DatasetDownloader()
