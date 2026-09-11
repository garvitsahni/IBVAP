# Task 8: Wire Threat Scoring into Alert Creation

## Objective
Wire the existing `calculate_threat_score()` function into live alert creation paths, replacing hardcoded threat_score values with deterministic calculations.

## Context
- `calculate_threat_score()` exists in `fusion_server/core/threat_scoring.py` but is never called by live code
- Two locations use hardcoded threat_score values:
  - `fusion_server/api/events.py` line 116: `threat_score=0.9` for watchlist matches
  - `fusion_server/api/routes/cameras.py` line 71: `threat_score=0.8` for camera compromise

## Requirements

### 1. Add missing violation types to VIOLATION_BASE_SCORES
- Add `camera_tamper` and `camera_drift` violation types for camera health alerts
- Add `unauthorized_object` for unexpected object types in restricted zones

### 2. Replace hardcoded threat_score in events.py
- Import `calculate_threat_score` and `ThreatContext`
- For watchlist matches, create a ThreatContext with `is_watchlist_match=True`
- Use the calculated score instead of hardcoded 0.9

### 3. Replace hardcoded threat_score in cameras.py
- Import `calculate_threat_score` and `ThreatContext`
- For camera compromise, create a ThreatContext with appropriate violation type
- Use the calculated score instead of hardcoded 0.8

### 4. Create tests
- Create `tests/test_threat_scoring_wiring.py`
- Test that watchlist matches produce threat_score >= 0.9
- Test that camera compromise produces appropriate threat_score
- Test that all violation types have base scores

## Exit Criteria
- [ ] All existing tests still pass
- [ ] New tests pass for wired threat scoring
- [ ] No hardcoded threat_score values remain in events.py or cameras.py
- [ ] calculate_threat_score() is called in both alert creation paths
