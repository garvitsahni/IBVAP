# Task 6: Power Manager — Report

**Status:** DONE

## Summary

Implemented `PowerManager` class that monitors CPU/memory via psutil and switches between three power modes: `normal`, `reduced`, and `critical`.

## Files Created/Modified

- `fusion_server/services/power_manager.py` — new module
- `tests/test_power_manager.py` — new test file (6 tests)
- `requirements.txt` — added `psutil>=5.9.0`

## Test Results

**6/6 passed**

| Test | Description |
|------|-------------|
| `test_power_manager_initializes_normal` | Starts in normal mode |
| `test_power_manager_switches_to_reduced` | CPU > 80% triggers reduced mode |
| `test_power_manager_switches_to_critical` | CPU > 95% or mem < 10% free triggers critical |
| `test_power_manager_recovers` | 6 consecutive low-load checks recover to normal |
| `test_camera_priority_by_roi_area` | Lowest ROI cameras are dropped first |
| `test_mode_callback` | Mode change fires callback with (old, new, reason) |

## Mode Behavior

| Mode | Condition | Action |
|------|-----------|--------|
| normal | CPU < 80%, free mem > 20% | Full operation |
| reduced | CPU 80-95%, free mem 10-20% | Drop cameras with smallest ROI area |
| critical | CPU > 95%, free mem < 10% | Detection runs at reduced FPS |

Recovery requires 6 consecutive checks with CPU < 60% and free mem > 20%.

## Commit

`17fb0c9` — `feat: add PowerManager with tiered throttle modes`
