# Task 10 Report: Dashboard SystemHealth Component

## Summary

Created a `SystemHealth` React component that displays a color-coded health badge in the dashboard header, with an expandable detail panel showing detection tier, power mode, ledger status, and per-camera status.

## Files

| Action | File |
|--------|------|
| Created | `dashboard/src/components/SystemHealth.tsx` |
| Modified | `dashboard/src/components/Header.tsx` (import + render placement) |

## Implementation Details

- **Status badge:** Color-coded pill button (`ok`=green, `degraded`=yellow, `critical`=red, `unknown`=gray) — clicks toggle an expandable detail panel.
- **Data fetch:** Initial `GET /api/v1/system/health` call on mount, with fallback to `unknown` state on failure.
- **Live updates:** Subscribes to `system_health_changed` SSE events via `EventSource("/api/v1/stream")` to keep the badge current without page refresh.
- **Detail panel:** Absolute-positioned dropdown showing detection tier, power mode, ledger status, and a per-camera online/offline list. Closes on outside click (by toggling state on re-click).
- **Integration:** `<SystemHealth />` added as the last child in Header's flex container, naturally right-aligned after the stats row.

## Build Result

Build succeeded (Vite 8.3.0, 30 modules, 712ms). Pre-existing chunk size warning (>500 kB) unrelated to this change.

## Commits

- `c7134cc` — `feat: add SystemHealth badge to dashboard header`

## Concerns

None. Component matches the spec exactly, build passes cleanly.
