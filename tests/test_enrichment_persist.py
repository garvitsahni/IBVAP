"""Enrichment persistence + honest source labeling (Task 1)."""
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.core.rule_engine import ROI


def _pipeline_with_roi(db=None):
    from unittest.mock import MagicMock as MM

    pipeline = AlertPipeline(db=db or MM())
    pipeline.rule_engine.add_roi(ROI(
        camera_id="cam1",
        name="Zone A",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    return pipeline


def test_enrich_with_source_labels_template():
    from fusion_server.services.ai_enrichment import AIEnrichmentService

    svc = AIEnrichmentService()
    # No model loaded -> template path
    text, source = svc.enrich_with_source({
        "alert_id": "a1", "object_id": "o1", "camera_id": "cam1",
        "reason": "enter", "threat_score": 0.7,
    })
    assert source == "template"
    assert "[TEMPLATE]" in text


def test_enrich_and_broadcast_persists_enriched():
    """_enrich_and_broadcast writes ai_explanation + enriched status to DB."""
    from unittest.mock import MagicMock as MM

    enrichment = MM()
    enrichment.enrich_with_source.return_value = ("Zone entry. [TEMPLATE]", "template")
    broadcaster = AsyncMock()
    pipeline = _pipeline_with_roi(MM())
    pipeline.set_enrichment_service(enrichment)
    pipeline.set_sse_broadcaster(broadcaster)

    alert = MM()
    alert.alert_id = "persist-1"
    alert.object_id = "obj1"
    alert.camera_id = "cam1"
    alert.reason = "roi_intrusion"
    alert.threat_score = 0.8
    alert.timestamp = datetime(2025, 1, 1, 12, 0, 0)
    alert.plate_text = None

    fake_row = MM()
    fake_session = MM()
    fake_session.query.return_value.filter.return_value.first.return_value = fake_row

    with patch("fusion_server.db.session.SessionLocal", return_value=fake_session):
        asyncio.run(pipeline._enrich_and_broadcast(alert, {"camera_id": "cam1"}, []))

    assert fake_row.ai_explanation == "Zone entry. [TEMPLATE]"
    assert fake_row.status == "enriched"
    assert fake_session.commit.called
    broadcaster.broadcast_alert_fired.assert_called_once()
    broadcaster.broadcast_alert_enriched.assert_called_once()
