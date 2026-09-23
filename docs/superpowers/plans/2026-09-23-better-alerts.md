# Better Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every IBVAP alert something you can see, hear, trust, and act on: no duplicate floods, deterministic plain-text reasons, snapshot images, working acknowledge/escalate/false-positive actions, a master–detail alerts page, and an in-page banner + beep when alerts fire.

**Architecture:** Backend first — a deterministic `CooldownGate` (plain dict + lock, no ML) gates alert creation before the ledger write; new `reason_detail` text is generated at fire time; edge nodes attach an optional base64 JPEG thumbnail (≤640px, at most 1/second per camera) to events, fusion decodes it to `storage/alerts/{alert_id}.jpg` after the alert is committed and broadcast; status lifecycle gains `escalated`/`false_positive` (requires a SQLite CHECK-constraint table rebuild in `init_db`). Frontend second — shared alert-mapping lib, enriched feed rows, persistent master–detail layout with filters, and an app-shell banner + Web-Audio beep.

**Tech Stack:** Python/FastAPI/SQLAlchemy (venv `.\venv\Scripts\python.exe`), pytest (asyncio_mode=auto), React+TS+Vite (no FE test runner — verify with `npm run build` + manual checklist), SQLite dev DB `ibvap.db`, OpenCV for JPEG encode.

## Global Constraints

- AGENTS.md Rule 1: only `fusion_server/core/rule_engine.py` (deterministic) decides alerts fire; `CooldownGate`/`reason_detail` are plain logic — never ML.
- AGENTS.md Rule 2: no raw video crosses edge→fusion; the `snapshot` field is ONE still JPEG ≤640px, event-triggered (≤1 attach/second) — strictly less than the already-allowed short clips.
- AGENTS.md Rule 3: ledger write stays synchronous/blocking; cooldown gate runs BEFORE the DB insert, never after.
- AGENTS.md Rule 4: snapshot file write + AI enrichment are post-broadcast, best-effort; alert delivery never waits on them.
- AGENTS.md Rule 5: ARCHITECTURE.md §5 changes (DetectionEvent `snapshot`, Alert `reason_detail`/`snapshot_path`/`plate_text`, status enum) must be edited in the same tasks that change the code, with a dated FLAGGED note (copy the style of the existing 2026-09-23 bbox flag at ARCHITECTURE.md:172).
- Shell is PowerShell: `;` not `&&`; no heredocs — use the write/edit tools for file content. Run everything from project root `C:\Users\Garvi\Desktop\Projects\IBVAP` unless a step says otherwise.
- Pytest: `.\venv\Scripts\python.exe -m pytest <path> -v` from project root. Dashboard build: `npm run build` with `workdir=dashboard`.
- Working tree has UNRELATED dirty files (`fusion_server/api/routes/detect.py`, `dashboard/src/components/camera/*`, `edge/plate_detector.py`, `scripts/eval_accuracy.py`, `tests/test_eval_gates.py`, `tests/test_plate_services.py`, `tests/test_detect_plate_speed.py` untracked). NEVER `git add -A` — stage only the exact files each task lists.
- Spec: `docs/superpowers/specs/2026-09-23-better-alerts-design.md`. Design clarifications made while planning (supersede spec wording): status transitions allowed from `fired | enriched | acknowledged | escalated`; only `false_positive` is terminal (400 on any further transition). Cooldown re-arm is per-ROI (leaving one ROI does not re-arm another).
- Commits happen only in a task's commit step; messages match repo style (`feat:`/`fix:`/`docs:`).

---

### Task 1: CooldownGate module (deterministic dedup)

**Files:**
- Create: `fusion_server/services/cooldown_gate.py`
- Test: `tests/test_cooldown_gate.py`

**Interfaces:**
- Consumes: nothing (stdlib only: `time`, `threading`).
- Produces (Tasks 2–3 depend on these EXACT signatures):
  - `get_cooldown_gate() -> CooldownGate` — process-wide singleton.
  - `CooldownGate.should_fire(camera_id: str, object_id: str, reason_key: str, violating: bool, now: float) -> bool`
  - `CooldownGate.update_presence(camera_id: str, object_id: str, violating_rois: set) -> None`
  - `CooldownGate.reset() -> None`
  - `CooldownGate.COOLDOWN_SECONDS: float = 60.0`
  - Key format: `(camera_id, object_id, reason_key)`. ROI callers pass `reason_key=f"roi:{roi_name}"`; the watchlist caller passes `reason_key="watchlist_match"`.
  - Semantics: `violating=False` → deactivate key, return False. `violating=True` → fire if key is fresh (no state, or deactivated by absence/`update_presence`) OR `now - last_fired >= 60`. `update_presence` deactivates every `roi:*` key of that object not in `violating_rois` (non-`roi:` keys untouched → watchlist is time-only cooldown).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cooldown_gate.py`:

```python
"""CooldownGate: deterministic alert dedup (no ML) — first fire, 60s cooldown,
per-ROI re-arm on absence, independent keys."""
import pytest

from fusion_server.services.cooldown_gate import CooldownGate, get_cooldown_gate


@pytest.fixture
def gate():
    return CooldownGate()


def test_first_fire_allowed(gate):
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1000.0) is True


def test_repeat_within_cooldown_blocked(gate):
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1000.0) is True
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1010.0) is False
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1059.0) is False


def test_refires_after_60s_while_still_inside(gate):
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1000.0) is True
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1060.0) is True


def test_absence_then_reentry_refires_immediately(gate):
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1000.0) is True
    gate.update_presence("cam1", "obj1", violating_rois=set())  # left every ROI
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1005.0) is True


def test_leaving_one_roi_does_not_rearm_another(gate):
    assert gate.should_fire("cam1", "obj1", "roi:A", violating=True, now=1000.0) is True
    assert gate.should_fire("cam1", "obj1", "roi:B", violating=True, now=1001.0) is True
    # Still inside B only → A deactivates, B stays active
    gate.update_presence("cam1", "obj1", violating_rois={"B"})
    assert gate.should_fire("cam1", "obj1", "roi:B", violating=True, now=1002.0) is False
    assert gate.should_fire("cam1", "obj1", "roi:A", violating=True, now=1003.0) is True


def test_keys_are_independent_per_object_and_camera(gate):
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1000.0) is True
    assert gate.should_fire("cam1", "obj2", "roi:Zone A", violating=True, now=1000.0) is True
    assert gate.should_fire("cam2", "obj1", "roi:Zone A", violating=True, now=1000.0) is True


def test_watchlist_key_is_time_only_cooldown(gate):
    assert gate.should_fire("cam1", "obj1", "watchlist_match", violating=True, now=1000.0) is True
    # update_presence must NOT deactivate non-roi keys
    gate.update_presence("cam1", "obj1", violating_rois=set())
    assert gate.should_fire("cam1", "obj1", "watchlist_match", violating=True, now=1030.0) is False
    assert gate.should_fire("cam1", "obj1", "watchlist_match", violating=True, now=1060.0) is True


def test_singleton():
    a = get_cooldown_gate()
    b = get_cooldown_gate()
    assert a is b
    a.reset()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_cooldown_gate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fusion_server.services.cooldown_gate'`

- [ ] **Step 3: Write minimal implementation**

Create `fusion_server/services/cooldown_gate.py`:

```python
"""
CooldownGate — deterministic alert dedup (AGENTS.md Rule 1: no ML).

Fires an alert at most once per (camera_id, object_id, reason_key) per
COOLDOWN_SECONDS, and re-arms an ROI key immediately when the object is
observed outside that ROI (update_presence with the current tick's
violating ROI set). Watchlist keys have no ROI presence signal, so they
use the pure 60s time cooldown.

Module-level singleton: AlertPipeline is constructed per request, the
gate must outlive it. Thread-safe (ingestion runs in the threadpool).
"""
import threading
from typing import Dict, Set, Tuple


class CooldownGate:
    COOLDOWN_SECONDS = 60.0

    def __init__(self):
        self._lock = threading.Lock()
        self._state: Dict[Tuple[str, str, str], Dict] = {}

    def should_fire(
        self,
        camera_id: str,
        object_id: str,
        reason_key: str,
        violating: bool,
        now: float,
    ) -> bool:
        key = (camera_id, object_id, reason_key)
        with self._lock:
            st = self._state.get(key)
            if not violating:
                if st is not None:
                    st["active"] = False
                return False
            if st is None:
                self._state[key] = {"active": True, "last_fired": now}
                return True
            fresh = not st["active"]
            if fresh or (now - st["last_fired"] >= self.COOLDOWN_SECONDS):
                st["active"] = True
                st["last_fired"] = now
                return True
            return False

    def update_presence(
        self, camera_id: str, object_id: str, violating_rois: Set[str]
    ) -> None:
        with self._lock:
            for (cam, obj, reason_key), st in self._state.items():
                if cam != camera_id or obj != object_id:
                    continue
                if not reason_key.startswith("roi:"):
                    continue  # watchlist etc. — time-only cooldown
                roi_name = reason_key[len("roi:"):]
                if roi_name not in violating_rois:
                    st["active"] = False

    def reset(self) -> None:
        with self._lock:
            self._state.clear()


_GATE = CooldownGate()


def get_cooldown_gate() -> CooldownGate:
    return _GATE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_cooldown_gate.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```powershell
git add fusion_server/services/cooldown_gate.py tests/test_cooldown_gate.py
git commit -m "feat: deterministic CooldownGate — per-object/ROI alert dedup with 60s cooldown and exit re-arm"
```

---

### Task 2: Wire cooldown into pipeline + watchlist (the 525-alert flood fix)

**Files:**
- Modify: `fusion_server/services/alert_pipeline.py` (presence update after rule-engine step ~line 97; gate as first statement of the alert-creation loop ~line 112)
- Modify: `fusion_server/api/events.py` (watchlist alert block ~line 183-205)
- Modify: `tests/conftest.py` (add autouse reset fixture)
- Test: `tests/test_alert_cooldown_wiring.py`

**Interfaces:**
- Consumes: `get_cooldown_gate()` from Task 1 (exact signature above).
- Produces: alerts created only when `should_fire` returns True; `result["violations"]` UNCHANGED (violations still reported when the alert is deduped); repeat `AlertPipeline.process()` for the same object+ROI no longer re-fires within 60s.
- Note: `tests/conftest.py` gets autouse fixture `reset_cooldown_gate` — without it, `test_alert_pipeline_loop_guard.py`'s second test (same `obj1`/`cam1`/`Zone A`) would be deduped by state leaking across tests.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_alert_cooldown_wiring.py`:

```python
"""Cooldown wiring: AlertPipeline.process must dedup repeat violations
(525-alert flood fix) while keeping violations reported, and re-arm on exit."""
from datetime import datetime
from unittest.mock import MagicMock

from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.services.cooldown_gate import get_cooldown_gate
from fusion_server.core.rule_engine import ROI


def _event(ts_minute, ts_second, bbox):
    return {
        "camera_id": "cam1",
        "object_id": "obj1",
        "object_type": "person",
        "timestamp": datetime(2025, 1, 1, 12, ts_minute, ts_second),
        "track_id": "trk1",
        "bbox": bbox,
        "confidence": 0.9,
    }


INSIDE = {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2}
OUTSIDE = {"x1": 0.8, "y1": 0.8, "x2": 0.9, "y2": 0.9}


def _mock_db():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = None
    mock_db.query.return_value.order_by.return_value.first.return_value = None
    return mock_db


def _pipeline():
    p = AlertPipeline(db=_mock_db())
    p.rule_engine.add_roi(ROI(
        camera_id="cam1",
        name="Zone A",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    return p


def test_repeat_violation_deduped_but_violations_still_reported():
    get_cooldown_gate().reset()
    p = _pipeline()

    r1 = p.process(_event(0, 0, INSIDE))
    assert len(r1["alerts"]) == 1
    assert len(r1["violations"]) == 1

    # 10s later, still inside: violation still detected, alert deduped
    r2 = p.process(_event(0, 10, INSIDE))
    assert len(r2["violations"]) == 1, "rule engine must still report the violation"
    assert len(r2["alerts"]) == 0, "second alert within 60s must be deduped"


def test_exit_rearm_refires_before_cooldown_elapsed():
    get_cooldown_gate().reset()
    p = _pipeline()

    assert len(p.process(_event(0, 0, INSIDE))["alerts"]) == 1
    outside = p.process(_event(0, 20, OUTSIDE))
    assert outside["violations"] == []
    # Left and re-entered 5s after exit, well within 60s of first fire
    assert len(p.process(_event(0, 25, INSIDE))["alerts"]) == 1


def test_refires_after_cooldown_window():
    get_cooldown_gate().reset()
    p = _pipeline()

    assert len(p.process(_event(0, 0, INSIDE))["alerts"]) == 1
    assert len(p.process(_event(1, 5, INSIDE))["alerts"]) == 1  # 65s later


def test_different_object_not_blocked():
    get_cooldown_gate().reset()
    p = _pipeline()

    assert len(p.process(_event(0, 0, INSIDE))["alerts"]) == 1
    other = dict(_event(0, 10, INSIDE), object_id="obj2")
    assert len(p.process(other)["alerts"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_alert_cooldown_wiring.py -v`
