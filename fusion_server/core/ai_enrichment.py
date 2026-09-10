"""
Async AI Enrichment Service - Phase 4
Non-blocking AI enrichment per ARCHITECTURE.md Rule 4:
AI enrichment never blocks alert delivery.
Alert must be visible on dashboard before any LLM/VLM call.
"""
import asyncio
from typing import Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from fusion_server.db.models import Alert


@dataclass
class EnrichmentResult:
    """Result of AI enrichment."""
    ai_explanation: str
    trajectory_projection: Optional[dict] = None


class AIEnrichmentService:
    """
    Async AI enrichment service.
    Runs as background task, NEVER blocks alert creation.
    Uses locally-hosted model (not external API) per AGENTS.md Section 5.
    """

    def __init__(self, model_path: str = "./models/llm"):
        self.model_path = model_path
        self.enabled = False  # Disabled by default until model is available
        self._queue = asyncio.Queue()

    async def enrich_alert(self, alert: Alert, db: Session) -> EnrichmentResult:
        """
        Generate AI explanation for an alert.
        This runs AFTER alert is already fired and visible on dashboard.
        """
        if not self.enabled:
            return EnrichmentResult(
                ai_explanation="[AI enrichment disabled - no local model configured]",
                trajectory_projection=None,
            )

        # Build context for LLM
        context = self._build_context(alert)

        # Call local model (placeholder - implement when model is available)
        explanation = await self._call_local_model(context)

        return EnrichmentResult(
            ai_explanation=explanation,
            trajectory_projection=alert.trajectory_projection,
        )

    def _build_context(self, alert: Alert) -> str:
        """Build prompt context for LLM."""
        return (
            f"Alert: {alert.reason}\n"
            f"Object: {alert.object_id}\n"
            f"Camera: {alert.camera_id}\n"
            f"Time: {alert.timestamp}\n"
            f"Threat Score: {alert.threat_score:.2f}\n"
            f"Trajectory: {alert.trajectory_projection}"
        )

    async def _call_local_model(self, context: str) -> str:
        """Call locally-hosted LLM/VLM. Placeholder for actual implementation."""
        # TODO: Implement with local model (e.g., llama.cpp, ollama, vLLM)
        # Must be async and non-blocking
        await asyncio.sleep(0.1)  # Simulate async call
        return f"AI Analysis: {context}\n\nThis is a placeholder explanation. Connect a local LLM for real enrichment."

    async def enqueue_alert(self, alert_id: int):
        """Add alert to enrichment queue (non-blocking)."""
        await self._queue.put(alert_id)

    async def process_queue(self, db_factory):
        """Background worker to process enrichment queue."""
        while True:
            alert_id = await self._queue.get()
            try:
                from fusion_server.db.session import SessionLocal
                db = SessionLocal()
                alert = db.query(Alert).filter(Alert.id == alert_id).first()
                if alert and alert.status == "fired":
                    result = await self.enrich_alert(alert, db)
                    alert.ai_explanation = result.ai_explanation
                    alert.status = "enriched"
                    from datetime import datetime
                    alert.enriched_at = datetime.utcnow()
                    db.commit()
            except Exception as e:
                print(f"AI enrichment error for alert {alert_id}: {e}")
            finally:
                db.close()
                self._queue.task_done()


# Global instance (initialized in main.py)
ai_enrichment_service: Optional[AIEnrichmentService] = None


def get_ai_enrichment_service() -> AIEnrichmentService:
    global ai_enrichment_service
    if ai_enrichment_service is None:
        ai_enrichment_service = AIEnrichmentService()
    return ai_enrichment_service