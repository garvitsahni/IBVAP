# Phase 3 — Security & Integrity Layer

**Status:** FINALIZED
**Date:** 2026-09-11
**Owner:** 1 engineer (does not need to wait on Phase 1/2)

---

## 1. Overview

Phase 3 adds the tamper-evident ledger, camera compromise detection, and local watchlist matching. These features are self-contained and can start immediately after Phase 0.

**Exit criteria (live demo):**
- (a) Manually edit a stored ledger entry in the DB, run verification, show it flagged as broken
- (b) Cover a camera lens, show a "camera compromised" alert fire
- (c) Add a face/plate to the watchlist, show a match fire correctly

---

## 2. Bug Fix — Hash Scheme Inconsistency

**Problem:** `FootprintChainWriter._compute_hash()` and `ledger.py verify_chain()` use different hash formulas. Verification always fails for entries written by the actual writer.

| Component | Current hash formula |
|---|---|
| `FootprintChainWriter._compute_hash()` | `SHA256(object_id + camera_id + timestamp + event_type + previous_hash)` |
| `ledger.py verify_chain()` | `SHA256(object_id + camera_id + timestamp + event_type + "footprint")` |

**Canonical scheme (chosen):** `SHA256(object_id + camera_id + timestamp + event_type + previous_hash)`

**Changes:**
- `fusion_server/core/ledger.py`: Update `verify_chain()` and `append_entry()` to use canonical scheme
- `fusion_server/services/footprint_writer.py`: Already correct, no change needed
- `scripts/verify_ledger.py`: Update `test_tamper_detection()` to use canonical scheme
- Add integration test: write via writer → verify via verifier → tamper → verify fails

---

## 3. Tamper-Evident Ledger (Feature #12)

### 3.1 Current State

- Hash chain linkage works for FootprintEntry writes
- `verify_chain()` in `ledger.py` verifies hash + previous_hash linkage
- `verify_ledger.py` script can verify all chains in the DB

### 3.2 Gaps

- Alert records have no hash chain linkage
- Verification only checks FootprintEntry, not Alert entries
- Alert model lacks `hash` and `previous_hash` columns

### 3.3 Changes

**Alert model (`fusion_server/db/models.py`):**
- Add `hash` column (String(64), nullable)
- Add `previous_hash` column (String(64), nullable)

**Alert lifecycle (`fusion_server/core/`):**
- New `alert_ledger.py` module that:
  - On alert write: computes `SHA256(alert_id + object_id + camera_id + timestamp + reason + previous_hash)`
  - Returns the hash for storage
  - Alerts form a **separate chain** from FootprintEntry (keyed by `alert_id`), because alerts and footprint entries have different schemas and lifecycles. The `verify_ledger.py` script verifies both chains independently.

**Verification (`scripts/verify_ledger.py`):**
- Extend to verify both FootprintEntry and Alert chains
- Single `--all` flag checks both

**API (`fusion_server/api/alerts.py`):**
- Update alert creation to include hash computation and chain linkage

---

## 4. Camera Tamper/Blinding Detection (Feature #19)

### 4.1 Current State

- `CameraHealthService` in `edge/camera_health.py` computes SSIM and scene drift
- `CameraHealthStore` in `fusion_server/services/camera_health_store.py` stores health status
- No alert firing on compromise

### 4.2 New Frame-Diff Heuristics

Add to `CameraHealthService`:

| Detection | Method | Threshold | Alert reason |
|---|---|---|---|
| **Darkness/blinding** | Mean pixel intensity of grayscale frame | < 15 (0-255 scale) | `camera_blinding` |
| **Blur/obscured** | Variance of Laplacian | < 50 | `camera_obscured` |
| **Frozen frame** | Mean absolute diff between consecutive frames | < 1.0 | `camera_frozen` |

Each returns a status dict: `{"status": "ok" | "blinding" | "obscured" | "frozen", "metric": float}`

### 4.3 Integration

**Edge (`edge/camera_worker.py`):**
- Create `CameraHealthService` per camera worker
- Set reference frame on first frame
- Run health checks every N frames (configurable, default 30)
- Send health status to fusion server via `POST /api/v1/cameras/{camera_id}/health`

**Fusion server (`fusion_server/api/routes/cameras.py`):**
- New `POST /api/v1/cameras/{camera_id}/health` endpoint
- Updates `CameraHealthStore`
- If status is not "ok": fires a `camera_compromised` Alert with reason = the specific status

**New event_type:**
- `camera_compromised` added to FootprintEntry `event_type` CHECK constraint

### 4.4 Data Flow

```
Edge camera_worker.py
  → CameraHealthService.check_health(frame)
  → POST /api/v1/cameras/{camera_id}/health {status, ssim, metric}
  → Fusion server CameraHealthStore.update()
  → If status != "ok":
      → Create Alert(reason="camera_{status}", status="fired")
      → Write FootprintEntry(event_type="camera_compromised")
      → Hash-chain linkage
```

---

## 5. Local Offline Watchlist Matching (Feature #21)

### 5.1 Current State

- Watchlist CRUD API (`fusion_server/api/watchlist.py`)
- Watchlist model with pgvector embedding column
- No encryption, no matching at detection time

### 5.2 Encryption

**Approach:** Fernet symmetric encryption (AES-128-CBC)

