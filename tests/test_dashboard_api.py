"""Tests for dashboard stats endpoint."""
import pytest


def test_dashboard_stats_returns_200(client):
    """Dashboard stats endpoint returns 200 with correct shape."""
    response = client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_alerts_today" in data
    assert "active_cameras" in data
    assert "alerts_by_severity" in data
    assert "active_watchlist_entries" in data


def test_dashboard_stats_severity_keys(client):
    """alerts_by_severity contains all four severity levels."""
    response = client.get("/api/v1/dashboard/stats")
    data = response.json()
    severity = data["alerts_by_severity"]
    assert "critical" in severity
    assert "high" in severity
    assert "medium" in severity
    assert "low" in severity
