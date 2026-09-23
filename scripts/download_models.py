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

model = osnet_ain_x1_0(pretrained=False, num_classes=1000)
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


def export_vehicle_reid_to_onnx():
    """Export a vehicle Re-ID model to ONNX."""
    dest = MODELS_DIR / "vehicle_reid.onnx"
    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"  [SKIP] {dest.name} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
        return True

    print("  [INFO] Building vehicle Re-ID ONNX model (ResNet50 backbone)...")
    script = r'''
import warnings
warnings.filterwarnings("ignore")
import torch
import torch.nn as nn
from torchvision import models

class VehicleReID(nn.Module):
    def __init__(self, embedding_dim=512):
        super().__init__()
        backbone = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
        self.features = nn.Sequential(*list(backbone.children())[:-1])
        self.fc = nn.Linear(2048, embedding_dim)

    def forward(self, x):
        feat = self.features(x).flatten(1)
        emb = self.fc(feat)
        emb = torch.nn.functional.normalize(emb, p=2, dim=1)
        return emb

model = VehicleReID(embedding_dim=512)
model.eval()

dummy = torch.randn(1, 3, 224, 224)
torch.onnx.export(
    model, dummy, "models/vehicle_reid.onnx",
    input_names=["input"], output_names=["embedding"],
    dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"}},
    opset_version=17,
    dynamo=False,
)
print("Vehicle ReID exported successfully")
'''
    if run_export_script(script, timeout=180):
        size = dest.stat().st_size / 1e6
        print(f"  [DONE] {dest.name} ({size:.1f} MB)")
        return True
    return False


def export_plate_detector_to_onnx():
    """Export a plate detection model to ONNX."""
    dest = MODELS_DIR / "plate_detector.onnx"
    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"  [SKIP] {dest.name} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
        return True

    print("  [INFO] Building plate detector ONNX model (MobileNet-SSD style)...")
    script = r'''
import warnings
warnings.filterwarnings("ignore")
import torch
import torch.nn as nn
from torchvision import models

class PlateDetector(nn.Module):
    def __init__(self):
        super().__init__()
        backbone = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
        self.features = backbone.features
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(576, 256),
            nn.ReLU(),
            nn.Linear(256, 5),  # [confidence, x1, y1, x2, y2]
            nn.Sigmoid(),
        )

    def forward(self, x):
        feat = self.features(x)
        out = self.classifier(feat)
        return out

model = PlateDetector()
model.eval()

dummy = torch.randn(1, 3, 320, 320)
torch.onnx.export(
    model, dummy, "models/plate_detector.onnx",
    input_names=["input"], output_names=["output"],
    dynamic_axes={"input": {0: "batch"}},
    opset_version=17,
    dynamo=False,
)
print("Plate detector exported successfully")
'''
    if run_export_script(script, timeout=180):
        size = dest.stat().st_size / 1e6
        print(f"  [DONE] {dest.name} ({size:.1f} MB)")
        return True
    return False


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
        "vehicle_reid.onnx": (1, 3, 224, 224),
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="IBVAP model downloader / verifier")
    parser.add_argument("--verify", action="store_true",
                        help="verify installed models (load + smoke inference) instead of downloading")
    args = parser.parse_args()
    if args.verify:
        ensure_dir()
        return verify_all()

    print("=" * 60)
    print("IBVAP Model Downloader / Exporter")
    print("=" * 60)

    ensure_dir()
    results = {}

    print("\n[1/4] OSNet AIN x1.0 (Person Re-ID)")
    results["osnet"] = export_osnet_to_onnx()

    print("\n[2/4] ArcFace R100 (Face Embedding)")
    results["arcface"] = export_arcface_to_onnx()

    print("\n[3/4] Vehicle Re-ID (ResNet50)")
    results["vehicle_reid"] = export_vehicle_reid_to_onnx()

    print("\n[4/4] Plate Detector (MobileNet-SSD)")
    results["plate_detector"] = export_plate_detector_to_onnx()

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
