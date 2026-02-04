# 📋 План v2.12.0: PPE Detection System — ФИНАЛЬНЫЙ v2

**Версия плана:** 2.1 (+ Test Strategy)
**Дата:** 2026-02-04
**Приоритет:** HIGH
**Статус:** ✅ УТВЕРЖДЁН (после совещания 6 специалистов + QA review)
**Оценка:** 11-14 сессий | 7 деплоев | 36 задач + 12 встроенных тестов

### 🧪 Стратегия тестирования (Вариант A: встроенные тесты)

Тесты встроены в задачи по принципу TDD — **пишутся ДО или ВМЕСТЕ с кодом**.
Критерий Verify расширен: **ручная проверка + автоматический тест**.

| Deploy | Тесты | Покрытие |
|--------|-------|----------|
| 1 | T01-TEST, T02-TEST, T03-TEST | Celery worker, API endpoints, file cleanup |
| 2 | T04-TEST, T06-TEST | Auto-annotate pipeline, GPU guard |
| 3 | T09-TEST, T10-TEST | WS progress, model deploy |
| 4 | T12-TEST, T16-TEST | data.yaml parser, class mapping |
| 5 | T20-TEST, T24-TEST | Redis activation, profile validation |
| 6 | T25-TEST | Security (JWT masking + WS origin) |
| 7 | T36 (E2E) | Full pipeline end-to-end |

**Минимально необходимые (5):** T04, T10, T20, T25, T36
**Файлы тестов:** `tests/unit/`, `tests/integration/`, `tests/e2e/`

---

## 📌 Краткое резюме

Профиль детекции и модель YOLO — две изолированные системы. При смене профиля модель не переключается. Тренировка падает, авто-аннотация не реализована, класс-маппинг разорван, логи небезопасны.

**Цель v2.12.0:** Связать профиль ↔ модель через Redis, починить тренировку, реализовать полный annotation pipeline, обеспечить деплой обученных моделей одной кнопкой.

---

## ⚙️ Архитектурные решения

| # | Решение | Статус | Обоснование |
|---|---------|--------|-------------|
| A1 | `active_model.json` → **Redis key + pub/sub** | ✅ Принято | Атомарность, нет race condition при read/write |
| A2 | Auto-annotate через **Celery worker** (не API) | ✅ Принято | YOLO 50-200MB → OOM risk в API-процессе |
| A3 | Training progress через **Redis pub/sub** | ✅ Принято | 0 нагрузка между обновлениями (vs polling 2с) |
| A4 | Auto-annotate на **CPU-only** | ✅ Принято | GPU — только detection + training |
| A5 | Объединить Ф2 + Ф11.2 → **единый Redis activation** | ✅ Принято | Один механизм вместо двух параллельных |
| A6 | WebSocket token → first-frame auth | ⏳ После v2.12 | Маскирование пока достаточно |
| A7 | Redis Streams для кадров детекции | ⏳ Backlog | Авто-ротация, не раздувает AOF |
| A8 | Разделение training_router.py (~2600 строк) | ⏳ Backlog | Рискованно в этом релизе |

### Решения по открытым вопросам

| Вопрос | Решение |
|--------|---------|
| **GPU sharing** | CPU-only для auto-annotate (A4). Training на GPU — детектор продолжает работать (разные процессы, shared GPU memory). При OOM — fallback training на CPU с warning. |
| **Feature flags** | `ENABLE_CLASS_MAPPING=true/false` для Deploy 4 (class mapping). По умолчанию `true`. Rollback через env var. |
| **MinIO backup** | Добавить cron-job `mc mirror` в отдельном контейнере. Warning в UI (задача T32). Полная стратегия — после v2.12.0. |

---

## 📊 Annotation Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    ANNOTATION LIFECYCLE                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  YOLO .txt (FS-датасеты):                                   │
│    файл .txt → парсинг → data.yaml классы → обучение        │
│    Storage: файловая система                                 │
│                                                              │
│  Redis (catalog + screenshot images):                        │
│    UI canvas → redis key annotations:{id} → export → train   │
│    Storage: Redis                                            │
│                                                              │
│  Auto-annotate (v2.12.0):                                   │
│    Celery worker (CPU) → YOLO predict → Redis key → UI       │
│    Storage: Redis (как ручные)                               │
│                                                              │
│  Class Mapping (v2.12.0):                                   │
│    dataset_class_mappings (PostgreSQL)                        │
│    dataset_class → profile_class при обучении                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 DEPLOY 1 — Training Unblock

> **Время:** ~30 мин | **Риск:** 🟢 LOW
> **Файлы:** `worker.py`, `training_router.py`
> **Результат:** Тренировка работает, модели видны, скриншоты удаляются
> **Rollback:** `git revert` + `docker-compose build --no-cache ppe_training ppe_api`

### T01. Fix Celery multiprocessing crash 🔴 CRITICAL

**Проблема:** `AssertionError: daemonic processes are not allowed to have children` — PyTorch DataLoader пытается создать субпроцессы внутри Celery daemon-процесса.

**Файл:** `services/training/worker.py` → `model.train()`

```python
# Было:
results = model.train(data=data_yaml_path, epochs=epochs, batch=batch_size,
    workers=4,          # ← CRASH
)

# Стало:
results = model.train(data=data_yaml_path, epochs=epochs, batch=batch_size,
    workers=0,          # ← FIX
)
```

**Сложность:** LOW (1 строка)
**Verify:** `docker logs ppe_training` — нет `AssertionError`, тренировка завершается

**🧪 T01-TEST:** `tests/unit/test_celery_worker.py`
```python
def test_train_task_workers_zero():
    """Celery train task uses workers=0 to avoid daemon subprocess crash."""
    # Mock model.train и проверить что workers=0 передаётся
    with patch("worker.YOLO") as mock_yolo:
        mock_model = mock_yolo.return_value
        run_training_task(dataset_id="test", epochs=1)
        call_kwargs = mock_model.train.call_args.kwargs
        assert call_kwargs["workers"] == 0

def test_train_task_no_assertion_error():
    """Training task completes without daemonic process error."""
    # Integration: запуск с мини-датасетом, assert нет AssertionError
```

---

### T02. Implement GET /api/training/models 🔴 CRITICAL

**Проблема:** UI поллит список обученных моделей → 10 раз 404 за 47 минут.

**Файл:** `services/api/training_router.py` — новый endpoint

```python
@router.get("/training/models")
async def list_trained_models():
    models_dir = Path("/app/training_data/models")
    models = []
    for pt_file in sorted(models_dir.glob("**/*.pt"),
                          key=lambda p: p.stat().st_mtime, reverse=True):
        stat = pt_file.stat()
        models.append({
            "name": pt_file.stem,
            "path": str(pt_file.relative_to(models_dir)),
            "size_mb": round(stat.st_size / 1024 / 1024, 1),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return {"models": models, "count": len(models)}
```

**Сложность:** LOW
**Verify:** `curl /api/training/models` → 200 + JSON array

