# v2.10.65 — Training Pipeline Fix

**Дата:** 2026-02-03
**Статус:** CRITICAL FIX

## Исправления

### 🔴 FIX-1: Training не запускается — Missing Celery (CRITICAL)
**Файл:** `services/api/requirements.txt`
**Проблема:** `celery` не был указан в зависимостях API-контейнера. При попытке запустить обучение — `No module named 'celery'`. Ошибка молча глоталась, возвращался 200 OK, но задача не ставилась в очередь.
**Решение:** 
- Добавлен `celery[redis]>=5.3.6` в requirements.txt
- При ошибке Celery теперь возвращается HTTP 500 с понятным сообщением
- Job в БД помечается как `failed` вместо `pending`

### 🟡 FIX-2: YOLOv9 Tiny/Compact/Extended → 422 Validation Error (HIGH)
**Файл:** `services/api/training_router.py`
**Проблема:** Валидатор `model_size` принимал только `[n, s, m, l, x]`. YOLOv9 использует `t` (Tiny), `c` (Compact), `e` (Extended). YOLOv10 использует `b` (Base). Frontend корректно отправлял `t`, но API отвечал 422.
**Решение:** Расширен валидатор: `['n', 's', 'm', 'l', 'x', 't', 'c', 'e', 'b']`

### 🟡 FIX-3: "Ошибка: [object Object]" в UI (MEDIUM)
**Файл:** `dashboard/src/api/training.ts`
**Проблема:** FastAPI 422 возвращает `{detail: [{loc, msg, type}]}` (массив). Frontend делал `throw new Error(error.detail)` — объект/массив превращался в `[object Object]`.
**Решение:** Корректный парсинг: если `detail` — string, используем напрямую; если массив — извлекаем `msg` из каждого элемента.

### 🟢 FIX-4: GPU Memory не отображается (LOW)
**Файл:** `services/detector/main.py`
**Проблема:** В Settings → GPU показывало "/ 32606 MB" (без текущего использования). Detector публиковал в Redis только `memory_total_mb`, а `memory_used_mb` и `memory_free_mb` оставались пустыми. GPU info публиковался только 1 раз при старте.
**Решение:**
- При старте детектора читаем текущее использование через `torch.cuda.mem_get_info()`
- Добавлено периодическое обновление каждые ~30 секунд в основном цикле
- Fallback на `nvidia-smi` если `mem_get_info` недоступен

### 🟢 FIX-5: Отображение стадий обучения в UI (UX)
**Файлы:** `dashboard/src/hooks/useTrainingProgress.ts`, `dashboard/src/pages/Training.tsx`
**Проблема:** Worker отправляет 6 стадий (preparing → loading_model → training → validating → evaluating → done) с текстовыми сообщениями, но frontend их не показывал. Пользователь не видел что происходит между нажатием кнопки и появлением первой эпохи.
**Решение:**
- Добавлены поля `stage` и `message` в интерфейс `TrainingProgress`
- Добавлен блок стадий между бейджем и прогресс-баром с иконками:
  - 📁 Подготовка датасета... (FolderOpen + pulse)
  - 📥 Загрузка модели yolov10x.pt... (Download + bounce)
  - 📈 Обучение... (TrendingUp)
  - ✅ Валидация... (CheckCircle)
  - 🔬 Финальная оценка модели... (Cpu + pulse)
  - ✅ Обучение завершено! (CheckCircle green)

## Затронутые файлы

| Файл | Изменение |
|------|----------|
| `services/api/requirements.txt` | +1 строка (celery[redis]) |
| `services/api/training_router.py` | Валидатор model_size + error handling |
| `services/api/models_router.py` | Без изменений (из v2.10.64) |
| `dashboard/src/api/training.ts` | Парсинг ошибок 422 |
| `dashboard/src/hooks/useTrainingProgress.ts` | +stage, +message в интерфейс |
| `dashboard/src/pages/Training.tsx` | Блок индикатора стадий обучения |
| `services/detector/main.py` | GPU memory publishing + periodic update |

## Инструкция по обновлению

```powershell
# 1. Заменить файлы (из ZIP)
# 2. Пересобрать с --no-cache (важно! celery устанавливается на этапе build)
docker-compose build --no-cache api
docker-compose build --no-cache detector
docker-compose build --no-cache dashboard

# 3. Перезапустить
docker-compose down
docker-compose up -d

# 4. Проверить celery установлен
docker exec ppe_api pip list | findstr celery

# 5. Проверить GPU memory
docker exec ppe_api curl -s http://localhost:8000/api/settings/gpu | python -m json.tool

# 6. Тест обучения: выбрать YOLOv8 Nano → Начать обучение
```

## Диагностика из логов (что было)

```
# Ошибка celery (20+ раз)
ERROR | training_api | Failed to queue training job: No module named 'celery'

# YOLOv9 Tiny → 422
POST /api/training/jobs HTTP/1.1" 422 Unprocessable Entity

# GPU endpoint тест (неверный URL)
curl http://localhost:8000/api/models/gpu-info → {"detail":"Method Not Allowed"}
# Правильный: http://localhost:8000/api/settings/gpu
```
