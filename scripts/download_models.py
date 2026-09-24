#!/usr/bin/env python3
"""
Download and export real ONNX models for the IBVAP pipeline.

Models needed:
1. OSNet AIN x1.0 (person Re-ID) -> models/osnet_ain_x1_0.onnx
2. Vehicle Re-ID (ResNet50-VeRi) -> models/vehicle_reid.onnx
3. ArcFace R100 (face embedding) -> models/arcface_r100.onnx
4. Plate Detector (YOLO-plate)  -> models/plate_detector.onnx

Usage:
    python scripts/download_models.py
"""
import os
import sys
import subprocess
from pathlib import Path

MODELS_DIR = Path(__file__).parent.parent / "models"


def ensure_dir():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def run_export_script(script: str, timeout: int = 180) -> bool:
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        cwd=str(Path(__file__).parent.parent),
        timeout=timeout,
    )
    if result.returncode != 0:
        # Print only last 30 lines of stderr to avoid overwhelming output
        lines = result.stderr.strip().split("\n")
        tail = "\n".join(lines[-15:])
        print(f"  [FAIL] {tail}")
        return False
    return True


def export_osnet_to_onnx():
    """Export OSNet AIN x1.0 to ONNX using torchreid."""
    dest = MODELS_DIR / "osnet_ain_x1_0.onnx"
    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"  [SKIP] {dest.name} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
        return True

    print("  [INFO] Exporting OSNet AIN x1.0 to ONNX (dynamo=False)...")
    script = r'''
import warnings
warnings.filterwarnings("ignore")
import torch
import torch.onnx

# Import directly from the reid subpackage to avoid top-level torchreid init
import importlib
mod = importlib.import_module("torchreid.reid.models.osnet_ain")
osnet_ain_x1_0 = mod.osnet_ain_x1_0

model = osnet_ain_x1_0(pretrained=True, num_classes=1000)
model.eval()

dummy = torch.randn(1, 3, 256, 128)
torch.onnx.export(
    model, dummy, "models/osnet_ain_x1_0.onnx",
    input_names=["input"], output_names=["embedding"],
    dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"}},
    opset_version=17,
    dynamo=False,
)
print("OSNet exported successfully")
'''
    if run_export_script(script):
        size = dest.stat().st_size / 1e6
        print(f"  [DONE] {dest.name} ({size:.1f} MB)")
        return True
    return False


def export_arcface_to_onnx():
    """Export ArcFace R100 to ONNX using insightface."""
    dest = MODELS_DIR / "arcface_r100.onnx"
    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"  [SKIP] {dest.name} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
        return True

    print("  [INFO] Trying insightface model zoo download...")
    script = r'''
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["INSIGHTFACE_HOME"] = "models/.insightface"
import shutil

from insightface.app import FaceAnalysis
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=(640, 640))

# Find the downloaded recognition model
model_dir = os.path.join(os.environ["INSIGHTFACE_HOME"], "models", "buffalo_l")
onnx_files = [f for f in os.listdir(model_dir) if f.endswith(".onnx")] if os.path.exists(model_dir) else []
print(f"Available ONNX files: {onnx_files}")

# Prefer w600k_r50.onnx or glint360k_r100.onnx
for preferred in ["w600k_r50.onnx", "glint360k_r100.onnx", "arcface_r100.onnx"]:
    src = os.path.join(model_dir, preferred)
    if os.path.exists(src):
        shutil.copy(src, "models/arcface_r100.onnx")
        print(f"ArcFace copied from {preferred}")
        break
else:
    # Just copy the first onnx file found
    for f in onnx_files:
        src = os.path.join(model_dir, f)
        shutil.copy(src, "models/arcface_r100.onnx")
        print(f"ArcFace copied from {f}")
        break
    else:
        print("ERROR: No ONNX model found in insightface cache")
        sys.exit(1)
'''
    if run_export_script(script, timeout=300):
        size = dest.stat().st_size / 1e6
        print(f"  [DONE] {dest.name} ({size:.1f} MB)")
        return True
    return False


