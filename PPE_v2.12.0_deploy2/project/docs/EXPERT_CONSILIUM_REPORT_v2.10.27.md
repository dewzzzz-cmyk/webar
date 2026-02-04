# 🔬 КОНСИЛИУМ ЭКСПЕРТОВ: PPE Detection System v2.10.27

**Дата:** 2026-01-27  
**Статус:** КРИТИЧЕСКИЙ АУДИТ  
**Версия системы:** 2.10.25 → 2.10.27

---

## 📋 СОСТАВ КОНСИЛИУМА

| Роль | Специализация | Статус |
|------|---------------|--------|
| **Build Error Resolver** | Ошибки сборки и типизации | ✅ Присутствует |
| **Code Reviewer** | Качество кода и безопасность | ✅ Присутствует |
| **Planner** | Архитектурное планирование | ✅ Присутствует |
| **Refactor Cleaner** | Рефакторинг и мёртвый код | ✅ Присутствует |
| **Security Expert** | Безопасность системы | ✅ Приглашён |
| **Database Architect** | Схемы БД и миграции | ✅ Приглашён |
| **Frontend Expert** | React/TypeScript интеграция | ✅ Приглашён |

---

## 🔴 КОРНЕВАЯ ПРИЧИНА ВСЕХ ПРОБЛЕМ

### ДИАГНОЗ: Несогласованность схемы данных между уровнями

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   PostgreSQL    │     │   Python API    │     │   React UI      │
│   (9 полей)     │ ≠   │  (13 полей)     │ ≠   │  (13 полей)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        ↓                       ↓                       ↓
  - id (UUID)            - id (string)           - id (string)
  - name                 - name                  - name
  - description          - description          - description
  - created_by           - created_by           - created_by
  - created_at           - created_at           - created_at
  - updated_at           - status               - status
  - images_count         - images_count         - images_count
  - annotations_count    - annotations_count    - annotations_count
  - status               - labeled_count ❌      - labeled_count
                         - classes ❌            - classes
                         - source ❌             - source
                         - path ❌               - path
```

**ВЫВОД:** Pydantic модель `DatasetResponse` требует 13 полей, PostgreSQL таблица содержит только 9.

---

## 📊 ВЫЯВЛЕННЫЕ ПРОБЛЕМЫ

### 🔴 КРИТИЧЕСКИЕ (P0) - Блокируют работу

#### P0-1: Несоответствие схемы БД и Pydantic модели

**Файлы:**
- `scripts/init_training_db.sql` (строки 12-22)
- `services/api/main.py` (строки 386-396) 
- `services/api/training_router.py` (строки 165-178)

**Проблема:**
```sql
-- PostgreSQL таблица (init_training_db.sql)
CREATE TABLE training_datasets (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    description TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    images_count INTEGER,
    annotations_count INTEGER,
    status VARCHAR(20)
    -- ❌ ОТСУТСТВУЮТ: labeled_count, classes, source, path
);
```

```python
# Pydantic модель требует (training_router.py)
class DatasetResponse(BaseModel):
    id: str                           # ❌ БД возвращает UUID объект
    name: str
    description: Optional[str]
    status: str
    images_count: int
    annotations_count: int
    labeled_count: int = 0            # ❌ НЕТ В БД
    created_by: Optional[str]
    created_at: Optional[datetime]
    classes: Optional[List[str]]      # ❌ НЕТ В БД
    source: Optional[str]             # ❌ НЕТ В БД
    path: Optional[str]               # ❌ НЕТ В БД
```

**Результат:** `ResponseValidationError: 8 validation errors`

---

#### P0-2: UUID не конвертируется в строку

**Файл:** `services/api/training_router.py`

**Проблема:**
```python
# PostgreSQL asyncpg возвращает UUID объект
row = await conn.fetchrow("SELECT * FROM training_datasets WHERE id = $1", id)
return dict(row)  # ❌ row['id'] = UUID('6bab2607-...')
                  # Pydantic ожидает: str
