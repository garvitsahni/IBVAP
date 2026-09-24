# Alert Generation Benchmark (event receipt -> alert)

Measured with `scripts/bench_alert.py` against the production `_ingest_event()` path on a fresh SQLite DB: full-frame ROI (deterministic rule engine fires every sample), unique random 512-dim embedding per sample (new object_id -> cooldown gate fresh), 30 samples -> 30 alerts (all fired).

**Metric definition (user-locked):** `Alert.created_at - DetectionEvent.timestamp` — time from event receipt to the alert row being persisted with its ledger hash. AI enrichment runs after this point (async, never blocks — AGENTS.md Rule 4).

| Metric | Mean ms | p50 ms | p95 ms |
|---|---:|---:|---:|
| Receipt -> alert (created_at - timestamp) | 24.9 | 22.1 | 24.8 |
| Full `_ingest_event()` wall time (context) | 30.9 | 27.7 | 33.6 |

Scope notes: measured at `_ingest_event()` entry (post JSON parse) — HTTP/JSON transport overhead of POST /api/v1/events (~1-3 ms) is excluded. Single-process SQLite; PostgreSQL adds commit latency under concurrency. Enrichment (LLM/VLM) is deliberately out of scope here.