**Implementation (`fusion_server/core/watchlist_crypto.py`):**
- `encrypt_embedding(embedding: List[float], key: bytes) -> bytes` — serialize to JSON, encrypt with Fernet
- `decrypt_embedding(encrypted: bytes, key: bytes) -> List[float]` — decrypt, deserialize
- Key loaded from `WATCHLIST_ENCRYPTION_KEY` env var (Fernet generates a new key if not set)

**Database change:**
- Watchlist `embedding` column type changes from `Vector(512)` to `LargeBinary` (encrypted blob)
- Add a separate `embedding_dim` column (Integer) to know the original dimension
- **Migration required:** Existing plaintext embeddings must be re-encrypted

### 5.3 Matching at Detection Time

**New service (`fusion_server/services/watchlist_matcher.py`):**
- `match_detection(db, embedding, object_type) -> Optional[WatchlistMatch]`
- Decrypts all active watchlist entries of matching type
- Computes cosine similarity against incoming embedding
- Returns match if similarity > threshold (default 0.70 for face, 0.65 for plate)

**Integration (`fusion_server/api/events.py`):**
- After storing the detection event, if embedding is present:
  - Call `WatchlistMatcher.match_detection()`
  - If match found: fire a `watchlist_match` Alert with `reference_id` from watchlist entry

**New alert reason:** `watchlist_match`

### 5.4 Data Flow

```
Edge → POST /api/v1/events {embedding, object_type}
  → Store DetectionEvent
  → WatchlistMatcher.match_detection(embedding, object_type)
  → Decrypt watchlist embeddings, compute similarities
  → If match found:
      → Create Alert(reason="watchlist_match", status="fired")
      → Include reference_id in alert metadata
```

---

## 6. Database Schema Changes

### Alert model additions
```sql
ALTER TABLE alerts ADD COLUMN hash VARCHAR(64);
ALTER TABLE alerts ADD COLUMN previous_hash VARCHAR(64);
```

### Watchlist model changes
Since this is Stage 1 with no production data, we drop and recreate the watchlist table rather than migrating:
```sql
DROP TABLE IF EXISTS watchlist;
CREATE TABLE watchlist (
    id BIGSERIAL PRIMARY KEY,
    watchlist_type VARCHAR(16) NOT NULL,
    reference_id VARCHAR(128) NOT NULL,
    embedding BYTEA NOT NULL,
    embedding_dim INTEGER DEFAULT 512,
    metadata JSON,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    CONSTRAINT ck_watchlist_type CHECK (watchlist_type IN ('face', 'plate'))
);
```

### FootprintEntry event_type constraint update
```sql
ALTER TABLE footprint_entries DROP CONSTRAINT ck_footprint_event_type;
ALTER TABLE footprint_entries ADD CONSTRAINT ck_footprint_event_type CHECK (event_type IN ('first_seen', 'hop', 'alert', 'last_seen', 'camera_compromised'));
```

---

## 7. Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `fusion_server/core/ledger.py` | Modify | Fix hash scheme in `verify_chain()` and `append_entry()` |
| `fusion_server/core/alert_ledger.py` | Create | Alert hash chain linkage |
| `fusion_server/core/watchlist_crypto.py` | Create | Fernet encryption for watchlist embeddings |
| `fusion_server/db/models.py` | Modify | Add hash/previous_hash to Alert, change Watchlist embedding type |
| `fusion_server/services/watchlist_matcher.py` | Create | Watchlist matching at detection time |
| `fusion_server/services/camera_health_store.py` | Modify | Add alert firing on compromise |
| `fusion_server/api/routes/cameras.py` | Modify | Add POST /health endpoint |
| `fusion_server/api/events.py` | Modify | Integrate watchlist matching |
| `fusion_server/api/alerts.py` | Modify | Include hash in alert creation |
| `edge/camera_health.py` | Modify | Add darkness/blur/frozen detection |
| `edge/camera_worker.py` | Modify | Send health status to fusion server |
| `scripts/verify_ledger.py` | Modify | Verify both FootprintEntry and Alert chains |
| `tests/test_phase3_*.py` | Create | Tests for all Phase 3 features |

---

## 8. Testing Strategy

### Unit tests
- `test_ledger_hash_scheme.py` — verify canonical hash scheme, writer-verifier consistency
- `test_alert_ledger.py` — alert hash chain linkage
- `test_watchlist_crypto.py` — encrypt/decrypt round-trip
- `test_watchlist_matcher.py` — matching with mock DB
- `test_camera_compromise_detection.py` — darkness, blur, frozen-frame heuristics

### Integration tests
- `test_phase3_integration.py`:
  - Write footprint → verify chain → tamper entry → verify fails
  - Write alert → verify it's in the chain
  - Add watchlist entry → send detection with matching embedding → alert fires
  - Send camera health status "blinding" → alert fires

### Live demo tests (require infrastructure)
- Manual DB edit → verification script flags break
- Cover camera lens → alert fires
- Add face to watchlist → detection triggers match alert

---

## 9. Cross-Phase Rules Compliance

- No phase begins consuming another phase's output until that output matches the frozen data contract in ARCHITECTURE.md Section 5
- Every phase ends with a live demo on real/simulated input
- Any deviation from "fully working, not faked" is flagged in this spec

**Deviations flagged:**
- Watchlist encryption key management: key is in `.env` file (acceptable for Stage 1 laptop development). Production deployment needs a proper key management solution.
- Camera compromise thresholds (darkness=15, blur=50, frozen=1.0) are initial values that may need tuning on real hardware.

---

*Phase 3 Design Spec — IBVAP*