def download_hf_onnx(repo_id: str, filename: str, dest_name: str,
                     source_note: str) -> bool:
    """Fetch a pretrained ONNX model from the Hugging Face Hub into models/.

    Replaces the old random-weight torch builders — every model this script
    installs must be trained weights (AGENTS.md no-faking rule).
    """
    dest = MODELS_DIR / dest_name
    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"  [SKIP] {dest.name} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
        return True
    print(f"  [INFO] Downloading {source_note} ...")
    try:
        from huggingface_hub import hf_hub_download
        src = hf_hub_download(repo_id, filename)
        dest.write_bytes(Path(src).read_bytes())
        size = dest.stat().st_size / 1e6
        print(f"  [DONE] {dest.name} ({size:.1f} MB)")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def export_vehicle_reid_to_onnx():
    """Install vehicle Re-ID weights: ResNet34 trained on VeRi-776 (512-d, 256x256)."""
    return download_hf_onnx(
        "dgwon/resnet-34-veri776-onnx", "resnet34_veri776.onnx",
        "vehicle_reid.onnx",
        "vehicle Re-ID ResNet34 (VeRi-776-trained) from HF dgwon/resnet-34-veri776-onnx",
    )


def export_plate_detector_to_onnx():
    """Install plate detector weights: YOLOv11 license-plate detector (raw [5,N] output)."""
    return download_hf_onnx(
        "morsetechlab/yolov11-license-plate-detection",
        "license-plate-finetune-v1n.onnx",
        "plate_detector.onnx",
        "YOLOv11 plate detector from HF morsetechlab/yolov11-license-plate-detection",
    )