```

**Результат:** `{'type': 'string_type', 'loc': ('response', 'id'), 'msg': 'Input should be a valid string', 'input': UUID('...')}`

---

#### P0-3: Отсутствие fallback в критических эндпоинтах

**Файл:** `services/api/training_router.py`

**Проблемные места (без проверки `if db_pool:`):**
- Строка 749: `upload_images()` - падает если БД недоступна
- Строка 762: `upload_images()` - второй acquire
- Строка 996: `create_annotation()` - падает
- Строка 1045: `update_annotation()` - падает
- Строка 1163: `start_training()` - падает
- Строка 1215: `stop_training()` - падает

**Результат:** При недоступности PostgreSQL система полностью неработоспособна.

---

### 🟠 ВЫСОКИЕ (P1) - Серьёзные проблемы

#### P1-1: Смешивание типов данных

**Проблема:** Разные источники данных возвращают разные типы:

| Источник | created_at | id |
|----------|------------|-----|
| PostgreSQL | `datetime` объект | `UUID` объект |
| metadata.json | `""` пустая строка | `string` |
| data.yaml | отсутствует | `string` |
| screenshots | отсутствует | `"screenshots"` |

**Результат:** Ошибка сортировки `'<' not supported between datetime and str`

---

#### P1-2: Дублирование логики нормализации

**Проблема:** Код нормализации разбросан по файлу без централизованной функции:
- Строки 344-368: нормализация PostgreSQL в `list_datasets()`
- Строки 407-420: нормализация metadata.json
- Строки 445-458: нормализация data.yaml
- Строки 493-507: нормализация screenshots
- Строки 549-562: нормализация в `create_dataset()`

**Результат:** При добавлении нового поля нужно править 5+ мест.

---

#### P1-3: Telegram бот в бесконечном рестарте

**Логи:**
```
ppe_telegram_bot   Restarting (0) 53 seconds ago
```

**Вероятная причина:** Отсутствует `TELEGRAM_BOT_TOKEN` или ошибка подключения.

---

### 🟡 СРЕДНИЕ (P2) - Требуют внимания

#### P2-1: Отсутствие автоматической миграции схемы

**Проблема:** В `main.py` есть `DO $$ BEGIN ... EXCEPTION WHEN duplicate_column ...` для training_jobs, но НЕТ для training_datasets.

---

#### P2-2: Hardcoded пути

```python
# training_router.py
TRAINING_IMAGES_PATH = os.getenv('TRAINING_IMAGES_PATH', '/app/training_data/images')
# Но в коде также hardcoded:
catalog_path = Path("/app/datasets")  # строка 379
custom_path = Path("/app/datasets/custom")  # строка 466
screenshots_path = Path("/app/training_data/screenshots")  # строка 485
```

---

#### P2-3: Отсутствие типизации db_pool

```python
def create_training_router(db_pool) -> APIRouter:  # db_pool: ??? 
```

Должно быть:
```python
from typing import Optional
import asyncpg

def create_training_router(db_pool: Optional[asyncpg.Pool]) -> APIRouter:
```

---

## 🛠️ РЕШЕНИЕ КОНСИЛИУМА

### Фаза 1: Срочные исправления (v2.10.27)

#### 1.1 Добавить недостающие колонки в БД

```sql
-- Добавить в init_training_db.sql И в main.py lifespan
ALTER TABLE training_datasets ADD COLUMN IF NOT EXISTS labeled_count INTEGER DEFAULT 0;
ALTER TABLE training_datasets ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'user';
ALTER TABLE training_datasets ADD COLUMN IF NOT EXISTS path VARCHAR(500);
ALTER TABLE training_datasets ADD COLUMN IF NOT EXISTS classes JSONB DEFAULT '[]'::jsonb;
```

#### 1.2 Создать централизованную функцию нормализации

```python
def normalize_dataset(raw_data: dict, source: str = "unknown") -> dict:
    """
    Нормализует данные датасета из любого источника.
    Гарантирует соответствие DatasetResponse.
    """
    # Нормализация ID
    raw_id = raw_data.get('id')
    if hasattr(raw_id, 'hex'):  # UUID object
        dataset_id = str(raw_id)
    else:
        dataset_id = str(raw_id) if raw_id else ""
    
    # Нормализация created_at
    created_at = raw_data.get('created_at')
    if created_at == "" or created_at is None:
        created_at = None
    elif isinstance(created_at, str) and created_at:
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            created_at = None
    
    return {
        "id": dataset_id,
        "name": raw_data.get('name', dataset_id),
        "description": raw_data.get('description') or None,
        "status": raw_data.get('status', 'created'),
        "images_count": raw_data.get('images_count', 0) or 0,
        "annotations_count": raw_data.get('annotations_count', 0) or 0,
        "labeled_count": raw_data.get('labeled_count', 0) or 0,
        "created_by": raw_data.get('created_by') or None,
        "created_at": created_at,
        "classes": raw_data.get('classes') or [],
        "source": raw_data.get('source', source),
        "path": raw_data.get('path'),
    }
```

#### 1.3 Добавить fallback во все эндпоинты

```python
# Паттерн для каждого эндпоинта
if db_pool:
    try:
        async with db_pool.acquire() as conn:
            # PostgreSQL логика
    except Exception as e:
        logger.warning(f"PostgreSQL unavailable: {e}")
        # Fallback на файловую систему

# Fallback логика
```

---

### Фаза 2: Архитектурные улучшения (v2.11.0)

#### 2.1 Создать слой репозитория

```python
# repositories/dataset_repository.py
class DatasetRepository:
    def __init__(self, db_pool: Optional[asyncpg.Pool]):
        self.db_pool = db_pool
    
    async def list_all(self, status: Optional[str] = None) -> List[dict]:
        datasets = []
        datasets.extend(await self._from_postgres(status))
        datasets.extend(await self._from_filesystem(status))
        return self._sort_and_dedupe(datasets)
    
    async def _from_postgres(self, status) -> List[dict]:
        if not self.db_pool:
            return []
        # ...
    
    async def _from_filesystem(self, status) -> List[dict]:
        # ...
