"""SSE streaming endpoint for real-time alerts."""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

router = APIRouter(tags=["stream"])

# Global broadcaster instance
_broadcaster = None


def get_broadcaster():
    global _broadcaster
    if _broadcaster is None:
        from fusion_server.services.sse_broadcaster import SSEBroadcaster
        _broadcaster = SSEBroadcaster()
    return _broadcaster


@router.get("/api/v1/alerts/stream")
async def alert_stream(request: Request):
    """SSE endpoint — streams alert events in real-time."""
    broadcaster = get_broadcaster()
    queue = broadcaster.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event['event']}\ndata: {event['data']}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