**🧪 T02-TEST:** `tests/integration/test_training_api.py`
```python
async def test_list_trained_models_empty(client):
    """GET /api/training/models returns empty list when no models."""
    resp = await client.get("/api/training/models")
    assert resp.status_code == 200
    assert resp.json()["models"] == []
    assert resp.json()["count"] == 0

async def test_list_trained_models_with_files(client, tmp_models_dir):
    """GET /api/training/models returns sorted model list."""
    # Создать 2 .pt файла → ответ содержит оба, newest first
    resp = await client.get("/api/training/models")
    assert resp.json()["count"] == 2
    assert resp.json()["models"][0]["size_mb"] > 0
```

---

### T03. Fix Screenshot Image Deletion 🟡 HIGH

**Проблема:** Удаление скриншотов → 404 (нет записи в БД, только файл на диске).

**Файл:** `services/api/training_router.py` → `delete_image()`

```python
async def delete_image(image_id: str):
    row = await conn.fetchrow("SELECT * FROM training_images WHERE id = $1", image_id)
    if row:
        # Удаляем из БД + файл
        ...
    else:
        # Fallback: ищем по UUID в screenshots директории
        screenshots_dir = Path("/app/training_data/screenshots")
        for img_file in screenshots_dir.iterdir():
            if image_id in img_file.stem:
                img_file.unlink()
                return {"deleted": True, "source": "filesystem"}
        raise HTTPException(404, "Image not found")
```

**Сложность:** LOW
**Verify:** DELETE screenshot → 200, файл удалён с диска

**🧪 T03-TEST:** `tests/integration/test_screenshot_deletion.py`
```python
async def test_delete_screenshot_removes_file(client, tmp_screenshot):
    """DELETE /screenshots/{id} removes file from disk and DB."""
    resp = await client.delete(f"/api/screenshots/{tmp_screenshot.id}")
    assert resp.status_code == 200
    assert not Path(tmp_screenshot.path).exists()

async def test_delete_screenshot_cleans_redis_annotations(client, tmp_screenshot, redis):
    """DELETE removes associated Redis annotations."""
    resp = await client.delete(f"/api/screenshots/{tmp_screenshot.id}")
    assert await redis.get(f"annotations:{tmp_screenshot.id}") is None
```

---

## 🚀 DEPLOY 2 — Smart Annotation

> **Время:** ~2 сессии | **Риск:** 🟡 MEDIUM
> **Файлы:** `training_router.py`, `worker.py`, `Training.tsx`
> **Результат:** Полный annotation workflow — авто-разметка одним кликом
> **Rollback:** Откатить worker.py + training_router.py. Auto-annotate — новая функция, откат безопасен.

### T04. Implement Auto-Annotate (Celery + CPU) 🔴 CRITICAL

**Проблема:** `POST /api/training/images/{id}/auto-annotate` → 501 Not Implemented

> Арх. решение A2 + A4: Celery worker на CPU, НЕ API-процесс.

**Файлы:** `services/api/training_router.py` + `services/training/worker.py`

```python
# API — ставит задачу в очередь:
@router.post("/training/images/{image_id}/auto-annotate")
async def auto_annotate_image(
    image_id: str,
    threshold: float = Query(0.3, ge=0.05, le=0.95)  # Security: валидация
):
    task = celery_app.send_task("auto_annotate", args=[image_id, threshold])
    return {"task_id": task.id, "status": "queued"}

# Worker — inference на CPU:
@celery_app.task(name="auto_annotate")
def auto_annotate_task(image_id: str, threshold: float):
    image_path = resolve_image_path(image_id)
    model = YOLO(get_active_model_path())
    model.to("cpu")  # GPU guard: CPU-only
    results = model.predict(str(image_path), conf=threshold, device="cpu")

    annotations = []
    for r in results[0].boxes:
        cls_id = int(r.cls[0])
        x, y, w, h = r.xywhn[0].tolist()
        annotations.append({
            "class_id": cls_id,
            "class_name": model.names[cls_id],
            "bbox": [x, y, w, h],
            "confidence": float(r.conf[0])
        })

    redis.set(f"annotations:{image_id}", json.dumps(annotations))
    return {"annotations": annotations, "count": len(annotations)}
```

**Сложность:** MEDIUM
**Verify:** POST /auto-annotate → task queued → annotations появляются в Redis

**🧪 T04-TEST:** `tests/unit/test_auto_annotate.py` + `tests/integration/test_auto_annotate_api.py`
```python
# Unit: парсинг YOLO predictions → Redis формат
def test_yolo_predictions_to_annotations():
    """YOLO predict results correctly converted to annotation format."""
    mock_result = MockYOLOResult(boxes=[(0.1, 0.2, 0.5, 0.6, 0.95, 0)])
    annotations = parse_yolo_to_annotations(mock_result, image_w=640, image_h=480)
    assert len(annotations) == 1
    assert annotations[0]["confidence"] == 0.95
    assert annotations[0]["source"] == "auto"

def test_auto_annotate_filters_low_confidence():
    """Predictions below threshold are excluded."""
    # conf=0.15 при threshold=0.25 → пусто

# Integration: Celery task + Redis
async def test_auto_annotate_task_stores_in_redis(redis):
    """Auto-annotate Celery task stores results in Redis."""
    result = auto_annotate_image.apply(args=["test_image_id", "yolov8n.pt"])
    stored = json.loads(await redis.get("annotations:test_image_id"))
    assert len(stored) > 0
    assert all(a["source"] == "auto" for a in stored)

# API endpoint
async def test_post_auto_annotate_returns_task_id(client):
    """POST /auto-annotate returns Celery task ID."""
    resp = await client.post("/api/auto-annotate", json={"image_id": "test"})
    assert resp.status_code == 202
    assert "task_id" in resp.json()
```

---

### T05. Batch Auto-Annotate (весь датасет) 🔴 CRITICAL

> Совещание (Product Owner): "При 44 скриншотах пользователь нажмёт 44 раза"

**Файлы:** `training_router.py` + `worker.py` + `Training.tsx`

```python
# API:
@router.post("/training/datasets/{dataset_id}/auto-annotate")
async def batch_auto_annotate(
    dataset_id: str,
    threshold: float = Query(0.3, ge=0.05, le=0.95)
):
    task = celery_app.send_task("batch_auto_annotate", args=[dataset_id, threshold])
    return {"task_id": task.id, "status": "queued"}

# Worker:
@celery_app.task(name="batch_auto_annotate")
def batch_auto_annotate_task(dataset_id: str, threshold: float):
    images = get_unannotated_images(dataset_id)
    model = YOLO(get_active_model_path())
    model.to("cpu")

    for i, img in enumerate(images):
        results = model.predict(str(img.path), conf=threshold, device="cpu")
        annotations = convert_to_annotations(results)
        redis.set(f"annotations:{img.id}", json.dumps(annotations))

        redis.publish(f"autoannotate:progress:{dataset_id}", json.dumps({
            "current": i + 1,
            "total": len(images),
            "progress_pct": round((i+1)/len(images)*100)
        }))

    return {"annotated": len(images)}
```

**UI:** Кнопка "🤖 Авто-разметить всё" + progress bar

**Сложность:** MEDIUM
**Verify:** Кнопка → прогресс → все изображения получают аннотации

---

### T06. GPU Resource Guard 🟡 HIGH

> Совещание (Performance): GPU contention при parallel inference

**Решение:** Интегрировано в T04 + T05: `model.to("cpu")` + `device="cpu"`.