Expected: FAIL — `assert len(r2["alerts"]) == 0` receives `1 == 0` (no gate wired yet).

- [ ] **Step 3: Add the autouse reset fixture to conftest**

Append to `tests/conftest.py` (top-level, after imports):

```python
@pytest.fixture(autouse=True)
def reset_cooldown_gate():
    """Fresh CooldownGate per test — module singleton must not leak dedup state."""
    from fusion_server.services.cooldown_gate import get_cooldown_gate
    get_cooldown_gate().reset()
    yield
    get_cooldown_gate().reset()
```

- [ ] **Step 4: Wire the pipeline**

In `fusion_server/services/alert_pipeline.py`:

1. Add import after the other `fusion_server` imports (~line 18):
```python
from fusion_server.services.cooldown_gate import get_cooldown_gate
```

2. Right after the rule-engine step (after `violations = self.rule_engine.evaluate(...)`, before "# 4. Check suspicious activity"), insert:
```python
        # 3b. Presence update: deactivate ROI keys the object is no longer
        # violating (per-ROI re-arm). Watchlist keys untouched (time-only).
        get_cooldown_gate().update_presence(
            camera_id, object_id, {v.roi_name for v in violations}
        )
```

3. In the alert-creation loop (`for violation in violations:`), as the FIRST statement:
```python
                gate = get_cooldown_gate()
                if not gate.should_fire(
                    camera_id,
                    object_id,
                    f"roi:{violation.roi_name}",
                    violating=True,
                    now=ts_float,
                ):
                    continue  # deduped — violation stays in result["violations"]
```

- [ ] **Step 5: Wire the watchlist alert in events.py**

In `fusion_server/api/events.py`, inside `if final_match is not None:` BEFORE `alert = Alert(...)`, insert:

```python
        from fusion_server.services.cooldown_gate import get_cooldown_gate
        watchlist_object_id = object_id or f"unknown-{db_event.id}"
        if not get_cooldown_gate().should_fire(
            event.camera_id,
            watchlist_object_id,
            "watchlist_match",
            violating=True,
            now=event.timestamp.timestamp(),
        ):
            final_match = None  # deduped within 60s — no alert, no ledger write
```

And change the `Alert(...)` kwargs line `object_id=object_id or f"unknown-{db_event.id}",` to `object_id=watchlist_object_id,` (same value — reuse the local so gate key and row agree).

- [ ] **Step 6: Run the new tests plus regression suites**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_alert_cooldown_wiring.py tests/test_alert_pipeline_loop_guard.py tests/test_alert_sse_wiring.py -v`
Expected: all pass (loop_guard still gets 1 alert per test via autouse reset; sse_wiring unaffected).

- [ ] **Step 7: Run the full backend suite**

Run: `.\venv\Scripts\python.exe -m pytest -q`
Expected: all green (425 + 4 new = 429 passed, 0 failed).

- [ ] **Step 8: Commit**

```powershell
git add fusion_server/services/alert_pipeline.py fusion_server/api/events.py tests/conftest.py tests/test_alert_cooldown_wiring.py
git commit -m "fix: gate alert creation with CooldownGate — stops duplicate ROI/watchlist floods, violations still reported"
```

---

### Task 3: reason_detail + new Alert columns + API/SSE fields (incl. missing plate_text fix)

**Files:**
- Modify: `fusion_server/db/models.py:65-101` (Alert: add 2 columns; do NOT touch the status CHECK — Task 4 owns it)
- Modify: `fusion_server/db/session.py:61-72` (init_db: additive ALTERs, same try/except pattern as `ai_source`)
- Modify: `fusion_server/db/schema.sql:47-63` (alerts DDL: 2 columns)
- Modify: `fusion_server/services/alert_pipeline.py` (set `reason_detail` on its alert-creation path; add fields to `fired_payload` ~line 251-260)
- Modify: `fusion_server/api/events.py` (watchlist `Alert(...)` gets `reason_detail`; extra_alerts broadcast payload ~line 282-291 gains `reason_detail` + `snapshot_path`)
- Modify: `fusion_server/api/alerts.py` (`AlertResponse` + ALL 5 manual constructions: create ~line 100, list ~line 144, get ~line 204, patch ~line 244, acknowledge ~line 274 — each currently OMITS `plate_text`, and none have the new fields)
- Modify: `ARCHITECTURE.md` §5 Alert contract (~line 114-134)
- Test: `tests/test_alert_reason_detail.py`, `tests/test_alerts_api_fields.py`

**Interfaces:**
- Consumes: Tasks 1–2 (unaffected).
- Produces (Tasks 5 and FE 7 depend on these EXACT field names):
  - `Alert.reason_detail: Text NULL` — human sentence, set synchronously at fire time.
  - `Alert.snapshot_path: String(512) NULL` — set asynchronously by Task 5 (`"storage/alerts/{alert_id}.jpg"` relative path, or NULL).
  - `GET /api/v1/alerts` items now include `plate_text`, `reason_detail`, `snapshot_path`.
  - SSE `alert_fired` payload gains `reason_detail` (and `snapshot_path`, null at broadcast time — Task 5 fills it in DB afterward).
  - Exact `reason_detail` templates: ROI → `f"{object_type} {verb} ROI \"{violation.roi_name}\" · score {score:.2f}"` with `verb = "entered" if violation_type == "enter" else "exited"`; watchlist → `f"{event.object_type} matched watchlist '{final_match['reference_id']}' (similarity {final_match['similarity']:.4f}) · score {score:.2f}"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_alerts_api_fields.py`:

```python
"""AlertResponse must return plate_text (silently omitted from all 5 manual
constructions — why AlertsPage never showed plates), plus new reason_detail
and snapshot_path fields."""
from datetime import datetime

import pytest

from fusion_server.db.models import Alert


@pytest.fixture
def full_alert(db_session):
    a = Alert(
        alert_id="fields-test-1",
        object_id="obj1",
        camera_id="cam1",
        timestamp=datetime(2026, 9, 23, 12, 0, 0),
        reason="roi_intrusion",
        status="fired",
        threat_score=0.6,
        plate_text="DL01AB1234",
        reason_detail='person entered ROI "Zone A" · score 0.60',
        snapshot_path="storage/alerts/fields-test-1.jpg",
    )
    db_session.add(a)
    db_session.commit()
    return a


def test_list_alerts_returns_all_view_fields(client, full_alert):
    resp = client.get("/api/v1/alerts")
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["alert_id"] == "fields-test-1")
    assert row["plate_text"] == "DL01AB1234"
    assert row["reason_detail"] == 'person entered ROI "Zone A" · score 0.60'
    assert row["snapshot_path"] == "storage/alerts/fields-test-1.jpg"


def test_get_alert_returns_all_view_fields(client, full_alert):
    resp = client.get("/api/v1/alerts/fields-test-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plate_text"] == "DL01AB1234"
    assert body["reason_detail"].startswith("person entered")
    assert body["snapshot_path"].endswith(".jpg")


def test_acknowledge_response_returns_fields(client, full_alert):
    resp = client.post("/api/v1/alerts/fields-test-1/acknowledge")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plate_text"] == "DL01AB1234"
    assert "reason_detail" in body
    assert "snapshot_path" in body
```

Create `tests/test_alert_reason_detail.py`:

```python
"""reason_detail is generated deterministically at fire time (Rule 1: no ML)."""
from datetime import datetime
from unittest.mock import MagicMock

from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.services.cooldown_gate import get_cooldown_gate
from fusion_server.core.rule_engine import ROI


def _mock_db():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = None
    mock_db.query.return_value.order_by.return_value.first.return_value = None
    return mock_db


