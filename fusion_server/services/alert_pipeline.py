"""
Alert Pipeline Orchestrator — Phase 4
Ties together rule engine, trajectory buffer, threat scoring,
trajectory projection, suspicious activity detection, and alert ledger.
"""
import uuid
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from fusion_server.core.rule_engine import RuleEngine, RuleViolation
from fusion_server.core.trajectory_buffer import TrajectoryBuffer
from fusion_server.core.trajectory import TrajectoryPoint, TrajectoryProjector
from fusion_server.core.threat_scoring import calculate_threat_score, ThreatContext, get_threat_level
from fusion_server.core.suspicious_activity import SuspiciousActivityDetector
from fusion_server.core.alert_ledger import AlertLedger
from fusion_server.db.models import Alert

logger = logging.getLogger(__name__)


class AlertPipeline:
    """
    Orchestrates the full alert processing pipeline for a single detection event:
    1. Update trajectory buffer
    2. Run rule engine checks
    3. Detect suspicious activity
    4. Calculate threat scores
    5. Create alerts via AlertLedger
    6. Project trajectory
    7. Broadcast via SSE (if configured)
    """

    def __init__(
        self,
        rule_engine: Optional[RuleEngine] = None,
        trajectory_buffer: Optional[TrajectoryBuffer] = None,
        suspicious_detector: Optional[SuspiciousActivityDetector] = None,
        db=None,
        enrichment_service=None,
    ):
        self.rule_engine = rule_engine or RuleEngine()
        self.trajectory_buffer = trajectory_buffer or TrajectoryBuffer()
        self.suspicious_detector = suspicious_detector or SuspiciousActivityDetector()
        self.db = db
        self._alert_ledger = AlertLedger()
        self.sse_broadcaster = None
        self.enrichment_service = enrichment_service

        # Load ROIs from DB if available
        if self.db is not None:
            self.rule_engine.load_rois_from_db(self.db)

    def set_sse_broadcaster(self, broadcaster) -> None:
        """Inject SSE broadcaster for live alert delivery (called later when available)."""
        self.sse_broadcaster = broadcaster

    def set_enrichment_service(self, service) -> None:
        """Inject AI enrichment service (called later when available)."""
        self.enrichment_service = service

    def process(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a detection event through the full pipeline.
        Returns a result dict with violations, alerts, trajectory projection,
        and suspicious activities.
        """
        camera_id = event["camera_id"]
        object_id = event["object_id"]
        object_type = event["object_type"]
        timestamp = event["timestamp"]
        bbox = event["bbox"]

        # 1. Update trajectory buffer
        centroid_x = (bbox["x1"] + bbox["x2"]) / 2
        centroid_y = (bbox["y1"] + bbox["y2"]) / 2
        ts_float = timestamp.timestamp() if isinstance(timestamp, datetime) else timestamp
        self.trajectory_buffer.add(
            object_id,
            TrajectoryPoint(x=centroid_x, y=centroid_y, timestamp=ts_float),
        )

        # 2. Update suspicious activity detector
        self.suspicious_detector.update(
            object_id, camera_id, centroid_x, centroid_y, ts_float,
        )

        # 3. Run rule engine
        ts_str = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
        violations = self.rule_engine.evaluate(
            object_id=object_id,
            camera_id=camera_id,
            timestamp=ts_str,
            bbox=bbox,
            object_type=object_type,
        )

        # 4. Check suspicious activity
        suspicious_activities = []
        for roi in self.rule_engine.rois:
            if roi.camera_id == camera_id:
                suspicious_activities.extend(
                    self.suspicious_detector.check_loitering(object_id, roi.polygon)
                )
        suspicious_activities.extend(self.suspicious_detector.check_path_reversal(object_id))
        suspicious_activities.extend(self.suspicious_detector.check_group_clustering())

        # 5. Create alerts for violations
        alerts = []
        if self.db is not None:
            for violation in violations:
                threat_context = ThreatContext(
                    object_type=object_type,
                    time_of_day=self._infer_time_of_day(timestamp),
                    camera_zone="perimeter",  # Default; camera config lookup can override
                )
                score = calculate_threat_score([violation], threat_context)

                alert = Alert(
                    alert_id=str(uuid.uuid4()),
                    object_id=object_id,
                    camera_id=camera_id,
                    timestamp=timestamp,
                    reason="roi_intrusion",
                    status="fired",
                    threat_score=score,
                )
                self.db.add(alert)
                self.db.flush()  # Persist before ledger reads previous hash
                self._alert_ledger.write_alert_with_hash(self.db, alert)
                alerts.append(alert)

                # Fire-and-forget enrichment + broadcast (does not block alert delivery)
                if self.sse_broadcaster is not None or self.enrichment_service is not None:
                    try:
                        asyncio.create_task(
                            self._enrich_and_broadcast(alert, event, trajectory_projection=[])
                        )
                    except RuntimeError:
                        # No running event loop — skip enrichment silently
                        logger.debug("No event loop; skipping enrichment for alert %s", alert.alert_id)

        # 6. Project trajectory
        trajectory_projection = []
        history = self.trajectory_buffer.get_history(object_id)
        if len(history) >= 2:
            trajectory_projection = self._project_trajectory(history)

        return {
            "violations": violations,
            "alerts": alerts,
            "trajectory_projection": trajectory_projection,
            "suspicious_activities": suspicious_activities,
        }

    @staticmethod
    def _project_trajectory(history: List[TrajectoryPoint], steps: int = 10) -> List[tuple]:
        """Project trajectory from buffer history."""
        from fusion_server.core.trajectory import project_trajectory
        return project_trajectory(history, prediction_steps=steps)

    async def _enrich_and_broadcast(self, alert, event: Dict[str, Any], trajectory_projection=None) -> None:
        """
        Fire-and-forget: enrich alert with AI explanation, then broadcast both
        the alert_fired and alert_enriched events via SSE.

        This method catches ALL exceptions internally so it never blocks
        or crashes the main alert delivery path (AGENTS.md Rule 4).
        """
        try:
            ai_explanation = ""
            if self.enrichment_service is not None:
                alert_data = {
                    "alert_id": alert.alert_id,
                    "object_id": alert.object_id,
                    "camera_id": alert.camera_id,
                    "reason": alert.reason,
                    "threat_score": alert.threat_score,
                    "timestamp": alert.timestamp.isoformat() if hasattr(alert.timestamp, "isoformat") else str(alert.timestamp),
                    "trajectory": {"history": trajectory_projection or []},
                }
                try:
                    ai_explanation = self.enrichment_service.enrich(alert_data)
                except Exception:
                    logger.exception("AI enrichment failed for alert %s", alert.alert_id)
                    ai_explanation = ""

            if self.sse_broadcaster is not None:
                # Broadcast alert_fired first
                try:
                    await self.sse_broadcaster.broadcast_alert_fired({
                        "alert_id": alert.alert_id,
                        "object_id": alert.object_id,
                        "camera_id": alert.camera_id,
                        "reason": alert.reason,
                        "threat_score": alert.threat_score,
                        "threat_level": get_threat_level(alert.threat_score),
                        "plate_text": alert.plate_text,
                        "timestamp": alert.timestamp.isoformat() if hasattr(alert.timestamp, "isoformat") else str(alert.timestamp),
                    })
                except Exception:
                    logger.exception("SSE broadcast_alert_fired failed for alert %s", alert.alert_id)

                # Broadcast alert_enriched if we got an explanation
                if ai_explanation:
                    try:
                        await self.sse_broadcaster.broadcast_alert_enriched(
                            alert_id=alert.alert_id,
                            ai_explanation=ai_explanation,
                            trajectory_projection=trajectory_projection,
                        )
                    except Exception:
                        logger.exception("SSE broadcast_alert_enriched failed for alert %s", alert.alert_id)
        except Exception:
            logger.exception("Unexpected error in _enrich_and_broadcast for alert %s", alert.alert_id)

    @staticmethod
    def _infer_time_of_day(timestamp: datetime) -> str:
        """Infer time of day from timestamp hour."""
        if isinstance(timestamp, datetime):
            hour = timestamp.hour
        else:
            return "day"
        if 6 <= hour < 8:
            return "dawn"
        elif 8 <= hour < 18:
            return "day"
        elif 18 <= hour < 20:
            return "dusk"
        else:
            return "night"