**Файл:** `services/training/worker.py`

**Сложность:** LOW (часть T04/T05)
**Verify:** Auto-annotate при работающем детекторе (6 камер) → нет OOM

**🧪 T06-TEST:** `tests/unit/test_gpu_guard.py`
```python
def test_gpu_guard_blocks_when_busy():
    """GPU guard prevents concurrent GPU access."""
    with patch("gpu_guard.get_gpu_memory_usage", return_value=85):
        assert can_start_training() is False

def test_gpu_guard_allows_when_free():
    """GPU guard allows training when memory is sufficient."""
    with patch("gpu_guard.get_gpu_memory_usage", return_value=30):
        assert can_start_training() is True

def test_auto_annotate_uses_cpu_only():
    """Auto-annotate task explicitly sets device='cpu'."""
    with patch("worker.YOLO") as mock_yolo:
        auto_annotate_image("test_id", "model.pt")
        call_kwargs = mock_yolo.return_value.predict.call_args.kwargs
        assert call_kwargs["device"] == "cpu"
```

---

### T07. Training Job 400 — UI feedback 🟡 HIGH

**Проблема:** 6 неудачных POST /api/training/jobs за 2 мин. UI молчит.

**Файлы:** `Training.tsx` + `training_router.py`

```tsx
// Frontend — показать причину:
const handleTrain = async () => {
    try {
        const res = await api.post('/training/jobs', config);
    } catch (err) {
        if (err.response?.status === 400) {
            const msg = err.response?.data?.detail || 'Ошибка запуска';
            toast.error(msg);
            if (msg.includes('аннотац')) {
                toast.info('💡 Сначала аннотируйте изображения');
            }
        }
    }
};
```

```python
# Backend — понятное сообщение:
if annotation_count == 0:
    raise HTTPException(400, detail=f"Датасет '{name}' не содержит аннотаций. "
                                     f"Разметьте вручную или используйте авто-аннотацию.")
```

**Сложность:** LOW
**Verify:** Тренировка без аннотаций → toast с объяснением

---

### T08. Dataset API polling → debounce 🟡 HIGH

**Проблема:** 14 вызовов GET /api/training/datasets за 3 мин (~каждые 13 сек).

**Файл:** `dashboard/src/pages/Training.tsx`

```tsx
// Было: setInterval(fetchDatasets, 13000)
// Стало:
useEffect(() => {
    fetchDatasets();
    const interval = setInterval(fetchDatasets, 60000);  // 60 сек
    return () => clearInterval(interval);
}, []);
// + обновление после действий (upload, delete, annotate)
```

**Сложность:** LOW
**Verify:** Network tab — datasets poll 1 раз в 60 сек

---

## 🚀 DEPLOY 3 — Training Progress & Deploy

> **Время:** ~1 сессия | **Риск:** 🟡 MEDIUM
> **Файлы:** `training_router.py`, `worker.py`, `Training.tsx`
> **Результат:** Прогресс тренировки в реальном времени + деплой одной кнопкой
> **Rollback:** WS endpoint — новый, откат безопасен. Deploy button — откат = убрать endpoint.

### T09. Training Progress WebSocket (Redis pub/sub) 🔴 CRITICAL

**Проблема:** 9 запросов GET /api/training/ws/progress/{job_id} → 404

> Арх. решение A3: pub/sub вместо polling loop.

**Файлы:** `training_router.py` + `worker.py`

```python
# WebSocket endpoint:
@router.websocket("/training/ws/progress/{job_id}")
async def training_progress_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"training:progress:{job_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
                if data.get("status") in ("completed", "failed"):
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe()

# Worker — publish на каждом epoch:
def on_train_epoch_end(trainer):
    redis.publish(f"training:progress:{job_id}", json.dumps({
        "status": "training",
        "epoch": trainer.epoch,
        "total_epochs": trainer.epochs,
        "loss": float(trainer.loss),
        "progress_pct": round(trainer.epoch / trainer.epochs * 100),
    }))
```

**Сложность:** MEDIUM
**Verify:** Запуск тренировки → WS получает epoch updates → completion event

**🧪 T09-TEST:** `tests/integration/test_training_ws.py`
```python
async def test_ws_receives_epoch_updates(ws_client, redis):
    """WebSocket receives training progress from Redis pub/sub."""
    # Publish mock epoch data
    await redis.publish("training:progress", json.dumps({
        "epoch": 5, "total_epochs": 50, "loss": 0.42
    }))
    msg = await asyncio.wait_for(ws_client.receive_json(), timeout=2.0)
    assert msg["epoch"] == 5
    assert msg["loss"] == 0.42

async def test_ws_receives_completion_event(ws_client, redis):
    """WebSocket receives training completion event."""
    await redis.publish("training:progress", json.dumps({
        "status": "completed", "model_path": "/models/best.pt"
    }))
    msg = await asyncio.wait_for(ws_client.receive_json(), timeout=2.0)
    assert msg["status"] == "completed"
```

---

### T10. Deploy Trained Model 🟡 HIGH

> Совещание (PO): "Как пользователь применяет обученную модель?"

**Файлы:** `training_router.py` + `Training.tsx`

```python
@router.put("/models/deploy")
async def deploy_model(model_path: str = Body(...)):
    # Security: path traversal protection
    base = Path("/app/training_data/models")
    full_path = (base / model_path).resolve()
    if not str(full_path).startswith(str(base.resolve())):
        raise HTTPException(400, "Invalid model path")
    if not full_path.exists():
        raise HTTPException(404, "Model file not found")

    # Копировать + активировать через Redis (A1):
    dest = Path("/app/models") / full_path.name
    shutil.copy2(full_path, dest)

    await redis.set("active_model", json.dumps({
        "file": full_path.name,
        "source": "training",
        "deployed_at": datetime.now().isoformat()
    }))
    await redis.publish("model:changed", full_path.name)

    return {"deployed": full_path.name, "status": "active"}
```

**UI:** Кнопка "🚀 Применить" в списке моделей

**Сложность:** LOW
**Verify:** Обучить → "Применить" → детектор подхватил (лог)

**🧪 T10-TEST:** `tests/integration/test_model_deploy.py`
```python
async def test_deploy_model_updates_redis(client, redis):
    """POST /deploy-model sets active model in Redis."""
    resp = await client.post("/api/deploy-model", json={
        "model_path": "/models/best.pt", "profile_id": "ppe-safety"
    })
    assert resp.status_code == 200
    active = await redis.get("active_model:ppe-safety")
    assert "best.pt" in active

async def test_deploy_model_validates_file_exists(client):
    """Deploy rejects nonexistent model path."""
    resp = await client.post("/api/deploy-model", json={
        "model_path": "/models/nonexistent.pt", "profile_id": "ppe-safety"
    })
    assert resp.status_code == 400

async def test_deploy_model_notifies_detector(client, redis):
    """Deploy publishes notification for detector to reload."""
    # Subscribe to channel, deploy, assert message received
```

---

### T11. Training Job Recovery 🟡 HIGH

> Совещание (Senior Dev): "Job висит 'training' навечно при crash worker-а"

**Файлы:** `worker.py` + `training_router.py`

