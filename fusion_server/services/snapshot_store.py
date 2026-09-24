"""
Snapshot store — persist event-triggered alert thumbnails (AGENTS.md Rule 4:
best-effort, post-broadcast, never blocks alert delivery; Rule 2: one still
≤640px, not video).

Edge nodes attach optional base64 JPEG (`snapshot`) to DetectionEvents.
We decode after the alert row is committed + SSE broadcast, write
storage/alerts/{alert_id}.jpg, and persist the RELATIVE path.
Base64 is never written to the DB. Any failure ⇒ log warning, return None.
"""
import asyncio
import base64
import logging
import os

logger = logging.getLogger(__name__)

# Env override lets tests (and operators) redirect storage without touching code.
ENV_DIR = "IBVAP_SNAPSHOT_DIR"


def get_snapshot_dir() -> str:
    return os.environ.get(ENV_DIR) or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "storage", "alerts",
    )


def decode_jpeg_b64(snapshot_b64: str) -> bytes:
    """Decode base64 → bytes; validate JPEG SOI magic. Raises ValueError."""
    try:
        data = base64.b64decode(snapshot_b64, validate=True)
    except Exception as exc:
        raise ValueError("invalid base64 snapshot") from exc
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("snapshot is not a JPEG (missing SOI marker)")
    return data


def save_alert_snapshots(alert_ids, snapshot_b64) -> "str | None":
    """
    Synchronous save (call from async code via run_in_executor / ensure_future).

    Writes {snapshot_dir}/{alert_id}.jpg for the FIRST id (one event → one
    frame; extra ids ignored defensively). Returns the DB-relative path
    ('storage/alerts/{id}.jpg') on success, None on any failure.
    Never raises.
    """
    if not snapshot_b64 or not alert_ids:
        return None
    alert_id = alert_ids[0]
    try:
        data = decode_jpeg_b64(snapshot_b64)
        out_dir = get_snapshot_dir()
        os.makedirs(out_dir, exist_ok=True)
        abs_path = os.path.join(out_dir, f"{alert_id}.jpg")
        with open(abs_path, "wb") as fh:
            fh.write(data)
        return f"storage/alerts/{alert_id}.jpg"
    except Exception as exc:
        logger.warning("snapshot save failed for alert %s: %s", alert_id, exc)
        return None


async def save_alert_snapshots_async(alert_ids, snapshot_b64) -> "str | None":
    """Non-blocking wrapper: file I/O in the default executor."""
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, save_alert_snapshots, alert_ids, snapshot_b64
        )
    except Exception as exc:
        logger.warning("async snapshot save failed: %s", exc)
        return None
