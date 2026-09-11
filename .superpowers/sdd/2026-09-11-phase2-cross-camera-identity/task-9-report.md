# Task 9 Report: API Routes — Footprint Write + Camera Health

**Status:** DONE

## Summary

Implemented two new API endpoints:
1. **POST /api/v1/footprint** — Writes footprint entries with hash chain linkage via `FootprintChainWriter`
2. **GET /api/v1/cameras/health** — Returns camera health status from in-memory `CameraHealthStore`

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `fusion_server/api/footprint.py` | Modified | Added `FootprintWriteRequest`, `FootprintWriteResponse` models and POST endpoint |
| `fusion_server/api/routes/__init__.py` | Created | Package init for routes subdirectory |
| `fusion_server/api/routes/cameras.py` | Created | Camera health GET endpoint with module-level `CameraHealthStore` singleton |
| `fusion_server/main.py` | Modified | Registered `cameras.router` |
| `tests/test_api_phase2.py` | Created | TDD tests for both endpoints |

## Implementation Details

### POST /api/v1/footprint
- Request body: `object_id`, `camera_id`, `timestamp`, `event_type`, optional `detection_event_id`
- Uses `FootprintChainWriter.write_entry()` for hash chain linkage
- Returns 201 with created entry, or 409 if entry skipped (duplicate within time window)
- Follows existing patterns from `events.py` and `alerts.py`

### GET /api/v1/cameras/health
- Returns `Dict[str, Dict[str, Any]]` — all camera health data
- Uses module-level `CameraHealthStore` singleton (in-memory, no DB)
- Returns 200 with empty dict `{}` when no cameras have reported yet

## Test Results

```
tests/test_api_phase2.py::test_footprint_write_endpoint PASSED
tests/test_api_phase2.py::test_camera_health_endpoint PASSED

Full suite: 67 passed, 0 failed
```

## Commit

```
a271d57 Phase 2: add footprint write endpoint and camera health API
```

## Design Notes

- The `CameraHealthStore` is a module-level singleton since it's in-memory (not DB-backed). This is appropriate for the current design where camera workers push health updates via a separate mechanism.
- The POST endpoint returns 409 Conflict when `FootprintChainWriter` skips an entry due to the same-camera time window constraint (30s default). This gives callers clear feedback that the write was intentionally skipped, not an error.
- The cameras router lives in `fusion_server/api/routes/` to establish the sub-route pattern for future camera-specific endpoints (e.g., `GET /api/v1/cameras/{camera_id}/health`).
