# Live Cross-Camera Link Rate (production matching path)

Measured with `scripts/bench_link_rate.py`: K VeRi-776 identity pairs (same vehicle, two different cameras) embedded with the production vehicle ReID path (`ReIDService.extract_embedding` -> `vehicle_reid.onnx`) and ingested through the production `_ingest_event()` + `MatchingEngine` (vehicle threshold 0.60 cosine, 5-minute window; event B at T+4min, pairs spaced 10 min apart so each window contains only its own pair).

**Deviation from plan (flagged):** the original plan proposed cam1->cam2 footage walk-throughs, but repo footage has no verified cross-camera identity ground truth — a footage success % would be unverifiable. VeRi provides real cross-camera ground truth through the same production code path.

## Result: 20/20 linked = **100.0%**

- pairs with cosine >= 0.60 threshold: 20/20
- mean same-id cross-camera cosine: 0.870

| Vehicle ID | Cam A | Cam B | Cosine | Linked |
|---|---|---|---:|:---:|
| 0247 | c001 | c002 | 0.952 | yes |
| 0727 | c003 | c004 | 0.847 | yes |
| 0398 | c001 | c002 | 0.927 | yes |
| 0770 | c001 | c002 | 0.905 | yes |
| 0446 | c001 | c002 | 0.877 | yes |
| 0485 | c003 | c004 | 0.865 | yes |
| 0066 | c001 | c012 | 0.969 | yes |
| 0006 | c014 | c015 | 0.900 | yes |
| 0240 | c001 | c002 | 0.857 | yes |
| 0166 | c001 | c013 | 0.843 | yes |
| 0569 | c001 | c012 | 0.932 | yes |
| 0660 | c014 | c015 | 0.839 | yes |
| 0518 | c014 | c015 | 0.765 | yes |
| 0299 | c002 | c003 | 0.931 | yes |
| 0624 | c002 | c003 | 0.945 | yes |
| 0654 | c002 | c003 | 0.835 | yes |
| 0172 | c001 | c002 | 0.780 | yes |
| 0541 | c001 | c002 | 0.754 | yes |
| 0126 | c001 | c002 | 0.895 | yes |
| 0009 | c001 | c012 | 0.791 | yes |

Scope notes: K=20 pairs (default); detection-box quality is not tested here (full-image crops, as VeRi images are vehicle crops) — end-to-end with detector noise is bounded by this + the gated Rank-1 metric in tests/test_eval_gates.py. Single-process SQLite.
