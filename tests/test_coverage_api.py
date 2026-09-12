"""Tests for blind-spot API endpoint."""
import pytest


def test_blind_spots_returns_200(client):
    response = client.get("/api/v1/coverage/blind-spots")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
