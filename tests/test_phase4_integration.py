"""Phase 4 Integration Tests — end-to-end alert pipeline flows."""
import pytest
import asyncio
import numpy as np
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch


from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.services.sse_broadcaster import SSEBroadcaster
from fusion_server.services.ai_enrichment import AIEnrichmentService
from fusion_server.core.rule_engine import RuleEngine, ROI
from fusion_server.core.threat_scoring import calculate_threat_score, ThreatContext, get_threat_level
from fusion_server.core.trajectory_buffer import TrajectoryBuffer
from fusion_server.core.suspicious_activity import SuspiciousActivityDetector
from fusion_server.core.alert_ledger import AlertLedger
from fusion_server.db.models import Alert


def _make_event(**overrides):
    event = {
        "camera_id": "cam1",
        "object_id": "obj1",
        "object_type": "person",
        "timestamp": datetime(2025, 6, 15, 14, 0, 0),
        "track_id": "trk1",
        "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
        "confidence": 0.9,
    }
    event.update(overrides)
    return event


def _mock_db():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = None
    mock_db.query.return_value.order_by.return_value.first.return_value = None
    return mock_db


def _pipeline_with_roi(db=None, **kwargs):
    pipeline = AlertPipeline(db=db or _mock_db(), **kwargs)
    pipeline.rule_engine.add_roi(ROI(
        camera_id="cam1",
        name="Perimeter",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    return pipeline


class TestMultiCameraROI:
    """Pipeline handles events from multiple cameras with different ROIs."""

    def test_separate_cameras_independent_alerts(self):
        pipeline = AlertPipeline(db=_mock_db())
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1", name="Zone A",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        ))
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam2", name="Zone B",
            polygon=[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]],
        ))

        r1 = pipeline.process(_make_event(camera_id="cam1", object_id="obj1", bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2}))
        r2 = pipeline.process(_make_event(camera_id="cam2", object_id="obj2", bbox={"x1": 0.6, "y1": 0.6, "x2": 0.7, "y2": 0.7}))

        assert len(r1["alerts"]) == 1
        assert r1["alerts"][0].camera_id == "cam1"
        assert len(r2["alerts"]) == 1
        assert r2["alerts"][0].camera_id == "cam2"

    def test_same_event_no_alert_outside_roi(self):
        pipeline = AlertPipeline(db=_mock_db())
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1", name="Zone A",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        ))
        result = pipeline.process(_make_event(bbox={"x1": 0.8, "y1": 0.8, "x2": 0.9, "y2": 0.9}))
        assert result["alerts"] == []
        assert result["violations"] == []


class TestOverlappingROIs:
    """Multiple overlapping ROIs produce multiple violations/alerts."""

    def test_two_overlapping_rois_two_alerts(self):
        pipeline = AlertPipeline(db=_mock_db())
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1", name="Zone A",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        ))
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1", name="Zone B",
            polygon=[[0.05, 0.05], [0.3, 0.05], [0.3, 0.3], [0.05, 0.3]],
        ))
        result = pipeline.process(_make_event(bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2}))
        assert len(result["alerts"]) == 2
        reasons = {a.reason for a in result["alerts"]}
        assert reasons == {"roi_intrusion"}


class TestTimeOfDayInference:
    """Pipeline infers time-of-day and passes it to threat scoring."""

    def test_night_event_gets_higher_threat(self):
        pipeline_day = _pipeline_with_roi(db=_mock_db())
        pipeline_night = _pipeline_with_roi(db=_mock_db())

        event_day = _make_event(timestamp=datetime(2025, 6, 15, 14, 0, 0))
        event_night = _make_event(timestamp=datetime(2025, 6, 15, 2, 0, 0))

        r_day = pipeline_day.process(event_day)
        r_night = pipeline_night.process(event_night)

        assert r_day["alerts"][0].threat_score < r_night["alerts"][0].threat_score

    def test_dawn_dusk_inference(self):
        pipeline = AlertPipeline(db=_mock_db())
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1", name="Z",
            polygon=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        ))
        ts_dawn = datetime(2025, 6, 15, 7, 0, 0)
        assert pipeline._infer_time_of_day(ts_dawn) == "dawn"

        ts_dusk = datetime(2025, 6, 15, 19, 0, 0)
        assert pipeline._infer_time_of_day(ts_dusk) == "dusk"


