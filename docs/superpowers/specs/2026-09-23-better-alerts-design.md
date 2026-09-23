# Better Alerts — Design Spec

**Date:** 2026-09-23
**Status:** Approved (design sections 1–2), pending spec review
**Scope:** Alert quality + content + live notifications + alerts-page redesign (IBVAP)

## 1. Problem

- 525 alerts in DB, all `fired`, repeating the same 5-alert cycle — rule pipeline has **no cooldown/dedup**, so a track inside an ROI re-fires every evaluation.
- `reason` is a raw rule id (`roi_intrusion`); `ai_explanation` only exists for watchlist matches; severity thresholds are fine but nothing explains *why* a score was assigned.
- Dashboard: `mapApiAlert` drops `plateText` (and score/reason detail) so plates never render on the Alerts page; Snapshot slot is a permanent placeholder (nothing captures an image); Escalate / False Positive buttons receive no handlers (dead).
- No live notification when an alert fires — the feed just silently prepends.
- Feed is a flat text list; detail is a modal slide-over that blocks the feed.

## 2. Goals (user decisions)

1. **Quality:** stop duplicate floods; every alert carries a deterministic human-readable explanation.
2. **Content:** snapshot image, plate, AI explanation, working acknowledge/escalate/false-positive actions.
3. **Notifications:** in-page red banner + short beep + auto-select/scroll on `alert_fired` (no OS notifications).
4. **Redesign:** master–detail two-column layout with severity/status filters.

Non-goals (YAGNI): browser Notification API, plate/full-text search, retuning score thresholds, backfilling snapshots for historical alerts, score bumps on escalate, FE unit-test framework, wiring webcam `/detect` detections into the rule engine (webcam ROI alerts).

## 3. Architecture overview

```
edge camera_worker ──event + snapshot b64 (optional)──► fusion /api/v1/events
                                                                     │
                                                                     ▼
                                              cooldown/dedup gate (NEW)
                                                                     ▼
                                       DB write (sync, Rule 3) + broadcast SSE
                                                                     ▼
                                       async: decode+save snapshot JPEG, AI enrichment
                                                                     ▼
                    FE: app-shell banner+beep → AlertsPage master-detail re-render
```

Note: the webcam `/api/v1/detect` path does **not** invoke the alert pipeline today (verified: only `events.py` and camera-health in `cameras.py` create alerts). Wiring webcam detections into the rule engine is explicitly **out of scope** (would be its own phase decision).

Rules compliance: Rule 1 (pipeline cooldown is deterministic; scores unchanged, ML never fires alerts), Rule 2 (one event-triggered still ≤640px crosses edge→fusion — strictly less than the already-allowed short clips; no video), Rule 3 (ledger/synchronous DB write ordering unchanged; cooldown gate runs *before* the write), Rule 4 (snapshot save + AI enrichment are post-broadcast, best-effort), Rule 5 (**§5 addition — see §5 below, must be doc-updated + flagged to phase owners in the same PR**).

## 4. Backend design

### 4.1 Cooldown / re-arm (flood fix)

Location: `fusion_server/services/alert_pipeline.py`, immediately before the alert DB insert (orchestration layer; `core/rule_engine.py` stays pure geometry).

- Key: `(camera_id, reason, object_id)`.
- State: in-memory dict `{key: last_fired_at}` (process-lifetime is acceptable for demo scale; persistence = future work, noted out of scope).
- Fire allowed when: key absent **OR** `now - last_fired_at >= 60s` **OR** the object has **left the ROI** since last fire (pipeline knows current vs previous containment from the violation stream — re-arm on exit is tracked per key with an `active` flag cleared when no violation is present this tick).
- Applies to `roi_intrusion`, `virtual_fence_crossing`, and `watchlist_match` (same gate, same keys).
- Dedup happens before the DB write so duplicates never touch the ledger.

### 4.2 Deterministic reason detail

At fire time the pipeline sets `reason_detail` (plain text, no ML):

- ROI/fence: `"{object_class} entered ROI \"{roi_name}\" · score {threat_score:.2f}"` (variant for exit when `alert_on_exit` fires).
- Watchlist: keeps existing similarity sentence (already present).
- Other rule reasons: f-string template per reason with score appended.

UI-side label map (FE, not contract): `roi_intrusion → ROI Intrusion`, `virtual_fence_crossing → Virtual Fence Crossing`, `watchlist_match → Watchlist Match`.

### 4.3 Snapshot capture (edge path — the only object-alert path)

- New column: `alerts.snapshot_path TEXT NULL` (SQLite + PG; schema.sql comment migration, same pattern as prior TEXT/encrypted changes). Not an ML decision → Rule 1 fine.
- **Edge:** `camera_worker` encodes the triggering frame at event time (long edge ≤640, quality 80, base64) and includes it in the event as `snapshot` (optional; field simply absent on encode failure). Applies to object alerts (ROI/fence/watchlist). Camera-health alerts (`cameras.py`) have no frame → `snapshot_path` stays NULL (honest placeholder in UI).
- **Fusion:** at events ingest, decode `snapshot`, write `storage/alerts/{alert_id}.jpg` (same quality/size as received), store relative path — **base64 is never persisted to DB**.
- **Async + best-effort:** file write happens after the alert row is committed and SSE is broadcast; failure ⇒ `snapshot_path` stays NULL and a warning is logged. Alert delivery never waits on it (Rule 4). Serving: `GET /api/v1/alerts/{id}/snapshot` returns the file (404 if null).

