"""Regression: AlertPipeline.process must not orphan coroutines when no event loop is running.

Bug: process() built `asyncio.create_task(self._enrich_and_broadcast(...))` — the
coroutine argument is created BEFORE create_task raises RuntimeError (threadpool /
sync callers), leaving it never-awaited ("coroutine ... was never awaited" RuntimeWarning).
"""
import warnings
from datetime import datetime
from unittest.mock import MagicMock

from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.core.rule_engine import ROI


def _make_event():
    return {
        "camera_id": "cam1",
        "object_id": "obj1",
        "object_type": "person",
        "timestamp": datetime(2025, 1, 1, 12, 0, 0),
        "track_id": "trk1",
        "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
        "confidence": 0.9,
    }


def _mock_db():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = None
    mock_db.query.return_value.order_by.return_value.first.return_value = None
    return mock_db


def _pipeline_with_roi():
    pipeline = AlertPipeline(db=_mock_db())
    pipeline.rule_engine.add_roi(ROI(
        camera_id="cam1",
        name="Zone A",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    return pipeline


def test_process_without_loop_does_not_orphan_coroutine():
    """With services configured and no running loop, process() must not create the coroutine.

    create_task is patched to behave like the real one without a loop (raises
    RuntimeError) while capturing the coroutine argument — if process() built the
    coroutine anyway, it would be orphaned (never awaited).
    """
    pipeline = _pipeline_with_roi()
    pipeline.set_sse_broadcaster(MagicMock())

    captured = []

    def fake_create_task(coro):
        captured.append(coro)
        raise RuntimeError("no running event loop")

    from unittest.mock import patch
    with patch(
        "fusion_server.services.alert_pipeline.asyncio.create_task",
        side_effect=fake_create_task,
    ):
        result = pipeline.process(_make_event())

    for coro in captured:
        coro.close()
    assert captured == [], (
        f"process() created {len(captured)} coroutine(s) with no event loop to run them"
    )
    assert len(result["alerts"]) == 1
    assert result["alerts"][0].status == "fired"


def test_process_without_services_without_loop_clean():
    """No services configured: still clean (no coroutine attempt at all)."""
    pipeline = _pipeline_with_roi()

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        result = pipeline.process(_make_event())

    assert len(result["alerts"]) == 1
