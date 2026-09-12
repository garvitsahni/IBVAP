"""Tests for clip serving endpoint."""
import pytest


def test_clip_serving_returns_404_for_missing(client):
    response = client.get("/api/v1/clips/nonexistent.mp4")
    assert response.status_code == 404
