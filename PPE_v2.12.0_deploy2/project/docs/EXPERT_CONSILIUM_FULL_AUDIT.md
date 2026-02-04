# 🏛️ КОНСИЛИУМ ЭКСПЕРТОВ: PPE Detection System

## КРИТИЧЕСКИЙ АУДИТ КОДОВОЙ БАЗЫ

**Дата проведения:** 28 января 2026 г.
**Председатель:** Главный Архитектор  
**Версии проанализированы:** v2.10.7 → v2.10.27

---

## 📊 АНАЛИЗ ИСТОРИИ ПРОБЛЕМ

### Хронология исправлений (из journal.txt):

| Дата | Версия | Проблемы | Исправления |
|------|--------|----------|-------------|
| 26.01 | v2.10.7 | Review сессия | Обзор архитектуры |
| 26.01 | v2.10.8 | Видео зависает, скриншоты, GPU | 4 критических фикса |
| 26.01 | v2.10.9 | TypeScript ошибки | Build fixes |
| 26.01 | v2.10.10 | Мерцание камер, OOM, датасеты | 5 критических багов |
| 27.01 | v2.10.11 | Удаление мёртвого кода | -3500 строк |
| 27.01 | v2.10.12 | Memory leak, FPS, Roboflow | 3 бага |
| 27.01 | v2.10.13 | DB миграции, GPU | 4 бага |
| 27.01 | v2.10.14 | Training service, GPU | Critical fix |
| 27.01 | v2.10.15 | start.bat, API key UI | 2 бага |
| 27.01 | v2.10.16 | YOLO модели, split | New feature |
| 27.01 | v2.10.17 | Token refresh, Roboflow URL | 2 бага |
| 27.01 | v2.10.18 | Roboflow API key | UI fix |
| 27.01 | v2.10.19 | Camera offline, dataset validation | 2 бага |
| 27.01 | v2.10.21 | YAML parsing, dependencies | 2 бага |
| 27.01 | v2.10.22 | Multi-role audit | 8 issues |
| 27.01 | v2.10.24 | Datasets visibility | API fix |
| 27.01 | v2.10.26 | Pydantic validation | 8 errors |
| 27.01 | v2.10.27 | Consilium fix | Screenshots |

**ВЫВОД:** 20+ версий за 2 дня = системные проблемы архитектуры

---

## 👥 СОСТАВ ЭКСПЕРТНОГО КОНСИЛИУМА

### Внутренние эксперты (из проекта):

| # | Роль | Специализация |
|---|------|---------------|
| 1 | 🔧 Build Error Resolver | TypeScript, Pydantic |
| 2 | 👀 Code Reviewer | Качество кода |
| 3 | 📋 Planner | Архитектура решений |
| 4 | 🧹 Refactor Cleaner | Мёртвый код, дубли |
| 5 | 📚 Doc Updater | Документация |

### Приглашённые сторонние эксперты:

| # | Роль | Специализация |
|---|------|---------------|
| 6 | 🔒 Security Expert | Уязвимости, аутентификация |
| 7 | 🗄️ Database Architect | PostgreSQL, Redis |
| 8 | 🐳 DevOps Engineer | Docker, инфраструктура |
| 9 | ⚛️ Frontend Specialist | React, TypeScript |
| 10 | 🧪 QA Engineer | Тестирование |
| 11 | 🏗️ Software Architect | Системный дизайн |

---

## 🔴 ВЕРДИКТ КОНСИЛИУМА: КОРНЕВАЯ ПРИЧИНА

### ГЛАВНАЯ АРХИТЕКТУРНАЯ ПРОБЛЕМА

**Эксперт:** 🏗️ Software Architect

> **"Функция normalize_dataset() создана, но НЕ ИСПОЛЬЗУЕТСЯ КОНСИСТЕНТНО. Код дублирует логику нормализации в 6+ местах вместо использования единой функции."**

#### Доказательство (grep анализ):

```bash
$ grep -n "normalize_dataset" training_router.py

161: def normalize_dataset(raw_data: dict, source_type: str = "unknown") -> dict:
544:                             normalized = normalize_dataset(metadata, source_type="custom")
561:                     screenshots_data = normalize_dataset({
```

**Функция используется только в 2 местах из 6 необходимых!**

#### Где функция НЕ используется (но должна):