def test_pipeline_sets_reason_detail_with_roi_and_score():
    get_cooldown_gate().reset()
    p = AlertPipeline(db=_mock_db())
    p.rule_engine.add_roi(ROI(
        camera_id="cam1",
        name="Zone A",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    result = p.process({
        "camera_id": "cam1",
        "object_id": "obj1",
        "object_type": "person",
        "timestamp": datetime(2025, 1, 1, 12, 0, 0),
        "track_id": "trk1",
        "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
        "confidence": 0.9,
    })
    assert len(result["alerts"]) == 1
    detail = result["alerts"][0].reason_detail
    assert 'entered ROI "Zone A"' in detail
    assert "score " in detail
    assert "person" in detail
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_alerts_api_fields.py tests/test_alert_reason_detail.py -v`
Expected: FAIL — `OperationalError`/`AttributeError` (columns don't exist yet) and missing response keys.

- [ ] **Step 3: Add model columns + startup ALTERs + schema.sql**

1. `fusion_server/db/models.py` — after `plate_text` (line 82), add:
```python
    reason_detail = Column(Text, nullable=True)  # Deterministic plain-text explanation (set at fire time)
    snapshot_path = Column(String(512), nullable=True)  # Relative path under storage/alerts/ (set async post-broadcast)
```

2. `fusion_server/db/session.py` — in `init_db()` after the `ai_source` try/except, add (same additive, idempotent pattern):
```python
    for _ddl in (
        "ALTER TABLE alerts ADD COLUMN reason_detail TEXT",
        "ALTER TABLE alerts ADD COLUMN snapshot_path VARCHAR(512)",
    ):
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text(_ddl))
        except Exception:
            pass  # column already exists
```

3. `fusion_server/db/schema.sql` — inside `CREATE TABLE alerts`, after `enriched_at TIMESTAMPTZ` (line 62), add:
```sql
    reason_detail TEXT,  -- Deterministic plain-text explanation (additive 2026-09-23)
    snapshot_path VARCHAR(512)  -- Relative path under storage/alerts/ (additive 2026-09-23)
```

- [ ] **Step 4: Generate reason_detail + extend payloads**

1. `fusion_server/services/alert_pipeline.py`, in the alert-creation loop — before `alert = Alert(...)`:
```python
                verb = "entered" if violation.violation_type == "enter" else "exited"
                reason_detail = (
                    f'{object_type} {verb} ROI "{violation.roi_name}" · score {score:.2f}'
                )
```
   Add `reason_detail=reason_detail,` to the `Alert(...)` kwargs.

2. Same file, `fired_payload` dict — after `"plate_text": alert.plate_text,`:
```python
                        "reason_detail": alert.reason_detail,
                        "snapshot_path": alert.snapshot_path,
```

3. `fusion_server/api/events.py`, watchlist block — before `alert = Alert(...)`:
```python
        reason_detail = (
            f"{event.object_type} matched watchlist '{final_match['reference_id']}' "
            f"(similarity {final_match['similarity']:.4f}) · score {score:.2f}"
        )
```
   Add `reason_detail=reason_detail,` to that `Alert(...)`.

4. Same file, extra_alerts `broadcast_alert_fired({...})` payload — after `"plate_text": alert.plate_text,`:
```python
                "reason_detail": alert.reason_detail,
                "snapshot_path": alert.snapshot_path,
```

- [ ] **Step 5: Extend AlertResponse (all 5 construction sites)**

In `fusion_server/api/alerts.py`:

1. In `class AlertResponse` after `plate_text` (line 49):
```python
    reason_detail: Optional[str] = None
    snapshot_path: Optional[str] = None
```

2. In EACH of the 5 manual `AlertResponse(...)` constructions the `plate_text` key is MISSING — add all three fields to every one, using that function's existing local variable prefix exactly as its neighboring kwargs do (`db_alert.plate_text` in create_alert; `a.plate_text` in list_alerts; `alert.plate_text` in get_alert, update_alert, acknowledge_alert):
```python
        <prefix>plate_text=<prefix>plate_text,
        <prefix>reason_detail=<prefix>reason_detail,
        <prefix>snapshot_path=<prefix>snapshot_path,
```
   (i.e. literally add the three missing kwargs with the same `<prefix>` each site already uses for `clip_path`/`footprint_entry_id`.)

- [ ] **Step 6: Update ARCHITECTURE.md §5 Alert contract (Rule 5)**

In `ARCHITECTURE.md`, `### Alert` JSON block: add after the `"reason"` line:
```json
  "reason_detail": "string | null",
```
after the `"clip_path"` line:
```json
  "snapshot_path": "string | null",
```
after the `"footprint_entry_id"` line:
```json
  "plate_text": "string | null",
```
Immediately after the closing ``` of that block (before `### ROI`), append (same style as line 172):

> Contract addition (2026-09-23, FLAGGED TO ALL PHASE OWNERS): `Alert` gained three additive fields — `reason_detail` (deterministic plain-text explanation generated at fire time, never AI), `snapshot_path` (relative path to the event-triggered snapshot JPEG under `storage/alerts/`, set asynchronously after broadcast; NULL on failure), and `plate_text` (implemented since the ANPR work but previously missing from this contract). All are optional/nullable — no consumer breaks by ignoring them.

- [ ] **Step 7: Run the new tests**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_alerts_api_fields.py tests/test_alert_reason_detail.py -v`
Expected: 3 + 1 = 4 passed.

- [ ] **Step 8: Run the full backend suite**

Run: `.\venv\Scripts\python.exe -m pytest -q`
Expected: all green.

- [ ] **Step 9: Commit**

```powershell
git add fusion_server/db/models.py fusion_server/db/session.py fusion_server/db/schema.sql fusion_server/services/alert_pipeline.py fusion_server/api/events.py fusion_server/api/alerts.py ARCHITECTURE.md tests/test_alerts_api_fields.py tests/test_alert_reason_detail.py
git commit -m "feat: reason_detail + snapshot_path columns; AlertResponse returns plate_text/reason_detail/snapshot_path; §5 flagged"
```

---

### Task 4: Status lifecycle — escalated/false_positive (SQLite CHECK rebuild + endpoints)

**Files:**
- Modify: `fusion_server/db/models.py:100` (CHECK constraint string)
- Modify: `fusion_server/db/session.py` (new `migrate_alert_status_check` + call from `init_db`)
- Modify: `fusion_server/db/schema.sql:54` (PG CHECK + migration comment)
- Modify: `fusion_server/api/alerts.py` (transition helper; acknowledge guard; 2 new endpoints)
- Modify: `ARCHITECTURE.md` §5 Alert `"status"` line + flag note
- Test: `tests/test_alerts_migration.py`, `tests/test_alert_status_lifecycle.py`

**Interfaces:**
- Consumes: Task 3 fields/AlertResponse.
- Produces (FE Task 9 depends on these):
  - `POST /api/v1/alerts/{alert_id}/escalate` → 200, `status="escalated"`; `POST /api/v1/alerts/{alert_id}/false-positive` → 200, `status="false_positive"`; acknowledge path unchanged but 400 when current status is `false_positive`; 404 unknown id.
  - Allowed transitions from `fired|enriched|acknowledged|escalated`; `false_positive` terminal (400 `{"detail":"false_positive is terminal"}`).
  - `migrate_alert_status_check(conn, db_path: str) -> bool` (module-level in `session.py`) — SQLite cannot ALTER a CHECK: rebuilds `alerts` preserving rows, PK ids (child FKs stay valid), named indexes; returns True iff rebuilt; caller (`init_db`, sqlite only) backs up `ibvap.db` → `ibvap.db.bak-status-migration` (once, best-effort) BEFORE rebuild.

- [ ] **Step 1: Write the failing migration test**

Create `tests/test_alerts_migration.py`:

```python
"""SQLite cannot ALTER a CHECK constraint — migrating alerts.status must
rebuild the table, preserve rows + child FK references, and recreate indexes."""
import sqlite3

from fusion_server.db.session import migrate_alert_status_check


OLD_ALERTS_DDL = """
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY,
    alert_id TEXT NOT NULL UNIQUE,
    object_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'fired' CHECK (status IN ('fired', 'enriched', 'acknowledged')),
    threat_score REAL NOT NULL DEFAULT 0.0
)
"""


def _fresh_old_db(tmp_path):
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute(OLD_ALERTS_DDL)
    conn.execute("CREATE INDEX idx_alerts_status ON alerts (status)")
    conn.execute("CREATE INDEX idx_alerts_alert_id ON alerts (alert_id)")
    conn.execute(
        "INSERT INTO alerts (alert_id, object_id, camera_id, timestamp, reason, status, threat_score) "
        "VALUES ('a1', 'o1', 'cam1', '2026-09-23T12:00:00', 'roi_intrusion', 'acknowledged', 0.6)"
    )
    conn.execute(
        "CREATE TABLE child (id INTEGER PRIMARY KEY, "
        "alert_ref INTEGER REFERENCES alerts(id))"
    )
    conn.execute("INSERT INTO child (alert_ref) VALUES (1)")
    conn.commit()
    return db_path, conn


def test_rebuild_allows_new_statuses_and_preserves_children(tmp_path):
    db_path, conn = _fresh_old_db(tmp_path)

    # Sanity: the old CHECK really is there
    try:
        conn.execute("UPDATE alerts SET status='escalated'")
        raise AssertionError("precondition failed: old CHECK must reject 'escalated'")
    except sqlite3.IntegrityError:
        pass
    conn.rollback()

    did = migrate_alert_status_check(conn, db_path=str(db_path))
    assert did is True

    conn.execute("UPDATE alerts SET status='escalated'")
    conn.execute(
        "INSERT INTO alerts (alert_id, object_id, camera_id, timestamp, reason, status, threat_score) "
        "VALUES ('a2', 'o1', 'cam1', '2026-09-23T12:01:00', 'roi_intrusion', 'false_positive', 0.5)"
    )
    conn.commit()

    assert conn.execute("SELECT status FROM alerts WHERE alert_id='a1'").fetchone() == ("escalated",)
    assert conn.execute("SELECT COUNT(*) FROM child").fetchone()[0] == 1
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    idx = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='alerts'"
    )]
    assert "idx_alerts_status" in idx and "idx_alerts_alert_id" in idx
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    db_path, conn = _fresh_old_db(tmp_path)
    assert migrate_alert_status_check(conn, db_path=str(db_path)) is True
    assert migrate_alert_status_check(conn, db_path=str(db_path)) is False
    conn.close()


def test_new_db_ddl_is_skipped(tmp_path):
    """A DB created from the NEW model (create_all) must not be rebuilt."""
    from sqlalchemy import create_engine
    from fusion_server.db.models import Base
    engine = create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    Base.metadata.create_all(bind=engine)
    raw = engine.raw_connection()
    try:
        assert migrate_alert_status_check(raw, db_path=str(tmp_path / "new.db")) is False
    finally:
        raw.close()
```

- [ ] **Step 2: Write the failing endpoints test**

Create `tests/test_alert_status_lifecycle.py`:

```python
"""Status lifecycle: fired → acknowledged | escalated | false_positive;
false_positive is terminal; 404 unknown ids."""