def verify_all() -> int:
    """Startup verification: each model loads + runs one dummy inference.

    Prints a per-model report (provider, latency, ok/fail). Returns 0 only
    when every expected model verifies. Uses GPU when available, CPU fallback.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from edge.model_runtime import verify_model

    expected = {
        "osnet_ain_x1_0.onnx": (1, 3, 256, 128),
        "arcface_r100.onnx": (1, 3, 112, 112),
        "vehicle_reid.onnx": (1, 3, 256, 256),
        "plate_detector.onnx": (1, 3, 320, 320),
    }
    print("=" * 60)
    print("IBVAP Model Verification (GPU-primary, CPU fallback)")
    print("=" * 60)
    all_ok = True
    for name, shape in expected.items():
        path = MODELS_DIR / name
        try:
            report = verify_model(str(path), shape)
        except RuntimeError as e:
            print(f"  [MISSING] {name}: {e}")
            all_ok = False
            continue
        status = "OK" if report["ok"] else "FAIL"
        latency = f"{report['latency_ms']:.1f}ms" if report["latency_ms"] else "n/a"
        providers = ",".join(report["providers"])
        extra = "" if report["ok"] else f" error={report['error']}"
        print(f"  [{status}] {name} providers=[{providers}] latency={latency}{extra}")
        all_ok = all_ok and report["ok"]
    return 0 if all_ok else 1


# Static provenance + measured eval scores (re-measured via
# scripts/eval_accuracy.py; only real measured numbers go here — update the
# score fields only from a fresh eval run).
MODEL_META = {
    "osnet_ain_x1_0.onnx": {
        "role": "person Re-ID embedding",
        "source": "torchreid osnet_ain_x1_0 pretrained (Market-1501)",
        "input": [1, 3, 256, 128],
        "eval": "footage gate (cam1+cam2): temporal=0.780 cross=0.469 "
                "margin=0.311 tracks=7 @2026-09-24",
    },
    "vehicle_reid.onnx": {
        "role": "vehicle Re-ID embedding",
        "source": "https://huggingface.co/dgwon/resnet-34-veri776-onnx "
                  "(resnet34_veri776.onnx, VeRi-776-trained)",
        "input": [1, 3, 256, 256],
        "eval": "VeRi-776 Rank-1=0.865 (200 queries, stride-5 gallery, "
                "ImageNet-norm) @2026-09-24",
    },
    "plate_detector.onnx": {
        "role": "license-plate region detection",
        "source": "https://huggingface.co/morsetechlab/yolov11-license-plate-detection "
                  "(license-plate-finetune-v1n.onnx)",
        "input": [1, 3, 320, 320],
        "eval": "keremberke plate test split precision=0.999 (860/861 TP, "
                "882 images, IoU>=0.5) @2026-09-24",
    },
    "arcface_r100.onnx": {
        "role": "face embedding",
        "source": "insightface buffalo_l model zoo (w600k/glint360k recognition ONNX)",
        "input": [1, 3, 112, 112],
        "eval": "LFW Rank-1=0.950 (200 identities, production "
                "detect->crop->embed path, gate >=0.90) @2026-09-24",
    },
}


def write_manifest() -> int:
    """Write models/MANIFEST.json: sha256 + provenance + measured eval score."""
    import hashlib
    import json
    from datetime import datetime, timezone

    ensure_dir()
    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(),
                "models": {}}
    all_present = True
    for name, meta in MODEL_META.items():
        path = MODELS_DIR / name
        if not path.is_file():
            print(f"  [MISSING] {name}")
            all_present = False
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["models"][name] = {
            **meta,
            "bytes": path.stat().st_size,
            "sha256": sha,
        }
        print(f"  [OK] {name} sha256={sha[:16]}…")
    out = MODELS_DIR / "MANIFEST.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {out}")
    return 0 if all_present else 1


def download_yolov8m() -> bool:
    """Fetch the YOLOv8m detector weights (GPU-tier /detect default).

    Pinned to the ultralytics v8.3.0 release with the sha256 of the
    canonical artifact; ultralytics auto-downloads the same file at runtime,
    but downloading here keeps `download_models.py` a one-shot setup.
    """
    import hashlib
    import urllib.request

    dest = Path(__file__).parent.parent / "yolov8m.pt"
    expected_sha = "5d4a90cdc7a21786cc59cd19778e9eafff836df9e2da32524737c7ee6efe4fe5"
    if dest.exists():
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        if sha == expected_sha:
            print(f"  [SKIP] {dest.name} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
            return True
        print(f"  [WARN] {dest.name} sha256 mismatch — re-downloading")
        dest.unlink()
    url = ("https://github.com/ultralytics/assets/releases/download/"
           "v8.3.0/yolov8m.pt")
    print(f"  [INFO] Downloading {dest.name} from ultralytics release ...")
    try:
        urllib.request.urlretrieve(url, dest)
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        if sha != expected_sha:
            dest.unlink(missing_ok=True)
            print(f"  [FAIL] sha256 mismatch: {sha}")
            return False
        print(f"  [DONE] {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        dest.unlink(missing_ok=True)
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="IBVAP model downloader / verifier")
    parser.add_argument("--verify", action="store_true",
                        help="verify installed models (load + smoke inference) instead of downloading")
    parser.add_argument("--manifest", action="store_true",
                        help="write models/MANIFEST.json (sha256 + provenance + eval scores)")
    args = parser.parse_args()
    if args.verify:
        ensure_dir()
        return verify_all()
    if args.manifest:
        return write_manifest()

    print("=" * 60)
    print("IBVAP Model Downloader / Exporter")
    print("=" * 60)

    ensure_dir()
    results = {}

    print("\n[1/5] OSNet AIN x1.0 (Person Re-ID)")
    results["osnet"] = export_osnet_to_onnx()

    print("\n[2/5] ArcFace R100 (Face Embedding)")
    results["arcface"] = export_arcface_to_onnx()

    print("\n[3/5] Vehicle Re-ID (ResNet34-VeRi-776)")
    results["vehicle_reid"] = export_vehicle_reid_to_onnx()

    print("\n[4/5] Plate Detector (YOLOv11 license-plate)")
    results["plate_detector"] = export_plate_detector_to_onnx()

    print("\n[5/5] YOLOv8m detector (GPU-tier /detect default)")
    results["yolov8m"] = download_yolov8m()

    # Summary
    print("\n" + "=" * 60)
    print("Results:")
    for name, ok in results.items():
        status = "OK" if ok else "FAILED"
        print(f"  {name}: {status}")

    all_ok = all(results.values())
    if all_ok:
        print("\nAll models ready!")
    else:
        print("\nSome models failed. The pipeline will use graceful fallbacks.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
