"""
Shared ONNX model runtime — GPU-primary provider resolution + loud model loading.

GPU-preferred policy: CUDAExecutionProvider first when available, falling back
to CPUExecutionProvider. The active provider is always logged so degraded
(CPU) mode is loud, never silent. Model files that are missing or corrupt
raise RuntimeError with the path in the message (fail fast at startup,
not mid-pipeline).
"""
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import onnxruntime as ort
except Exception:  # pragma: no cover - import guard
    ort = None  # type: ignore

_dll_dirs_done = False


def _ensure_windows_dll_dirs():
    """Register pip-installed NVIDIA DLL dirs (nvidia-cudnn-cu12 etc.).

    On Windows those DLLs live under site-packages/nvidia/*/lib, which is
    not on the OS DLL search path — without this, CUDAExecutionProvider
    fails to load cuDNN/cuBLAS and silently drops to CPU.
    """
    global _dll_dirs_done
    if _dll_dirs_done or os.name != "nt":
        return
    _dll_dirs_done = True
    try:
        import site
        roots = site.getsitepackages() + [site.getusersitepackages()]
        import glob
        for root in roots:
            for pattern in ("nvidia/*/lib", "nvidia/*/bin"):
                for libdir in glob.glob(os.path.join(root, pattern)):
                    if not os.path.isdir(libdir):
                        continue
                    try:
                        os.add_dll_directory(libdir)
                    except OSError:
                        pass
                    if libdir not in os.environ.get("PATH", ""):
                        os.environ["PATH"] = libdir + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:  # pragma: no cover - best effort
        logger.debug(f"DLL dir registration skipped: {e}")


def resolve_providers(prefer_gpu: bool = True) -> List[str]:
    """Return ONNX providers ordered by preference.

    GPU-primary: CUDA first when the installed onnxruntime build offers it.
    Always ends with CPUExecutionProvider as the guaranteed fallback.
    """
    available = []
    if ort is not None:
        try:
            available = list(ort.get_available_providers())
        except Exception:
            available = []
    ordered: List[str] = []
    if prefer_gpu and "CUDAExecutionProvider" in available:
        ordered.append("CUDAExecutionProvider")
    if "CPUExecutionProvider" in available:
        ordered.append("CPUExecutionProvider")
    if not ordered:
        # onnxruntime always ships CPU; this covers mocked/odd builds.
        ordered = ["CPUExecutionProvider"]
    elif prefer_gpu and ordered[0] != "CUDAExecutionProvider" and "CUDAExecutionProvider" in available:
        ordered.insert(0, "CUDAExecutionProvider")
    # De-duplicate while preserving order, CPU last as fallback.
    seen: List[str] = []
    for p in ordered:
        if p not in seen:
            seen.append(p)
    if "CPUExecutionProvider" in seen:
        seen.append(seen.pop(seen.index("CPUExecutionProvider")))
    return seen


def create_session(model_path: str, prefer_gpu: bool = True):
    """Create an ONNX InferenceSession with loud provider logging.

    Raises RuntimeError if the file is missing or the session cannot start.
    """
    if ort is None:
        raise RuntimeError("onnxruntime is not installed; cannot load " + model_path)
    if not model_path or not os.path.isfile(model_path):
        raise RuntimeError(f"ONNX model file not found: {model_path}")
    _ensure_windows_dll_dirs()
    providers = resolve_providers(prefer_gpu=prefer_gpu)
    try:
        session = ort.InferenceSession(model_path, providers=providers)
    except Exception as e:
        raise RuntimeError(f"Failed to start ONNX session for {model_path}: {e}")
    try:
        active = session.get_providers()
    except Exception:
        active = providers
    logger.info(f"ONNX model loaded: {model_path} (providers: {active})")
    if active and active[0] == "CPUExecutionProvider" and prefer_gpu:
        logger.warning(
            f"Model {os.path.basename(model_path)} running on CPU — "
            "CUDAExecutionProvider unavailable (CPU fallback mode)"
        )
    return session


def verify_model(model_path: str, dummy_shape: Tuple[int, ...],
                 prefer_gpu: bool = True, timeout_s: float = 60.0) -> Dict:
    """Load a model and run one dummy inference. Returns a report dict.

    Never raises for inference issues — reports ok=False with the error.
    Raises RuntimeError only if the file itself is missing (fail fast).
    """
    import numpy as np

    if not model_path or not os.path.isfile(model_path):
        raise RuntimeError(f"ONNX model file not found: {model_path}")
    session = create_session(model_path, prefer_gpu=prefer_gpu)
    try:
        active = session.get_providers()
    except Exception:
        active = resolve_providers(prefer_gpu=prefer_gpu)
    report: Dict = {"path": model_path, "providers": active, "ok": False,
                    "latency_ms": None, "error": None}
    try:
        input_name = session.get_inputs()[0].name
        dummy = np.zeros(dummy_shape, dtype=np.float32)
        start = time.perf_counter()
        session.run(None, {input_name: dummy})
        report["latency_ms"] = (time.perf_counter() - start) * 1000.0
        report["ok"] = True
    except Exception as e:
        report["error"] = str(e)[:300]
    return report
