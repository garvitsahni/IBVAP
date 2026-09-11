# Task 1: Install Dependencies + Download Models — Report

## What I Implemented

1. **requirements.txt** — Added `onnxruntime>=1.17.0` and `scikit-image>=0.22.0` under a new "Re-ID / Embeddings" section.

2. **models/osnet_ain_x1_0.onnx** — Stub ONNX model for person Re-ID (256-dim embeddings). The OSNet download from GitHub failed (404), so a functional stub was created per the task instructions.

3. **models/vehicle_reid_stub.onnx** — Stub ONNX model for vehicle Re-ID (512-dim embeddings), as specified.

Both stubs use GlobalAveragePool → Reshape → MatMul, producing correct output shapes:
- Person Re-ID: input `[batch, 3, 256, 128]` → output `[batch, 256]`
- Vehicle Re-ID: input `[batch, 3, 256, 128]` → output `[batch, 512]`

## Installed Packages

- `onnxruntime` 1.30.0
- `scikit-image` 0.26.0
- `onnx` 1.22.0 (transient, needed to create stub models)

## Test Results

All 41 existing tests pass — no regressions.

```
41 passed, 2 warnings in 18.80s
```

Warnings are pre-existing (Starlette deprecation, pytest asyncio_mode config).

## TDD Evidence

Not applicable — this task did not require TDD.

## Files Changed

| File | Action |
|------|--------|
| `requirements.txt` | Modified — added 2 dependencies |
| `models/osnet_ain_x1_0.onnx` | Created — person Re-ID stub |
| `models/vehicle_reid_stub.onnx` | Created — vehicle Re-ID stub |

## Self-Review Findings

- The `onnx` package was installed to create the stub models but was **not** added to `requirements.txt` since it is not needed at runtime (only `onnxruntime` is needed to load/infer). If model creation/validation is needed in future code, `onnx` should be added then.
- OSNet download failed from the URL in the task brief; the stub is functional and loadable by onnxruntime.
- No concerns about correctness.

## Commit

- `b540415` — Phase 2: add onnxruntime, scikit-image dependencies and model directory
