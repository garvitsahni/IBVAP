"""Tests for time-range alert filtering."""
import pytest


def test_alerts_supports_since_param(client):
    response = client.get("/api/v1/alerts?since=2026-01-01T00:00:00Z")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_alerts_supports_until_param(client):
    response = client.get("/api/v1/alerts?until=2026-12-31T23:59:59Z")
    assert response.status_code == 200
