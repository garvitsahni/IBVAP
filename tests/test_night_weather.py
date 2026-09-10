"""Tests for night/weather adaptation module."""
import numpy as np

def test_brightness_normal_frame():
    """Bright frame detected as normal mode."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    frame = np.full((480, 640, 3), 150, dtype=np.uint8)
    _, info = proc.process(frame)
    assert info["brightness"] > 80
    assert info["mode"] == "normal"

def test_brightness_night_frame():
    """Dark frame detected as night mode (after stability window)."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    frame = np.full((480, 640, 3), 10, dtype=np.uint8)
    for _ in range(5):
        _, info = proc.process(frame)
    assert info["mode"] == "night"

def test_brightness_low_light_frame():
    """Dim frame detected as low-light mode."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    frame = np.full((480, 640, 3), 50, dtype=np.uint8)
    for _ in range(5):
        _, info = proc.process(frame)
    assert info["mode"] == "night"

def test_visibility_sharp_frame():
    """Sharp high-contrast frame has high visibility."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:240, :] = 200
    frame[240:, :] = 50
    _, info = proc.process(frame)
    assert info["visibility"] > 0.3

def test_mode_stability():
    """Mode doesn't flicker with single outlier frame."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    bright = np.random.RandomState(42).randint(180, 220, (480, 640, 3), dtype=np.uint8)
    for _ in range(10):
        _, info = proc.process(bright)
    assert info["mode"] == "normal"

    dark = np.full((480, 640, 3), 10, dtype=np.uint8)
    _, info = proc.process(dark)
    assert info["mode"] == "normal"

def test_force_mode_overrides():
    """Force mode parameter bypasses estimation."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    bright = np.full((480, 640, 3), 200, dtype=np.uint8)
    _, info = proc.process(bright, force_mode="night")
    assert info["mode"] == "night"

def test_night_preprocessing_enhances_dark_frame():
    """Night preprocessing brightens a dark frame."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    dark = np.full((480, 640, 3), 20, dtype=np.uint8)
    processed, _ = proc.process(dark, force_mode="night")
    assert processed.mean() > dark.mean()
