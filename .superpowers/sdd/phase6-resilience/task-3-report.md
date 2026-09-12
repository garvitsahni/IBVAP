# Task 3 Report: Two-Tier Model Fallback + Motion Detection

## Status: DONE

## Summary

Implemented two-tier model fallback system with motion detection fallback as specified in the task brief.

## Files Created/Modified

1. **Created:** `fusion_server/services/detector_fallback.py` - DetectorFallback class that monitors inference load and switches model tiers based on latency, queue depth, and error rate metrics
2. **Modified:** `edge/detector.py` - Added `motion_detection()` function for frame-difference motion detection and `set_model()` method to DetectionService class
3. **Created:** `tests/test_detector_fallback.py` - 9 tests covering fallback tier switching and motion detection

## Implementation Details

### DetectorFallback (fusion_server/services/detector_fallback.py)
- Three tiers: normal, degraded, critical
- Switches to degraded when latency >200ms or queue depth >10
- Switches to critical when latency >500ms, queue depth >30, or error rate >10%
- Recovery mechanism returns to normal when metrics improve
- Supports tier change callbacks for system integration

### Motion Detection (edge/detector.py)
- Frame-difference motion detection using OpenCV
- Converts frames to grayscale, computes absolute difference
- Thresholds and finds contours, filters by minimum area
- Returns bounding boxes with confidence scores

### Set Model (edge/detector.py)
- Added `set_model()` method to DetectionService class
- Allows dynamic switching of YOLO model weights

## Test Results

All 9 new tests pass:
- 7 tests for DetectorFallback tier switching logic
- 2 tests for motion detection functionality

Note: 6 pre-existing test failures exist in the codebase due to a corrupted `yolov8n.pt` model file (PytorchStreamReader error). These are unrelated to this task's changes.

## Commits Created

- `f7947fd` - "feat: add two-tier model fallback with motion detection"

## Concerns

None. Implementation follows the task brief exactly and all tests pass.