"""
Bounding box + track ID rendering and MJPEG HTTP server.
"""
import cv2
import numpy as np
import time
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

COLOR_PERSON = (0, 255, 0)
COLOR_VEHICLE = (255, 128, 0)
COLOR_TEXT_BG = (0, 0, 0)
COLOR_TEXT_FG = (255, 255, 255)


class _MJPEGHandler(BaseHTTPRequestHandler):

    def __init__(self, *args, visualizer=None, **kwargs):
        self._visualizer = visualizer
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == "/stream":
            self._serve_stream()
        elif self.path == "/snapshot":
            self._serve_snapshot()
        else:
            self.send_error(404)

    def _serve_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        while True:
            frame = self._visualizer._last_annotated
            if frame is None:
                time.sleep(0.05)
                continue

            ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                continue

            self.wfile.write(b"--frame\r\n")
            self.wfile.write(b"Content-Type: image/jpeg\r\n\r\n")
            self.wfile.write(jpeg.tobytes())
            self.wfile.write(b"\r\n")

            try:
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                break

            time.sleep(0.033)

    def _serve_snapshot(self):
        frame = self._visualizer._last_annotated
        if frame is None:
            self.send_error(503, "No frame available")
            return

        ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ret:
            self.send_error(500, "JPEG encode failed")
            return

        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpeg.tobytes())))
        self.end_headers()
        self.wfile.write(jpeg.tobytes())

    def log_message(self, format, *args):
        pass


class Visualizer:
    """Renders annotations on frames and serves MJPEG stream."""

    def __init__(self, camera_id: str, port: int, enabled: bool = True):
        self.camera_id = camera_id
        self.port = port
        self.enabled = enabled
        self._last_annotated: Optional[np.ndarray] = None
        self._http_server: Optional[HTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None
        self._fps_counter = 0
        self._fps_time = time.time()
        self._current_fps = 0.0
        self._window_name = f"{camera_id} — Track View"

        if enabled:
            self._start_http_server()

    def _start_http_server(self):
        def handler(*args, **kwargs):
            _MJPEGHandler(*args, visualizer=self, **kwargs)

        try:
            self._http_server = HTTPServer(("0.0.0.0", self.port), handler)
            self._http_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
            self._http_thread.start()
            logger.info(f"MJPEG server started on port {self.port}")
        except OSError as e:
            logger.warning(f"Could not start MJPEG server on port {self.port}: {e}")
            self._http_server = None

    def render(self, frame: np.ndarray, tracks: List, mode_info: Dict):
        annotated = frame.copy()

        for track in tracks:
            x1, y1, x2, y2 = [int(v) for v in track.bbox]
            color = COLOR_PERSON if track.class_name == "person" else COLOR_VEHICLE

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            label = f"#{track.track_id} {track.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 4, y1), COLOR_TEXT_BG, -1)
            cv2.putText(annotated, label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXT_FG, 1)

        self._fps_counter += 1
        now = time.time()
        if now - self._fps_time >= 1.0:
            self._current_fps = self._fps_counter / (now - self._fps_time)
            self._fps_counter = 0
            self._fps_time = now

        cv2.putText(
            annotated,
            f"FPS: {self._current_fps:.1f}",
            (annotated.shape[1] - 120, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            COLOR_TEXT_FG,
            2,
        )

        mode = mode_info.get("mode", "normal")
        if mode == "night":
            cv2.putText(annotated, "[NIGHT MODE]", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        elif mode == "hazy":
            cv2.putText(annotated, "[LOW VISIBILITY]", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        self._last_annotated = annotated

        if self.enabled:
            try:
                cv2.imshow(self._window_name, annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    return False
            except cv2.error:
                pass

        return True

    def shutdown(self):
        if self._http_server:
            self._http_server.shutdown()
        if self.enabled:
            try:
                cv2.destroyWindow(self._window_name)
            except cv2.error:
                pass
