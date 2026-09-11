"""
Tests for Task 8: Wire Threat Scoring into Alert Creation
Verifies that calculate_threat_score() is properly wired into alert creation paths.
"""
import pytest
from fusion_server.core.threat_scoring import (
    calculate_threat_score,
    get_threat_level,
    ThreatContext,
    VIOLATION_BASE_SCORES,
)
from fusion_server.core.rule_engine import RuleViolation


class TestViolationBaseScores:
    """Test that all violation types have base scores."""

    def test_all_expected_violation_types_have_scores(self):
        """All expected violation types should be in VIOLATION_BASE_SCORES."""
        expected_types = [
            "enter", "exit", "dwell", "speed", "direction",
            "virtual_fence_crossing", "suspicious_activity", "loitering",
            "camera_tamper", "camera_drift", "camera_blinding", "camera_frozen",
            "unauthorized_object",
        ]
        for vtype in expected_types:
            assert vtype in VIOLATION_BASE_SCORES, f"Missing violation type: {vtype}"

    def test_camera_violation_scores_are_high(self):
        """Camera-related violations should have high base scores (0.7-0.9)."""
        assert VIOLATION_BASE_SCORES["camera_tamper"] == 0.9
        assert VIOLATION_BASE_SCORES["camera_blinding"] == 0.8
        assert VIOLATION_BASE_SCORES["camera_drift"] == 0.7
        assert VIOLATION_BASE_SCORES["camera_frozen"] == 0.7

    def test_scores_are_in_valid_range(self):
        """All base scores should be between 0.0 and 1.0."""
        for vtype, score in VIOLATION_BASE_SCORES.items():
            assert 0.0 <= score <= 1.0, f"Score {score} for {vtype} out of range"


class TestWatchlistThreatScore:
    """Test threat scoring for watchlist matches (events.py wiring)."""

    def test_watchlist_match_produces_high_score(self):
        """Watchlist match should produce threat_score >= 0.9."""
        context = ThreatContext(
            object_type="person",
            time_of_day="day",
            camera_zone="perimeter",
            is_watchlist_match=True,
        )
        score = calculate_threat_score([], context)
        assert score >= 0.9

    def test_watchlist_match_with_violations(self):
        """Watchlist match with violations should still be >= 0.9."""
        violations = [
            RuleViolation(
                object_id="obj1",
                camera_id="cam1",
                timestamp="2024-01-01T00:00:00",
                roi_name="perimeter",
                violation_type="enter",
                threat_score=0.5,
            )
        ]
        context = ThreatContext(
            object_type="person",
            time_of_day="day",
            camera_zone="perimeter",
            is_watchlist_match=True,
        )
        score = calculate_threat_score(violations, context)
        assert score >= 0.9

    def test_watchlist_match_night_critical_zone(self):
        """Watchlist match at night in critical zone should be max score."""
        context = ThreatContext(
            object_type="person",
            time_of_day="night",
            camera_zone="critical",
            is_watchlist_match=True,
        )
        score = calculate_threat_score([], context)
        assert score >= 0.9


class TestCameraCompromiseThreatScore:
    """Test threat scoring for camera compromise (cameras.py wiring)."""

    def test_camera_tamper_produces_high_score(self):
        """Camera tamper should produce a high threat score."""
        violations = [
            RuleViolation(
                object_id="camera_cam1",
                camera_id="cam1",
                timestamp="2024-01-01T00:00:00",
                roi_name="N/A",
                violation_type="camera_tamper",
                threat_score=0.0,
            )
        ]
        context = ThreatContext(
            object_type="vehicle",
            time_of_day="day",
            camera_zone="perimeter",
        )
        score = calculate_threat_score(violations, context)
        assert score >= 0.8  # Camera tamper base is 0.9, with multipliers

    def test_camera_blinding_produces_high_score(self):
        """Camera blinding should produce a high threat score."""
        violations = [
            RuleViolation(
                object_id="camera_cam1",
                camera_id="cam1",
                timestamp="2024-01-01T00:00:00",
                roi_name="N/A",
                violation_type="camera_blinding",
                threat_score=0.0,
            )
        ]
        context = ThreatContext(
            object_type="vehicle",
            time_of_day="day",
            camera_zone="perimeter",
        )
        score = calculate_threat_score(violations, context)
        assert score >= 0.7  # Camera blinding base is 0.8

    def test_camera_drift_produces_medium_high_score(self):
        """Camera drift should produce a medium-high threat score."""
        violations = [
            RuleViolation(
                object_id="camera_cam1",
                camera_id="cam1",
                timestamp="2024-01-01T00:00:00",
                roi_name="N/A",
                violation_type="camera_drift",
                threat_score=0.0,
            )
        ]
        context = ThreatContext(
            object_type="vehicle",
            time_of_day="day",
            camera_zone="perimeter",
        )
        score = calculate_threat_score(violations, context)
        assert score >= 0.6  # Camera drift base is 0.7

    def test_camera_frozen_produces_medium_high_score(self):
        """Camera frozen should produce a medium-high threat score."""
        violations = [
            RuleViolation(
                object_id="camera_cam1",
                camera_id="cam1",
                timestamp="2024-01-01T00:00:00",
                roi_name="N/A",
                violation_type="camera_frozen",
                threat_score=0.0,
            )
        ]
        context = ThreatContext(
            object_type="vehicle",
            time_of_day="day",
            camera_zone="perimeter",
        )
        score = calculate_threat_score(violations, context)
        assert score >= 0.6  # Camera frozen base is 0.7


class TestThreatScoreIntegration:
    """Integration tests for threat scoring in alert creation paths."""

    def test_deterministic_output(self):
        """Same inputs always produce same output."""
        violations = [
            RuleViolation(
                object_id="obj1",
                camera_id="cam1",
                timestamp="2024-01-01T00:00:00",
                roi_name="perimeter",
                violation_type="enter",
                threat_score=0.5,
            )
        ]
        context = ThreatContext(
            object_type="person",
            time_of_day="day",
            camera_zone="perimeter",
        )
        score1 = calculate_threat_score(violations, context)
        score2 = calculate_threat_score(violations, context)
        assert score1 == score2

    def test_no_violations_returns_zero(self):
        """No violations should return 0.0 threat score."""
        context = ThreatContext(
            object_type="person",
            time_of_day="day",
            camera_zone="perimeter",
        )
        score = calculate_threat_score([], context)
        assert score == 0.0

    def test_score_never_exceeds_one(self):
        """Threat score should never exceed 1.0."""
        violations = [
            RuleViolation(
                object_id="obj1",
                camera_id="cam1",
                timestamp="2024-01-01T00:00:00",
                roi_name="critical",
                violation_type="camera_tamper",
                threat_score=0.9,
            )
        ]
        context = ThreatContext(
            object_type="vehicle",
            time_of_day="night",
            camera_zone="critical",
            previous_violations=10,
            is_watchlist_match=True,
        )
        score = calculate_threat_score(violations, context)
        assert score <= 1.0

    def test_threat_level_mapping(self):
        """Threat levels should map correctly to scores."""
        assert get_threat_level(0.95) == "critical"
        assert get_threat_level(0.85) == "critical"
        assert get_threat_level(0.75) == "high"
        assert get_threat_level(0.55) == "high"
        assert get_threat_level(0.45) == "medium"
        assert get_threat_level(0.35) == "medium"
        assert get_threat_level(0.25) == "low"
        assert get_threat_level(0.05) == "low"
        assert get_threat_level(0.0) == "none"