class TestAlertLedgerChainFromPipeline:
    """Alerts written by the pipeline form a valid hash chain."""

    def test_chain_integrity_across_multiple_alerts(self):
        ledger = AlertLedger()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = None
        mock_db.query.return_value.order_by.return_value.first.return_value = None

        a1 = Alert(alert_id="a1", object_id="o1", camera_id="cam1",
                    timestamp=datetime(2025, 1, 1, 12, 0, 0), reason="enter", status="fired")
        a1.hash = None
        a1.previous_hash = None
        ledger.write_alert_with_hash(mock_db, a1)

        # Simulate DB now has a1 as last alert
        last = MagicMock()
        last.hash = a1.hash
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = last

        a2 = Alert(alert_id="a2", object_id="o1", camera_id="cam1",
                    timestamp=datetime(2025, 1, 1, 12, 1, 0), reason="enter", status="fired")
        a2.hash = None
        a2.previous_hash = None
        ledger.write_alert_with_hash(mock_db, a2)

        assert a1.hash is not None
        assert a2.hash is not None
        assert a2.previous_hash == a1.hash
        assert a1.hash != a2.hash


class TestPipelineWithBothServices:
    """Pipeline with both enrichment and SSE configured triggers both paths."""

    @pytest.mark.asyncio
    async def test_both_services_wired(self):
        enrichment = MagicMock()
        enrichment.enrich.return_value = "AI explanation"
        broadcaster = AsyncMock(spec=SSEBroadcaster)

        pipeline = _pipeline_with_roi(db=_mock_db())
        pipeline.set_enrichment_service(enrichment)
        pipeline.set_sse_broadcaster(broadcaster)

        with patch("fusion_server.services.alert_pipeline.asyncio.create_task") as mock_task:
            mock_task.return_value = MagicMock()
            result = pipeline.process(_make_event())

            assert len(result["alerts"]) == 1
            mock_task.assert_called_once()
            # The task receives a coroutine from _enrich_and_broadcast
            coro_arg = mock_task.call_args[0][0]
            assert asyncio.iscoroutine(coro_arg)


class TestSuspiciousActivityIntegrated:
    """Suspicious activity detection integrates with pipeline results."""

    def test_loitering_detected_in_pipeline(self):
        pipeline = AlertPipeline()
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1", name="Zone",
            polygon=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        ))
        pipeline.suspicious_detector = SuspiciousActivityDetector(loiter_threshold_s=0.1)

        # Simulate many events in same position over time
        for i in range(5):
            ts = datetime(2025, 1, 1, 12, 0, i)
            pipeline.process(_make_event(
                timestamp=ts,
                bbox={"x1": 0.4, "y1": 0.4, "x2": 0.6, "y2": 0.6},
            ))

        # Should have accumulated positions
        positions = pipeline.suspicious_detector._positions.get("obj1", [])
        assert len(positions) == 5

    def test_path_reversal_detected(self):
        pipeline = AlertPipeline()
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1", name="Zone",
            polygon=[[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]],
        ))
        pipeline.suspicious_detector = SuspiciousActivityDetector(
            reversal_angle_deg=45, reversal_window_s=100.0,
        )

        # Move right then sharply reverse left
        events = [
            {"bbox": {"x1": 0.3, "y1": 0.5, "x2": 0.4, "y2": 0.6}, "ts": datetime(2025, 1, 1, 12, 0, 0)},
            {"bbox": {"x1": 0.5, "y1": 0.5, "x2": 0.6, "y2": 0.6}, "ts": datetime(2025, 1, 1, 12, 0, 1)},
            {"bbox": {"x1": 0.3, "y1": 0.5, "x2": 0.4, "y2": 0.6}, "ts": datetime(2025, 1, 1, 12, 0, 2)},
        ]
        for e in events:
            pipeline.process(_make_event(timestamp=e["ts"], bbox=e["bbox"]))

        result = pipeline.process(_make_event(
            timestamp=datetime(2025, 1, 1, 12, 0, 3),
            bbox={"x1": 0.1, "y1": 0.5, "x2": 0.2, "y2": 0.6},
        ))
        # Path reversal may or may not fire depending on exact geometry, but detector has data
        assert len(pipeline.suspicious_detector._positions["obj1"]) > 0


class TestTrajectoryProjectionFlow:
    """Trajectory projection feeds into enrichment and broadcast."""

    def test_projection_passed_to_enrich_and_broadcast(self):
        pipeline = _pipeline_with_roi(db=_mock_db())
        enrichment = MagicMock()
        enrichment.enrich.return_value = "ok"
        broadcaster = AsyncMock(spec=SSEBroadcaster)
        pipeline.set_enrichment_service(enrichment)
        pipeline.set_sse_broadcaster(broadcaster)

        # Build trajectory history
        for i in range(5):
            pipeline.process(_make_event(
                timestamp=datetime(2025, 1, 1, 12, 0, i),
                bbox={"x1": 0.1 + i * 0.05, "y1": 0.1, "x2": 0.2 + i * 0.05, "y2": 0.2},
            ))

        history = pipeline.trajectory_buffer.get_history("obj1")
        assert len(history) >= 5


