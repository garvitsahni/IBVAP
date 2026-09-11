# tests/test_plates_api.py
"""Tests for plate detection query API."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from fusion_server.main import app
from fusion_server.db.session import get_db


def test_list_plates():
    """GET /api/v1/plates returns list."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.get("/api/v1/plates")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    finally:
        app.dependency_overrides.clear()