| # | Место | Строки | Проблема |
|---|-------|--------|----------|
| 1 | PostgreSQL в `list_datasets()` | 407-431 | Дублирующий код |
| 2 | metadata.json в `list_datasets()` | 470-486 | Дублирующий код |
| 3 | data.yaml в `list_datasets()` | 508-524 | Дублирующий код |
| 4 | PostgreSQL в `create_dataset()` | 618-631 | Дублирующий код |
| 5 | PostgreSQL в `get_dataset()` | 697-710 | Дублирующий код |
| 6 | metadata.json в `get_dataset()` | 734-747 | Дублирующий код |

#### Последствия:

1. При исправлении одного места, другие остаются сломанными
2. Несогласованность типов между endpoint'ами
3. Pydantic валидация падает случайным образом
4. Невозможно отследить все места для исправления

---

## 📋 ПОЛНЫЙ РЕЕСТР ПРОБЛЕМ

### 🔴 КРИТИЧЕСКИЕ (БЛОКИРУЮТ РАБОТУ)

#### ПРОБЛЕМА #1: Дублирование кода нормализации
**Эксперты:** 🏗️ Architect + 🧹 Cleaner

**Текущее состояние:**
```python
# training_router.py - ДУБЛИРОВАНИЕ В 6+ МЕСТАХ

# Место 1: PostgreSQL в list_datasets (строки 407-431)
normalized = {
    "id": dataset_id,
    "name": row_dict.get('name', dataset_id),
    # ... 12 полей вручную
}

# Место 2: metadata.json в list_datasets (строки 470-486)  
dataset_entry = {
    "id": str(metadata.get("id", dataset_dir.name)),
    "name": metadata.get("name", dataset_dir.name),
    # ... 12 полей вручную
}

# Место 3: data.yaml в list_datasets (строки 508-524)
dataset_entry = {
    "id": str(dataset_dir.name),
    "name": dataset_dir.name.replace('-', ' ').title(),
    # ... 12 полей вручную
}

# И так далее в create_dataset, get_dataset...
```

**Требуемое решение:**
```python
# ВЕЗДЕ должно быть:
normalized = normalize_dataset(raw_data, source_type="postgres")
```

---

#### ПРОБЛЕМА #2: Несогласованность версий
**Эксперт:** 👀 Code Reviewer

**Файл:** `main.py`

```python
# Строка 355:
logger.info("  API SERVICE v2.10.27 - Запуск...")

# Строка 542:
version="2.10.27",  # FastAPI

# Строка 654:
"version": "2.10.27",  # Health check

# НО В training_router.py:
# Нет версии вообще!
```

**Решение:** Единая константа VERSION

---

#### ПРОБЛЕМА #3: Telegram бот в бесконечном рестарте
**Эксперт:** 🐳 DevOps

**Файл:** `telegram_bot/main.py`

```python
# Текущий код:
if not TELEGRAM_BOT_TOKEN:
    logger.warning("⚠️ TELEGRAM_BOT_TOKEN not set! Bot is disabled.")
    while True:
        await asyncio.sleep(3600)  # Спать час
```

**Статус:** ✅ ИСПРАВЛЕНО в v2.10.27

---

### 🟡 СЕРЬЁЗНЫЕ (ВЛИЯЮТ НА СТАБИЛЬНОСТЬ)

#### ПРОБЛЕМА #4: db_pool может быть None
**Эксперт:** 🗄️ Database Architect

**Анализ:**
```python
# main.py lifespan:
try:
    state.db_pool = await asyncpg.create_pool(...)
except Exception as e:
    logger.warning(f"Training module недоступен: {e}")
    # db_pool остаётся None!
```

**Endpoint'ы без проверки:**
- `upload_images()` - падает
- `list_images()` - падает  
- `create_annotation()` - падает
- `update_annotation()` - падает
- `delete_annotation()` - падает
- `list_jobs()` - падает
- `create_job()` - падает

---

#### ПРОБЛЕМА #5: Отсутствие тестов для API
**Эксперт:** 🧪 QA Engineer

**Анализ:**
```bash
$ ls tests/unit/
test_api.py           # Базовые тесты
test_detector.py      # Детектор
test_training.py      # Training worker
test_training_api.py  # Training API

$ grep -c "def test_" tests/unit/test_training_api.py
8  # Только 8 тестов!
```

