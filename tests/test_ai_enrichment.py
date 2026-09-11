"""Tests for AI enrichment service."""
import pytest
from unittest.mock import MagicMock, patch
from fusion_server.services.ai_enrichment import AIEnrichmentService


def test_enrichment_service_initializes():
    """AI enrichment service can be created."""
    service = AIEnrichmentService()
    assert service is not None


def test_enrichment_generates_explanation():
    """Enrichment produces a natural language explanation."""
    service = AIEnrichmentService()
    alert_data = {
        "alert_id": "test-123",
        "object_id": "obj1",
        "camera_id": "cam1",
        "reason": "enter",
        "threat_score": 0.7,
        "trajectory": {"history": [[0.1, 0.2], [0.3, 0.4]], "predicted": [[0.5, 0.6]]},
    }
    with patch.object(service, '_call_llava', return_value="Person detected entering restricted zone at 10:00 AM"):
        result = service.enrich(alert_data)
    assert result is not None
    assert len(result) > 0


def test_enrichment_returns_template_on_model_failure():
    """Falls back to template when model unavailable."""
    service = AIEnrichmentService()
    alert_data = {
        "alert_id": "test-123",
        "object_id": "obj1",
        "camera_id": "cam1",
        "reason": "enter",
        "threat_score": 0.7,
    }
    with patch.object(service, '_call_llava', side_effect=Exception("Model not loaded")):
        result = service.enrich(alert_data)
    assert result is not None
    assert "enter" in result.lower() or "alert" in result.lower()