```python
# Worker — heartbeat каждые 30 сек:
def train_with_heartbeat(job_id, ...):
    heartbeat_key = f"training:heartbeat:{job_id}"

    def heartbeat_callback(trainer):
        redis.setex(heartbeat_key, 90, datetime.now().isoformat())

    model.add_callback("on_train_epoch_end", heartbeat_callback)
    model.add_callback("on_train_batch_end", heartbeat_callback)

# API — проверка zombie jobs:
async def check_job_status(job_id):
    heartbeat = await redis.get(f"training:heartbeat:{job_id}")
    if heartbeat:
        last = datetime.fromisoformat(heartbeat)
        if (datetime.now() - last).seconds > 120:  # 2 мин без heartbeat
            await mark_job_failed(job_id, reason="Worker heartbeat timeout")
            return {"status": "failed", "reason": "Worker crashed"}
```

**UI:** Кнопка "🔄 Повторить" для failed jobs

**Сложность:** MEDIUM
**Verify:** Убить worker → через 2 мин job → "failed" → retry доступен

---

## 🚀 DEPLOY 4 — Class Mapping

> **Время:** ~2 сессии | **Риск:** 🟡 MEDIUM (затрагивает 4 файла в критическом пути)
> **Файлы:** `training_router.py`, `worker.py`, `dataset_downloader.py`, `Training.tsx`, `main.py`
> **Результат:** Правильные имена классов везде
> **Feature flag:** `ENABLE_CLASS_MAPPING=true` (env var). При `false` — классы из data.yaml as-is.
> **Rollback:** Установить `ENABLE_CLASS_MAPPING=false` + restart. Таблица остаётся, но не используется.

### T12. Quick fix: рекурсивный поиск data.yaml 🔴 CRITICAL

**Проблема:** bbox-ы показывают "0", "2" вместо "Helmet", "NoVest"

**Файл:** `services/api/training_router.py:1128`

```python
# Было: только корень
data_yaml_path = dataset_path / "data.yaml"

# Стало: рекурсивный поиск (как в worker.py:305-316)
data_yaml_path = None
for p in dataset_path.rglob("data.yaml"):
    data_yaml_path = p
    break
if not data_yaml_path:
    data_yaml_path = dataset_path / "data.yaml"
```

**Сложность:** LOW
**Verify:** Открыть FS-датасет → bbox-ы: "Helmet", "NoVest" (не числа)

**🧪 T12-TEST:** `tests/unit/test_data_yaml_parser.py`
```python
def test_find_data_yaml_recursive(tmp_path):
    """Finds data.yaml in nested directory structure."""
    nested = tmp_path / "dataset" / "subfolder"
    nested.mkdir(parents=True)
    (nested / "data.yaml").write_text("names:\n  0: Helmet\n  1: NoHelmet")
    result = find_data_yaml(tmp_path / "dataset")
    assert result is not None
    assert "Helmet" in result["names"].values()

def test_data_yaml_class_names_not_indices():
    """Parser returns class names, not numeric indices."""
    yaml_content = "names:\n  0: Helmet\n  1: Vest"
    parsed = parse_data_yaml(yaml_content)
    assert parsed["names"] == {0: "Helmet", 1: "Vest"}

def test_find_data_yaml_missing_returns_none(tmp_path):
    """Returns None when no data.yaml found."""
    assert find_data_yaml(tmp_path) is None
```

---

### T13. Миграция: таблица dataset_class_mappings 🟡 HIGH

**Файл:** `services/api/main.py` → startup migration

```sql
CREATE TABLE IF NOT EXISTS dataset_class_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id TEXT NOT NULL,
    dataset_class_index INT NOT NULL,
    dataset_class_name TEXT NOT NULL,
    profile_class_name TEXT,
    profile_id UUID REFERENCES detection_profiles(id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(dataset_id, dataset_class_index, profile_id)
);
```

**Сложность:** LOW
**Verify:** Таблица создаётся при старте, CRUD работает

---

### T14. Автозаполнение маппинга при загрузке датасета 🟡 HIGH

**Файл:** `services/api/dataset_downloader.py`

При скачивании Roboflow-датасета → парсить data.yaml → INSERT в `dataset_class_mappings`.

**Сложность:** MEDIUM
**Verify:** Скачать датасет → записи маппинга автозаполнены

---

### T15. UI: маппинг классов на Training page 🟡 HIGH

```
Классы датасета:           → Класс профиля:
● Helmet                   → [▼ Каска        ]
● NoHelmet                 → [▼ Без каски    ]
● NoVest                   → [▼ Без жилета   ]
● Vest                     → [▼ Жилет        ]
                              [💾 Сохранить маппинг]
```

**Сложность:** MEDIUM
**Verify:** UI dropdown-ы с классами профиля, маппинг сохраняется в БД

---

### T16. Training Worker: единый маппинг при обучении 🟡 HIGH

**Файл:** `services/training/worker.py:559-560`

При `ENABLE_CLASS_MAPPING=true` + маппинг существует → переиндексировать классы.
Без маппинга → data.yaml as-is + warning.

**Сложность:** HIGH
**Verify:** Обучение с маппингом → модель выдаёт классы профиля

**🧪 T16-TEST:** `tests/unit/test_class_mapping.py`
```python
def test_apply_class_mapping():
    """Class mapping remaps dataset classes to profile classes."""
    mapping = {"Helmet": "hard_hat", "NoHelmet": "no_hard_hat"}
    labels = [("Helmet", 0.5, 0.5, 0.1, 0.1)]
    remapped = apply_class_mapping(labels, mapping)
    assert remapped[0][0] == "hard_hat"

def test_class_mapping_missing_class_raises():
    """Unmapped class raises ValueError."""
    mapping = {"Helmet": "hard_hat"}
    labels = [("Unknown", 0.5, 0.5, 0.1, 0.1)]
    with pytest.raises(ValueError, match="Unknown"):
        apply_class_mapping(labels, mapping)

def test_generate_mapped_data_yaml(tmp_path):
    """Generates data.yaml with profile class names."""
    mapping = {0: "hard_hat", 1: "no_hard_hat"}
    yaml_path = generate_mapped_data_yaml(tmp_path, mapping)
    content = yaml.safe_load(yaml_path.read_text())
    assert content["names"] == {0: "hard_hat", 1: "no_hard_hat"}
```

---

## 🚀 DEPLOY 5 — Profile-Model Binding

> **Время:** ~2 сессии | **Риск:** 🟡 MEDIUM
> **Файлы:** `main.py`, `profiles_router.py`, `detector/main.py`, `Settings.tsx`, `StatsCards.tsx`
> **Результат:** Полная система профилей с мгновенным переключением через Redis
> **Rollback:** Откатить profiles_router.py + detector/main.py. Детектор вернётся к polling файла.

### T17. Миграция таблицы detection_profiles 🟡 HIGH

```sql
ALTER TABLE detection_profiles
  ADD COLUMN IF NOT EXISTS model_path VARCHAR(255) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS model_id VARCHAR(100) DEFAULT NULL;
```

**Сложность:** LOW
**Verify:** Колонки существуют

---

### T18. Обновить seed-данные 🟡 HIGH

Дефолтный профиль PPE → заполнить `model_path`.

