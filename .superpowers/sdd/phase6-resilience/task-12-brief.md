# Task 12: Final Verification + Cleanup

**Files:**
- Modify: `fusion_server/main.py` (startup hooks)

**Interfaces:**
- All monitors initialized and started on server startup
- All SSE broadcasts wired

## Steps

### Step 1: Wire all monitors into main.py startup

Edit `fusion_server/main.py` — in the startup event, after database init, add:

```python
from fusion_server.services.camera_offline_monitor import CameraOfflineMonitor
from fusion_server.services.detector_fallback import DetectorFallback
from fusion_server.services.ledger_checkpoint import LedgerCheckpoint
from fusion_server.services.clip_checkpoint import ClipCheckpoint
from fusion_server.services.power_manager import PowerManager
from fusion_server.services.resilience_aggregator import ResilienceAggregator
from fusion_server.api.routes.system import set_aggregator

# Initialize checkpoint services
ledger_cp = LedgerCheckpoint()
clip_cp = ClipCheckpoint()

# Resume ledger from checkpoint
ledger_status = ledger_cp.resume()
logger.info(f"Ledger checkpoint: {ledger_status}")

# Scan for orphaned clips
orphans = clip_cp.scan_orphans()
if orphans:
    logger.warning(f"Found {len(orphans)} orphaned clip(s): {orphans}")

# Initialize aggregator
aggregator = ResilienceAggregator()
aggregator.update_ledger_status(ledger_status.get("status", "ok"))
set_aggregator(aggregator)

# Initialize monitors (will be started by their respective owners)
detector_fallback = DetectorFallback()
power_manager = PowerManager()
```

**IMPORTANT:** Read `fusion_server/main.py` FIRST to understand the existing startup structure. Place the new code in the existing `lifespan` or `startup` function, NOT as a duplicate.

### Step 2: Run full test suite one final time

Run: `pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: all tests pass (except the 6 pre-existing failures from corrupted model / pgvector in SQLite)

### Step 3: Build dashboard

Run: `cd dashboard; npm run build 2>&1 | tail -5`
Expected: build succeeds

### Step 4: Final commit

```bash
git add fusion_server/main.py
git commit -m "feat: wire all Phase 6 resilience monitors into server startup"
```
