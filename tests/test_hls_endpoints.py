"""Tests for HLS stream endpoints."""
import pytest


def test_hls_playlist_returns_404_when_not_ready(client):
    response = client.get("/api/v1/streams/cam1.m3u8")
    assert response.status_code == 404


def test_hls_segment_returns_404_when_not_ready(client):
    response = client.get("/api/v1/streams/cam1/segment001.ts")
    assert response.status_code == 404