**Сложность:** LOW
**Verify:** `SELECT model_path FROM detection_profiles WHERE name = 'PPE Safety'` → не NULL

---

### T19. Data Migration Script 🟡 HIGH

> Совещание (Архитектор): "Нет миграции для существующих данных"

```python
async def migrate_v2_12():
    # 1. Для .pt в /app/models/ → обновить active profile.model_path
    for pt in Path("/app/models").glob("*.pt"):
        await conn.execute(
            "UPDATE detection_profiles SET model_path = $1 "
            "WHERE is_active = true AND model_path IS NULL", pt.name)

    # 2. Для каждого датасета с data.yaml → заполнить class_mappings
    for dataset_dir in Path("/app/datasets").iterdir():
        data_yaml = find_data_yaml(dataset_dir)
        if data_yaml:
            classes = parse_data_yaml(data_yaml)
            for idx, name in enumerate(classes):
                await conn.execute(
                    "INSERT INTO dataset_class_mappings "
                    "(dataset_id, dataset_class_index, dataset_class_name) "
                    "VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                    dataset_dir.name, idx, name)
```

**Сложность:** LOW-MEDIUM
**Verify:** Запуск скрипта → профили получили model_path, датасеты — маппинг

---

### T20. Redis-based Model/Profile Activation 🟡 HIGH

> Арх. решения A1 + A5: Redis вместо файла. Объединяет старые Ф2 + Ф11.2.

**Файлы:** `profiles_router.py` + `detector/main.py`

```python
# API — при активации профиля:
async def activate_profile(profile_id):
    profile = await load_profile(profile_id)

    await redis.set("active_model", json.dumps({
        "file": profile["model_path"],
        "profile_id": str(profile_id),
        "profile_name": profile["name"],
        "activated_at": datetime.now().isoformat()
    }))
    await redis.set("active_profile", json.dumps(profile))
    await redis.publish("model:changed", profile["model_path"])
    await redis.publish("profile:changed", str(profile_id))

# Детектор — подписка (заменяет polling файла + БД):
class Detector:
    _profile_hash: str = ""

    async def subscribe_changes(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("model:changed", "profile:changed")
        async for message in pubsub.listen():
            if message["type"] == "message":
                if message["channel"] == "model:changed":
                    await self.reload_model()
                elif message["channel"] == "profile:changed":
                    await self.reload_profile()
```

**Сложность:** MEDIUM
**Verify:** Активировать профиль → детектор мгновенно подхватывает (лог)

**🧪 T20-TEST:** `tests/integration/test_redis_activation.py` ⭐ CRITICAL
```python
async def test_activate_profile_sets_redis_keys(client, redis):
    """Profile activation atomically sets model + config in Redis."""
    resp = await client.post("/api/profiles/ppe-safety/activate")
    assert resp.status_code == 200
    model = await redis.get("active_model")
    config = await redis.get("active_profile")
    assert model is not None
    assert config is not None

async def test_activate_profile_publishes_event(redis):
    """Activation publishes reload event for detector."""
    pubsub = redis.pubsub()
    await pubsub.subscribe("model:reload")
    await activate_profile("ppe-safety")
    msg = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=2.0)
    assert msg is not None

async def test_activate_profile_atomic_on_failure(redis):
    """If model file missing, neither key is updated (atomic rollback)."""
    old_model = await redis.get("active_model")
    with pytest.raises(Exception):
        await activate_profile("broken-profile")
    assert await redis.get("active_model") == old_model  # unchanged

async def test_concurrent_activation_no_race(redis):
    """Two concurrent activations don't corrupt Redis state."""
    # asyncio.gather(activate("A"), activate("B")) → one wins, state consistent
```

---

### T21. UI: таб «Профили детекции» в Настройках 🟢 MEDIUM

**Файл:** `dashboard/src/pages/Settings.tsx`

```
Табы: [Камеры] [Детектор] [Каталог] [Система] [🆕 Профили]

┌─────────────────────────────────────────────────────┐
│ Профили детекции                    [+ Новый профиль]│
├─────────────────────────────────────────────────────┤
│ ✅ PPE Safety          yolov8_ppe.pt    [Активен]   │
│    Fire Detection      fire_v2.pt       [Активировать]│
│    Custom Model        best.pt          [Активировать]│
└─────────────────────────────────────────────────────┘
```

**Компоненты:**
- `ProfileList.tsx` — список профилей с индикатором активного
- `ProfileCard.tsx` — карточка профиля (название, модель, статус)
- Кнопка активации → `PUT /profiles/{id}/activate` → Redis pub/sub

**Сложность:** MEDIUM
**Verify:** Таб отображается, список профилей, кнопки активации работают

---

### T22. UI: редактор профиля (модалка) 🟢 MEDIUM

**Файл:** `dashboard/src/components/profiles/ProfileEditor.tsx`

```
┌─ Редактировать профиль ─────────────────────────────┐
│ Название:  [PPE Safety                          ]    │
│ Описание:  [Контроль средств индивидуальной...  ]    │
│ Модель:    [▼ Выбрать модель .pt             ]       │
│                                                      │
│ Классы детекции:                                     │
│ ┌────────┬──────────┬─────────┬───────┬──────┐      │
│ │ Класс  │ Название │  Роль   │ Цвет  │  🗑  │      │
│ ├────────┼──────────┼─────────┼───────┼──────┤      │
│ │no_hard │Без каски │violation│ #EF44 │  🗑  │      │
│ └────────┴──────────┴─────────┴───────┴──────┘      │
│                              [+ Добавить класс]      │
│                       [Отмена]  [💾 Сохранить]       │
└─────────────────────────────────────────────────────┘
```

**Логика:**
- Выбор модели → `GET /training/models` (T02) для списка .pt файлов
- Сохранение → `PUT /profiles/{id}` + обновление `model_path`
- Валидация: название обязательно, минимум 1 класс

**Сложность:** MEDIUM
**Verify:** Редактирование → сохранение → данные обновляются в БД и Redis

---

### T23. StatsCards: цвета из профиля 🟢 LOW

**Файл:** `dashboard/src/components/stats/StatsCards.tsx`

**Было:**
```tsx
// idx % 2 === 0 ? 'bg-warning-100' : 'bg-primary-100'  ← чередование
```

**Стало:**
```tsx
// style={{ backgroundColor: `${classConfig.color}20`, color: classConfig.color }}
// Цвет берётся из activeProfile.classes[classId].color
```

**Сложность:** LOW
**Verify:** Карточки окрашены в цвета из профиля, не чередуются

---

### T24. Валидация совместимости профиль ↔ модель 🟢 MEDIUM

**Файлы:** `services/api/profiles_router.py`, `ProfileEditor.tsx`

При активации профиля — проверить что все классы модели покрыты маппингом:

```
⚠️ Модель fire_safety.pt содержит классы [fire, smoke, person],
   но профиль маппит только [fire, smoke].
   Класс "person" будет игнорироваться.
   [Настроить маппинг] [Активировать всё равно]
```

**Backend:**
```python
@router.put("/profiles/{profile_id}/activate")
async def activate_profile(profile_id: int):
    profile = await get_profile(profile_id)
    model_classes = read_model_classes(profile.model_path)
    profile_classes = {c.class_id for c in profile.classes}
    unmapped = set(model_classes) - profile_classes
    if unmapped:
        return {"warning": f"Unmapped classes: {unmapped}", "require_confirm": True}
    # ... activate
```

