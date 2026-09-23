"""C2 webhook forwarder tests (Task 3)."""
import asyncio


def test_c2_disabled_returns_false():
    from fusion_server.services.c2_forwarder import C2Forwarder

    f = C2Forwarder(url="", secret="x")
    assert f.enabled is False
    assert asyncio.run(f.forward_async({"alert_id": "a1"})) is False


def test_c2_signs_and_posts(monkeypatch):
    from fusion_server.services import c2_forwarder as mod

    calls = {}

    class R:
        status_code = 200

    def fake_post(url, data=None, headers=None, timeout=None):
        calls.update(url=url, data=data, headers=headers, timeout=timeout)
        return R()

    monkeypatch.setattr(mod.requests, "post", fake_post)
    f = mod.C2Forwarder(url="http://c2.local/hook", secret="s3cr3t")
    assert f.enabled is True
    assert f.forward({"alert_id": "a1", "reason": "roi_intrusion"}) is True
    assert calls["url"] == "http://c2.local/hook"
    assert calls["headers"]["X-IBVAP-Alert-ID"] == "a1"
    assert len(calls["headers"]["X-IBVAP-Signature"]) == 64


def test_c2_never_raises_on_connection_error(monkeypatch):
    from fusion_server.services import c2_forwarder as mod

    def boom(*a, **k):
        raise ConnectionError("down")

    monkeypatch.setattr(mod.requests, "post", boom)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    f = mod.C2Forwarder(url="http://c2.local/hook", secret="s", max_retries=1)
    assert f.forward({"alert_id": "a1"}) is False