**Отсутствуют тесты для:**
- `normalize_dataset()` функции
- Pydantic валидации
- Fallback на файловую систему
- Edge cases (пустые датасеты, None значения)

---

#### ПРОБЛЕМА #6: Неполная обработка ошибок
**Эксперт:** 🔒 Security Expert

**Примеры:**
```python
# training_router.py:487
except Exception as e:
    logger.warning(f"Failed to read metadata from {dataset_dir}: {e}")
    # Продолжаем без re-raise - ошибка проглатывается!

# training_router.py:525
except Exception as e:
    logger.warning(f"Failed to read data.yaml from {dataset_dir}: {e}")
    # Та же проблема
```

---

### 🟢 СРЕДНИЕ (ТЕХНИЧЕСКИЙ ДОЛГ)

#### ПРОБЛЕМА #7: Import внутри функций
**Эксперт:** 👀 Code Reviewer

```python
# training_router.py - ПЛОХО:
async def list_datasets(...):
    ...
    from pathlib import Path  # Импорт внутри функции!
    import json               # Импорт внутри функции!
```

**Должно быть:** Все импорты в начале файла

---

#### ПРОБЛЕМА #8: Магические строки
**Эксперт:** 🧹 Cleaner

```python
# Разбросаны по коду:
"created"
"ready"  
"downloaded"
"catalog"
"user"
"postgres"
"screenshots"
```

**Должно быть:** Enum или константы

---

#### ПРОБЛЕМА #9: Отсутствие типизации
**Эксперт:** ⚛️ Frontend Specialist

```python
# training_router.py - raw_data без типа:
def normalize_dataset(raw_data: dict, source_type: str = "unknown") -> dict:
```

**Должно быть:**
```python
from typing import TypedDict

class RawDatasetData(TypedDict, total=False):
    id: Union[str, UUID]
    name: str
    description: Optional[str]
    # ...

def normalize_dataset(raw_data: RawDatasetData, source_type: str = "unknown") -> DatasetDict:
```

---

## 🗳️ ГОЛОСОВАНИЕ КОНСИЛИУМА

### Вопрос: Какой подход к исправлению?

| Эксперт | Решение | Аргумент |
|---------|---------|----------|
| 🏗️ Architect | **РЕФАКТОРИНГ** | Корневая причина требует исправления |
| 🔧 Build Error | Hotfix | Быстро починить валидацию |
| 👀 Code Reviewer | **РЕФАКТОРИНГ** | Дублирование = баги |
| 🧹 Cleaner | **РЕФАКТОРИНГ** | Устранить технический долг |
| 🔒 Security | **РЕФАКТОРИНГ** | Консистентность = безопасность |
| 🗄️ Database | **РЕФАКТОРИНГ** | Единая точка входа для данных |
| 🐳 DevOps | Hotfix | Минимальные изменения |
| ⚛️ Frontend | **РЕФАКТОРИНГ** | Типизация важна |
| 🧪 QA | **РЕФАКТОРИНГ** | Нужны тесты |
| 📋 Planner | **РЕФАКТОРИНГ** | Долгосрочная стратегия |
| 📚 Doc Updater | **РЕФАКТОРИНГ** | Документация упростится |

**РЕЗУЛЬТАТ: 9 за РЕФАКТОРИНГ, 2 за Hotfix**

---

## ✅ ПЛАН ИСПРАВЛЕНИЯ

### Фаза 1: КРИТИЧЕСКИЙ РЕФАКТОРИНГ (v2.10.28)
**Срок:** Немедленно

#### Задача 1.1: Унификация normalize_dataset

```python
# ЗАМЕНИТЬ все дублирования на:

# В list_datasets() - PostgreSQL:
for r in rows:
    normalized = normalize_dataset(dict(r), source_type="postgres")
    datasets.append(normalized)
    seen_ids.add(normalized["id"])

# В list_datasets() - metadata.json:
metadata = json.loads(metadata_file.read_text())
metadata['path'] = str(dataset_dir)
normalized = normalize_dataset(metadata, source_type="catalog")
datasets.append(normalized)

# В list_datasets() - data.yaml:
yaml_data = {
    "id": dataset_dir.name,
    "name": dataset_dir.name.replace('-', ' ').title(),
    # ...минимальные поля
}
normalized = normalize_dataset(yaml_data, source_type="catalog")
datasets.append(normalized)

# В create_dataset() - PostgreSQL:
row_dict = dict(row)
return normalize_dataset(row_dict, source_type="postgres")

# В get_dataset() - PostgreSQL:
row_dict = dict(row)
return normalize_dataset(row_dict, source_type="postgres")

# В get_dataset() - filesystem:
metadata = json.loads(metadata_file.read_text())
return normalize_dataset(metadata, source_type="catalog")
```