**Сложность:** MEDIUM
**Verify:** Активация с немаппленными классами → предупреждение, требуется подтверждение

**🧪 T24-TEST:** `tests/unit/test_profile_validation.py`
```python
def test_validate_profile_model_compatible():
    """Compatible profile + model passes validation."""
    profile = {"classes": ["hard_hat", "no_hard_hat"]}
    model_meta = {"classes": ["hard_hat", "no_hard_hat"]}
    assert validate_profile_model_compatibility(profile, model_meta) is True

def test_validate_profile_model_incompatible():
    """Mismatched classes returns validation error."""
    profile = {"classes": ["hard_hat", "vest"]}
    model_meta = {"classes": ["helmet", "no_helmet"]}
    result = validate_profile_model_compatibility(profile, model_meta)
    assert result is False

def test_validate_profile_missing_classes_warns():
    """Profile with unmapped classes produces warning list."""
    profile = {"classes": ["hard_hat", "vest", "gloves"]}
    model_meta = {"classes": ["hard_hat", "vest"]}
    warnings = get_unmapped_class_warnings(profile, model_meta)
    assert "gloves" in warnings

def test_validate_empty_profile_rejected():
    """Profile with no classes is rejected."""
    with pytest.raises(ValueError):
        validate_profile_model_compatibility({"classes": []}, {"classes": ["x"]})
```

---

## 🚀 Deploy 6 — Hardening (T25-T32)

> **Цель:** Безопасность + стабильность + чистые логи
> **Риск: 🟢 LOW** — изолированные исправления, нет изменений в бизнес-логике
> **Откат:** Каждый fix независим — revert отдельного файла

---

### T25. JWT Token Masking в логах 🟡 HIGH

**Проблема:** 27 вхождений полных JWT-токенов в nginx логах

**Файл:** `services/nginx/nginx.conf`

```nginx
map $request_uri $request_masked {
    ~^(?<prefix>.+[?&]token=)[^&]+(?<suffix>.*)$  "${prefix}[MASKED]${suffix}";
    default                                         $request_uri;
}

log_format masked '$remote_addr - $remote_user [$time_local] '
                  '"$request_method $request_masked" $status $body_bytes_sent';

access_log /var/log/nginx/access.log masked;
```

**Сложность:** LOW-MEDIUM
**Verify:** `docker logs nginx` — нет `eyJ...` в URL

**🧪 T25-TEST:** `tests/unit/test_security.py` ⭐ CRITICAL
```python
def test_jwt_masked_in_logs():
    """JWT tokens are masked in log output."""
    raw_log = "GET /ws?token=eyJhbGciOiJIUzI1NiJ9.abc.xyz HTTP/1.1"
    masked = mask_sensitive_data(raw_log)
    assert "eyJ" not in masked
    assert "***" in masked or "[MASKED]" in masked

def test_jwt_masked_in_error_messages():
    """JWT not leaked in error responses."""
    token = "eyJhbGciOiJIUzI1NiJ9.payload.sig"
    error_msg = format_error_response(f"Invalid token: {token}")
    assert token not in error_msg

def test_ws_origin_validation_allows_configured():
    """WebSocket accepts connections from allowed origins."""
    assert validate_ws_origin("https://ppe.local:3000", 
           allowed=["https://ppe.local:3000"]) is True

def test_ws_origin_validation_rejects_unknown():
    """WebSocket rejects connections from unknown origins."""
    assert validate_ws_origin("https://evil.com",
           allowed=["https://ppe.local:3000"]) is False

def test_ws_origin_missing_rejects():
    """WebSocket rejects connections with no origin header."""
    assert validate_ws_origin(None, allowed=["https://ppe.local:3000"]) is False
```

> 📝 **Отложено (после v2.12.0):** Перенос JWT из query string в WebSocket first-frame auth.

---

### T26. WebSocket Origin Validation 🟡 HIGH

**Файл:** `services/api/ws_manager.py`

```python
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

async def accept_websocket(websocket: WebSocket):
    origin = websocket.headers.get("origin", "")
    if origin and origin not in ALLOWED_ORIGINS:
        await websocket.close(code=4003, reason="Origin not allowed")
        return False
    await websocket.accept()
    return True
```

**Сложность:** LOW
**Verify:** WS с чужого origin → 4003, с разрешённого → connect

---

### T27. Redis AOF Rewrite Optimization 🟡 HIGH

**Проблема:** 332 AOF rewrite за 47 минут

**Файл:** `docker-compose.yml`

```yaml
redis:
  command: >
    redis-server
    --save 300 10000
    --auto-aof-rewrite-percentage 200
    --auto-aof-rewrite-min-size 128mb
```

**Сложность:** LOW-MEDIUM
**Verify:** `docker logs redis` — AOF rewrite < 10 раз в час (было ~420)

---

### T28. WebSocket Connection Cleanup 🟢 MEDIUM

**Проблема:** 133 opened / 129 closed = 4 утечки за сессию

**Файл:** `services/api/ws_manager.py`

```python
class ConnectionManager:
    async def monitor_connections(self):
        while True:
            stale = [ws for ws, t in self.connections.items()
                     if time.time() - t > 60]
            for ws in stale:
                await self.disconnect(ws)
            await asyncio.sleep(30)
```

**Сложность:** LOW
**Verify:** Мониторинг 1 час → opened == closed (0 утечек)

---

### T29. HEVC Error Log Reduction 🟢 MEDIUM

**Проблема:** 226 ошибок HEVC за 47 минут

**Файл:** `services/capture/main.py`

```python
_hevc_last_log: dict[str, float] = {}

def log_hevc_error(camera_id: str, error: str):
    now = time.time()
    if now - _hevc_last_log.get(camera_id, 0) > 60:
        logger.warning(f"HEVC error on {camera_id}: {error}")
        _hevc_last_log[camera_id] = now
```

**Сложность:** LOW
**Verify:** Max 6 HEVC warnings в минуту (6 камер × 1)

---

### T30. Camera Reconnect Alerting 🟢 MEDIUM

**Файлы:** `services/capture/main.py`, `dashboard/src/components/Notifications.tsx`

```python
async def on_camera_disconnect(camera_id: str):
    await redis.publish("camera:status", json.dumps({
        "camera_id": camera_id, "status": "disconnected"
    }))
```

**Сложность:** LOW
**Verify:** Отключить камеру → toast «⚠️ cam_2 отключена» → reconnect → «✅ восстановлена»

---

### T31. MinIO Single-Drive Warning 🟢 LOW

**Файл:** `dashboard/src/pages/Settings.tsx` — вкладка System

```
⚠️ Хранилище MinIO работает без резервирования.
   Рекомендуется настроить: mc mirror minio/ppe-data /backup/ --overwrite
```

**Сложность:** LOW
**Verify:** Settings → System → предупреждение отображается

---

### T32. Ultralytics Version Update 🟢 LOW

**Файл:** `services/training/Dockerfile`

```dockerfile
RUN pip install ultralytics==8.4.11
```

> ⚠️ Делать ПОСЛЕ T01 (fix workers=0).

