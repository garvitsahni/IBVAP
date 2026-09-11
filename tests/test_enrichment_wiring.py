"""Tests for AI Enrichment wiring into AlertPipeline (Task 13)."""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.services.ai_enrichment import AIEnrichmentService
from fusion_server.services.sse_broadcaster import SSEBroadcaster
from fusion_server.core.rule_engine import ROI


def _make_event(**overrides):
    """Create a minimal detection event dict for pipeline processing."""
    event = {
        "camera_id": "cam1",
        "object_id": "obj1",
        "object_type": "person",
        "timestamp": datetime(2025, 1, 1, 12, 0, 0),
        "track_id": "trk1",
        "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
        "confidence": 0.9,
    }
    event.update(overrides)
    return event


def _mock_db():
    """Create a mock DB session for alert tests."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = None
    mock_db.query.return_value.order_by.return_value.first.return_value = None
    return mock_db


def _pipeline_with_roi(db=None):
    """Create a pipeline with a matching ROI on cam1."""
    pipeline = AlertPipeline(db=db or _mock_db())
    pipeline.rule_engine.add_roi(ROI(
        camera_id="cam1",
        name="Zone A",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    return pipeline


class TestEnrichmentServiceInjection:
    """Pipeline accepts AIEnrichmentService via constructor or setter."""

    def test_enrichment_service_initially_none(self):
        pipeline = AlertPipeline()
        assert pipeline.enrichment_service is None

    def test_enrichment_service_via_constructor(self):
        svc = AIEnrichmentService()
        pipeline = AlertPipeline(enrichment_service=svc)
        assert pipeline.enrichment_service is svc

    def test_set_enrichment_service(self):
        pipeline = AlertPipeline()
        svc = AIEnrichmentService()
        pipeline.set_enrichment_service(svc)
        assert pipeline.enrichment_service is svc

    def test_set_enrichment_service_replaces(self):
        pipeline = AlertPipeline()
        svc1 = AIEnrichmentService()
        svc2 = AIEnrichmentService()
        pipeline.set_enrichment_service(svc1)
        pipeline.set_enrichment_service(svc2)
        assert pipeline.enrichment_service is svc2


class TestEnrichmentFireAndForget:
    """Enrichment runs as fire-and-forget task, never blocking alert delivery."""

    @pytest.mark.asyncio
    async def test_enrichment_called_asynchronously(self):
        """Enrichment service is invoked via asyncio.create_task, not inline."""
        enrichment = MagicMock()
        enrichment.enrich.return_value = "Test explanation"
        broadcaster = AsyncMock(spec=SSEBroadcaster)
        pipeline = _pipeline_with_roi(_mock_db())
        pipeline.set_enrichment_service(enrichment)
        pipeline.set_sse_broadcaster(broadcaster)

        with patch("fusion_server.services.alert_pipeline.asyncio.create_task") as mock_create_task:
            mock_create_task.return_value = MagicMock()  # fake Task
            result = pipeline.process(_make_event())

            # Alert was created
            assert len(result["alerts"]) == 1
            # create_task was called (fire-and-forget)
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrichment_does_not_block_on_exception(self):
        """If enrichment service raises, alert is still delivered."""
        enrichment = MagicMock()
        enrichment.enrich.side_effect = RuntimeError("Model crashed")
        broadcaster = AsyncMock(spec=SSEBroadcaster)
        pipeline = _pipeline_with_roi(_mock_db())
        pipeline.set_enrichment_service(enrichment)
        pipeline.set_sse_broadcaster(broadcaster)

        with patch("fusion_server.services.alert_pipeline.asyncio.create_task") as mock_create_task:
            # Make the task run the coroutine immediately for testing
            async def run_coro(coro):
                await coro
                return MagicMock()
            mock_create_task.side_effect = lambda c: asyncio.ensure_future(run_coro(c))

            result = pipeline.process(_make_event())
            assert len(result["alerts"]) == 1

    @pytest.mark.asyncio
    async def test_no_enrichment_when_service_not_set(self):
        """Without enrichment service, pipeline still works."""
        broadcaster = AsyncMock(spec=SSEBroadcaster)
        pipeline = _pipeline_with_roi(_mock_db())
        pipeline.set_sse_broadcaster(broadcaster)

        with patch("fusion_server.services.alert_pipeline.asyncio.create_task") as mock_create_task:
            mock_create_task.return_value = MagicMock()
            result = pipeline.process(_make_event())
            assert len(result["alerts"]) == 1
            mock_create_task.assert_called_once()


class TestEnrichAndBroadcast:
    """Test the _enrich_and_broadcast coroutine directly."""

    @pytest.mark.asyncio
    async def test_broadcasts_alert_fired(self):
        """_enrich_and_broadcast calls broadcast_alert_fired on the broadcaster."""
        enrichment = MagicMock()
        enrichment.enrich.return_value = "AI says something"
        broadcaster = AsyncMock(spec=SSEBroadcaster)
        pipeline = _pipeline_with_roi(_mock_db())
        pipeline.set_enrichment_service(enrichment)
        pipeline.set_sse_broadcaster(broadcaster)

        # Create a mock alert
        alert = MagicMock()
        alert.alert_id = "test-alert-1"
        alert.object_id = "obj1"
        alert.camera_id = "cam1"
        alert.reason = "roi_intrusion"
        alert.threat_score = 0.85
        alert.timestamp = datetime(2025, 1, 1, 12, 0, 0)

        event = _make_event()
        await pipeline._enrich_and_broadcast(alert, event)

        broadcaster.broadcast_alert_fired.assert_called_once()
        fired_data = broadcaster.broadcast_alert_fired.call_args[0][0]
        assert fired_data["alert_id"] == "test-alert-1"
        assert fired_data["camera_id"] == "cam1"

    @pytest.mark.asyncio
    async def test_broadcasts_alert_enriched_after_enrichment(self):
        """After enrichment, broadcast_alert_enriched is called with the explanation."""
        enrichment = MagicMock()
        enrichment.enrich.return_value = "Suspicious activity detected"
        broadcaster = AsyncMock(spec=SSEBroadcaster)
        pipeline = _pipeline_with_roi(_mock_db())
        pipeline.set_enrichment_service(enrichment)
        pipeline.set_sse_broadcaster(broadcaster)

        alert = MagicMock()
        alert.alert_id = "test-alert-2"
        alert.object_id = "obj1"
        alert.camera_id = "cam1"
        alert.reason = "roi_intrusion"
        alert.threat_score = 0.75
        alert.timestamp = datetime(2025, 1, 1, 12, 0, 0)

        await pipeline._enrich_and_broadcast(alert, _make_event())

        broadcaster.broadcast_alert_enriched.assert_called_once()
        enriched_args = broadcaster.broadcast_alert_enriched.call_args
        assert enriched_args[1]["alert_id"] == "test-alert-2"
        assert enriched_args[1]["ai_explanation"] == "Suspicious activity detected"

    @pytest.mark.asyncio
    async def test_enrichment_failure_does_not_crash_broadcast(self):
        """If enrichment fails, broadcast_alert_fired still fires and enriched is skipped."""
        enrichment = MagicMock()
        enrichment.enrich.side_effect = RuntimeError("LLaVA OOM")
        broadcaster = AsyncMock(spec=SSEBroadcaster)
        pipeline = _pipeline_with_roi(_mock_db())
        pipeline.set_enrichment_service(enrichment)
        pipeline.set_sse_broadcaster(broadcaster)

        alert = MagicMock()
        alert.alert_id = "test-alert-3"
        alert.object_id = "obj1"
        alert.camera_id = "cam1"
        alert.reason = "roi_intrusion"
        alert.threat_score = 0.6
        alert.timestamp = datetime(2025, 1, 1, 12, 0, 0)

        # Should not raise
        await pipeline._enrich_and_broadcast(alert, _make_event())

        broadcaster.broadcast_alert_fired.assert_called_once()
        # enriched NOT called because enrichment failed (no explanation to send)
        broadcaster.broadcast_alert_enriched.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_failure_does_not_crash(self):
        """If broadcast_alert_fired raises, the method catches and continues."""
        enrichment = MagicMock()
        enrichment.enrich.return_value = "ok"
        broadcaster = AsyncMock(spec=SSEBroadcaster)
        broadcaster.broadcast_alert_fired.side_effect = ConnectionError("SSE down")
        pipeline = _pipeline_with_roi(_mock_db())
        pipeline.set_enrichment_service(enrichment)
        pipeline.set_sse_broadcaster(broadcaster)

        alert = MagicMock()
        alert.alert_id = "test-alert-4"
        alert.object_id = "obj1"
        alert.camera_id = "cam1"
        alert.reason = "roi_intrusion"
        alert.threat_score = 0.5
        alert.timestamp = datetime(2025, 1, 1, 12, 0, 0)

        # Should not raise
        await pipeline._enrich_and_broadcast(alert, _make_event())

    @pytest.mark.asyncio
    async def test_no_broadcaster_no_enrichment_still_works(self):
        """_enrich_and_broadcast is a no-op when neither service is set."""
        pipeline = _pipeline_with_roi(_mock_db())
        alert = MagicMock()
        alert.alert_id = "test-alert-5"
        alert.timestamp = datetime(2025, 1, 1, 12, 0, 0)

        # Should not raise
        await pipeline._enrich_and_broadcast(alert, _make_event())

    @pytest.mark.asyncio
    async def test_enrichment_receives_alert_data(self):
        """Enrichment service receives a properly shaped alert_data dict."""
        enrichment = MagicMock()
        enrichment.enrich.return_value = "explanation"
        pipeline = _pipeline_with_roi(_mock_db())
        pipeline.set_enrichment_service(enrichment)

        alert = MagicMock()
        alert.alert_id = "aid-1"
        alert.object_id = "obj1"
        alert.camera_id = "cam1"
        alert.reason = "roi_intrusion"
        alert.threat_score = 0.9
        alert.timestamp = datetime(2025, 6, 15, 22, 30, 0)

        await pipeline._enrich_and_broadcast(alert, _make_event())

        enrichment.enrich.assert_called_once()
        alert_data = enrichment.enrich.call_args[0][0]
        assert alert_data["alert_id"] == "aid-1"
        assert alert_data["reason"] == "roi_intrusion"
        assert alert_data["threat_score"] == 0.9
        assert "trajectory" in alert_data

    @pytest.mark.asyncio
    async def test_trajectory_projection_passed_to_enriched_broadcast(self):
        """trajectory_projection is forwarded to broadcast_alert_enriched."""
        enrichment = MagicMock()
        enrichment.enrich.return_value = "explanation"
        broadcaster = AsyncMock(spec=SSEBroadcaster)
        pipeline = _pipeline_with_roi(_mock_db())
        pipeline.set_enrichment_service(enrichment)
        pipeline.set_sse_broadcaster(broadcaster)

        alert = MagicMock()
        alert.alert_id = "aid-2"
        alert.object_id = "obj1"
        alert.camera_id = "cam1"
        alert.reason = "roi_intrusion"
        alert.threat_score = 0.7
        alert.timestamp = datetime(2025, 1, 1, 12, 0, 0)

        traj = [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]
        await pipeline._enrich_and_broadcast(alert, _make_event(), trajectory_projection=traj)

        enriched_args = broadcaster.broadcast_alert_enriched.call_args
        assert enriched_args[1]["trajectory_projection"] == traj


class TestBackwardCompatibility:
    """Existing pipeline behavior is preserved when enrichment is not configured."""

    def test_pipeline_works_without_enrichment(self):
        """Pipeline processes events normally when no enrichment service is set."""
        pipeline = _pipeline_with_roi(_mock_db())
        result = pipeline.process(_make_event())
        assert len(result["alerts"]) == 1
        assert result["alerts"][0].status == "fired"

    def test_enrichment_service_does_not_affect_sync_result(self):
        """The synchronous result dict is unchanged by enrichment wiring."""
        pipeline_with = _pipeline_with_roi(_mock_db())
        pipeline_without = _pipeline_with_roi(_mock_db())
        pipeline_with.set_enrichment_service(MagicMock())

        with patch("fusion_server.services.alert_pipeline.asyncio.create_task"):
            result_with = pipeline_with.process(_make_event())
        result_without = pipeline_without.process(_make_event())

        # Same alert structure
        assert len(result_with["alerts"]) == len(result_without["alerts"])
        assert result_with["alerts"][0].status == result_without["alerts"][0].status
        assert result_with["violations"] == result_without["violations"]
