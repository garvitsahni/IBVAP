"""Regression: loopback URLs must use 127.0.0.1, not 'localhost' (Bug D).

On this host IPv6 loopback (::1) drops connections — resolving 'localhost'
burns ~2s before falling back to IPv4 (measured: localhost ~2.05s vs
127.0.0.1 13-35ms). The edge publish timeout is 2.0s, so 'localhost' makes
edge->fusion and ffmpeg->mediamtx legs borderline/failing.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_edge_default_camera_urls_use_ipv4_loopback():
    from edge.run_all import DEFAULT_CAMERA_URLS
    assert DEFAULT_CAMERA_URLS, "no default camera URLs defined"
    for cam, url in DEFAULT_CAMERA_URLS.items():
        assert "localhost" not in url, f"{cam} URL uses 'localhost': {url}"
        assert "127.0.0.1" in url, f"{cam} URL not on 127.0.0.1: {url}"


def test_run_all_fusion_default_uses_ipv4_loopback():
    src = (ROOT / "edge" / "run_all.py").read_text(encoding="utf-8")
    assert 'default="http://127.0.0.1:8000"' in src


def test_mediamtx_publish_urls_use_ipv4_loopback():
    src = (ROOT / "mediamtx.yml").read_text(encoding="utf-8")
    assert "rtsp://localhost" not in src, "mediamtx runOnDemand publishes to 'localhost' (IPv6 drop)"
    assert "rtsp://127.0.0.1:8554" in src
