"""Shared SSE Broadcaster singleton."""
from fusion_server.services.sse_broadcaster import SSEBroadcaster

_broadcaster: SSEBroadcaster | None = None


def get_broadcaster() -> SSEBroadcaster:
    """Get the global SSE broadcaster instance."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = SSEBroadcaster()
    return _broadcaster