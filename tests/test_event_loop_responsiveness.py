"""Regression tests: the fusion server event loop must stay responsive while
synchronous-heavy endpoints (/detect inference, /events ingestion) are busy.

Root cause reproduced: both endpoints are `async def` but ran multi-second
sync work (YOLO+OCR / DB matching) directly on the event loop, which blocked
every other request — edge event publishes timed out at 2s and no alerts fired.
"""
import asyncio
import base64
import time

import cv2
import httpx
import numpy as np
import pytest

from fusion_server.db.session import get_db
from fusion_server.main import app

STUB_SLEEP = 0.8


@pytest.fixture
def asgi_app(db_session):
    """App with test DB dependency override (no lifespan — ASGITransport)."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


def _tiny_jpeg_b64() -> str:
    frame = np.full((64, 64, 3), 255, dtype=np.uint8)  # bright -> single YOLO pass
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    return base64.b64encode(buf.tobytes()).decode()


def _event_payload(embedding=None):
    payload = {
        "camera_id": "cam1",
        "timestamp": "2026-09-23T10:00:00",
        "object_type": "person",
        "track_id": "1",
        "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.3},
        "confidence": 0.9,
    }
    if embedding is not None:
        payload["embedding"] = embedding
    return payload


@pytest.mark.asyncio
async def test_events_reach_server_while_detect_is_running(asgi_app, monkeypatch):
    """POST /events must complete while /detect is mid-inference (loop not blocked)."""
    from fusion_server.api.routes import detect as detect_mod

    def slow_yolo(frame, conf_threshold, camera_id="browser-webcam", plate_reads=None):
        time.sleep(STUB_SLEEP)
        return []

    monkeypatch.setattr(detect_mod, "_run_yolo", slow_yolo)

    detect_finished = asyncio.Event()
    results = {}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=asgi_app), base_url="http://test"
    ) as ac:
        async def run_detect():
            resp = await ac.post(
                "/api/v1/detect",
                json={"image": _tiny_jpeg_b64(), "camera_id": "cam1"},
            )
            detect_finished.set()
            results["detect_status"] = resp.status_code

        async def run_events():
            resp = await ac.post("/api/v1/events", json=_event_payload())
            results["events_status"] = resp.status_code
            results["events_while_detect_busy"] = not detect_finished.is_set()

        await asyncio.gather(run_detect(), run_events())

    assert results["detect_status"] == 200
    assert results["events_status"] == 201
    assert results["events_while_detect_busy"] is True, (
        "POST /events only completed AFTER /detect finished — "
        "the event loop was blocked by synchronous inference"
    )


@pytest.mark.asyncio
async def test_other_requests_reach_server_while_events_is_matching(asgi_app, monkeypatch):
    """GET /rois must complete while /events is mid ingestion (loop not blocked)."""
    from fusion_server.services.matching_engine import MatchingEngine

    def slow_match(self, db, embedding, object_type, camera_id, timestamp):
        time.sleep(STUB_SLEEP)
        return "obj-test-slow"

    monkeypatch.setattr(MatchingEngine, "match_or_create", slow_match)

    events_finished = asyncio.Event()
    results = {}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=asgi_app), base_url="http://test"
    ) as ac:
        async def run_events():
            resp = await ac.post(
                "/api/v1/events",
                json=_event_payload(embedding=[0.0] * 512),
            )
            events_finished.set()
            results["events_status"] = resp.status_code

        async def run_rois():
            resp = await ac.get("/api/v1/rois")
            results["rois_status"] = resp.status_code
            results["rois_while_events_busy"] = not events_finished.is_set()

        await asyncio.gather(run_events(), run_rois())

    assert results["events_status"] == 201
    assert results["rois_status"] == 200
    assert results["rois_while_events_busy"] is True, (
        "GET /rois only completed AFTER /events finished — "
        "the event loop was blocked by synchronous ingestion work"
    )
