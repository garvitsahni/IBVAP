"""Tests for the shared ONNX model runtime (Task 1)."""
import pytest


def test_resolve_providers_prefers_cuda_when_available(monkeypatch):
    import edge.model_runtime as mr
    monkeypatch.setattr(mr.ort, "get_available_providers",
                        lambda: ["CPUExecutionProvider", "CUDAExecutionProvider"])
    assert mr.resolve_providers()[0] == "CUDAExecutionProvider"


def test_resolve_providers_falls_back_to_cpu(monkeypatch):
    import edge.model_runtime as mr
    monkeypatch.setattr(mr.ort, "get_available_providers",
                        lambda: ["CPUExecutionProvider"])
    assert mr.resolve_providers() == ["CPUExecutionProvider"]


def test_resolve_providers_cpu_when_gpu_not_preferred(monkeypatch):
    import edge.model_runtime as mr
    monkeypatch.setattr(mr.ort, "get_available_providers",
                        lambda: ["CPUExecutionProvider", "CUDAExecutionProvider"])
    assert mr.resolve_providers(prefer_gpu=False)[0] == "CPUExecutionProvider"


def test_create_session_missing_file_raises(tmp_path):
    import edge.model_runtime as mr
    try:
        mr.create_session(str(tmp_path / "nope.onnx"))
        assert False, "should have raised"
    except RuntimeError as e:
        assert "nope.onnx" in str(e)
