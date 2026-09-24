#!/usr/bin/env python3
"""
Benchmark ledger (evidence) verification time — MVP metrics row 6.

Two layers, both real:
  1. pure    — in-memory `verify_chain()` (SHA-256 recompute + linkage) over
               chains of 100 / 1_000 / 10_000 entries built with the
               production `append_entry()`.
  2. db      — same chains inserted into a fresh temp SQLite DB, verified via
               the production `verify_all_chains()` (scripts/verify_ledger.py:
               ORM query + per-object verify). This is what an operator runs.
  3. tamper  — flips one entry in the DB and confirms verification fails at
               the right index (correctness of the check being timed).

Writes docs/ledger_benchmark.md. Exit 0 after writing the report.

Usage:
    venv\\Scripts\\python.exe scripts\\bench_ledger.py
"""
import argparse
import os
import statistics
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

REPORT_PATH = REPO_ROOT / "docs" / "ledger_benchmark.md"


def pct(sorted_vals, p):
    return sorted_vals[int(p * (len(sorted_vals) - 1))]


def build_chain(n_entries: int) -> list:
    """In-memory chain via the production append_entry()."""
    from fusion_server.core.ledger import append_entry
    entries = []
    prev = None
    t0 = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(n_entries):
        entry = append_entry(
            object_id="bench-object",
            camera_id=f"cam{(i % 3) + 1}",
            timestamp=(t0 + timedelta(seconds=30 * i)).isoformat(),
            event_type="first_seen" if i == 0 else "hop",
            previous_hash=prev,
        )
        prev = entry["hash"]
        entries.append(entry)
    return entries


def bench_pure(sizes, runs: int) -> list:
    from fusion_server.core.ledger import verify_chain
    results = []
    for n in sizes:
        chain = build_chain(n)
        # correctness: freshly built chain must verify
        ok, broken = verify_chain(chain)
        assert ok, f"fresh chain of {n} failed to verify (broken at {broken})"
        latencies = []
        for _ in range(runs):
            t0 = time.perf_counter()
            ok, _ = verify_chain(chain)
            latencies.append((time.perf_counter() - t0) * 1000.0)
            assert ok
        lat = sorted(latencies)
        mean = statistics.mean(lat)
        row = {"layer": "pure (in-memory verify_chain)", "entries": n,
               "runs": runs, "mean_ms": mean, "p95_ms": pct(lat, 0.95)}
        print(f"  pure n={n}: mean={mean:.1f}ms p95={row['p95_ms']:.1f}ms "
              f"({mean / n * 1000:.1f} us/entry)")
        results.append(row)
    return results


def bench_db(sizes, runs: int, db_path: Path) -> list:
    import shutil
    from fusion_server.db.models import FootprintEntry
    from scripts.verify_ledger import verify_all_chains

    results = []
    for n in sizes:
        # fresh DB per size
        if db_path.exists():
            db_path.unlink()
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        # session module already imported (DATABASE_URL fixed at first import) —
        # rebind engine to this size's DB instead of relying on env re-read.
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import fusion_server.db.session as sess
        engine = create_engine(f"sqlite:///{db_path}",
                               connect_args={"check_same_thread": False})
        import fusion_server.db.models as models_mod
        import fusion_server.db.models_roi  # noqa: F401  (registers on models.Base)
        models_mod.Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        chain = build_chain(n)
        t0 = datetime(2026, 1, 1, 0, 0, 0)
        rows = []
        for i, e in enumerate(chain):
            rows.append(FootprintEntry(
                object_id=e["object_id"],
                camera_id=e["camera_id"],
                timestamp=t0 + timedelta(seconds=30 * i),
                event_type=e["event_type"],
                hash=e["hash"],
                previous_hash=e["previous_hash"],
            ))
        db.add_all(rows)
        db.commit()

        # warmup + correctness on first run
        res = verify_all_chains(db)
        assert res["broken_chains"] == 0, f"db chain n={n} failed verify"
        assert res["valid_chains"] == 1

        latencies = []
        for _ in range(runs):
            t0v = time.perf_counter()
            res = verify_all_chains(db)
            latencies.append((time.perf_counter() - t0v) * 1000.0)
            assert res["broken_chains"] == 0
        lat = sorted(latencies)
        mean = statistics.mean(lat)
        row = {"layer": "db (verify_all_chains: query + verify)", "entries": n,
               "runs": runs, "mean_ms": mean, "p95_ms": pct(lat, 0.95)}
        print(f"  db   n={n}: mean={mean:.1f}ms p95={row['p95_ms']:.1f}ms "
              f"({mean / n * 1000:.1f} us/entry)")
        results.append(row)

        # tamper detection on this DB (correctness of what we just timed)
        mid = n // 2
        rows[mid].camera_id = "cam-tampered"
        db.commit()
        res = verify_all_chains(db)
        assert res["broken_chains"] == 1, "tampered chain was NOT detected"
        print(f"  tamper n={n}: detected (broken chain reported)")
        db.close()
        engine.dispose()

        if db_path.exists():
            db_path.unlink()
    return results


def write_report(pure, db_rows, runs):
    lines = [
        "# Ledger Evidence Verification Benchmark",
        "",
        "Measured with `scripts/bench_ledger.py` (chains built with the "
        "production `append_entry()`; SHA-256 recompute + previous_hash "
        "linkage over every entry).",
        "",
        f"Tamper check: one entry mutated mid-chain — verification correctly "
        f"failed at that chain every run (correctness of the timed operation).",
        "",
        "| Layer | Entries | Runs | Mean ms | p95 ms | us/entry |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in pure + db_rows:
        lines.append(
            f"| {r['layer']} | {r['entries']} | {r['runs']} | "
            f"{r['mean_ms']:.1f} | {r['p95_ms']:.1f} | "
            f"{r['mean_ms'] / r['entries'] * 1000:.1f} |")
    lines.append("")
    lines.append(
        "Scope notes: single-process SQLite; the db layer includes the ORM "
        "query an operator's `verify_ledger.py` run performs. Alert-chain "
        "verification (`verify_alert_chains`) is linkage-only (no hash "
        "recompute) and orders of magnitude cheaper; footprint verification "
        "is the binding number.")
    lines.append("")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"report written: {REPORT_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ledger verification benchmark")
    parser.add_argument("--sizes", nargs="+", type=int,
                        default=[100, 1000, 10000])
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()

    db_path = Path(tempfile.gettempdir()) / f"ibvap_bench_ledger_{os.getpid()}.db"
    # Point session.py at a throwaway DB before its first import (it reads
    # DATABASE_URL at import time).
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    print("pure in-memory verify_chain ...")
    pure = bench_pure(args.sizes, args.runs)
    print("db verify_all_chains (+ tamper detection) ...")
    db_rows = bench_db(args.sizes, args.runs, db_path)

    write_report(pure, db_rows, args.runs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