**Сложность:** LOW
**Verify:** `python -c "import ultralytics; print(ultralytics.__version__)"` → 8.4.11

---

## 🚀 Deploy 7 — Cleanup & E2E Tests (T33-T36)

> **Цель:** Чистый код + тестовое покрытие
> **Риск: 🟢 LOW** — косметика + тесты, нет изменений в бизнес-логике
> **Откат:** Не требуется

---

### T33. Удалить hardcoded список классов 🟢 LOW

**Файл:** `services/api/training_router.py:2621-2623`

**Было:**
```python
classes = ["Hardhat", "NO-Hardhat", "Safety Vest", ...]
```

**Стало:**
```python
classes = parse_data_yaml(dataset_path / "data.yaml")["names"]
```

**Сложность:** LOW
**Verify:** `grep -n "Hardhat\|NO-Hardhat\|Safety Vest" training_router.py` → 0

---

### T34. Различать источник аннотаций в UI 🟢 LOW

**Файл:** `dashboard/src/pages/Training.tsx`

Иконки: 🏷️ YOLO .txt | ✏️ ручная | 🤖 авто-детекция

**Сложность:** LOW
**Verify:** UI показывает иконки-индикаторы источника

---

### T35. Показывать реальную статистику разметки 🟢 LOW

**Файл:** `dashboard/src/pages/Training.tsx`

**Было:** «4000/4000 размечено»
**Стало:** «4000 YOLO / 0 ручных / 0 авто»

**Сложность:** LOW
**Verify:** Training page → статистика разбита по источникам

---

### T36. E2E Training Pipeline Test 🟢 MEDIUM

**Файл:** `tests/test_training_pipeline_e2e.py`

```python
async def test_training_pipeline_e2e():
    # 1. Upload 5 test images
    images = await upload_test_images(5)
    # 2. Batch auto-annotate
    task = await api.post(f"/training/datasets/{ds_id}/auto-annotate")
    await wait_for_task(task["task_id"])
    # 3. Verify annotations exist
    for img in images:
        assert await redis.get(f"annotations:{img['id']}") is not None
    # 4. Train 1 epoch
    job = await api.post("/training/jobs", {"dataset_id": ds_id, "epochs": 1})
    # 5. Wait via WebSocket
    progress = await ws_wait_completion(job["id"])
    assert progress["status"] == "completed"
    # 6. Deploy model
    models = await api.get("/training/models")
    await api.put("/models/deploy", {"model_path": models[0]["path"]})
    # 7. Verify detector picked up
    active = json.loads(await redis.get("active_model"))
    assert active["file"] == models[0]["path"]
```

**Сложность:** MEDIUM
**Verify:** Тест проходит green от начала до конца

---

## ═══════════════════════════════════════════════
## ЧАСТЬ 4: РАЗРЕШЁННЫЕ ОТКРЫТЫЕ ВОПРОСЫ
## ═══════════════════════════════════════════════

| # | Вопрос | Решение | Статус |
|---|--------|---------|--------|
| Q1 | GPU sharing: auto-annotate vs detector | CPU-only для auto-annotate (Celery), GPU свободен для детектора | ✅ Решено (T04) |
| Q2 | GPU sharing: training vs detector | Детектор останавливается на время обучения (`training_lock`) | ✅ Решено (T06) |
| Q3 | Feature flags | `ENABLE_CLASS_MAPPING=true/false` в `.env` для Deploy 4 | ✅ Решено (T16) |
| Q4 | MinIO backup | `mc mirror` cron-job + UI warning (T31) | ✅ Решено (T31) |
| Q5 | JWT в WebSocket | Маскирование в v2.12 (T25), first-frame auth — post-v2.12 | ✅ Отложено |

---

## ═══════════════════════════════════════════════
## ЧАСТЬ 5: ANNOTATION DATA FLOW
## ═══════════════════════════════════════════════

