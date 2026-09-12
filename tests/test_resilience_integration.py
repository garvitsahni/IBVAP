"""Phase 6 integration tests — simulated failure scenarios."""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

from fusion_server.services.camera_health_store import CameraHealthStore
from fusion_server.services.camera_offline_monitor import CameraOfflineMonitor
from fusion_server.services.detector_fallback import DetectorFallback
from fusion_server.services.ledger_checkpoint import LedgerCheckpoint
from fusion_server.services.clip_checkpoint import ClipCheckpoint
from fusion_server.services.power_manager import PowerManager
from fusion_server.services.resilience_aggregator import ResilienceAggregator


class TestCameraDisconnectSimulation:
    def test_camera_goes_offline_detected(self):
        store = CameraHealthStore()
        store.update("cam1", {"status": "ok"})
        store.heartbeat("cam1")
        store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)

        monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock(), heartbeat_interval=30)
        statuses = monitor.get_statuses()
        assert statuses["cam1"] == "offline"

    def test_offline_updates_aggregator(self):
        store = CameraHealthStore()
        store.update("cam1", {"status": "ok"})
        store.heartbeat("cam1")
        store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)

        agg = ResilienceAggregator()
        monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock(), heartbeat_interval=30)
        for cam_id, status in monitor.get_statuses().items():
            agg.update_camera_status(cam_id, status)
        health = agg.get_health()
        assert health["status"] == "degraded"
        assert health["cameras"]["cam1"] == "offline"


class TestComputeOverloadSimulation:
    def test_high_latency_triggers_fallback(self):
        fb = DetectorFallback()
        for _ in range(6):
            fb.report_metrics(latency_ms=300, queue_depth=5, errors=0)
        assert fb.get_current_tier() == "degraded"

    def test_extreme_load_triggers_critical(self):
        fb = DetectorFallback()
        for _ in range(6):
            fb.report_metrics(latency_ms=600, queue_depth=35, errors=0)
        assert fb.get_current_tier() == "critical"

    def test_fallback_updates_aggregator(self):
        fb = DetectorFallback()
        agg = ResilienceAggregator()
        for _ in range(6):
            fb.report_metrics(latency_ms=300, queue_depth=5, errors=0)
        agg.update_detection_tier(fb.get_current_tier())
        assert agg.get_health()["status"] == "degraded"


class TestCrashMidWriteSimulation:
    def test_checkpoint_writes_and_resumes(self, tmp_path):
        cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
        cp.write_checkpoint(alert_id=10, hash="hash10", chain_length=10)
        cp.write_checkpoint(alert_id=20, hash="hash20", chain_length=20)
        status = cp.resume()
        assert status["last_alert_id"] == 20
        assert status["chain_length"] == 20

    def test_clip_orphan_detection(self, tmp_path):
        cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
        cp.mark_pending("alert-1")
        cp.mark_pending("alert-2")
        orphans = cp.scan_orphans()
        assert len(orphans) == 2

    def test_checkpoint_updates_aggregator(self, tmp_path):
        cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
        cp.write_checkpoint(alert_id=5, hash="h5", chain_length=5)
        agg = ResilienceAggregator()
        status = cp.get_status()
        agg.update_ledger_status(status["status"])
        assert agg.get_health()["ledger"]["status"] == "ok"


class TestPowerLossSimulation:
    def test_high_cpu_triggers_reduced(self):
        with pytest.MonkeyPatch.context() as mp:
            import fusion_server.services.power_manager as pm_mod
            mock_psutil = MagicMock()
            mock_psutil.cpu_percent.return_value = 85.0
            mock_mem = MagicMock()
            mock_mem.percent = 50.0
            mock_psutil.virtual_memory.return_value = mock_mem
            mp.setattr(pm_mod, "psutil", mock_psutil)

            pm = PowerManager()
            pm.check_and_update()
            assert pm.get_mode() == "reduced"

    def test_power_mode_updates_aggregator(self):
        agg = ResilienceAggregator()
        agg.update_power_mode("reduced")
        health = agg.get_health()
        assert health["status"] == "degraded"
        assert health["power_mode"] == "reduced"


class TestEndToEndResilience:
    def test_multiple_failures_compound(self):
        agg = ResilienceAggregator()
        agg.update_camera_status("cam1", "offline")
        agg.update_detection_tier("degraded")
        agg.update_power_mode("reduced")
        health = agg.get_health()
        assert health["status"] == "degraded"

    def test_critical_status_from_any_signal(self):
        agg = ResilienceAggregator()
        agg.update_detection_tier("critical")
        assert agg.get_health()["status"] == "critical"

        agg2 = ResilienceAggregator()
        agg2.update_ledger_status("gap_detected")
        assert agg2.get_health()["status"] == "critical"

    def test_full_recovery(self):
        agg = ResilienceAggregator()
        agg.update_camera_status("cam1", "offline")
        agg.update_detection_tier("degraded")
        agg.update_power_mode("reduced")
        assert agg.get_health()["status"] == "degraded"

        agg.update_camera_status("cam1", "online")
        agg.update_detection_tier("normal")
        agg.update_power_mode("normal")
        assert agg.get_health()["status"] == "ok"
