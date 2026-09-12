"""Tests for ResilienceAggregator — unified system health."""
import pytest
from fusion_server.services.resilience_aggregator import ResilienceAggregator


def test_aggregator_initializes_ok():
    """Aggregator starts with 'ok' status."""
    agg = ResilienceAggregator()
    health = agg.get_health()
    assert health["status"] == "ok"


def test_aggregator_degraded_on_camera_offline():
    """Camera offline triggers 'degraded' status."""
    agg = ResilienceAggregator()
    agg.update_camera_status("cam1", "offline")
    health = agg.get_health()
    assert health["status"] == "degraded"
    assert health["cameras"]["cam1"] == "offline"


def test_aggregator_critical_on_detection_critical():
    """Critical detection tier triggers 'critical' status."""
    agg = ResilienceAggregator()
    agg.update_detection_tier("critical")
    health = agg.get_health()
    assert health["status"] == "critical"


def test_aggregator_degraded_on_power_reduced():
    """Reduced power mode triggers 'degraded' status."""
    agg = ResilienceAggregator()
    agg.update_power_mode("reduced")
    health = agg.get_health()
    assert health["status"] == "degraded"


def test_aggregator_critical_on_ledger_gap():
    """Ledger gap triggers 'critical' status."""
    agg = ResilienceAggregator()
    agg.update_ledger_status("gap_detected")
    health = agg.get_health()
    assert health["status"] == "critical"


def test_aggregator_aggregates_multiple_signals():
    """Multiple degraded signals keep worst status."""
    agg = ResilienceAggregator()
    agg.update_camera_status("cam1", "offline")
    agg.update_power_mode("reduced")
    health = agg.get_health()
    assert health["status"] == "degraded"
    assert health["cameras"]["cam1"] == "offline"
    assert health["power_mode"] == "reduced"


def test_aggregator_recovery():
    """Recovery from degraded to ok."""
    agg = ResilienceAggregator()
    agg.update_camera_status("cam1", "offline")
    assert agg.get_health()["status"] == "degraded"
    agg.update_camera_status("cam1", "online")
    assert agg.get_health()["status"] == "ok"