```
┌──────────────────────────────────────────────────────────────┐
│                    ANNOTATION LIFECYCLE                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  YOLO .txt (FS-датасеты):                                   │
│    файл .txt → парсинг → data.yaml классы → обучение        │
│    Storage: файловая система                                 │
│                                                              │
│  Redis (catalog + screenshot images):                        │
│    UI canvas → redis key annotations:{id} → export → обучение│
│    Storage: Redis                                            │
│                                                              │
│  Auto-annotate (новое в v2.12):                              │
│    Celery worker (CPU) → YOLO predict → redis → UI review    │
│    Storage: Redis (как ручные)                               │
│                                                              │
│  Class Mapping (новое в v2.12):                              │
│    dataset_class_mappings (PostgreSQL)                        │
│    dataset_class → profile_class при обучении                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## ═══════════════════════════════════════════════
## ЧАСТЬ 6: СВОДНАЯ ТАБЛИЦА ЗАДАЧ
## ═══════════════════════════════════════════════

| # | Задача | Файлы | Сложн. | Deploy | Риск | 🧪 |
|---|--------|-------|--------|--------|------|-----|
| T01 | 🔴 Fix workers=0 | `worker.py` | LOW | D1 | 🟢 | ✅ |
| T02 | 🔴 GET /training/models | `training_router.py` | LOW | D1 | 🟢 | ✅ |
| T03 | 🟡 Fix screenshot deletion | `training_router.py` | LOW | D1 | 🟢 | ✅ |
| T04 | 🔴 Auto-annotate (Celery CPU) | `training_router.py` + `worker.py` | MED | D2 | 🟡 | ⭐ |
| T05 | 🔴 Batch auto-annotate | `training_router.py` + `worker.py` + UI | MED | D2 | 🟡 | — |
| T06 | 🟡 GPU resource guard | `worker.py` | LOW | D2 | 🟢 | ✅ |
| T07 | 🟡 Training 400 feedback | `Training.tsx` + `training_router.py` | LOW | D2 | 🟢 | — |
| T08 | 🟡 Dataset polling debounce | `Training.tsx` | LOW | D2 | 🟢 | — |
| T09 | 🔴 Training progress WS | `training_router.py` + `worker.py` | MED | D3 | 🟡 | ✅ |
| T10 | 🟡 Deploy trained model | `training_router.py` + `Training.tsx` | LOW | D3 | 🟢 | ⭐ |
| T11 | 🟡 Training job recovery | `worker.py` + `training_router.py` | MED | D3 | 🟡 | — |
| T12 | 🔴 Recursive data.yaml | `training_router.py:1128` | LOW | D4 | 🟢 | ✅ |
| T13 | 🟡 Миграция class_mappings | `main.py` (migration) | LOW | D4 | 🟢 | — |
| T14 | 🟡 Автозаполнение маппинга | `dataset_downloader.py` | MED | D4 | 🟡 | — |
| T15 | 🟡 UI маппинг классов | `Training.tsx` | MED | D4 | 🟢 | — |
| T16 | 🟡 Worker unified mapping | `worker.py` | HIGH | D4 | 🟡 | ⭐ |
| T17 | 🟡 ALTER TABLE model_path | `main.py` | LOW | D5 | 🟢 | — |
| T18 | 🟡 Seed данные | `main.py` | LOW | D5 | 🟢 | — |
| T19 | 🟡 Data migration .pt | скрипт | LOW-MED | D5 | 🟡 | — |
| T20 | 🟡 Redis activation pub/sub | `profiles_router.py` + `detector` | MED | D5 | 🟡 | ⭐ |
| T21 | 🟢 UI таб Профили | `Settings.tsx` | MED | D5 | 🟢 | — |
| T22 | 🟢 Редактор профиля | `ProfileEditor.tsx` | MED | D5 | 🟢 | — |
| T23 | 🟢 StatsCards цвета | `StatsCards.tsx` | LOW | D5 | 🟢 | — |
| T24 | 🟢 Валидация совместимости | `profiles_router.py` + UI | MED | D5 | 🟢 | ✅ |
| T25 | 🟡 JWT masking | `nginx.conf` + `main.py` | LOW-MED | D6 | 🟢 | ⭐ |
| T26 | 🟡 WS origin validation | `ws_manager.py` | LOW | D6 | 🟢 | (в T25) |
| T27 | 🟡 Redis AOF optimization | `docker-compose.yml` | LOW-MED | D6 | 🟢 | — |
| T28 | 🟢 WS connection cleanup | `ws_manager.py` | LOW | D6 | 🟢 | — |
| T29 | 🟢 HEVC log reduction | `capture/main.py` | LOW | D6 | 🟢 | — |
| T30 | 🟢 Camera reconnect alerts | `capture/main.py` + frontend | LOW | D6 | 🟢 | — |
| T31 | 🟢 MinIO warning | `Settings.tsx` | LOW | D6 | 🟢 | — |
| T32 | 🟢 Ultralytics 8.4.11 | `Dockerfile` | LOW | D6 | 🟢 | — |
| T33 | 🟢 Удалить hardcoded классы | `training_router.py` | LOW | D7 | 🟢 | — |
| T34 | 🟢 Источник аннотаций | `Training.tsx` | LOW | D7 | 🟢 | — |
| T35 | 🟢 Статистика разметки | `Training.tsx` | LOW | D7 | 🟢 | — |
| T36 | 🟢 E2E training test | тесты | MED | D7 | 🟢 | ⭐ |

**Легенда 🧪:** ⭐ = обязательный тест (5 минимально необходимых), ✅ = рекомендованный тест, — = ручная проверка достаточна

---

## ═══════════════════════════════════════════════
## ЧАСТЬ 7: ЗАВИСИМОСТИ И СТАТУС
## ═══════════════════════════════════════════════

| Компонент | Статус | Действие |
|-----------|--------|----------|
| Детектор hot reload | ✅ работает | → Redis pub/sub (T20) |
| API CRUD профилей | ✅ 15 endpoints | + model_path (T17) |
| Hook useProfile() | ✅ работает | Не трогать |
| Dashboard (4 стр.) | ✅ подключены | Не трогать |
| Redis | ✅ работает | AOF tuning (T27) |
| Celery worker | ✅ работает | Fix workers=0 (T01) |
| WebSocket | ✅ базовая | + progress (T09) + origin (T26) |
| Auto-annotate | ❌ 501 | Implement (T04-T05) |
| Model deploy | ❌ ручной | Implement (T10) |
| Job recovery | ❌ нет | Implement (T11) |
| Class mapping | ❌ разорван | Implement (T12-T16) |
| Nginx logging | ⚠️ JWT plain | Fix (T25) |
| WS origin check | ⚠️ нет | Fix (T26) |

**НЕ трогать:** useProfile.ts, страницы (Мониторинг/Аналитика/Обучение/Журнал), Docker base images, PostgreSQL (кроме миграций T13, T17), MinIO config

---

## ═══════════════════════════════════════════════
## ЧАСТЬ 8: ТАЙМЛАЙН
## ═══════════════════════════════════════════════

| Deploy | Задачи | Сессии | Ориентир | Checkpoint |
|--------|--------|--------|----------|------------|
| **D1** Training Unblock | T01-T03 | 1 (30 мин) | День 1 | `v2.12.0-d1` |
| **D2** Smart Annotation | T04-T08 | 2 | День 2-3 | `v2.12.0-d2` |
| **D3** Progress & Deploy | T09-T11 | 2 | День 4-5 | `v2.12.0-d3` |
| **D4** Class Mapping | T12-T16 | 2 | День 6-7 | `v2.12.0-d4` |
| **D5** Profile-Model | T17-T24 | 2-3 | День 8-10 | `v2.12.0-d5` |
| **D6** Hardening | T25-T32 | 1 | День 11 | `v2.12.0-d6` |
| **D7** Cleanup & Tests | T33-T36 | 1 | День 12 | `v2.12.0-final` |
| | **Итого** | **10-12** | **~12 дней** | |

### Быстрый старт (Deploy 1 — 30 минут)

```bash
# 1. worker.py — workers=4 → workers=0 (1 строка)
# 2. training_router.py — добавить GET /training/models
# 3. training_router.py — fix delete_image fallback
# 4. docker-compose build --no-cache ppe_training ppe_api
# 5. docker-compose up -d
# 6. Тест: запустить тренировку → завершается без crash
```

---

## ═══════════════════════════════════════════════
## ЧАСТЬ 9: СТАТИСТИКА
## ═══════════════════════════════════════════════

| Метрика | Значение |
|---------|----------|
| Всего деплоев | **7** |
| Всего задач | **36** |
| 🔴 CRITICAL | **6** (T01, T02, T04, T05, T09, T12) |
| 🟡 HIGH | **11** |
| 🟢 MEDIUM | **19** |
| Архитектурных решений | **8** (A1-A8) |
| 🧪 Встроенных тестов | **12** (из них 5 обязательных ⭐) |
| Оценка сессий | **11-14** (с тестами) |

| Источник проблем | Найдено |
|------------------|---------|
| UI-анализ скриншотов | 7 проблем |
| Class mapping исследование | 6 задач |
| Логи production #1 (6644 строки) | 8 проблем |
| Логи production #2 (1193 строки) | 8 проблем |
| Совещание 6 ролей | +7 задач |
| QA review (test gap analysis) | +12 тестов |
| **Итого** | **39 проблем → 36 задач + 12 тестов** |

### 🧪 Тестовые файлы (создаются в процессе)

```
tests/
├── unit/
│   ├── test_celery_worker.py         # T01-TEST
│   ├── test_auto_annotate.py         # T04-TEST
│   ├── test_gpu_guard.py             # T06-TEST
│   ├── test_data_yaml_parser.py      # T12-TEST
│   ├── test_class_mapping.py         # T16-TEST
│   ├── test_profile_validation.py    # T24-TEST
│   └── test_security.py             # T25-TEST
├── integration/
│   ├── test_training_api.py          # T02-TEST
│   ├── test_screenshot_deletion.py   # T03-TEST
│   ├── test_auto_annotate_api.py     # T04-TEST
│   ├── test_training_ws.py           # T09-TEST
│   ├── test_model_deploy.py          # T10-TEST
│   └── test_redis_activation.py      # T20-TEST
└── e2e/
    └── test_training_pipeline.py     # T36
```

---

*Документ: PLAN_v2.12.0_FINAL.md*
*Версия: 2.1 (+ Test Strategy, QA review)*
*Дата: 2026-02-04*
