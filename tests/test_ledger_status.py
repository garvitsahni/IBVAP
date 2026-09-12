"""Tests for ledger global status endpoint."""
import pytest


def test_ledger_status_returns_200(client):
    response = client.get("/api/v1/ledger/status")
    assert response.status_code == 200
    data = response.json()
    assert "is_valid" in data
    assert "total_entries" in data
    assert isinstance(data["is_valid"], bool)


def test_ledger_status_has_all_fields(client):
    response = client.get("/api/v1/ledger/status")
    data = response.json()
    assert "broken_at_index" in data
    assert "last_verified" in data
