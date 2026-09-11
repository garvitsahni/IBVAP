# Task 6 Report: FootprintChainWriter — Hash Chain Logic

## What I Implemented

Created `fusion_server/services/footprint_writer.py` containing the `FootprintChainWriter` class:

- **`_compute_hash()`** — SHA-256 hash of `(object_id, camera_id, timestamp, event_type, previous_hash)`, producing a 64-char hex digest
- **`_get_last_entry()`** — queries the most recent `FootprintEntry` for a given `object_id` from the DB
- **`write_entry()`** — main method that:
  1. Fetches last entry for the object
  2. Skips hop entries when same camera + gap < 30 seconds (deduplication)
  3. Forces `first_seen` event type when no prior entry exists
  4. Computes chained hash including previous hash for tamper-evidence
  5. Creates and persists a `FootprintEntry` via SQLAlchemy
  6. Returns entry dict if written, `None` if skipped

## Test Results

```
5/5 passing (test_footprint_writer.py), 57/57 passing (full suite), output pristine
```

## TDD Evidence

**RED:** All 5 tests failed with `ModuleNotFoundError: No module named 'fusion_server.services.footprint_writer'` — expected since the module didn't exist yet.

**GREEN:** All 5 tests pass after implementation.

**Note on mock fix:** The task brief's test mock chains used `.order_by.return_value.all.return_value` but the implementation calls `.limit(1).all()`, breaking the mock chain (resulting in MagicMock objects instead of the intended lists, causing `TypeError: object supporting the buffer API required`). Fixed the mock chains to `.order_by.return_value.limit.return_value.all.return_value` to correctly match the implementation's query chain.

## Files Changed

| File | Action |
|------|--------|
| `fusion_server/services/footprint_writer.py` | Created (102 lines) |
| `tests/test_footprint_writer.py` | Created (85 lines) |

## Self-Review Findings

- **Completeness:** All 5 acceptance criteria implemented and tested. Hash computation, first_seen, hop detection, same-camera skip, and instantiation all verified.
- **Quality:** Code follows existing patterns (`MatchingEngine` in the same `services/` directory). Clean, minimal, well-named.
- **Discipline:** No overbuilding — implemented exactly what was specified. The `MIN_SAME_CAMERA_GAP = 30` threshold is configurable via constructor.
- **Testing:** Tests verify real behavior (hash output length, event types, previous_hash linkage, skip logic) — not just mocks calling mocks. Mock chains correctly match the implementation's SQLAlchemy query pattern.
