# Task 10: Event Ingestion — Async Matching + Footprint Write

## Status: DONE

## What Was Done

Modified `fusion_server/api/events.py` to trigger async matching and footprint chain writes when a detection event with an embedding is received.

### Changes

**`fusion_server/api/events.py`:**
- Added imports for `MatchingEngine`, `FootprintChainWriter`, `numpy`, and `logging`
- Updated `create_event` handler: after storing the event, if an embedding is provided, runs `MatchingEngine.match_or_create` to get/assign a global `object_id`, updates the event, then writes a footprint entry via `FootprintChainWriter.write_entry`
- Matching and footprint write only execute when `embedding is not None`, keeping no-embedding events fast

**`tests/test_api_phase2.py`:**
- Added `test_event_ingestion_triggers_matching` — POSTs an event with a 512-dim embedding and asserts `object_id` is present and not None

## Test Results

- **68/68 tests pass** (full suite)
- Phase 2 API tests: 3/3 pass

## Commits

- `9234893` — Phase 2: add async matching and footprint write to event ingestion

## Concerns

None. The implementation follows the architectural rules:
- Rule 1 (deterministic vs AI boundary): Matching engine uses geometry/threshold logic, not an ML model making final decisions
- Rule 3 (synchronous ledger write): Footprint write is synchronous and blocking before response
- Rule 4 (AI enrichment doesn't block): No AI enrichment involved in this path
