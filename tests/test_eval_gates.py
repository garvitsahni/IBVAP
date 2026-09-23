"""Accuracy gates for IBVAP Re-ID models (Tasks 2-4).

- Fast smoke tests always run (determinism, real-model sanity).
- Dataset gates run only when eval data is cached (data/eval/...); otherwise
  they skip with a loud message telling the operator how to fetch data.
  Skipped gates must be run before claiming accuracy — see scripts/eval_accuracy.py.
"""
import os
from pathlib import Path

import pytest

try:
    import ultralytics  # noqa: F401
    _HAS_YOLO = True
except Exception:
    _HAS_YOLO = False

REPO_ROOT = Path(__file__).parent.parent
EVAL_DIR = REPO_ROOT / "data" / "eval"
MARKET1501_DIR = EVAL_DIR / "market1501"


def _onnx_session():
    from edge.model_runtime import create_session
    return create_session(str(REPO_ROOT / "models" / "osnet_ain_x1_0.onnx"))


def test_osnet_embedding_deterministic():
    """Same crop twice -> cosine ~1.0 (smoke: model loads and runs)."""
    import numpy as np
    rng = np.random.default_rng(7)
    crop = rng.random((1, 3, 256, 128), dtype=np.float32)
    s = _onnx_session()
    name = s.get_inputs()[0].name
    e1 = s.run(None, {name: crop})[0].flatten()
    e2 = s.run(None, {name: crop})[0].flatten()
    cos = float(e1 @ e2 / (np.linalg.norm(e1) * np.linalg.norm(e2)))
    assert cos > 0.999


def test_osnet_weights_are_trained():
    """Trained OSNet responds to structure: a striped crop embeds far from
    flat-grey relative to duplicate consistency (guards against random-weight
    regressions like pretrained=False exports)."""
    import numpy as np
    s = _onnx_session()
    name = s.get_inputs()[0].name
    stripes = np.zeros((1, 3, 256, 128), dtype=np.float32)
    stripes[:, :, ::8, :] = 1.0
    grey = np.full((1, 3, 256, 128), 0.5, dtype=np.float32)

    def emb(x):
        e = s.run(None, {name: x})[0].flatten()
        return e / np.linalg.norm(e)

    es, eg = emb(stripes), emb(grey)
    cross = float(es @ eg)
    assert cross < 0.999, f"model looks untrained (stripes-vs-grey cos={cross})"


@pytest.mark.skipif(not (REPO_ROOT / "footage" / "cam1.mp4").exists(),
                    reason="footage/cam1.mp4 and cam2.mp4 required for accuracy gate")
@pytest.mark.skipif(not _HAS_YOLO,
                    reason="ultralytics required. Run with the ML env: venv/Scripts/python -m pytest tests/test_eval_gates.py")
def test_person_reid_footage_gate():
    """Temporal consistency >= 0.70 and identity margin >= 0.15 on repo footage."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from eval_accuracy import eval_person_footage, GATE_TEMPORAL, GATE_MARGIN
    vids = [str(REPO_ROOT / "footage" / "cam1.mp4"),
            str(REPO_ROOT / "footage" / "cam2.mp4")]
    res = eval_person_footage(str(REPO_ROOT / "models" / "osnet_ain_x1_0.onnx"),
                              vids, frames_per_video=25)
    print(f"\ntemporal={res['temporal']:.3f} cross={res['cross']:.3f} "
          f"margin={res['margin']:.3f} tracks={res['n_tracks']}")
    assert res["n_tracks"] >= 1, "no person tracks found in footage"
    assert res["temporal"] >= GATE_TEMPORAL, (
        f"temporal {res['temporal']:.3f} below gate {GATE_TEMPORAL}")
    assert res["margin"] >= GATE_MARGIN, (
        f"margin {res['margin']:.3f} below gate {GATE_MARGIN}")


VERI_DIR = EVAL_DIR / "veri-776" / "VeRi"


@pytest.mark.skipif(not VERI_DIR.exists(),
                    reason="data/eval/veri-776/VeRi required for vehicle gate")
def test_vehicle_reid_veri_gate():
    """Rank-1 >= 0.60 on VeRi-776 with production preprocessing (200 queries)."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from eval_accuracy import eval_vehicle_veri, GATE_VEHICLE_RANK1
    res = eval_vehicle_veri(str(REPO_ROOT / "models" / "vehicle_reid.onnx"),
                            str(VERI_DIR), max_queries=200)
    print(f"\nvehicle Rank-1={res['rank1']:.3f} queries={res['n_queries']} "
          f"gallery={res['n_gallery']}")
    assert res["n_queries"] >= 200, "expected at least 200 queries"
    assert res["rank1"] >= GATE_VEHICLE_RANK1, (
        f"Rank-1 {res['rank1']:.3f} below gate {GATE_VEHICLE_RANK1}")
