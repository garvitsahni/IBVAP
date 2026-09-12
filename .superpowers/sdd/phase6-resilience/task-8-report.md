# Task 8 Report: Resilience Aggregator + System Health API

**Status:** DONE

## What was implemented

### ResilienceAggregator (`fusion_server/services/resilience_aggregator.py`)
- Collects signals from all monitors (camera offline, detection tier, power mode, ledger status)
- Computes unified system health status: `ok` | `degraded` | `critical`
- Status priority logic:
  - `critical`: detection tier critical, ledger gap, power critical, or 2+ cameras offline
  - `degraded`: non-normal detection tier, non-normal power mode, or 1 camera offline
  - `ok`: all signals nominal
- Provides `get_health()` returning full health dict with all signal details

### System Health API (`fusion_server/api/routes/system.py`)
- `GET /api/v1/system/health` — returns aggregated system health
- Returns `{"status": "unknown", "error": "aggregator not initialized"}` if startup hasn't completed

### Router Registration (`fusion_server/main.py`)
- Added `system_router` import and `include_router` call
- Added `ResilienceAggregator` initialization in lifespan startup

## Tests
- 7/7 passing: initialization, camera offline degradation, detection critical, power reduced, ledger gap, multi-signal aggregation, recovery

## Files
- Created: `fusion_server/services/resilience_aggregator.py`
- Created: `fusion_server/api/routes/system.py`
- Modified: `fusion_server/main.py`
- Created: `tests/test_resilience_aggregator.py`
