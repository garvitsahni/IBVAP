"""System health API — unified degraded mode status."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/system", tags=["system"])

_aggregator = None


def set_aggregator(aggregator):
    global _aggregator
    _aggregator = aggregator


@router.get("/health")
def system_health():
    if _aggregator is None:
        return {"status": "unknown", "error": "aggregator not initialized"}
    return _aggregator.get_health()