def _create(client):
    resp = client.post("/api/v1/alerts", json={
        "object_id": "obj1",
        "camera_id": "cam1",
        "timestamp": "2026-09-23T12:00:00",
        "reason": "roi_intrusion",
        "threat_score": 0.6,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["alert_id"]


def test_escalate(client):
    aid = _create(client)
    resp = client.post(f"/api/v1/alerts/{aid}/escalate")
    assert resp.status_code == 200
    assert resp.json()["status"] == "escalated"


def test_false_positive(client):
    aid = _create(client)
    resp = client.post(f"/api/v1/alerts/{aid}/false-positive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "false_positive"


def test_terminal_false_positive_rejects_acknowledge(client):
    aid = _create(client)
    client.post(f"/api/v1/alerts/{aid}/false-positive")
    resp = client.post(f"/api/v1/alerts/{aid}/acknowledge")
    assert resp.status_code == 400
    assert "terminal" in resp.json()["detail"]


def test_escalate_then_acknowledge_allowed(client):
    aid = _create(client)
    client.post(f"/api/v1/alerts/{aid}/escalate")
    resp = client.post(f"/api/v1/alerts/{aid}/acknowledge")
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"


def test_unknown_id_404(client):
    assert client.post("/api/v1/alerts/nope-404/escalate").status_code == 404
    assert client.post("/api/v1/alerts/nope-404/false-positive").status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_alerts_migration.py tests/test_alert_status_lifecycle.py -v`
Expected: FAIL — `ImportError: cannot import name 'migrate_alert_status_check'`; endpoints `405` (no route).

- [ ] **Step 4: Implement migration + model CHECK + schema.sql**

1. `fusion_server/db/models.py` line 100 — replace with:
```python
        CheckConstraint("status IN ('fired', 'enriched', 'acknowledged', 'escalated', 'false_positive')", name='ck_alert_status'),
```

2. `fusion_server/db/schema.sql` line 54 — replace with:
```sql
    status VARCHAR(16) NOT NULL DEFAULT 'fired' CHECK (status IN ('fired', 'enriched', 'acknowledged', 'escalated', 'false_positive')),
```
   Append after the existing alerts indexes (~line 73):
```sql
-- Migration for EXISTING PG databases (fresh installs get the CHECK above):
-- ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alert_status;
-- ALTER TABLE alerts ADD CONSTRAINT ck_alert_status CHECK (status IN ('fired', 'enriched', 'acknowledged', 'escalated', 'false_positive'));
```

3. `fusion_server/db/session.py` — add module-level function above `init_db`:
```python
def migrate_alert_status_check(conn, db_path: str) -> bool:
    """SQLite CHECK constraints cannot be ALTERed — rebuild the alerts table
    with an extended status enum. Returns True if a rebuild happened.
    Preserves rows, PK ids (child FKs stay valid), and named indexes.
    Idempotent: no-op when the CHECK already lists 'escalated'.
    Backup is the CALLER's job (see init_db)."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='alerts'"
    ).fetchone()
    if row is None or row[0] is None:
        return False
    old_sql = row[0]
    marker = "('fired', 'enriched', 'acknowledged')"
    if marker not in old_sql:
        return False  # already migrated (or created from the new model)
    new_sql = old_sql.replace(
        marker, "('fired', 'enriched', 'acknowledged', 'escalated', 'false_positive')"
    )
    index_sql = [
        r[0] for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' "
            "AND tbl_name='alerts' AND sql IS NOT NULL"
        ).fetchall()
    ]
    fk_was_off = conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0
    if not fk_was_off:
        conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN")
        conn.execute(new_sql.replace("CREATE TABLE alerts", "CREATE TABLE alerts_new", 1))
        conn.execute("INSERT INTO alerts_new SELECT * FROM alerts")
        conn.execute("DROP TABLE alerts")
        conn.execute("ALTER TABLE alerts_new RENAME TO alerts")
        for sql in index_sql:
            conn.execute(sql)
        bad = conn.execute("PRAGMA foreign_key_check").fetchall()
        if bad:
            conn.execute("ROLLBACK")
            raise RuntimeError(f"foreign_key_check failed after rebuild: {bad[:5]}")
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        if not fk_was_off:
            conn.execute("PRAGMA foreign_keys=ON")
    return True
```

4. Same file, in `init_db()` after the Task 3 ALTER loop, add:
```python
    if DATABASE_URL.startswith("sqlite"):
        # "sqlite:///./ibvap.db" → "./ibvap.db" (works as-is with os.path.isfile)
        db_path = DATABASE_URL.split("sqlite:///", 1)[1]
        if db_path and db_path != ":memory:" and os.path.isfile(db_path):
            bak = db_path + ".bak-status-migration"
            if not os.path.isfile(bak):
                try:
                    import shutil
                    shutil.copy2(db_path, bak)
                except OSError:
                    pass  # best-effort backup — never block startup
            raw = engine.raw_connection()
            try:
                migrate_alert_status_check(raw, db_path=db_path)
                raw.commit()
            except Exception:
                try:
                    raw.rollback()
                except Exception:
                    pass
            finally:
                raw.close()
```
   (Note `DATABASE_URL` default is `sqlite:///./ibvap.db` — the `split` form above yields `./ibvap.db`, which `os.path.isfile` resolves correctly relative to the working directory; `:memory:` and empty paths are skipped.)

- [ ] **Step 5: Implement the endpoints**

In `fusion_server/api/alerts.py`, after `router = APIRouter(...)`:

```python
_TERMINAL_STATUS = "false_positive"


def _transition_status(db: Session, alert: Alert, new_status: str) -> None:
    """fired|enriched|acknowledged|escalated → anything; false_positive terminal."""
    if alert.status == _TERMINAL_STATUS:
        raise HTTPException(status_code=400, detail="false_positive is terminal")
    alert.status = new_status
    db.commit()
    db.refresh(alert)


def _alert_response(alert: Alert) -> AlertResponse:
    return AlertResponse(
        id=alert.id, alert_id=alert.alert_id, object_id=alert.object_id,
        camera_id=alert.camera_id, timestamp=alert.timestamp, reason=alert.reason,
        status=alert.status, threat_score=alert.threat_score, clip_path=alert.clip_path,
        ai_explanation=alert.ai_explanation, ai_source=getattr(alert, "ai_source", None),
        trajectory_projection=alert.trajectory_projection, plate_text=alert.plate_text,
        reason_detail=alert.reason_detail, snapshot_path=alert.snapshot_path,
        footprint_entry_id=alert.footprint_entry_id, created_at=alert.created_at,
        enriched_at=alert.enriched_at,
    )
```

Rewrite `acknowledge_alert` body:
```python
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    _transition_status(db, alert, "acknowledged")
    return _alert_response(alert)
```

Add the two new endpoints:
```python
@router.post("/{alert_id}/escalate", response_model=AlertResponse)
async def escalate_alert(alert_id: str, db: Session = Depends(get_db)):
    """Escalate an alert (status only — threat_score is rule-engine owned)."""
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    _transition_status(db, alert, "escalated")
    return _alert_response(alert)


@router.post("/{alert_id}/false-positive", response_model=AlertResponse)
async def false_positive_alert(alert_id: str, db: Session = Depends(get_db)):
    """Mark an alert a false positive (terminal status — audit trail kept)."""
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    _transition_status(db, alert, "false_positive")
    return _alert_response(alert)
```

- [ ] **Step 6: ARCHITECTURE.md §5 status enum (Rule 5)**

Replace `"status": "fired | enriched | acknowledged",` in the Alert block with:
```json
  "status": "fired | enriched | acknowledged | escalated | false_positive",
```
Append a second dated paragraph after the Task 3 flag note:

> Contract addition (2026-09-23, FLAGGED TO ALL PHASE OWNERS): `Alert.status` gained `escalated` and `false_positive`. `false_positive` is terminal; all other statuses may transition among themselves via `POST /api/v1/alerts/{alert_id}/{acknowledge,escalate,false-positive}`. Existing SQLite databases are migrated automatically at startup (`init_db` rebuilds the `alerts` table — CHECK constraints cannot be ALTERed); a pre-migration backup is written to `ibvap.db.bak-status-migration`. PostgreSQL operators must run the commented `ALTER TABLE` block in `schema.sql`.

- [ ] **Step 7: Run the new tests**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_alerts_migration.py tests/test_alert_status_lifecycle.py -v`
Expected: 3 + 5 = 8 passed.

- [ ] **Step 8: Run the full backend suite**

Run: `.\venv\Scripts\python.exe -m pytest -q`
Expected: all green.

- [ ] **Step 9: Commit**

```powershell
git add fusion_server/db/models.py fusion_server/db/session.py fusion_server/db/schema.sql fusion_server/api/alerts.py ARCHITECTURE.md tests/test_alerts_migration.py tests/test_alert_status_lifecycle.py
git commit -m "feat: alert status lifecycle — escalated/false_positive with SQLite CHECK rebuild + endpoints; §5 flagged"
```

---

### Task 5: Snapshot store — decode edge thumbnail, save JPEG, serve endpoint

**Files:**
- Create: `fusion_server/services/snapshot_store.py`
- Modify: `fusion_server/api/events.py` (`DetectionEventCreate` gains `snapshot`; `create_event` schedules async save AFTER broadcasts)
- Modify: `fusion_server/api/alerts.py` (add `GET /{alert_id}/snapshot`)
- Modify: `.gitignore` (add `storage/`)
- Test: `tests/test_snapshot_store.py`

**Interfaces:**
- Consumes: Tasks 1–4. `pipeline_result["alerts"]` (SQLAlchemy `Alert` rows) and `extra_alerts` from `_ingest_event`; new `event.snapshot: Optional[str]` (base64 JPEG) on `DetectionEventCreate`.
- Produces (FE Task 9 depends on): `GET /api/v1/alerts/{alert_id}/snapshot` → 200 `image/jpeg` FileResponse, or 404 (unknown id OR `snapshot_path` NULL/missing file). DB stores RELATIVE path `storage/alerts/{alert_id}.jpg`; base64 never persisted.
- Failure semantics (AGENTS.md Rule 4): any decode/write error ⇒ log warning, `snapshot_path` stays NULL, alert delivery unaffected (save is `asyncio.ensure_future` after broadcast).
- API URL for FE: `alertSnapshotUrl(id)` = `` `/api/v1/alerts/${id}/snapshot` `` (same-origin, matches clips pattern).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_snapshot_store.py`:

```python
"""Snapshot store: decode edge base64 thumbnail → JPEG on disk after broadcast
(best-effort; base64 never hits the DB; relative path persisted)."""
import base64
import os

import pytest

from fusion_server.db.models import Alert
from fusion_server.services import snapshot_store
from fusion_server.services.snapshot_store import (
    decode_jpeg_b64,
    get_snapshot_dir,
    save_alert_snapshots,
)


@pytest.fixture(autouse=True)
def isolated_snapshot_dir(tmp_path, monkeypatch):
    """Point the store at a temp dir for every test in this module."""
    monkeypatch.setenv("IBVAP_SNAPSHOT_DIR", str(tmp_path))
    yield tmp_path


def _tiny_jpeg_b64() -> str:
    """1x1 JPEG (SOI + EOI bytes) — decode gate only checks magic bytes."""
    raw = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00,
        0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
        0xFF, 0xD9,
    ])
    return base64.b64encode(raw).decode("ascii")


def test_get_snapshot_dir_env_override(tmp_path):
    assert get_snapshot_dir() == str(tmp_path)


def test_decode_rejects_non_jpeg():
    bad = base64.b64encode(b"not a jpeg at all").decode("ascii")
    with pytest.raises(ValueError):
        decode_jpeg_b64(bad)


def test_decode_rejects_invalid_base64():
    with pytest.raises(ValueError):
        decode_jpeg_b64("!!!not-base64!!!")


def test_decode_returns_jpeg_bytes():
    data = decode_jpeg_b64(_tiny_jpeg_b64())
    assert data[:2] == b"\xff\xd8"


def test_save_writes_file_and_returns_relative_path(tmp_path):
    path = save_alert_snapshots(["snap-ok-1"], _tiny_jpeg_b64())
    assert path == "storage/alerts/snap-ok-1.jpg"
    on_disk = tmp_path / "snap-ok-1.jpg"
    assert on_disk.is_file()
    assert on_disk.read_bytes()[:2] == b"\xff\xd8"


def test_save_never_raises_on_bad_payload(tmp_path):
    assert save_alert_snapshots(["snap-bad-1"], "not-valid-b64!!!") is None
    assert not (tmp_path / "snap-bad-1.jpg").exists()


def test_save_never_raises_on_unwritable_dir(monkeypatch, tmp_path):
    def _boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(snapshot_store.os, "makedirs", _boom)
    assert save_alert_snapshots(["snap-err-1"], _tiny_jpeg_b64()) is None


def test_save_with_empty_snapshot_is_noop(tmp_path):
    assert save_alert_snapshots(["snap-none-1"], None) is None
    assert not (tmp_path / "snap-none-1.jpg").exists()


def test_snapshot_get_endpoint(client, db_session):
    """200 with image/jpeg when file exists; 404 when snapshot_path is NULL."""
    import tempfile, time
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8fakejpg\xff\xd9")
        tmp_file = f.name

    alert = Alert(
        alert_id="snap-api-1", object_id="o", camera_id="c",
        timestamp=__import__("datetime").datetime(2026, 9, 23, 12, 0, 0),
        reason="roi_intrusion", status="fired", threat_score=0.5,
        snapshot_path=tmp_file,
    )
    db_session.add(alert)
    no_snap = Alert(
        alert_id="snap-api-none", object_id="o", camera_id="c",
        timestamp=__import__("datetime").datetime(2026, 9, 23, 12, 0, 0),
        reason="roi_intrusion", status="fired", threat_score=0.5,
        snapshot_path=None,
    )
    db_session.add(no_snap)
    db_session.commit()

    resp = client.get("/api/v1/alerts/snap-api-1/snapshot")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/jpeg")

    assert client.get("/api/v1/alerts/snap-api-none/snapshot").status_code == 404
    assert client.get("/api/v1/alerts/does-not-exist/snapshot").status_code == 404

    os.unlink(tmp_file)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_snapshot_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fusion_server.services.snapshot_store'` and 404 route missing for endpoint test.

- [ ] **Step 3: Implement snapshot_store**

Create `fusion_server/services/snapshot_store.py`:

```python
"""
Snapshot store — persist event-triggered alert thumbnails (AGENTS.md Rule 4:
best-effort, post-broadcast, never blocks alert delivery; Rule 2: one still
≤640px, not video).

Edge nodes attach optional base64 JPEG (`snapshot`) to DetectionEvents.
We decode after the alert row is committed + SSE broadcast, write
storage/alerts/{alert_id}.jpg, and persist the RELATIVE path.
Base64 is never written to the DB. Any failure ⇒ log warning, return None.
"""
import asyncio
import base64
import logging
import os

logger = logging.getLogger(__name__)

# Env override lets tests (and operators) redirect storage without touching code.
ENV_DIR = "IBVAP_SNAPSHOT_DIR"


def get_snapshot_dir() -> str:
    return os.environ.get(ENV_DIR) or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "storage", "alerts",
    )


def decode_jpeg_b64(snapshot_b64: str) -> bytes:
    """Decode base64 → bytes; validate JPEG SOI magic. Raises ValueError."""
    try:
        data = base64.b64decode(snapshot_b64, validate=True)
    except Exception as exc:
        raise ValueError("invalid base64 snapshot") from exc
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("snapshot is not a JPEG (missing SOI marker)")
    return data


def save_alert_snapshots(alert_ids, snapshot_b64) -> "str | None":
    """
    Synchronous save (call from async code via run_in_executor / ensure_future).

    Writes {snapshot_dir}/{alert_id}.jpg for the FIRST id (one event → one
    frame; extra ids ignored defensively). Returns the DB-relative path
    ('storage/alerts/{id}.jpg') on success, None on any failure.
    Never raises.
    """
    if not snapshot_b64 or not alert_ids:
        return None
    alert_id = alert_ids[0]
    try:
        data = decode_jpeg_b64(snapshot_b64)
        out_dir = get_snapshot_dir()
        os.makedirs(out_dir, exist_ok=True)
        abs_path = os.path.join(out_dir, f"{alert_id}.jpg")
        with open(abs_path, "wb") as fh:
            fh.write(data)
        return f"storage/alerts/{alert_id}.jpg"
    except Exception as exc:
        logger.warning("snapshot save failed for alert %s: %s", alert_id, exc)
        return None


async def save_alert_snapshots_async(alert_ids, snapshot_b64) -> "str | None":
    """Non-blocking wrapper: file I/O in the default executor."""
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, save_alert_snapshots, alert_ids, snapshot_b64
        )
    except Exception as exc:
        logger.warning("async snapshot save failed: %s", exc)
        return None
```

- [ ] **Step 4: Wire save into create_event (after broadcasts)**

In `fusion_server/api/events.py`:

1. In `class DetectionEventCreate`, after `confidence: float`:
```python
    snapshot: Optional[str] = None  # Optional base64 JPEG thumbnail (≤640px), edge→fusion only
```

2. In `create_event`, immediately AFTER the extra_alerts `for` loop (the block ending `pass  # Never block alert delivery on broadcast failure` for extra_alerts) and BEFORE the detection broadcast — insert:
```python
    # Snapshot save: post-broadcast, best-effort (Rule 4). One frame per event;
    # alert_ids = pipeline alerts first, then watchlist extra_alerts.
    if event.snapshot:
        try:
            from fusion_server.services.snapshot_store import save_alert_snapshots_async
            _snap_alert_ids = [a.alert_id for a in (pipeline_result or {}).get("alerts", [])]
            _snap_alert_ids += [a.alert_id for a in (ingest.get("extra_alerts") or [])]
            if _snap_alert_ids:
                asyncio.ensure_future(_persist_snapshot(_snap_alert_ids, event.snapshot))
        except Exception:
            pass  # Never block alert delivery on snapshot failure
```

3. Same file, add the module-level helper (above `create_event`):
```python
async def _persist_snapshot(alert_ids, snapshot_b64: str) -> None:
    """Best-effort: write JPEG, then update alert rows in a fresh session."""
    try:
        from fusion_server.services.snapshot_store import save_alert_snapshots_async
        from fusion_server.db.session import SessionLocal
        rel_path = await save_alert_snapshots_async(alert_ids, snapshot_b64)
        if not rel_path:
            return
        def _update():
            s = SessionLocal()
            try:
                for aid in alert_ids:
                    row = s.query(Alert).filter(Alert.alert_id == aid).first()
                    if row is not None:
                        row.snapshot_path = rel_path
                s.commit()
            finally:
                s.close()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _update)
    except Exception as exc:
        logger.warning("snapshot persist failed: %s", exc)
```
   (`Alert` is already imported inside `_ingest_event` — move `from fusion_server.db.models import Alert` to module level if needed, or import inside `_persist_snapshot`.)

- [ ] **Step 5: Snapshot serving endpoint**

In `fusion_server/api/alerts.py`, add (place BEFORE `@router.get("/{alert_id}")` so path routing is unambiguous — static suffix wins in FastAPI either way, but keep it adjacent):

```python
@router.get("/{alert_id}/snapshot")
async def get_alert_snapshot(alert_id: str, db: Session = Depends(get_db)):
    """Serve the event-triggered snapshot JPEG (404 if none / unknown alert)."""
    import os as _os
    from fastapi.responses import FileResponse
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert or not alert.snapshot_path:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    sp = alert.snapshot_path
    if _os.path.isabs(sp):
        # Trust absolute paths (written only by our own store / test fixtures).
        abs_path = _os.path.abspath(sp)
    else:
        # Project-relative path we wrote ourselves — reject traversal escapes.
        root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
        abs_path = _os.path.abspath(_os.path.join(root, sp))
        if not abs_path.startswith(root + _os.sep):
            raise HTTPException(status_code=404, detail="Snapshot not found")
    if not _os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(abs_path, media_type="image/jpeg",
                        filename=f"{alert_id}.jpg")
```
   (Absolute-path branch is REQUIRED for the test fixture, which stores a temp-file path; production rows always use the relative `storage/alerts/...` form and hit the traversal guard.)

- [ ] **Step 6: Ignore snapshot storage**

Append to `.gitignore`:
```
storage/
```

- [ ] **Step 7: Run the new tests**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_snapshot_store.py -v`
Expected: 9 passed (8 unit + 1 endpoint).

- [ ] **Step 8: Run the full backend suite**

Run: `.\venv\Scripts\python.exe -m pytest -q`
Expected: all green.

- [ ] **Step 9: Commit**

```powershell
git add fusion_server/services/snapshot_store.py fusion_server/api/events.py fusion_server/api/alerts.py .gitignore tests/test_snapshot_store.py
git commit -m "feat: snapshot store — decode edge thumbnail post-broadcast, persist JPEG, serve GET /alerts/{id}/snapshot"
```

---

### Task 6: Edge snapshot encode + attach (throttled ≤1/sec per camera)

**Files:**
- Modify: `edge/event_publisher.py` (add `encode_snapshot`, `SnapshotThrottle`)
- Modify: `edge/camera_worker.py` (encode once per frame batch; attach `event["snapshot"]`)
- Modify: `ARCHITECTURE.md` §5 DetectionEvent contract + dated FLAGGED note (Rule 5)
- Test: `tests/test_edge_snapshot.py`

**Interfaces:**
- Consumes: nothing new (cv2, base64, time — camera_worker already imports numpy/time).
- Produces (Task 5 consumes): `event["snapshot"]: str | None` on the wire (field simply ABSENT when encode fails or throttled — backward compatible). Exact helpers:
  - `encode_snapshot(frame, max_side: int = 640, quality: int = 80) -> Optional[str]` — if `max(h, w) > max_side`, scale down preserving aspect; `cv2.imencode(".jpg", ..., [cv2.IMWRITE_JPEG_QUALITY, quality])`; return base64 ASCII str; `None` on any failure (never raises).
  - `class SnapshotThrottle(interval: float = 1.0)` with `should_attach(now: float) -> bool` — True at most once per `interval` per instance (first call True); camera_worker keeps ONE throttle per camera worker instance.
- RULE 2 boundary: this is ONE still JPEG ≤640px, event-triggered — not video.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_edge_snapshot.py`:

```python
"""Edge snapshot: base64 JPEG ≤640px long edge, throttled ≤1/camera/sec,
field absent on failure (never raises — publish path must not break)."""
import base64

import numpy as np

from edge.event_publisher import SnapshotThrottle, encode_snapshot


def _frame(h=480, w=640):
    return np.zeros((h, w, 3), dtype=np.uint8)


def test_encode_returns_base64_jpeg():
    out = encode_snapshot(_frame())
    assert out is not None
    raw = base64.b64decode(out)
    assert raw[:2] == b"\xff\xd8"


def test_encode_downscales_large_frame():
    out = encode_snapshot(_frame(h=1080, w=1920))
    assert out is not None
    # Decode via cv2 to verify long edge <= 640
    import cv2
    img = cv2.imdecode(np.frombuffer(base64.b64decode(out), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img is not None
    assert max(img.shape[:2]) <= 640


def test_encode_never_raises_on_bad_input():
    assert encode_snapshot(None) is None
    assert encode_snapshot(np.zeros((10, 10), dtype=np.uint8)) is None  # not BGR


def test_throttle_first_call_true_then_false():
    t = SnapshotThrottle(interval=1.0)
    assert t.should_attach(now=100.0) is True
    assert t.should_attach(now=100.5) is False
    assert t.should_attach(now=101.0) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_edge_snapshot.py -v`
Expected: FAIL — `ImportError: cannot import name 'encode_snapshot'`.

- [ ] **Step 3: Implement helpers in event_publisher**

Append to `edge/event_publisher.py` (after imports, before or after `EventPublisher` — module level):

```python
import base64
import time as _time
from typing import Optional

import cv2
import numpy as np


def encode_snapshot(frame, max_side: int = 640, quality: int = 80) -> Optional[str]:
    """
    Encode a BGR frame as base64 JPEG for alert thumbnails (≤640px long edge).
    Returns None on any failure — callers must treat that as 'omit the field'.
    RULE 2: this is a single still, never video.
    """
    if frame is None or not isinstance(frame, np.ndarray) or frame.ndim != 3:
        return None
    try:
        h, w = frame.shape[:2]
        long_edge = max(h, w)
        if long_edge > max_side:
            scale = max_side / float(long_edge)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        if not ok:
            return None
        return base64.b64encode(buf.tobytes()).decode("ascii")
    except Exception:
        return None


class SnapshotThrottle:
    """Allow a snapshot attach at most once per `interval` seconds."""

    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self._last = None

    def should_attach(self, now: float = None) -> bool:
        now = _time.time() if now is None else now
        if self._last is None or (now - self._last) >= self.interval:
            self._last = now
            return True
        return False
```

- [ ] **Step 4: Wire into camera_worker publish loop**

In `edge/camera_worker.py`:

1. Extend the import: `from edge.event_publisher import EventPublisher, SnapshotThrottle, encode_snapshot`

2. In `CameraWorker.__init__`, after `self.publisher = EventPublisher(fusion_url)`:
```python
        self._snapshot_throttle = SnapshotThrottle(interval=1.0)
```

3. In `run()`, in the publish block (`for track in tracks:` … before `self.publisher.publish(event)`) — encode ONCE per frame batch (outside the per-track loop), attach inside:

Replace the block starting `# Publish events with embeddings` … `self.publisher.publish(event)` with:

```python
            # Publish events with embeddings
            ts_iso = timestamp.isoformat() + "Z"
            # One snapshot per frame batch, throttled ≤1/sec (RULE 2: single still).
            snapshot_b64 = None
            if tracks and self._snapshot_throttle.should_attach():
                snapshot_b64 = encode_snapshot(frame)
            for track in tracks:
                object_type = "person" if track.class_name == "person" else "vehicle"
                embedding = reid_embeddings.get((self._frame_id, track.track_id))
                face_emb = face_embeddings.get((self._frame_id, track.track_id))
                plate_text = plate_texts.get((self._frame_id, track.track_id))
                event = self.publisher.build_event(
                    camera_id=self.camera_id,
                    timestamp=ts_iso,
                    object_type=object_type,
                    track_id=str(track.track_id),
                    bbox_pixels=track.bbox,
                    frame_shape=(h, w),
                    confidence=track.confidence,
                    embedding=embedding,
                )
                if face_emb is not None:
                    event["face_embedding"] = face_emb.tolist()
                if plate_text is not None:
                    event["plate_text"] = plate_text
                if snapshot_b64 is not None:
                    event["snapshot"] = snapshot_b64
                self.publisher.publish(event)
```

- [ ] **Step 5: ARCHITECTURE.md §5 DetectionEvent contract (Rule 5)**

In the `### DetectionEvent` JSON block, after the `"confidence": float` line add:
```json
  , "snapshot": "string | null"
```
(cleanly: change the last two lines to `"confidence": float,` + `"snapshot": "string | null"`).

Immediately after that block's closing ``` add (same flag style as lines 170–172):

> Contract addition (2026-09-23, FLAGGED TO ALL PHASE OWNERS): `DetectionEvent.snapshot` is an OPTIONAL base64-encoded JPEG thumbnail (≤640px long edge, quality 80) of the triggering frame, attached by edge nodes at most once per camera per second when an object event is published. Edge→fusion only; never persisted as base64 (fusion decodes to `storage/alerts/{alert_id}.jpg` post-broadcast and stores `Alert.snapshot_path`). Encode failure ⇒ field omitted entirely (same as `embedding: null` semantics). This is ONE still image per throttled event — strictly less than the already-permitted short event-triggered clips; no raw video crosses the boundary (AGENTS.md Rule 2). Old edge nodes simply omit the field ⇒ `snapshot_path` stays NULL.

- [ ] **Step 6: Run the new tests**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_edge_snapshot.py -v`
Expected: 4 passed.

- [ ] **Step 7: Run full backend suite (event publisher regression)**

Run: `.\venv\Scripts\python.exe -m pytest -q`
Expected: all green (includes `test_event_publisher.py` — build_event unchanged).

- [ ] **Step 8: Commit**

```powershell
git add edge/event_publisher.py edge/camera_worker.py ARCHITECTURE.md tests/test_edge_snapshot.py
git commit -m "feat: edge snapshot thumbnails — encode ≤640px JPEG, throttle 1/s, attach to events; §5 DetectionEvent flagged"
```

---

### Task 7: Frontend shared alert lib + types + API methods (fixes missing plates)

**Files:**
- Create: `dashboard/src/lib/alerts.ts`
- Modify: `dashboard/src/types/api.ts` (`Alert.status` union + `reason_detail`/`snapshot_path`)
- Modify: `dashboard/src/services/api.ts` (escalate / false-positive / snapshot URL)
- Modify: `dashboard/src/pages/AlertsPage.tsx` (delete local `DashboardAlert`/`mapSeverity`/`mapApiAlert`; import from lib)
- Modify: `dashboard/src/pages/DashboardPage.tsx` (same dedup — uses the SAME mapper so plates/details are consistent)
- Verify: `npm run build` (workdir `dashboard/`)

**Interfaces:**
- Consumes: Task 3 API fields (`plate_text`, `reason_detail`, `snapshot_path` on every `AlertResponse`), Task 4 endpoints.
- Produces (Tasks 8–10 depend on these EXACT exports):
  - `export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'`
  - `export interface FeedAlert { id: string; type: string; severity: Severity; cameraId: string; timestamp: string; status: string; plateText: string | null; reasonDetail: string | null; threatScore: number; snapshotPath: string | null; aiExplanation: string | null; aiSource: string | null }`
  - `export const REASON_LABELS: Record<string, string>` — `{ roi_intrusion: 'ROI Intrusion', virtual_fence_crossing: 'Virtual Fence Crossing', watchlist_match: 'Watchlist Match', camera_dark: 'Camera Dark', camera_blur: 'Camera Blur', camera_frozen: 'Camera Frozen', camera_blinding: 'Camera Blinding', camera_obscured: 'Camera Obscured' }` with fallback `labelForReason(reason)` returning the raw reason when unknown.
  - `export function mapSeverity(threatScore: number): Severity` — **unchanged thresholds** (≥0.8 critical, ≥0.6 high, ≥0.4 medium, ≥0.2 low, else info).
  - `export function mapApiAlert(raw: Alert): FeedAlert` — carries ALL fields including `plateText: raw.plate_text || null`, `reasonDetail: raw.reason_detail || null`, `threatScore: raw.threat_score`, `snapshotPath: raw.snapshot_path || null`.
  - `export function isOpenStatus(status: string): boolean` — `status === 'fired' || status === 'enriched'`.
  - `api.escalateAlert(id)`, `api.falsePositiveAlert(id)` → `post<Alert>(...)`; `api.alertSnapshotUrl(id)` → `` `/api/v1/alerts/${id}/snapshot` `` — both live in `api.ts` alongside the other alert methods.
- No FE test runner — verification is `npm run build` + manual checklist (Task 11).

- [ ] **Step 1: Extend API types**

In `dashboard/src/types/api.ts`, in `interface Alert`:
1. Replace `status: "fired" | "enriched" | "acknowledged";` with:
```ts
  status: "fired" | "enriched" | "acknowledged" | "escalated" | "false_positive";
```
2. After `plate_text: string | null;` add:
```ts
  reason_detail: string | null;
  snapshot_path: string | null;
```

- [ ] **Step 2: Create the shared lib**

Create `dashboard/src/lib/alerts.ts`:

```ts
import type { Alert } from "@/types/api";

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface FeedAlert {
  id: string;
  type: string;
  severity: Severity;
  cameraId: string;
  timestamp: string;
  status: string;
  plateText: string | null;
  reasonDetail: string | null;
  threatScore: number;
  snapshotPath: string | null;
  aiExplanation: string | null;
  aiSource: string | null;
}

export const REASON_LABELS: Record<string, string> = {
  roi_intrusion: "ROI Intrusion",
  virtual_fence_crossing: "Virtual Fence Crossing",
  watchlist_match: "Watchlist Match",
  camera_dark: "Camera Dark",
  camera_blur: "Camera Blur",
  camera_frozen: "Camera Frozen",
  camera_blinding: "Camera Blinding",
  camera_obscured: "Camera Obscured",
};

export function labelForReason(reason: string): string {
  return REASON_LABELS[reason] ?? reason.replace(/_/g, " ");
}

export function mapSeverity(threatScore: number): Severity {
  if (threatScore >= 0.8) return "critical";
  if (threatScore >= 0.6) return "high";
  if (threatScore >= 0.4) return "medium";
  if (threatScore >= 0.2) return "low";
  return "info";
}

export function mapApiAlert(raw: Alert): FeedAlert {
  return {
    id: raw.alert_id || String(raw.id),
    type: labelForReason(raw.reason),
    severity: mapSeverity(raw.threat_score),
    cameraId: raw.camera_id,
    timestamp: raw.timestamp,
    status: raw.status,
    plateText: raw.plate_text || null,
    reasonDetail: raw.reason_detail || null,
    threatScore: raw.threat_score,
    snapshotPath: raw.snapshot_path || null,
    aiExplanation: raw.ai_explanation || null,
    aiSource: raw.ai_source || null,
  };
}

export function isOpenStatus(status: string): boolean {
  return status === "fired" || status === "enriched";
}
```

- [ ] **Step 3: Extend api.ts**

In `dashboard/src/services/api.ts`, after `acknowledgeAlert`:
```ts
  escalateAlert: (id: string) => post<Alert>(`/alerts/${id}/escalate`),
  falsePositiveAlert: (id: string) => post<Alert>(`/alerts/${id}/false-positive`),
  alertSnapshotUrl: (id: string) => `${BASE}/alerts/${id}/snapshot`,
```

- [ ] **Step 4: Rewire AlertsPage to the shared lib**

In `dashboard/src/pages/AlertsPage.tsx`:
1. Delete the local `interface DashboardAlert`, `mapSeverity`, `mapApiAlert` (lines 9–35).
2. Add imports:
```ts
import { mapApiAlert, type FeedAlert } from '@/lib/alerts';
```
3. Replace `DashboardAlert` type annotations with `FeedAlert` (state type, `selectedAlert` inference follows).
4. `handleAcknowledge` stays; (Task 9 will add escalate/false-positive handlers — leave as-is now, build must stay green).

- [ ] **Step 5: Rewire DashboardPage to the shared lib**

In `dashboard/src/pages/DashboardPage.tsx`:
1. Delete local `interface DashboardAlert` (keep `DashboardCamera`/`mapApiCamera`), delete local `mapSeverity` + `mapApiAlert`.
2. Import `import { mapApiAlert, type FeedAlert } from '@/lib/alerts';`
3. Replace `DashboardAlert` usages with `FeedAlert` (alerts + toasts state).
4. The existing `plateText: raw.plate_text || null` behavior now lives in the shared mapper — plates keep working and gain reasonDetail/snapshotPath.

- [ ] **Step 6: Build**

Run: `npm run build` (workdir `dashboard/`)
Expected: tsc + vite clean, exit 0. Fix any type errors (AlertFeed/AlertDetailPanel still declare their OWN local `Alert` interfaces with optional `plateText` — they accept `FeedAlert` structurally because FeedAlert's fields are all present; if tsc complains about extra fields being passed, that's fine — extra props on JSX spread are allowed; only missing required props error).

- [ ] **Step 7: Commit**

```powershell
git add dashboard/src/lib/alerts.ts dashboard/src/types/api.ts dashboard/src/services/api.ts dashboard/src/pages/AlertsPage.tsx dashboard/src/pages/DashboardPage.tsx
git commit -m "feat(dashboard): shared FeedAlert mapper — plateText/reasonDetail/snapshotPath flow to UI; escalate/false-positive API methods"
```

---

### Task 8: Enriched feed row (`AlertItem`) + shared prop types

**Files:**
- Modify: `dashboard/src/components/alert/AlertItem.tsx` (thumbnail/placeholder, reason label, plate chip, status dot, reason line)
- Modify: `dashboard/src/components/alert/AlertFeed.tsx` (local `Alert` iface → `FeedAlert`)
- Modify: `dashboard/src/components/alert/AlertDetailPanel.tsx` (local `Alert` iface → `FeedAlert`)
- Verify: `npm run build` (workdir `dashboard/`)

**Interfaces:**
- Consumes: Task 7 `FeedAlert`, `labelForReason`, `api.alertSnapshotUrl`.
- Produces: AlertFeed/AlertDetailPanel accept `FeedAlert[]` / `FeedAlert | null` — Tasks 9–10 pass these directly.
- Visual contract (spec §5.2): row = thumbnail (when `snapshotPath`; else compact placeholder block) + human-readable type + StatusBadge + camera + relative time + plate chip (mono, only when present) + status dot + `reasonDetail` line when present (truncated).

- [ ] **Step 1: Rewrite AlertItem**

Replace `dashboard/src/components/alert/AlertItem.tsx` content with:

```tsx
import { StatusBadge } from "@/components/ui/StatusBadge"
import { Camera, ImageOff } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/services/api"
import type { FeedAlert } from "@/lib/alerts"

interface AlertItemProps {
  alert: FeedAlert
  isSelected?: boolean
  onClick?: () => void
}

function timeAgo(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function statusDotColor(status: string): string {
  switch (status) {
    case "fired": return "bg-severity-critical"
    case "enriched": return "bg-severity-high"
    case "acknowledged": return "bg-status-online"
    case "escalated": return "bg-severity-critical animate-pulse"
    case "false_positive": return "bg-text-muted"
    default: return "bg-text-muted"
  }
}

export function AlertItem({ alert, isSelected, onClick }: AlertItemProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "flex cursor-pointer gap-3 border-l-2 px-3 py-2.5 transition-colors",
        {
          "border-l-severity-critical bg-severity-critical/5": alert.severity === "critical" && !isSelected,
          "border-l-severity-high bg-severity-high/5": alert.severity === "high" && !isSelected,
          "border-l-severity-medium": alert.severity === "medium" && !isSelected,
          "border-l-severity-low": alert.severity === "low" && !isSelected,
          "border-l-severity-info": alert.severity === "info" && !isSelected,
        },
        isSelected && "bg-surface-3 border-l-accent",
        !isSelected && "hover:bg-surface-2"
      )}
    >
      {/* Thumbnail */}
      <div className="h-12 w-16 shrink-0 overflow-hidden rounded border border-border bg-surface-2">
        {alert.snapshotPath ? (
          <img
            src={api.alertSnapshotUrl(alert.id)}
            alt=""
            loading="lazy"
            className="h-full w-full object-cover"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none" }}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <ImageOff size={14} className="text-text-muted/40" />
          </div>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 truncate text-[13px] font-medium text-text-primary">
            <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", statusDotColor(alert.status))} />
            {alert.type}
          </span>
          <StatusBadge severity={alert.severity} />
        </div>
        <div className="mt-1 flex items-center gap-1.5 text-[11px] text-text-muted">
          <Camera size={11} />
          <span className="font-mono">{alert.cameraId}</span>
          <span className="text-border-subtle">·</span>
          <span>{timeAgo(alert.timestamp)}</span>
        </div>
        {alert.plateText && (
          <div className="mt-1 inline-block rounded bg-severity-high/10 px-1.5 py-0.5 text-[11px] font-mono font-semibold tracking-wider text-severity-high">
            {alert.plateText}
          </div>
        )}
        {alert.reasonDetail && (
          <p className="mt-1 truncate text-[11px] text-text-muted" title={alert.reasonDetail}>
            {alert.reasonDetail}
          </p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Point AlertFeed at FeedAlert**

In `dashboard/src/components/alert/AlertFeed.tsx`: delete the local `interface Alert {...}` and replace usages with:
```ts
import type { FeedAlert } from "@/lib/alerts"
// props: alerts: FeedAlert[]; onSelect?: (alert: FeedAlert) => void
```

- [ ] **Step 3: Point AlertDetailPanel at FeedAlert**

In `dashboard/src/components/alert/AlertDetailPanel.tsx`: delete the local `interface Alert {...}` and `import type { FeedAlert } from "@/lib/alerts"`; change props `alert: FeedAlert | null`. Keep the modal/backdrop for now (Task 9 replaces the AlertsPage usage with `AlertDetailColumn`; DashboardPage still opens this modal — leave it working).

Note: existing body references `alert.type` (already the human label from `mapApiAlert`) — unchanged.

- [ ] **Step 4: Build**

Run: `npm run build` (workdir `dashboard/`)
Expected: clean exit 0.

- [ ] **Step 5: Commit**

```powershell
git add dashboard/src/components/alert/AlertItem.tsx dashboard/src/components/alert/AlertFeed.tsx dashboard/src/components/alert/AlertDetailPanel.tsx
git commit -m "feat(dashboard): enriched alert rows — thumbnail, status dot, plate chip, reason detail line; FeedAlert prop types"
```

---

### Task 9: Master–detail layout — `AlertDetailColumn` + AlertsPage redesign + filters + wired actions

**Files:**
- Create: `dashboard/src/components/alert/AlertDetailColumn.tsx`
- Modify: `dashboard/src/pages/AlertsPage.tsx` (two-column grid, filter chips, auto-select, optimistic actions)
- Verify: `npm run build` (workdir `dashboard/`)

**Interfaces:**
- Consumes: Task 7 (`FeedAlert`, `mapApiAlert`, `isOpenStatus`, `labelForReason`), Task 8 (`AlertFeed`/`AlertItem`), Task 4 endpoints via `api.acknowledgeAlert/escalateAlert/falsePositiveAlert`, `api.alertSnapshotUrl`.
- Produces: non-modal persistent detail (spec §5.3): snapshot (or honest placeholder), severity + numeric score, `reasonDetail` sentence, plate row, camera/time/id metadata, AI block labeled `AI · {aiSource}` (only when present — never faked), actions row wired to the three endpoints with optimistic UI + revert + inline `error` text. Severity chips (All/Critical/High/Medium/Low/Info with counts) + status filter (`all | open | acknowledged`) are client-side. Newest auto-selected when none selected; SSE `alert_fired` prepends + becomes selection. Accepts optional `initialSelectedId` + `onSelectedIdChange` for Task 10 navigation handoff.
- The modal `AlertDetailPanel` remains for DashboardPage only; AlertsPage no longer renders it.

- [ ] **Step 1: Create AlertDetailColumn**

Create `dashboard/src/components/alert/AlertDetailColumn.tsx`:

```tsx
import { useState } from "react"
import { MapPin, Clock, AlertTriangle, Camera, Hash, Sparkles } from "lucide-react"
import { StatusBadge } from "@/components/ui/StatusBadge"
import { api } from "@/services/api"
import { labelForReason, type FeedAlert } from "@/lib/alerts"

interface AlertDetailColumnProps {
  alert: FeedAlert | null
  onChanged: (updated: FeedAlert) => void
}

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

export function AlertDetailColumn({ alert, onChanged }: AlertDetailColumnProps) {
  const [error, setError] = useState<string | null>(null)
  const [snapshotFailed, setSnapshotFailed] = useState(false)

  if (!alert) {
    return (
      <div className="flex h-full min-h-[320px] items-center justify-center rounded-lg border border-border bg-surface">
        <p className="text-sm text-text-muted">Select an alert to view details</p>
      </div>
    )
  }

  const runAction = async (
    action: 'acknowledge' | 'escalate' | 'false-positive',
    nextStatus: string,
  ) => {
    const prev = alert.status
    setError(null)
    onChanged({ ...alert, status: nextStatus }) // optimistic
    try {
      if (action === 'acknowledge') await api.acknowledgeAlert(alert.id)
      else if (action === 'escalate') await api.escalateAlert(alert.id)
      else await api.falsePositiveAlert(alert.id)
    } catch (e) {
      onChanged({ ...alert, status: prev }) // revert
      setError(`Failed to update status (${String(e)})`)
    }
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto rounded-lg border border-border bg-surface">
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface px-5 py-4">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-text-primary">Alert Detail</h2>
          <p className="text-[11px] text-text-muted font-mono">{alert.id}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge severity={alert.severity} />
          <span className="text-[11px] text-text-muted capitalize">{alert.status}</span>
        </div>
      </div>

      <div className="space-y-5 p-5">
        {/* Snapshot */}
        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-text-muted">Snapshot</p>
          <div className="flex aspect-video items-center justify-center overflow-hidden rounded-md border border-border bg-surface-2">
            {alert.snapshotPath && !snapshotFailed ? (
              <img
                src={api.alertSnapshotUrl(alert.id)}
                alt="Alert snapshot"
                className="h-full w-full object-contain"
                onError={() => setSnapshotFailed(true)}
              />
            ) : (
              <div className="text-center">
                <AlertTriangle size={20} className="mx-auto mb-1 text-text-muted/40" />
                <p className="text-[11px] text-text-muted">
                  {alert.snapshotPath ? "Snapshot failed to load" : "No snapshot captured"}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Severity + score */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-primary">{labelForReason(alert.type)}</span>
          <span className="font-mono text-[13px] text-text-secondary">
            score {alert.threatScore.toFixed(2)}
          </span>
        </div>

        {/* Reason detail */}
        {alert.reasonDetail && (
          <p className="rounded-md border border-border bg-surface-2 px-3 py-2 text-[13px] text-text-secondary">
            {alert.reasonDetail}
          </p>
        )}

        {/* Plate */}
        {alert.plateText && (
          <div className="flex items-center gap-2 text-[13px]">
            <Hash size={14} className="shrink-0 text-text-muted" />
            <span className="text-text-muted">Plate</span>
            <span className="ml-auto font-mono font-semibold tracking-wider text-severity-high">
              {alert.plateText}
            </span>
          </div>
        )}

        {/* Metadata */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-[13px]">
            <Camera size={14} className="shrink-0 text-text-muted" />
            <span className="text-text-muted">Camera</span>
            <span className="ml-auto font-mono text-text-primary">{alert.cameraId}</span>
          </div>
          <div className="flex items-center gap-2 text-[13px]">
            <Clock size={14} className="shrink-0 text-text-muted" />
            <span className="text-text-muted">Time</span>
            <span className="ml-auto text-text-primary">{formatTime(alert.timestamp)}</span>
          </div>
          <div className="flex items-center gap-2 text-[13px]">
            <MapPin size={14} className="shrink-0 text-text-muted" />
            <span className="text-text-muted">Status</span>
            <span className="ml-auto text-text-primary capitalize">{alert.status}</span>
          </div>
        </div>

        {/* AI explanation (only when backend provided it — never faked) */}
        {alert.aiExplanation && (
          <div className="rounded-md border border-border bg-surface-2 p-3">
            <p className="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-text-muted">
              <Sparkles size={11} />
              AI · {alert.aiSource || "local"}
            </p>
            <p className="text-[13px] leading-relaxed text-text-secondary">{alert.aiExplanation}</p>
          </div>
        )}

        {/* Actions */}
        <div>
          <p className="mb-3 text-[10px] font-medium uppercase tracking-wider text-text-muted">Actions</p>
          <div className="flex gap-2">
            <button
              onClick={() => runAction('acknowledge', 'acknowledged')}
              disabled={alert.status === 'false_positive'}
              className="flex-1 rounded-md border border-border bg-surface-2 py-2 text-[12px] font-medium text-text-secondary transition-colors hover:bg-surface-3 hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
            >
              Acknowledge
            </button>
            <button
              onClick={() => runAction('escalate', 'escalated')}
              disabled={alert.status === 'false_positive'}
              className="flex-1 rounded-md border border-severity-high/20 bg-severity-high/5 py-2 text-[12px] font-medium text-severity-high transition-colors hover:bg-severity-high/10 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Escalate
            </button>
            <button
              onClick={() => runAction('false-positive', 'false_positive')}
              disabled={alert.status === 'false_positive'}
              className="flex-1 rounded-md border border-border py-2 text-[12px] font-medium text-text-muted transition-colors hover:bg-surface-2 hover:text-text-secondary disabled:cursor-not-allowed disabled:opacity-40"
            >
              False Positive
            </button>
          </div>
          {error && <p className="mt-2 text-[11px] text-severity-critical">{error}</p>}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Rewrite AlertsPage as master–detail**

Replace `dashboard/src/pages/AlertsPage.tsx` content with:

```tsx
import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { AlertFeed } from '@/components/alert/AlertFeed';
import { AlertDetailColumn } from '@/components/alert/AlertDetailColumn';
import { api } from '@/services/api';
import { useSSE } from '@/hooks/useSSE';
import { mapApiAlert, isOpenStatus, type FeedAlert, type Severity } from '@/lib/alerts';
import type { Alert as ApiAlert } from '@/types/api';

type SeverityFilter = 'all' | Severity;
type StatusFilter = 'all' | 'open' | 'acknowledged';

const SEVERITIES: SeverityFilter[] = ['all', 'critical', 'high', 'medium', 'low', 'info'];

interface AlertsPageProps {
  initialSelectedId?: string | null;
}

export function AlertsPage({ initialSelectedId = null }: AlertsPageProps) {
  const [alerts, setAlerts] = useState<FeedAlert[]>([]);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(initialSelectedId);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('open');

  useEffect(() => {
    api
      .getAlerts()
      .then((raw) => setAlerts(raw.map(mapApiAlert)))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const { on } = useSSE('/api/v1/alerts/stream');
  useEffect(() => {
    on('alert_fired', (data) => {
      const mapped = mapApiAlert(data as unknown as ApiAlert);
      setAlerts((prev) => [mapped, ...prev]);
      setSelectedAlertId(mapped.id); // newest becomes selection
    });
  }, [on]);

  // Newest auto-selected when none selected (initialSelectedId from nav may miss if list still loading)
  useEffect(() => {
    if (!selectedAlertId && alerts.length > 0) {
      setSelectedAlertId(alerts[0].id);
    }
  }, [alerts, selectedAlertId]);

  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = { all: alerts.length, critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    for (const a of alerts) counts[a.severity] = (counts[a.severity] || 0) + 1;
    return counts;
  }, [alerts]);

  const filtered = useMemo(() => {
    return alerts.filter((a) => {
      if (severityFilter !== 'all' && a.severity !== severityFilter) return false;
      if (statusFilter === 'open' && !isOpenStatus(a.status)) return false;
      if (statusFilter === 'acknowledged' && a.status !== 'acknowledged') return false;
      return true;
    });
  }, [alerts, severityFilter, statusFilter]);

  const selectedAlert = alerts.find((a) => a.id === selectedAlertId) || null;

  const handleChanged = (updated: FeedAlert) => {
    setAlerts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="space-y-4"
    >
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Alerts</h1>
        <p className="text-sm text-text-secondary">
          Threat and anomaly alerts generated from detections.
        </p>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        {SEVERITIES.map((s) => (
          <button
            key={s}
            onClick={() => setSeverityFilter(s)}
            className={
              severityFilter === s
                ? 'rounded-full border border-accent bg-accent/10 px-3 py-1 text-[11px] font-medium text-accent'
                : 'rounded-full border border-border px-3 py-1 text-[11px] font-medium text-text-muted hover:bg-surface-2'
            }
          >
            {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
            <span className="ml-1.5 font-mono opacity-70">{severityCounts[s] ?? 0}</span>
          </button>
        ))}
        <span className="mx-1 h-4 w-px bg-border" />
        {(['all', 'open', 'acknowledged'] as StatusFilter[]).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={
              statusFilter === s
                ? 'rounded-full border border-accent bg-accent/10 px-3 py-1 text-[11px] font-medium text-accent'
                : 'rounded-full border border-border px-3 py-1 text-[11px] font-medium text-text-muted hover:bg-surface-2'
            }
          >
            {s === 'all' ? 'All statuses' : s === 'open' ? 'Open' : 'Acknowledged'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="animate-pulse space-y-2 rounded-md border border-border bg-surface p-4">
              <div className="h-3 w-3/4 rounded bg-surface-2" />
              <div className="h-2.5 w-1/3 rounded bg-surface-2" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="min-w-0">
            <AlertFeed
              alerts={filtered}
              selectedId={selectedAlertId ?? undefined}
              onSelect={(a) => setSelectedAlertId(a.id)}
            />
          </div>
          <div className="min-w-0">
            <AlertDetailColumn alert={selectedAlert} onChanged={handleChanged} />
          </div>
        </div>
      )}
    </motion.div>
  );
}
```

- [ ] **Step 3: Build**

Run: `npm run build` (workdir `dashboard/`)
Expected: clean exit 0.

- [ ] **Step 4: Commit**

```powershell
git add dashboard/src/components/alert/AlertDetailColumn.tsx dashboard/src/pages/AlertsPage.tsx
git commit -m "feat(dashboard): master-detail alerts page — persistent detail column, severity/status filters, wired acknowledge/escalate/false-positive"
```

---

### Task 10: App-shell alert banner + beep + mute (notifications, choice A)

**Files:**
- Create: `dashboard/src/components/alert/AlertBanner.tsx`
- Modify: `dashboard/src/components/layout/ConsoleLayout.tsx` (mount banner; navigation handoff to AlertsPage)
- Verify: `npm run build` (workdir `dashboard/`)

**Interfaces:**
- Consumes: Task 7 `mapApiAlert`, useSSE `/api/v1/alerts/stream`, react-router `useNavigate` + `location.state` for handoff (ConsoleLayout is inside `ProtectedRoute`+`BrowserRouter` — navigation is available).
- Produces (spec §5.4): on `alert_fired` — red banner slides in at top (auto-dismiss ~5s, click ⇒ navigate `/alerts` with `state: { selectAlertId }`), two-tone beep via Web Audio (no permissions), selects the alert when already on `/alerts` (via `navigate(..., { state })` re-dispatch OR simpler: page already auto-selects new SSE alerts from Task 9 — banner navigation carries `selectAlertId` for cross-page case only). Mute toggle persisted `localStorage['ibvap.alerts.muted']`; beep only when `document.visibilityState === 'visible'`; rate-limit beeps to 1/s (belt-and-braces over backend cooldown). Existing DashboardPage `plate_read` toasts untouched.
- AlertsPage must read `location.state.selectAlertId` on mount (small addition here or in Task 9's component — do it here to keep Task 9 focused): `useLocation()` + `useState(() => (location.state as {selectAlertId?: string} | null)?.selectAlertId ?? null)` as the initial `selectedAlertId`.

- [ ] **Step 1: Create AlertBanner**

Create `dashboard/src/components/alert/AlertBanner.tsx`:

```tsx
import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Bell, BellOff } from "lucide-react";
import { useSSE } from "@/hooks/useSSE";
import { mapApiAlert, type FeedAlert } from "@/lib/alerts";
import type { Alert as ApiAlert } from "@/types/api";

const MUTE_KEY = "ibvap.alerts.muted";
const BANNER_MS = 5000;
const BEEP_MIN_GAP_MS = 1000;

function readMuted(): boolean {
  try { return localStorage.getItem(MUTE_KEY) === "1"; } catch { return false; }
}

function playTwoToneBeep() {
  if (typeof window === "undefined") return;
  if (document.visibilityState !== "visible") return;
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.setValueAtTime(1174.7, now + 0.12);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.2, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.4);
    osc.onended = () => ctx.close().catch(() => {});
  } catch {
    // Audio may be blocked by browser policy — never break the page for a beep.
  }
}

export function AlertBanner() {
  const navigate = useNavigate();
  const location = useLocation();
  const { on } = useSSE("/api/v1/alerts/stream");
  const [banner, setBanner] = useState<FeedAlert | null>(null);
  const [muted, setMuted] = useState(readMuted);
  const lastBeep = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismiss = useCallback(() => {
    setBanner(null);
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
  }, []);

  const show = useCallback((alert: FeedAlert) => {
    setBanner(alert);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(dismiss, BANNER_MS);
  }, [dismiss]);

  useEffect(() => {
    on("alert_fired", (data) => {
      const mapped = mapApiAlert(data as unknown as ApiAlert);
      const now = Date.now();
      if (!readMuted() && now - lastBeep.current >= BEEP_MIN_GAP_MS) {
        lastBeep.current = now;
        playTwoToneBeep();
      }
      show(mapped);
    });
    // Cleanup: SSE client disconnects via useSSE unmount; clear local timer.
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [on, show]);

  const toggleMute = () => {
    const next = !muted;
    setMuted(next);
    try { localStorage.setItem(MUTE_KEY, next ? "1" : "0"); } catch { /* ignore */ }
  };

  const handleClick = () => {
    if (!banner) return;
    dismiss();
    navigate("/alerts", { state: { selectAlertId: banner.id }, replace: true });
  };

  if (!banner) {
    return (
      <button
        onClick={toggleMute}
        title={muted ? "Alert sound muted" : "Alert sound on"}
        className="fixed bottom-4 right-4 z-50 rounded-full border border-border bg-surface p-2 text-text-muted shadow-lg hover:text-text"
      >
        {muted ? <BellOff size={16} /> : <Bell size={16} />}
      </button>
    );
  }

  return (
    <>
      {/* Banner */}
      <div
        className="fixed left-1/2 top-4 z-50 w-[min(480px,92vw)] -translate-x-1/2 cursor-pointer rounded-lg border border-severity-critical/40 bg-surface px-4 py-3 shadow-xl"
        onClick={handleClick}
        role="alert"
      >
        <div className="flex items-center gap-3">
          <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-severity-critical" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold text-text-primary">
              {banner.type} · {banner.cameraId}
            </p>
            <p className="truncate text-[11px] text-text-muted">
              {banner.reasonDetail ?? `score ${banner.threatScore.toFixed(2)}`} — click to view
            </p>
          </div>
          <span className="shrink-0 rounded bg-severity-critical/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-severity-critical">
            {banner.severity}
          </span>
        </div>
      </div>

      {/* Mute toggle stays available while a banner shows */}
      <button
        onClick={toggleMute}
        title={muted ? "Alert sound muted" : "Alert sound on"}
        className="fixed bottom-4 right-4 z-50 rounded-full border border-border bg-surface p-2 text-text-muted shadow-lg hover:text-text"
      >
        {muted ? <BellOff size={16} /> : <Bell size={16} />}
      </button>
    </>
  );
}
```

- [ ] **Step 2: Mount in ConsoleLayout + accept nav handoff on AlertsPage**

1. `dashboard/src/components/layout/ConsoleLayout.tsx` — full replacement:
```tsx
import { Outlet } from "react-router-dom"
import { Sidebar } from "./Sidebar"
import { TopBar } from "./TopBar"
import { AlertBanner } from "@/components/alert/AlertBanner"

export function ConsoleLayout() {
  return (
    <div className="flex h-screen bg-bg">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <AlertBanner />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```

2. `dashboard/src/pages/AlertsPage.tsx` — accept nav-selected id: add `import { useLocation } from 'react-router-dom';`, and replace the initial state:
```ts
  const location = useLocation();
  const navSelectId = (location.state as { selectAlertId?: string } | null)?.selectAlertId ?? null;
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(navSelectId ?? initialSelectedId);
```
(also add `useLocation` to the react-router import line — currently AlertsPage has no react-router imports).

- [ ] **Step 3: Build**

Run: `npm run build` (workdir `dashboard/`)
Expected: clean exit 0.

- [ ] **Step 4: Commit**

```powershell
git add dashboard/src/components/alert/AlertBanner.tsx dashboard/src/components/layout/ConsoleLayout.tsx dashboard/src/pages/AlertsPage.tsx
git commit -m "feat(dashboard): app-shell alert banner + Web-Audio beep with localStorage mute; cross-page select handoff"
```

---

### Task 11: Full verification — backend suite, dashboard build, restart, manual checklist

**Files:**
- No new files. Verification only (plus fixing anything red found here — fix forward in the owning task's files).

**Interfaces:**
- Consumes: Tasks 1–10.
- Produces: evidence that the feature works (AGENTS.md: raw output, not agent-reported claims — paste actual command output in the final report).

- [ ] **Step 1: Full backend suite**

Run: `.\venv\Scripts\python.exe -m pytest -q`
Expected: all green. Record the EXACT pass/fail counts (baseline before this plan was 425 passed; expected new total ≈ 425 + 8 cooldown + 4 cooldown-wiring + 4 api-fields + 1 reason-detail + 3 migration + 5 status-lifecycle + 9 snapshot + 4 edge-snapshot ≈ 463 — exact number depends on collected tests; report what actually ran).

- [ ] **Step 2: Dashboard production build**

Run: `npm run build` (workdir `dashboard/`)
Expected: tsc + vite clean, exit 0. Paste the output tail.

- [ ] **Step 3: Restart fusion server with new code + health check**

The fusion server may still be running the old code (webcam-fix PID from earlier). Restart it (exact command per repo convention — if a helper script exists use it; otherwise the uvicorn entrypoint used previously) and run:
```powershell
Invoke-RestMethod http://localhost:8000/health
```
Expected: healthy JSON. Also hit the migrated DB once:
```powershell
Invoke-RestMethod http://localhost:8000/api/v1/alerts?limit=2
```
Expected: 200; items include `plate_text`, `reason_detail`, `snapshot_path` keys (nulls fine on old rows).

- [ ] **Step 4: Snapshot + status endpoint smoke (live)**

```powershell
# Unknown id → 404 (proves routes exist)
try { Invoke-WebRequest http://localhost:8000/api/v1/alerts/nope/snapshot -UseBasicParsing } catch { $_.Exception.Response.StatusCode.value__ }
try { Invoke-WebRequest -Method Post http://localhost:8000/api/v1/alerts/nope/escalate -UseBasicParsing } catch { $_.Exception.Response.StatusCode.value__ }
```
Expected: `404` and `404` (route exists, id doesn't). A `405` would mean the route is MISSING — fix before proceeding.

- [ ] **Step 5: Manual FE checklist (NO test runner — state results honestly, do NOT claim automated coverage)**

With dashboard dev server or built dist served, walk this checklist and record pass/fail per line:
1. Alerts page shows two columns (feed left, persistent detail right — no modal slide-over).
2. Severity chips render with counts; clicking filters the feed; status chips filter open/acknowledged.
3. A fresh alert row shows: thumbnail OR honest placeholder, human-readable type label, status dot, plate chip (when plate present), reason detail line.
4. Detail column shows snapshot (or "No snapshot captured"), score, reason sentence, plate, AI block ONLY when backend sent one (labeled `AI · {source}`).
5. Acknowledge → status updates in UI immediately, persists across reload (GET returns `acknowledged`).
6. Escalate → status `escalated`, persists across reload.
7. False Positive → status `false_positive`, persists; Acknowledge/Escalate now disabled (400 from API).
8. New alert (SSE) → red banner slides in at top + two-tone beep (tab visible); banner click navigates to /alerts with that alert selected.
9. Mute button toggles; reload page → mute persists (localStorage `ibvap.alerts.muted`).
10. Tab hidden (switch away) → new alert shows banner (if you come back within 5s) but NO beep on arrival rule: beep only fires while visible — verify by muting/unmuting and switching tabs.
11. Dashboard page still shows plates in its alert feed + plate_read toasts unchanged.
12. Duplicate suppression: same object sitting in an ROI for >60s while events stream → exactly one alert row (check GET /api/v1/alerts count for that object), re-arms after leaving ROI or 60s.

- [ ] **Step 6: Contract review (AGENTS.md Rule 5)**

Confirm `ARCHITECTURE.md` §5 contains: DetectionEvent `snapshot`, Alert `reason_detail` + `snapshot_path` + `plate_text`, status enum with `escalated | false_positive`, and each has a dated FLAGGED note. Confirm `schema.sql` alerts DDL matches. Grep for leftovers:
```powershell
Select-String -Path ARCHITECTURE.md -Pattern "reason_detail|snapshot_path|escalated"
```

- [ ] **Step 7: Final report (no commit unless user asked)**

Report to the user (with raw outputs, per AGENTS.md verification discipline):
- pytest tail (exact counts)
- dashboard build tail
- health/smoke results
- manual checklist table (12 rows, pass/fail/notes)
- what was committed (list the `git log --oneline` lines from Tasks 1–10 commits) vs what remains uncommitted (webcam-fix batch files)
- honest caveats: FE has no automated tests (build + manual only); cooldown state is in-memory (resets on restart — acceptable per spec §6); historical 525 alerts not backfilled with snapshots (out of scope).

---

## Summary

| Task | Deliverable | Spec trace |
|---|---|---|
| 1–2 | CooldownGate + wiring: 60s dedup, per-ROI re-arm, watchlist time-only — kills the 525-alert flood | §4.1 |
| 3 | `reason_detail` at fire time, `snapshot_path` column, AlertResponse/SSE fields incl. missing `plate_text` fix, §5 flag | §4.2, §4.5, §4.6 |
| 4 | Status lifecycle `escalated`/`false_positive` + SQLite CHECK rebuild + 2 endpoints, §5 flag | §4.4 |
| 5 | Snapshot store: post-broadcast decode/save, `GET /{id}/snapshot`, .gitignore `storage/` | §4.3 |
| 6 | Edge `encode_snapshot` ≤640px + 1/s throttle + camera_worker attach, §5 DetectionEvent flag | §4.3, §4.6, Rule 2 |
| 7 | Shared `FeedAlert` lib + types + API methods; plates/details finally reach both pages | §5.2 |
| 8 | Enriched `AlertItem` rows (thumb/dot/plate/reason) + Feed prop types | §5.2 |
| 9 | Master–detail AlertsPage, filters, auto-select, optimistic wired actions | §5.1, §5.3 |
| 10 | App-shell banner + beep + mute + cross-page select | §5.4 |
| 11 | Full verification: 463-ish pytest, build, restart, 12-row manual checklist, §5 grep | §7 |

Every task ends RED → GREEN → commit with exact file staging (never `git add -A` — webcam-fix files stay uncommitted).










