# Ledger Evidence Verification Benchmark

Measured with `scripts/bench_ledger.py` (chains built with the production `append_entry()`; SHA-256 recompute + previous_hash linkage over every entry).

Tamper check: one entry mutated mid-chain — verification correctly failed at that chain every run (correctness of the timed operation).

| Layer | Entries | Runs | Mean ms | p95 ms | us/entry |
|---|---:|---:|---:|---:|---:|
| pure (in-memory verify_chain) | 100 | 5 | 0.1 | 0.1 | 0.9 |
| pure (in-memory verify_chain) | 1000 | 5 | 1.0 | 1.0 | 1.0 |
| pure (in-memory verify_chain) | 10000 | 5 | 10.1 | 10.1 | 1.0 |
| db (verify_all_chains: query + verify) | 100 | 5 | 1.1 | 1.1 | 11.2 |
| db (verify_all_chains: query + verify) | 1000 | 5 | 8.5 | 8.6 | 8.5 |
| db (verify_all_chains: query + verify) | 10000 | 5 | 86.2 | 86.0 | 8.6 |

Scope notes: single-process SQLite; the db layer includes the ORM query an operator's `verify_ledger.py` run performs. Alert-chain verification (`verify_alert_chains`) is linkage-only (no hash recompute) and orders of magnitude cheaper; footprint verification is the binding number.
