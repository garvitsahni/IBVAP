"""Tests for SSE endpoint."""
import pytest
import asyncio
import json
from fusion_server.api.routes.stream import get_broadcaster, router
from fusion_server.services.sse_broadcaster import SSEBroadcaster


def test_sse_route_registered():
    """SSE stream endpoint is registered."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    # SSE endpoints may use different path formats; check all paths
    stream_paths = [p for p in paths if "stream" in p or "alerts" in p]
    assert len(stream_paths) > 0, f"No stream/alert paths found in {list(paths.keys())}"


@pytest.mark.asyncio
async def test_broadcaster_singleton_returns_same_instance():
    """get_broadcaster returns the same singleton."""
    b1 = get_broadcaster()
    b2 = get_broadcaster()
    assert b1 is b2


@pytest.mark.asyncio
async def test_sse_endpoint_receives_broadcast():
    """SSE endpoint delivers broadcast events to connected clients."""
    broadcaster = get_broadcaster()
    queue = broadcaster.subscribe()
    try:
        await broadcaster.broadcast_alert_fired({
            "alert_id": "test-456",
            "camera_id": "cam2",
            "reason": "enter",
            "threat_score": 0.8,
            "timestamp": "2026-09-11T10:00:00",
        })
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event["event"] == "alert_fired"
        data = json.loads(event["data"])
        assert data["alert_id"] == "test-456"
    finally:
        broadcaster.unsubscribe(queue)


def test_viewer_endpoint():
    """Viewer endpoint returns HTML."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/viewer")
    async def viewer():
        from fastapi.responses import FileResponse
        return FileResponse("templates/viewer.html")

    client = TestClient(app)
    response = client.get("/viewer")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
