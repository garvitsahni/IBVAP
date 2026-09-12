# Task 1: Heartbeat Endpoint + CameraHealthStore Update — Report

## Status: DONE

## What I Implemented

Added three new methods to `CameraHealthStore` and one new API endpoint:

1. **`heartbeat(camera_id)`** — Records a `last_seen` timestamp. If the camera already exists, only updates `last_seen`. If unknown, creates a new entry with `status: "unknown"` and the timestamp.
2. **`get_last_seen(camera_id)`** — Returns the `last_seen` datetime, or `None` for unknown cameras.
3. **`is_stale(camera_id, threshold_seconds=60)`** — Returns `True` if the camera hasn't heartbeat within the threshold. Unknown cameras are treated as stale.
4. **`POST /api/v1/cameras/{camera_id}/heartbeat`** — Edge workers call this to report liveness. Returns `{"camera_id": ..., "status": "ok"}`.

## Files Changed

- `fusion_server/services/camera_health_store.py` — Added `heartbeat()`, `get_last_seen()`, `is_stale()`
- `fusion_server/api/routes/cameras.py` — Added `POST /{camera_id}/heartbeat` endpoint
- `tests/test_camera_heartbeat.py` — 6 new tests (created)

## Tests

6 new tests, all passing:
- `test_heartbeat_updates_last_seen` — Verifies `last_seen` is set to current time
- `test_heartbeat_does_not_overwrite_health` — Verifies existing health fields preserved
- `test_is_stale_returns_false_when_recent` — Recent heartbeat → not stale
- `test_is_stale_returns_true_when_old` — Stale heartbeat → stale
- `test_is_stale_unknown_camera` — Unknown camera → stale
- `test_get_last_seen_unknown_camera` — Unknown camera → `None`

Full suite: 282 collected, 268 passed, 8 skipped, 6 failed (all pre-existing YOLO corruption issues). No regressions.

## Commit

- `dfe603d` — feat: add camera heartbeat endpoint and staleness detection

## Self-Review Findings

- Clean implementation matching task spec exactly
- `heartbeat()` correctly preserves existing health data via dict key update
- `is_stale()` treats unknown cameras as stale (correct safety default)
- No security concerns — no secrets logged, no new external calls
- Follows existing code conventions (same style as `update()`, `get()`)
