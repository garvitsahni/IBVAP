"""
Brightness/visibility estimation and preprocessing for night-time and
poor-visibility conditions.
"""
import cv2
import numpy as np
from typing import Tuple, Dict, Optional


class NightWeatherProcessor:
    """
    Estimates brightness and visibility per frame, applies preprocessing
    transforms for night/haze modes.

    Mode stability: requires 5 consecutive frames in the new state before switching.
    """

    BRIGHTNESS_NORMAL = 80
    BRIGHTNESS_NIGHT = 30
    VISIBILITY_THRESHOLD = 0.4
    STABILITY_FRAMES = 5

    def __init__(self):
        self._current_mode = "normal"
        self._candidate_mode = "normal"
        self._candidate_count = 0

    def process(
        self, frame: np.ndarray, force_mode: Optional[str] = None
    ) -> Tuple[np.ndarray, Dict]:
        brightness = self._estimate_brightness(frame)
        visibility = self._estimate_visibility(frame)

        if force_mode:
            mode = force_mode
        else:
            mode = self._update_mode(brightness, visibility)

        if mode == "night":
            processed = self._enhance_night(frame)
        elif mode == "hazy":
            processed = self._enhance_haze(frame)
        else:
            processed = frame.copy()

        mode_info = {
            "mode": mode,
            "brightness": float(brightness),
            "visibility": float(visibility),
        }
        return processed, mode_info

    def _estimate_brightness(self, frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray))

    def _estimate_visibility(self, frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        blur_var = laplacian.var()
        blur_score = min(1.0, blur_var / 500.0)

        min_val, max_val = float(np.min(gray)), float(np.max(gray))
        contrast = (max_val - min_val) / 255.0

        visibility = (blur_score + contrast) / 2.0
        return float(np.clip(visibility, 0.0, 1.0))

    def _update_mode(self, brightness: float, visibility: float) -> str:
        if brightness <= self.BRIGHTNESS_NIGHT:
            candidate = "night"
        elif brightness <= self.BRIGHTNESS_NORMAL:
            candidate = "night"
        elif visibility < self.VISIBILITY_THRESHOLD:
            candidate = "hazy"
        else:
            candidate = "normal"

        if candidate == self._candidate_mode:
            self._candidate_count += 1
        else:
            self._candidate_mode = candidate
            self._candidate_count = 1

        if self._candidate_count >= self.STABILITY_FRAMES:
            self._current_mode = candidate

        return self._current_mode

    def _enhance_night(self, frame: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l)

        lab_enhanced = cv2.merge([l_enhanced, a, b])
        enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        gamma = 0.7
        lut = np.array([((i / 255.0) ** gamma) * 255 for i in range(256)]).astype("uint8")
        enhanced = cv2.LUT(enhanced, lut)

        return enhanced

    def _enhance_haze(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        p5, p95 = np.percentile(gray, [5, 95])
        stretched = np.clip((frame.astype(np.float64) - p5) / (p95 - p5 + 1e-6) * 255, 0, 255).astype(np.uint8)

        blurred = cv2.GaussianBlur(stretched, (0, 0), 3)
        sharpened = cv2.addWeighted(stretched, 1.5, blurred, -0.5, 0)

        return sharpened