#### Задача 1.2: Единая версия

```python
# main.py - в начале файла:
VERSION = "2.10.28"

# Использовать везде:
logger.info(f"  API SERVICE v{VERSION} - Запуск...")
app = FastAPI(..., version=VERSION)
return {"version": VERSION, ...}
```

#### Задача 1.3: Enum для статусов

```python
# training_router.py:
from enum import Enum

class DatasetStatus(str, Enum):
    CREATED = "created"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    READY = "ready"
    ERROR = "error"

class DatasetSource(str, Enum):
    USER = "user"
    POSTGRES = "postgres"
    CATALOG = "catalog"
    SCREENSHOTS = "screenshots"
    CUSTOM = "custom"
```

### Фаза 2: ТЕСТИРОВАНИЕ (v2.10.29)
**Срок:** 1 день

```python
# tests/unit/test_normalize_dataset.py

def test_normalize_uuid():
    """UUID из PostgreSQL конвертируется в string."""
    from uuid import UUID
    raw = {"id": UUID("12345678-1234-1234-1234-123456789012")}
    result = normalize_dataset(raw)
    assert result["id"] == "12345678-1234-1234-1234-123456789012"
    assert isinstance(result["id"], str)

def test_normalize_empty_created_at():
    """Пустая строка created_at становится None."""
    raw = {"id": "test", "created_at": ""}
    result = normalize_dataset(raw)
    assert result["created_at"] is None

def test_normalize_iso_created_at():
    """ISO строка конвертируется в datetime."""
    raw = {"id": "test", "created_at": "2026-01-27T12:00:00Z"}
    result = normalize_dataset(raw)
    assert isinstance(result["created_at"], datetime)

def test_normalize_missing_fields():
    """Отсутствующие поля получают дефолты."""
    raw = {"id": "test"}
    result = normalize_dataset(raw)
    assert result["annotations_count"] == 0
    assert result["images_count"] == 0
    assert result["created_by"] is None

def test_pydantic_validation():
    """Результат проходит Pydantic валидацию."""
    raw = {"id": "test", "name": "Test Dataset"}
    result = normalize_dataset(raw)
    # Должно работать без ошибок:
    DatasetResponse(**result)
```

### Фаза 3: БЕЗОПАСНОСТЬ (v2.11.0)
**Срок:** 1 неделя

1. ⬜ bcrypt для паролей
2. ⬜ Сильный JWT_SECRET
3. ⬜ Rate limiting на auth
4. ⬜ Input validation audit

---

## 📊 МЕТРИКИ УСПЕХА

| Метрика | Текущее | Цель |
|---------|---------|------|
| Использование normalize_dataset | 2/6 мест | 6/6 мест |
| Тесты для normalize_dataset | 0 | 10+ |
| Дублирование кода | ~150 строк | 0 |
| Версий в коде | 3 разных | 1 единая |
| Enum для статусов | 0 | 2 |

---

## 📝 РЕЗОЛЮЦИЯ КОНСИЛИУМА

### ДИАГНОЗ:
Система страдает от **"Синдрома дублирования кода"** - критическая архитектурная проблема, где логика нормализации данных разбросана по 6+ местам вместо использования единой функции.

### РЕКОМЕНДАЦИИ:
1. **НЕМЕДЛЕННО:** Заменить все дублирования на вызовы `normalize_dataset()`
2. **СРОЧНО:** Добавить unit-тесты для функции нормализации
3. **ВАЖНО:** Внедрить Enum для статусов и источников
4. **ПЛАНОВО:** Провести security audit

### ПРОГНОЗ:
При выполнении рефакторинга, количество багов связанных с валидацией данных должно снизиться до нуля.

---

**Документ подписан:**
Консилиум экспертов PPE Detection System

**Дата:** 28 января 2026 г.

**Следующее заседание:** После внедрения Фазы 1
