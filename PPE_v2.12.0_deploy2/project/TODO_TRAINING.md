# 📋 TODO: PPE Detection System v2.5 - Training Module

## Принцип работы: "ЧТО РАБОТАЕТ - НЕ ТРОГАЕМ!"

### ✅ НЕ ТРОГАТЬ (работает стабильно):
- [x] Docker compose конфигурация
- [x] PostgreSQL схема и триггеры  
- [x] Redis pub/sub
- [x] Core detection pipeline (capture, detector, alerter)
- [x] Main dashboard pages (Dashboard, Violations, Analytics)
- [x] JWT аутентификация
- [x] Telegram bot
- [x] Monitoring stack (Prometheus, Grafana)

---

## 🔴 КРИТИЧЕСКИЙ ПРИОРИТЕТ (P0) - Training Integration

### 1. Подключить Training Router к API ✅ ВЫПОЛНЕНО
**Файл:** `services/api/main.py`

**Изменения:**
- Добавлен импорт asyncpg
- Расширен AppState для хранения db_pool
- В lifespan создаётся asyncpg pool и подключается training_router
- Добавлены зависимости в requirements.txt (asyncpg, aiofiles, Pillow)

**Статус:** ✅ Выполнено

---

### 2. Заменить Mock данные в Training.tsx на реальные API ✅ ВЫПОЛНЕНО
**Файл:** `dashboard/src/pages/Training.tsx`

**Изменения:**
- Добавлены импорты trainingApi и useTrainingProgress
- Добавлено состояние для датасетов (currentDatasetId)
- Заменены все mock queries на реальные API вызовы
- Добавлены mutations для: createDataset, upload, deleteImages, addAnnotation, deleteAnnotation, startTraining, cancelTraining, activateModel
- Добавлен UI для выбора/создания датасета
- Обновлены минимальные требования: 100 изображений, 500 аннотаций

**Статус:** ✅ Выполнено

---

### 3. Создать MinIO bucket при старте ✅ ВЫПОЛНЕНО
**Файл:** `scripts/init_minio.py`

Создан скрипт инициализации MinIO с созданием buckets:
- training-images
- training-models  
- violations

**Статус:** ✅ Выполнено

---

## 🟡 ВЫСОКИЙ ПРИОРИТЕТ (P1) - UX Improvements

### 4. Рефакторинг Training.tsx
- [x] Вынести компоненты в отдельные файлы (частично - используем существующие)
- [x] Использовать готовые типы из `/types/training.ts`
- [ ] Интегрировать `useAnnotationHistory` hook полностью
- [ ] Добавить `useTrainingShortcuts` hook

**Статус:** ⚠️ Частично выполнено

---

### 5. WebSocket Progress Integration ✅ ВЫПОЛНЕНО
**Файл:** `dashboard/src/pages/Training.tsx`

Интегрирован hook useTrainingProgress для real-time обновлений.

**Статус:** ✅ Выполнено

---

### 6. Валидация минимума изображений ✅ ВЫПОЛНЕНО
**Изменено:**
- MIN_IMAGES = 100 (было 10)
- MIN_ANNOTATIONS = 500 (было 50)
- Обновлены все проверки в UI

**Статус:** ✅ Выполнено

---

## 🟢 СРЕДНИЙ ПРИОРИТЕТ (P2) - Features

### 7. GPU Status Indicator
- [ ] API endpoint `/api/training/gpu/status`
- [ ] UI индикатор в Training page
- [ ] Показывать VRAM при обучении

---

### 8. Data Augmentation Preview
- [ ] Показывать примеры аугментации перед обучением
- [ ] Добавить настройки аугментации в UI

---

### 9. Confusion Matrix
- [ ] Визуализация после обучения
- [ ] Per-class метрики

---

## 🔵 ТЕСТЫ (P1)

### Созданные тесты:
- [x] `tests/unit/test_training.py` - 39 тестов ✅
- [x] `tests/integration/test_training_integration.py` - структура

### Нужно добавить:
- [ ] React component tests (Vitest/Jest)
- [ ] E2E tests с Playwright/Cypress
- [ ] Load tests для upload

---

## 📊 ПРОГРЕСС

| Задача | Статус | Приоритет |
|--------|--------|-----------|
| Training Router подключение | ✅ | P0 |
| Mock → Real API | ✅ | P0 |
| MinIO init | ✅ | P0 |
| Training.tsx рефакторинг | ⚠️ | P1 |
| WebSocket progress | ✅ | P1 |
| Валидация 100 изображений | ✅ | P1 |
| Unit тесты Training | ✅ 39/39 | P1 |
| Integration тесты | ⚠️ | P2 |
| GPU indicator | ❌ | P2 |
| Augmentation preview | ❌ | P2 |

---

## 🚀 QUICK START для разработки

```bash
# 1. Запустить инфраструктуру
docker-compose up -d postgres redis minio

# 2. Инициализировать MinIO buckets
python scripts/init_minio.py

# 3. Инициализировать БД
docker-compose exec postgres psql -U ppe -d ppe_detection -f /docker-entrypoint-initdb.d/02_training.sql

# 4. Запустить API (dev mode)
cd services/api && python main.py

# 5. Запустить Dashboard (dev mode)
cd dashboard && npm run dev

# 6. Запустить тесты
pytest tests/unit/test_training.py -v
```

---

**Последнее обновление:** 23 января 2026
**Автор:** DevOrchestra AI Team
