"""Tests for SSE broadcaster."""
import pytest
import asyncio
import json
from fusion_server.services.sse_broadcaster import SSEBroadcaster


@pytest.mark.asyncio
async def test_subscribe_and_broadcast():
    """Client subscribes and receives broadcast."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe()
    await broadcaster.broadcast_alert_fired({
        "alert_id": "test-123",
        "camera_id": "cam1",
        "reason": "enter",
        "threat_score": 0.7,
    })
    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event["event"] == "alert_fired"
    data = json.loads(event["data"])
    assert data["alert_id"] == "test-123"


@pytest.mark.asyncio
async def test_unsubscribe():
    """Unsubscribed client does not receive broadcasts."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe()
    broadcaster.unsubscribe(queue)
    await broadcaster.broadcast_alert_fired({"alert_id": "test"})
    assert queue.empty()


@pytest.mark.asyncio
async def test_multiple_subscribers():
    """Multiple subscribers all receive broadcasts."""
    broadcaster = SSEBroadcaster()
    q1 = broadcaster.subscribe()
    q2 = broadcaster.subscribe()
    await broadcaster.broadcast_alert_fired({"alert_id": "test"})
    assert not q1.empty()
    assert not q2.empty()
