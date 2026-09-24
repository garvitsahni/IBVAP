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
from fusion_server.services.cooldown_gate import get_cooldown_gate

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

        # 3b. Presence update: deactivate ROI keys the object is no longer
        # violating (per-ROI re-arm). Watchlist keys untouched (time-only).
        get_cooldown_gate().update_presence(
            camera_id, object_id, {v.roi_name for v in violations}
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
                gate = get_cooldown_gate()
                if not gate.should_fire(
                    camera_id,
                    object_id,
                    f"roi:{violation.roi_name}",
                    violating=True,
                    now=ts_float,
                ):
                    continue  # deduped — violation stays in result["violations"]
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

                # Fire-and-forget enrichment + broadcast (does not block alert delivery).
                # Only build the coroutine when a loop can actually schedule it —
                # creating it without a running loop would orphan it (never awaited).
                if self.sse_broadcaster is not None or self.enrichment_service is not None:
                    try:
                        asyncio.get_running_loop()
                    except RuntimeError:
                        logger.debug(
                            "No event loop; caller must schedule enrichment for alert %s",
                            alert.alert_id,
                        )
                    else:
                        asyncio.create_task(
                            self._enrich_and_broadcast(alert, event, trajectory_projection=[])
                        )

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
            ai_source = "template"
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
                    enricher = self.enrichment_service
                    # Prefer enrich_with_source (honest source label); fall back
                    # to legacy enrich() for older fakes/mocks in tests.
                    used_source_method = False
                    if hasattr(enricher, "enrich_with_source"):
                        try:
                            result = enricher.enrich_with_source(alert_data)
                        except Exception:
                            result = None
                        if isinstance(result, (tuple, list)) and len(result) == 2 and isinstance(result[1], str):
                            ai_explanation, ai_source = result[0], result[1]
                            used_source_method = True
                    if not used_source_method and hasattr(enricher, "enrich"):
                        try:
                            ai_explanation = enricher.enrich(alert_data)
                            ai_source = "template"
                        except Exception:
                            raise
                except Exception:
                    logger.exception("AI enrichment failed for alert %s", alert.alert_id)
                    ai_explanation = ""
                    ai_source = "template"

            # Persist enrichment back to the alert row (new session: this
            # coroutine runs on the event loop, self.db belongs to the
            # worker thread that called process()). Never raises.
            if ai_explanation:
                try:
                    from fusion_server.db.session import SessionLocal
                    from datetime import datetime as _dt
                    pdb = SessionLocal()
                    try:
                        db_alert = pdb.query(Alert).filter(
                            Alert.alert_id == alert.alert_id
                        ).first()
                        if db_alert is not None:
                            db_alert.ai_explanation = ai_explanation
                            try:
                                db_alert.ai_source = ai_source
                            except Exception:
                                pass  # column may not exist on older DBs
                            db_alert.status = "enriched"
                            db_alert.enriched_at = _dt.utcnow()
                            pdb.commit()
                    except Exception:
                        logger.exception("Enrichment persist failed for alert %s", alert.alert_id)
                        try:
                            pdb.rollback()
                        except Exception:
                            pass
                    finally:
                        try:
                            pdb.close()
                        except Exception:
                            pass
                except Exception:
                    logger.exception("Enrichment persist setup failed for alert %s", alert.alert_id)

            if self.sse_broadcaster is not None:
                # Broadcast alert_fired first
                fired_payload = {
                        "alert_id": alert.alert_id,
                        "object_id": alert.object_id,
                        "camera_id": alert.camera_id,
                        "reason": alert.reason,
                        "threat_score": alert.threat_score,
                        "threat_level": get_threat_level(alert.threat_score),
                        "plate_text": alert.plate_text,
                        "timestamp": alert.timestamp.isoformat() if hasattr(alert.timestamp, "isoformat") else str(alert.timestamp),
                    }
                try:
                    await self.sse_broadcaster.broadcast_alert_fired(fired_payload)
                except Exception:
                    logger.exception("SSE broadcast_alert_fired failed for alert %s", alert.alert_id)

                # Best-effort C2 push (opt-in via C2_WEBHOOK_URL; never blocks).
                try:
                    from fusion_server.services.c2_forwarder import get_c2_forwarder
                    c2 = get_c2_forwarder()
                    if c2 is not None and getattr(c2, "enabled", False):
                        await c2.forward_async(fired_payload)
                except Exception:
                    logger.exception("C2 forward failed for alert %s", alert.alert_id)

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