```

#### 2.2 Создать систему миграций

```python
# migrations/001_add_dataset_columns.py
async def upgrade(conn):
    await conn.execute("""
        ALTER TABLE training_datasets 
        ADD COLUMN IF NOT EXISTS labeled_count INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'user',
        ADD COLUMN IF NOT EXISTS path VARCHAR(500),
        ADD COLUMN IF NOT EXISTS classes JSONB DEFAULT '[]'::jsonb
    """)

async def downgrade(conn):
    # Reverse migration
```

---

## 📋 ЧЕКЛИСТ ДЛЯ v2.10.27

### Изменения в файлах:

- [ ] `scripts/init_training_db.sql` - Добавить колонки
- [ ] `services/api/main.py` - Добавить миграцию колонок в lifespan
- [ ] `services/api/training_router.py`:
  - [ ] Создать функцию `normalize_dataset()`
  - [ ] Использовать её во всех местах
  - [ ] Добавить `if db_pool:` проверки везде
  - [ ] Исправить типизацию
- [ ] `docker-compose.yml` - Проверить TELEGRAM_BOT_TOKEN

### Тестирование:

- [ ] `curl http://localhost:8000/api/training/datasets` → JSON массив
- [ ] `curl http://localhost:8000/api/training/datasets -X POST -d '{"name":"Test"}'` → Успех
- [ ] Проверить UI Training → Datasets отображаются
- [ ] Telegram бот не рестартует

---

## 🎯 ВЕРДИКТ КОНСИЛИУМА

### Голосование экспертов:

| Эксперт | Решение |
|---------|---------|
| Build Error Resolver | ✅ Согласен с планом |
| Code Reviewer | ✅ Согласен, добавить тесты |
| Planner | ✅ Согласен, разбить на фазы |
| Refactor Cleaner | ✅ Согласен, нужна централизация |
| Security Expert | ⚠️ Добавить валидацию путей |
| Database Architect | ✅ Согласен, нужны миграции |
| Frontend Expert | ✅ Согласен, API станет стабильным |

### ЕДИНОГЛАСНОЕ РЕШЕНИЕ:

> **Реализовать Фазу 1 немедленно в версии 2.10.27**
> 
> Корневая причина проблем - несогласованность схемы данных между PostgreSQL, Python API и React UI. 
> Решение: добавить недостающие колонки в БД, создать централизованную функцию нормализации, 
> добавить fallback во все эндпоинты.

---

## 📎 ПРИЛОЖЕНИЯ

### A. Traceback из логов

```
fastapi.exceptions.ResponseValidationError: 8 validation errors:
  {'type': 'string_type', 'loc': ('response', 0, 'id'), 'input': UUID('24b80fbc-...')}
  {'type': 'string_type', 'loc': ('response', 1, 'id'), 'input': UUID('00000000-...')}
  {'type': 'missing', 'loc': ('response', 2, 'annotations_count')}
  {'type': 'missing', 'loc': ('response', 2, 'created_by')}
  {'type': 'datetime_from_date_parsing', 'loc': ('response', 2, 'created_at'), 'input': ''}
  {'type': 'missing', 'loc': ('response', 3, 'annotations_count')}
  {'type': 'missing', 'loc': ('response', 3, 'created_by')}
  {'type': 'missing', 'loc': ('response', 3, 'created_at')}
```

### B. Схема данных (текущая vs требуемая)

```
ТЕКУЩАЯ БД (training_datasets):
┌──────────────────┬─────────────┬──────────┐
│ Column           │ Type        │ Default  │
├──────────────────┼─────────────┼──────────┤
│ id               │ UUID        │ auto     │
│ name             │ VARCHAR     │ -        │
│ description      │ TEXT        │ NULL     │
│ created_by       │ VARCHAR     │ 'system' │
│ created_at       │ TIMESTAMP   │ NOW()    │
│ updated_at       │ TIMESTAMP   │ NOW()    │
│ images_count     │ INTEGER     │ 0        │
│ annotations_count│ INTEGER     │ 0        │
│ status           │ VARCHAR     │ 'draft'  │
└──────────────────┴─────────────┴──────────┘

ТРЕБУЕМАЯ БД (после миграции):
┌──────────────────┬─────────────┬──────────┐
│ Column           │ Type        │ Default  │
├──────────────────┼─────────────┼──────────┤
│ id               │ UUID        │ auto     │
│ name             │ VARCHAR     │ -        │
│ description      │ TEXT        │ NULL     │
│ created_by       │ VARCHAR     │ 'system' │
│ created_at       │ TIMESTAMP   │ NOW()    │
│ updated_at       │ TIMESTAMP   │ NOW()    │
│ images_count     │ INTEGER     │ 0        │
│ annotations_count│ INTEGER     │ 0        │
│ labeled_count    │ INTEGER     │ 0        │  ← NEW
│ status           │ VARCHAR     │ 'draft'  │
│ source           │ VARCHAR     │ 'user'   │  ← NEW
│ path             │ VARCHAR     │ NULL     │  ← NEW
│ classes          │ JSONB       │ '[]'     │  ← NEW
└──────────────────┴─────────────┴──────────┘
```

---

**Документ подготовлен:** Claude AI Consilium  
**Дата утверждения:** 2026-01-27  
**Следующий шаг:** Реализация v2.10.27