### 4.4 Status lifecycle endpoints

Statuses: `fired → acknowledged | escalated | false_positive`.

- `POST /api/v1/alerts/{alert_id}/acknowledge`
- `POST /api/v1/alerts/{alert_id}/escalate`
- `POST /api/v1/alerts/{alert_id}/false-positive`

Each sets `status` (idempotent on repeat; 404 unknown id; 409/400 illegal transition — design choice: **allow any transition from `fired`/`acknowledged`, reject from terminal `false_positive`**). No threat-score mutation. Broadcast optional status update over SSE only if trivial; FE does optimistic update regardless.

### 4.5 Payload additions

`GET /api/v1/alerts` and SSE `alert_fired` include: `reason_detail`, `snapshot_path`, `plate_text`, `threat_score` (already partially present — implementation verifies and fills gaps; FE types extended to match).

### 4.6 §5 contract flag (Rule 5)

**Addition to ARCHITECTURE.md §5 event contract (frozen-doc change):** optional field `snapshot: string | null` (base64 JPEG ≤640px long edge) on the edge→fusion event payload. Must be updated in ARCHITECTURE.md §5 **and flagged to all phase owners in the same PR** that implements it. Backward compatible (optional field); old edge nodes omitting it simply produce `snapshot_path = NULL`.

## 5. Frontend design

### 5.1 Layout (master–detail)

- `AlertsPage`: two columns — feed ≈40% left, persistent detail right; remove slide-over modal + backdrop entirely.
- Filter bar above feed: severity chips with counts (All / Critical / High / Medium / Low / Info) + status toggle (Open / Acknowledged / all). Filters are client-side (list already fully loaded; no pagination yet).
- Newest alert auto-selected when none selected; new SSE alerts prepend + become selection.

### 5.2 Feed row (`AlertItem`)

Thumbnail (when `snapshot_path`; else compact placeholder block), human-readable type label, `StatusBadge`, camera + relative time, **plate chip** (mono, highlighted, only when present), status dot. Fix `mapApiAlert` to carry `plateText`, `reasonDetail`, `threatScore`, `snapshotPath`, `status`.

### 5.3 Detail column (`AlertDetailPanel` variant)

Sections top→bottom: snapshot (or honest "No snapshot captured" placeholder), severity badge + numeric score, `reason_detail` sentence, plate row, camera/time/id metadata, AI explanation block (label `AI · local`, present only when backend provided it — never faked), actions row: **Acknowledge / Escalate / False Positive** wired to the endpoints with optimistic UI update; on API failure revert status locally and show inline error text.

### 5.4 Notifications (app shell)

- New hook/component (e.g. `useAlertNotifications`) mounted in the app shell so every page gets it; subscribes to `/api/v1/alerts/stream` `alert_fired`.
- On event: red banner slides in at top (auto-dismiss ~5s, click ⇒ navigate/select that alert), short two-tone beep via Web Audio API (no permissions), selects the alert if the user is on Alerts page.
- Sound plays only while `document.visibilityState === "visible"`; **mute toggle persisted in `localStorage`** (key e.g. `ibvap.alerts.muted`); beep rate-limited to 1/s as belt-and-braces on top of the backend cooldown.
- Existing `plate_read` toasts on DashboardPage remain unchanged.

## 6. Error handling summary

| Failure | Behavior |
|---|---|
| Snapshot encode/write fails (edge or fusion) | Alert still fires; `snapshot_path` NULL; warning logged |
| Snapshot GET with NULL path | 404 |
| Status endpoint on unknown id | 404 |
| Status transition from `false_positive` | 400 |
| FE status action API error | Revert optimistic state + inline error text |
| SSE dropped | Feed shows stale list (existing behavior); banner simply misses events until reconnect — acceptable, noted |
| Cooldown state lost on process restart | Duplicate suppression resets (worst case = one extra alert); acceptable for demo scale |

## 7. Testing & verification

- **Backend (pytest/TDD, RED first):** cooldown fires once within 60s then re-arms on exit/re-entry; cooldown applied pre-insert (no DB row for dups); edge event includes thumbnail (encode-failure ⇒ field absent); fusion decodes `snapshot` → file, never stores b64 in DB, and forced write failure ⇒ `snapshot_path` NULL with alert still fired; three status endpoints (happy path, 404, illegal transition); `/alerts` + SSE payload include new fields.
- **Contract:** ARCHITECTURE.md §5 updated with `snapshot` field + flag note in same PR (Rule 5).
- **Frontend:** no test runner exists → verification = `npm run build` (tsc + vite) clean **+ manual retest checklist** (state honestly): feed shows labels/plate chips/filters; detail shows snapshot of a fresh alert; each status button persists across reload; banner + beep on new alert; mute persists; alert while tab hidden → no sound.
- Full backend suite must stay green (currently 425 passed).

## 8. Implementation order (for planning phase)

1. Backend: cooldown gate → RED/GREEN tests.
2. Backend: `reason_detail` generation + payload fields.
3. Backend: snapshot (edge thumbnail + ingest decode + §5 doc edit).
4. Backend: status endpoints.
5. Frontend: types + `mapApiAlert` fix (plate finally visible).
6. Frontend: master–detail layout + filters + enriched row/detail + wired actions.
7. Frontend: app-shell banner + beep + mute.
8. Full suite + dashboard build + manual checklist; restart fusion + rebuild dist for demo.

## 9. Open questions

None blocking — all clarified with user (quality: all issues; notifications: in-page A; layout: master–detail A; approaches: vertical slice #1).
