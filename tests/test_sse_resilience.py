"""Tests for resilience SSE events."""
import pytest
import asyncio
import json
from fusion_server.services.sse_broadcaster import SSEBroadcaster


@pytest.mark.asyncio
async def test_broadcast_camera_status_changed():
    b = SSEBroadcaster()
    q = b.subscribe()
    await b.broadcast_camera_status_changed({"camera_id": "cam1", "status": "offline"})
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["event"] == "camera_status_changed"
    data = json.loads(event["data"])
    assert data["camera_id"] == "cam1"


@pytest.mark.asyncio
async def test_broadcast_detection_tier_changed():
    b = SSEBroadcaster()
    q = b.subscribe()
    await b.broadcast_detection_tier_changed({"from": "normal", "to": "degraded"})
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["event"] == "detection_tier_changed"


@pytest.mark.asyncio
async def test_broadcast_power_mode_changed():
    b = SSEBroadcaster()
    q = b.subscribe()
    await b.broadcast_power_mode_changed({"from": "normal", "to": "reduced"})
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["event"] == "power_mode_changed"


@pytest.mark.asyncio
async def test_broadcast_system_health_changed():
    b = SSEBroadcaster()
    q = b.subscribe()
    await b.broadcast_system_health_changed({"status": "degraded"})
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["event"] == "system_health_changed"


@pytest.mark.asyncio
async def test_broadcast_ledger_resumed():
    b = SSEBroadcaster()
    q = b.subscribe()
    await b.broadcast_ledger_resumed({"status": "ok", "entries": 156})
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["event"] == "ledger_resumed"
