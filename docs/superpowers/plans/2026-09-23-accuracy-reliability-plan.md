# Accuracy & Reliability Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace three random-weight models with real trained weights, prove accuracy with measured gates, and harden runtime reliability — GPU-primary (RTX 4050, CUDA 12.7), CPU fallback always.

**Architecture:** All runtime inference stays ONNX (onnxruntime-gpu with CUDAExecutionProvider → CPUExecutionProvider fallback). One-time exports run on CPU torch. No training in this plan — public pretrained weights only. Deterministic alert path, sync ledger, and frozen contracts unchanged (additive only).

**Tech Stack:** Python 3.13, onnxruntime-gpu, torch (CPU export) + torchreid, ultralytics (YOLOv8n baseline, v8m benchmark), insightface (ArcFace, already real), Market-1501 / VeRi-776 / public plate samples for eval, pytest.

## Global Constraints

- Backend FastAPI Python only.
- GPU-primary, CPU fallback: every ONNX service resolves providers at runtime and logs the active one loudly.
- No cloud API for core; all weights local in models/ with SHA manifest.
- Ledger write stays synchronous/blocking; enrichment/C2 never block fired delivery.
- ARCHITECTURE.md Section 5 frozen; additive-only changes with doc update in same PR.
- Template enrichment output stays labeled [TEMPLATE]; eval gates must pass on real measured numbers, never hardcoded.

---

### Task 1: Shared GPU provider helper + startup model verify

**Files:**
- Create: `edge/model_runtime.py`
- Modify: `edge/reid_service.py`, `edge/plate_detector.py`, `edge/face_embedding.py` (use helper)
- Modify: `scripts/download_models.py` (add `--verify` mode: hash + smoke inference per model)
- Test: `tests/test_model_runtime.py`

**Interfaces:**
- Consumes: nothing new (stdlib + onnxruntime).
- Produces: `resolve_providers(prefer_gpu: bool = True) -> list[str]`; `create_session(path: str, prefer_gpu: bool = True) -> ort.InferenceSession` (logs active provider, raises RuntimeError with loud message if file missing/corrupt); `verify_model(path, dummy_shape) -> dict` (loads + times one dummy inference).

- [ ] **Step 1: Write the failing test**

```python
def test_resolve_providers_prefers_cuda_when_available(monkeypatch):
    import edge.model_runtime as mr
    monkeypatch.setattr(mr.ort, "get_available_providers",
                        lambda: ["CPUExecutionProvider", "CUDAExecutionProvider"])
    assert mr.resolve_providers()[0] == "CUDAExecutionProvider"

def test_resolve_providers_falls_back_to_cpu(monkeypatch):
    import edge.model_runtime as mr
    monkeypatch.setattr(mr.ort, "get_available_providers",
                        lambda: ["CPUExecutionProvider"])
    assert mr.resolve_providers() == ["CPUExecutionProvider"]

def test_create_session_missing_file_raises(tmp_path):
    import edge.model_runtime as mr
    try:
        mr.create_session(str(tmp_path / "nope.onnx"))
        assert False, "should have raised"
    except RuntimeError as e:
        assert "nope.onnx" in str(e)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model_runtime.py -v`
Expected: FAIL with "No module named 'edge.model_runtime'" (or collection error)

- [ ] **Step 3: Write minimal implementation** (`edge/model_runtime.py`, ~70 lines: resolve/create_session/verify_model + logging, no other behavior)
- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_model_runtime.py tests/test_reid_service.py -v`
Expected: PASS (excluding pre-existing `_preprocess_crop` signature failure, which is out of scope)

- [ ] **Step 5: Commit**

```bash
git add edge/model_runtime.py tests/test_model_runtime.py edge/reid_service.py edge/plate_detector.py edge/face_embedding.py scripts/download_models.py
git commit -m "feat: GPU-primary ONNX runtime helper with loud fallback"
```

### Task 2: OSNet pretrained=True re-export + Rank-1 gate

**Files:**
- Modify: `scripts/download_models.py` (`pretrained=True`, hash-pin, keep `.bak` of old file)
- Modify: `edge/reid_service.py` (use `model_runtime.create_session`)
- Create: `scripts/eval_accuracy.py` (person Rank-1 on Market-1501 sample)
- Test: `tests/test_eval_gates.py` (gate: Rank-1 >= 0.80 on bundled sample + cam1→cam2 match test)

**Interfaces:**
- Consumes: `edge.model_runtime.create_session`; torchreid Market-1501 weights (downloaded by torchreid).
- Produces: `models/osnet_ain_x1_0.onnx` (real weights); `eval_accuracy.py::eval_person_reid() -> dict` with `rank1` key.

- [ ] **Step 1: Write the failing test** (gate asserts rank1 >= 0.80 on a fixed 50-identity Market-1501 sample script downloads once to data/eval/)
- [ ] **Step 2: Run test to verify it fails** (random-weight model scores ~chance)
- [ ] **Step 3: Re-export with pretrained=True, back up old weights to .bak**
- [ ] **Step 4: Run gate to verify it passes**
- [ ] **Step 5: Commit** (`git commit -m "fix: real Market-1501 OSNet weights for person re-ID"`)

### Task 3: Vehicle Re-ID real VeRi-776 head weights + gate

**Files:**
- Modify: `scripts/download_models.py` (load public VeRi-776 ResNet50 checkpoint into VehicleReID head before export; record URL+SHA in manifest)
- Create: eval `eval_vehicle_reid() -> dict` (Rank-1 >= 0.70 on VeRi-776 sample)
- Test: extend `tests/test_eval_gates.py`

Same red-green-commit cycle as Task 2.

### Task 4: Real plate-detector ONNX + precision gate + YOLO benchmark

**Files:**
- Modify: `scripts/download_models.py` (public YOLOv8-LP .pt → ONNX 320x320; keep service I/O unchanged)
- Create: eval `eval_plate_detector()` (precision >= 0.85 @ IoU 0.5) + `scripts/bench_yolo.py` (v8n vs v8m FPS on GPU/CPU over footage/cam1.mp4)
- Test: extend `tests/test_eval_gates.py`; benchmark report committed to `docs/`

Same red-green-commit cycle. If v8m holds real-time on RTX 4050, set it as GPU-tier default via `YOLO_MODEL` env (v8n stays CPU fallback).

### Task 5: Latency guard, SHA manifest, docs, full verify

**Files:**
- Create: `models/MANIFEST.json` (file, sha256, source URL, eval score per model)
- Modify: edge services (inference latency log + `reduced_accuracy_mode` signal when p95 > budget)
- Modify: `ARCHITECTURE.md` (model table: real weights + measured scores)
- Test: full suite `pytest tests/ -q`

- [ ] Run full suite, record raw results; pre-existing env failures (missing pkgs) triaged, never hidden.
- [ ] Commit (`git commit -m "chore: model manifest, latency guard, arch docs"`)