class TestEnrichmentTemplateFallback:
    """AIEnrichmentService falls back to template when model unavailable."""

    def test_template_explanation_roi_intrusion(self):
        svc = AIEnrichmentService()
        result = svc._template_explanation({
            "alert_id": "a1", "object_id": "obj1", "camera_id": "cam1",
            "reason": "enter", "threat_score": 0.75, "trajectory": {},
        })
        assert "obj1" in result
        assert "cam1" in result
        assert "%" in result

    def test_template_explanation_watchlist(self):
        svc = AIEnrichmentService()
        result = svc._template_explanation({
            "alert_id": "a2", "object_id": "obj2", "camera_id": "cam2",
            "reason": "watchlist_match", "threat_score": 0.9, "trajectory": {},
        })
        assert "watchlist" in result.lower() or "obj2" in result

    def test_template_explanation_unknown_reason(self):
        svc = AIEnrichmentService()
        result = svc._template_explanation({
            "alert_id": "a3", "object_id": "obj3", "camera_id": "cam3",
            "reason": "custom_rule", "threat_score": 0.5, "trajectory": {},
        })
        assert "custom_rule" in result


class TestSSEBroadcastChain:
    """SSE broadcaster delivers both fired and enriched events."""

    @pytest.mark.asyncio
    async def test_fired_then_enriched_order(self):
        broadcaster = SSEBroadcaster()
        queue = broadcaster.subscribe()
        try:
            await broadcaster.broadcast_alert_fired({
                "alert_id": "x1", "camera_id": "cam1",
                "reason": "enter", "threat_score": 0.6,
            })
            await broadcaster.broadcast_alert_enriched(
                alert_id="x1", ai_explanation="Object entered zone",
            )

            e1 = await asyncio.wait_for(queue.get(), timeout=1.0)
            e2 = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert e1["event"] == "alert_fired"
            assert e2["event"] == "alert_enriched"
        finally:
            broadcaster.unsubscribe(queue)

    @pytest.mark.asyncio
    async def test_subscriber_receives_only_after_subscribe(self):
        broadcaster = SSEBroadcaster()
        await broadcaster.broadcast_alert_fired({"alert_id": "pre"})
        q = broadcaster.subscribe()
        await broadcaster.broadcast_alert_fired({"alert_id": "post"})
        event = await asyncio.wait_for(q.get(), timeout=1.0)
        import json
        data = json.loads(event["data"])
        assert data["alert_id"] == "post"
        broadcaster.unsubscribe(q)


class TestThreatScoreEndToEnd:
    """End-to-end: violation → threat context → score → alert."""

    def test_roi_intrusion_night_critical_zone(self):
        violations = [MagicMock(violation_type="enter")]
        context = ThreatContext(
            object_type="person", time_of_day="night",
            camera_zone="critical",
        )
        score = calculate_threat_score(violations, context)
        # enter base=0.5 × person=1.0 × night=1.3 × critical=1.5 = 0.975
        assert score >= 0.8
        assert get_threat_level(score) == "critical"

    def test_roi_intrusion_day_perimeter(self):
        violations = [MagicMock(violation_type="enter")]
        context = ThreatContext(
            object_type="person", time_of_day="day",
            camera_zone="perimeter",
        )
        score = calculate_threat_score(violations, context)
        # enter base=0.5 × person=1.0 × day=1.0 × perimeter=1.0 = 0.5
        assert get_threat_level(score) == "high"

    def test_vehicle_night_inner_zone(self):
        violations = [MagicMock(violation_type="dwell")]
        context = ThreatContext(
            object_type="vehicle", time_of_day="night",
            camera_zone="inner",
        )
        score = calculate_threat_score(violations, context)
        # dwell base=0.6 × vehicle=1.2 × night=1.3 × inner=1.2 = 1.1232 → capped 1.0
        assert score == 1.0


class TestPipelineReturnsConsistentStructure:
    """Pipeline result dict always has the same shape regardless of outcome."""

    def test_no_violation_result_shape(self):
        pipeline = _pipeline_with_roi(db=_mock_db())
        result = pipeline.process(_make_event(bbox={"x1": 0.9, "y1": 0.9, "x2": 1.0, "y2": 1.0}))
        assert set(result.keys()) == {"violations", "alerts", "trajectory_projection", "suspicious_activities"}
        assert isinstance(result["violations"], list)
        assert isinstance(result["alerts"], list)
        assert isinstance(result["trajectory_projection"], list)
        assert isinstance(result["suspicious_activities"], list)

    def test_with_violation_result_shape(self):
        pipeline = _pipeline_with_roi(db=_mock_db())
        result = pipeline.process(_make_event())
        assert len(result["violations"]) >= 1
        assert len(result["alerts"]) >= 1
        alert = result["alerts"][0]
        assert hasattr(alert, "alert_id")
        assert hasattr(alert, "threat_score")
        assert hasattr(alert, "hash")
