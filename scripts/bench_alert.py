#!/usr/bin/env python3
"""
Benchmark event-receipt -> alert-fire latency — MVP metrics row 4.

User-locked definition: Alert.created_at minus DetectionEvent.timestamp
(event receipt to alert row persisted with ledger hash). Also reports the
full synchronous _ingest_event wall time for context.

Method (real, not simulated):
  - fresh temp SQLite DB (DATABASE_URL set before importing fusion modules)
  - one full-frame ROI (camera_id='*', alert_on_enter=True) so the
    deterministic rule engine fires on every sample
  - N samples: unique random 512-dim embedding (no re-ID match -> new
    object_id per sample -> cooldown gate always fresh), bbox centroid
    inside the ROI, call the production _ingest_event() directly
  - assert every sample produced an alert (loud failure otherwise)

Caveat noted in the report: measured at _ingest_event entry (post JSON
parse); HTTP/JSON transport overhead of the /api/v1/events route (~1-3 ms)
is excluded.

Writes docs/alert_benchmark.md. Exit 0 after writing the report.

Usage:
    venv\\Scripts\\python.exe scripts\\bench_alert.py [--samples 30]
"""
import argparse
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

REPORT_PATH = REPO_ROOT / "docs" / "alert_benchmark.md"


def pct(sorted_vals, p):
    return sorted_vals[int(p * (len(sorted_vals) - 1))]


def main() -> int:
    parser = argparse.ArgumentParser(description="Alert latency benchmark")
    parser.add_argument("--samples", type=int, default=30)
    args = parser.parse_args()

    # Temp DB must be selected BEFORE any fusion_server.db import (session.py
    # reads DATABASE_URL at import; load_dotenv does not override existing env).
    db_path = Path(tempfile.gettempdir()) / f"ibvap_bench_alert_{os.getpid()}.db"
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    import numpy as np
    from datetime import datetime

    # Import models_roi so ROI table is registered on Base.metadata before
    # create_all (AlertPipeline.load_rois_from_db queries it).
    import fusion_server.db.models  # noqa: F401
    import fusion_server.db.models_roi  # noqa: F401
    from fusion_server.db.session import init_db, SessionLocal
    from fusion_server.api.events import DetectionEventCreate, BBox, _ingest_event
    from fusion_server.services.cooldown_gate import get_cooldown_gate
    from fusion_server.db.models import Alert

    init_db()
    get_cooldown_gate().reset()

    db = SessionLocal()
    try:
        from fusion_server.db.models_roi import ROI
        db.add(ROI(
            camera_id="*",
            name="bench_full_frame",
            polygon=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            alert_on_enter=True,
            alert_on_exit=False,
        ))
        db.commit()

        rng = np.random.default_rng(7)
        receipt_to_alert_ms = []
        ingest_wall_ms = []
        alerts_fired = 0

        print(f"ingesting {args.samples} samples ...")
        for i in range(args.samples):
            emb = rng.standard_normal(512)
            emb = emb / np.linalg.norm(emb)
            ts = datetime.utcnow()
            event = DetectionEventCreate(
                camera_id="bench-cam",
                timestamp=ts,
                object_type="person",
                track_id=str(i),
                bbox=BBox(x1=0.4, y1=0.4, x2=0.6, y2=0.6),
                embedding=emb.tolist(),
                confidence=0.9,
            )
            t0 = time.perf_counter()
            result = _ingest_event(event, db)
            wall = (time.perf_counter() - t0) * 1000.0
            ingest_wall_ms.append(wall)

            pipeline_result = result.get("pipeline_result") or {}
            fired = pipeline_result.get("alerts") or []
            if not fired:
                print(f"[FAIL] sample {i}: no alert fired "
                      f"(violations={len(pipeline_result.get('violations') or [])})")
                return 1
            for alert in fired:
                delta = (alert.created_at - ts).total_seconds() * 1000.0
                receipt_to_alert_ms.append(delta)
                alerts_fired += 1

        # sanity: DB has the alerts too
        db_count = db.query(Alert).count()
        if db_count != alerts_fired:
            print(f"[FAIL] alert row count {db_count} != fired {alerts_fired}")
            return 1

        r2a = sorted(receipt_to_alert_ms)
        wall = sorted(ingest_wall_ms)
        stats = {
            "samples": args.samples,
            "alerts": alerts_fired,
            "r2a_mean": statistics.mean(r2a),
            "r2a_p50": statistics.median(r2a),
            "r2a_p95": pct(r2a, 0.95),
            "wall_mean": statistics.mean(wall),
            "wall_p50": statistics.median(wall),
            "wall_p95": pct(wall, 0.95),
        }
        print(f"receipt->alert: mean={stats['r2a_mean']:.1f}ms "
              f"p50={stats['r2a_p50']:.1f}ms p95={stats['r2a_p95']:.1f}ms "
              f"({stats['alerts']} alerts from {stats['samples']} samples)")
        print(f"_ingest_event wall: mean={stats['wall_mean']:.1f}ms "
              f"p50={stats['wall_p50']:.1f}ms p95={stats['wall_p95']:.1f}ms")
    finally:
        db.close()

    lines = [
        "# Alert Generation Benchmark (event receipt -> alert)",
        "",
        "Measured with `scripts/bench_alert.py` against the production "
        "`_ingest_event()` path on a fresh SQLite DB: full-frame ROI "
        "(deterministic rule engine fires every sample), unique random 512-dim "
        "embedding per sample (new object_id -> cooldown gate fresh), "
        f"{stats['samples']} samples -> {stats['alerts']} alerts (all fired).",
        "",
        "**Metric definition (user-locked):** `Alert.created_at - "
        "DetectionEvent.timestamp` — time from event receipt to the alert row "
        "being persisted with its ledger hash. AI enrichment runs after this "
        "point (async, never blocks — AGENTS.md Rule 4).",
        "",
        "| Metric | Mean ms | p50 ms | p95 ms |",
        "|---|---:|---:|---:|",
        f"| Receipt -> alert (created_at - timestamp) | {stats['r2a_mean']:.1f} | "
        f"{stats['r2a_p50']:.1f} | {stats['r2a_p95']:.1f} |",
        f"| Full `_ingest_event()` wall time (context) | {stats['wall_mean']:.1f} | "
        f"{stats['wall_p50']:.1f} | {stats['wall_p95']:.1f} |",
        "",
        "Scope notes: measured at `_ingest_event()` entry (post JSON parse) — "
        "HTTP/JSON transport overhead of POST /api/v1/events (~1-3 ms) is "
        "excluded. Single-process SQLite; PostgreSQL adds commit latency under "
        "concurrency. Enrichment (LLM/VLM) is deliberately out of scope here.",
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"report written: {REPORT_PATH}")

    try:
        db_path.unlink()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
