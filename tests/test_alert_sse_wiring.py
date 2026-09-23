"""Regression: alerts fired via POST /events must reach SSE subscribers (Bug S).

The events path builds AlertPipeline in a worker thread but never called
pipeline.set_sse_broadcaster, so _enrich_and_broadcast's
`if self.sse_broadcaster is not None` gate silently skipped every alert_fired /
alert_enriched broadcast AND the C2 forwarder for edge-published events.
"""
import asyncio
import json

import numpy as np
import pytest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from fusion_server.main import app
from fusion_server.db.session import get_db
from fusion_server.services.broadcaster import get_broadcaster
from fusion_server.db.models_roi import ROI as ROIModel


@pytest.fixture
async def async_client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _next_event(q, wanted, timeout=5.0):
    """Read SSE events until `wanted` appears or timeout. Returns None on timeout."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return None
        evt = await asyncio.wait_for(q.get(), timeout=remaining)
        if evt["event"] == wanted:
            return evt


async def test_events_path_delivers_alert_fired_over_sse(async_client, db_session):
    # ROI covering bbox centroid (0.15, 0.15) so the rule engine fires.
    db_session.add(ROIModel(
        camera_id="cam1",
        name="Zone A",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    db_session.commit()

    broadcaster = get_broadcaster()
    queue = broadcaster.subscribe()
    try:
        with patch("fusion_server.services.ai_enrichment.AIEnrichmentService") as MockEnrich:
            MockEnrich.return_value.enrich_with_source.return_value = (
                "test explanation",
                "template",
            )
            resp = await async_client.post("/api/v1/events", json={
                "camera_id": "cam1",
                "timestamp": "2026-09-23T12:00:00",
                "object_type": "person",
                "track_id": "t-sse-1",
                "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
                "embedding": np.random.randn(512).tolist(),
                "confidence": 0.9,
            })
            assert resp.status_code == 201, resp.text

            evt = await _next_event(queue, "alert_fired", timeout=5.0)

        assert evt is not None, "alert_fired never reached SSE subscribers within 5s"
        data = json.loads(evt["data"])
        assert data["reason"] == "roi_intrusion"
        assert data["camera_id"] == "cam1"
        assert "threat_score" in data
    finally:
        broadcaster.unsubscribe(queue)


async def test_watchlist_match_alert_reaches_sse(async_client, db_session):
    """Bug W2: alerts created directly in _ingest_event (watchlist_match) —
    not via AlertPipeline — must still be broadcast to SSE subscribers."""
    emb = np.random.randn(512)
    emb = emb / np.linalg.norm(emb)

    resp = await async_client.post("/api/v1/watchlist", json={
        "watchlist_type": "face",
        "reference_id": "sse-wl-1",
        "embedding": emb.tolist(),
    })
    assert resp.status_code == 201, resp.text

    broadcaster = get_broadcaster()
    queue = broadcaster.subscribe()
    try:
        # No body embedding -> object_id None -> no AlertPipeline in this path;
        # only the watchlist_match alert exists.
        resp = await async_client.post("/api/v1/events", json={
            "camera_id": "cam1",
            "timestamp": "2026-09-23T12:05:00",
            "object_type": "person",
            "track_id": "t-wl-1",
            "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
            "face_embedding": emb.tolist(),
            "confidence": 0.9,
        })
        assert resp.status_code == 201, resp.text

        evt = await _next_event(queue, "alert_fired", timeout=5.0)

        assert evt is not None, "watchlist_match alert_fired never reached SSE within 5s"
        data = json.loads(evt["data"])
        assert data["reason"] == "watchlist_match"
        assert data["camera_id"] == "cam1"
    finally:
        broadcaster.unsubscribe(queue)
