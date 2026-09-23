"""C2 webhook forwarder — minimal signed push for existing command systems.

Opt-in via env (disabled when C2_WEBHOOK_URL is empty). Fire-and-forget:
never raises, never blocks alert delivery (AGENTS.md Rule 4). LAN only —
no cloud dependency; the URL is operator-configured (typically a LAN C2
collector). Only structured alert JSON is posted, never raw video.
"""
import hashlib
import hmac
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - optional dep guard
    requests = None  # type: ignore


class C2Forwarder:
    """Signed POST forwarder with short timeout + limited retry."""

    def __init__(
        self,
        url: str = "",
        secret: str = "",
        timeout_s: float = 3.0,
        max_retries: int = 2,
    ):
        self.url = (url or "").strip()
        self.secret = secret or ""
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    @classmethod
    def from_env(cls) -> "C2Forwarder":
        try:
            timeout_s = float(os.getenv("C2_TIMEOUT_S", "3") or "3")
        except ValueError:
            timeout_s = 3.0
        try:
            max_retries = int(os.getenv("C2_RETRY", "2") or "2")
        except ValueError:
            max_retries = 2
        return cls(
            url=os.getenv("C2_WEBHOOK_URL", "") or "",
            secret=os.getenv("C2_WEBHOOK_SECRET", "") or "",
            timeout_s=timeout_s,
            max_retries=max_retries,
        )

    def _sign(self, body: str) -> str:
        if not self.secret:
            return ""
        return hmac.new(
            self.secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def forward(self, payload: dict) -> bool:
        """Blocking POST with retry. Returns True on 2xx, False otherwise. Never raises."""
        if not self.enabled:
            return False
        if requests is None:
            logger.warning("C2 forward skipped (requests unavailable)")
            return False
        try:
            body = json.dumps(payload, default=str)
        except Exception as e:
            logger.warning(f"C2 forward skipped (unserializable payload): {e}")
            return False
        headers = {
            "Content-Type": "application/json",
            "X-IBVAP-Alert-ID": str(payload.get("alert_id", "")),
            "X-IBVAP-Signature": self._sign(body),
        }
        attempts = max(1, self.max_retries + 1)
        for attempt in range(attempts):
            try:
                resp = requests.post(
                    self.url, data=body, headers=headers, timeout=self.timeout_s
                )
                if 200 <= resp.status_code < 300:
                    return True
                logger.warning(
                    f"C2 forward attempt {attempt + 1}/{attempts} "
                    f"got status {resp.status_code}"
                )
            except Exception as e:
                logger.warning(
                    f"C2 forward attempt {attempt + 1}/{attempts} failed: {e}"
                )
            if attempt < attempts - 1:
                time.sleep(0.5)
        return False

    async def forward_async(self, payload: dict) -> bool:
        """Async wrapper for use on the event loop. Never raises."""
        try:
            from starlette.concurrency import run_in_threadpool

            return await run_in_threadpool(self.forward, payload)
        except Exception as e:
            logger.warning(f"C2 forward_async failed: {e}")
            return False


_forwarder = None


def get_c2_forwarder() -> C2Forwarder:
    """Process-wide singleton built from env (rebuilt only once)."""
    global _forwarder
    if _forwarder is None:
        _forwarder = C2Forwarder.from_env()
    return _forwarder


def reset_c2_forwarder() -> None:
    """Test hook: drop the cached singleton."""
    global _forwarder
    _forwarder = None
