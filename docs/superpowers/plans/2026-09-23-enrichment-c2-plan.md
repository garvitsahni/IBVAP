# Enrichment Honesty + C2 Webhook Shim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AI enrichment honest (template labeled + persisted) and add minimal opt-in C2 push.

**Architecture:** Keep two-speed design: rule engine fires status=fired + sync ledger first; enrichment + C2 forward run fire-and-forget via _enrich_and_broadcast. Only alert JSON crosses; no raw video; localhost only.

**Tech Stack:** FastAPI, SQLAlchemy, requests, SSE broadcaster, hmac/hashlib stdlib, pytest.

## Global Constraints

- Backend FastAPI Python only.
- YOLOv8n laptop baseline; this plan does not swap models.
- PostgreSQL + MinIO/filesystem; no external DB/cloud.
- No cloud API for core; enrichment local only.
- Ledger write sync/blocking; enrichment/C2 never block fired delivery.
- ARCHITECTURE.md Section 5 frozen; only additive nullable ai_source allowed.
- Template fallback labeled [TEMPLATE], never presented as LLM.

---

### Task 1: Persist enrichment + label source honestly

**Files:**
- Modify: `fusion_server/services/alert_pipeline.py`
- Modify: `fusion_server/services/ai_enrichment.py`
- Modify: `fusion_server/db/models.py` (Alert.ai_source nullable String(16))
- Modify: `fusion_server/db/schema.sql` (add ai_source column)
- Test: `tests/test_enrichment_persist.py`

**Interfaces:**
- Consumes: `AIEnrichmentService.enrich(alert_data: dict) -> str`
- Produces: `enrich_with_source(alert_data: dict) -> tuple[str, str]` with source in ("template","llava-local").

- [ ] Step 1: Write failing test (persist + [TEMPLATE] label).
- [ ] Step 2: Run test to verify it fails.
- [ ] Step 3: Implement enrich_with_source + DB persist in _enrich_and_broadcast (try/except, log only, never raise) + broadcast includes ai_source.
- [ ] Step 4: Run pytest targeted.
- [ ] Step 5: Commit.

### Task 2 (stretch, deferred): Ollama localhost opt-in

Deferred. Env keys documented only: AI_ENRICHMENT_BACKEND, OLLAMA_URL, OLLAMA_MODEL. Implement only if laptop has capacity.

### Task 3: Minimal C2 webhook shim (push-only, signed, retry)

**Files:**
- Create: `fusion_server/services/c2_forwarder.py`
- Modify: `fusion_server/services/alert_pipeline.py` (hook after broadcast_alert_fired)
- Modify: `.env.example` (C2_WEBHOOK_URL, C2_WEBHOOK_SECRET, C2_TIMEOUT_S, C2_RETRY)
- Test: `tests/test_c2_forwarder.py`

**Interfaces:**
- Consumes: alert dict {alert_id, object_id, camera_id, reason, threat_score, threat_level, timestamp}.
- Produces: `C2Forwarder.forward(payload: dict) -> bool` via POST with X-IBVAP-Signature hmac-sha256 + X-IBVAP-Alert-ID. False on disabled/failure, log only.

- [ ] Step 1: Write failing test.
- [ ] Step 2: Run to verify fail.
- [ ] Step 3: Implement ~60 lines with run_in_threadpool, retry 2x, never raise.
- [ ] Step 4: Run pytest targeted.
- [ ] Step 5: Commit.
