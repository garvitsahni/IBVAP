"""
Per-camera processing pipeline: ingest -> preprocess -> detect -> track -> publish -> visualize.
"""
import time
import logging
import multiprocessing
from typing import Optional

import numpy as np

from edge.ingestion import RTSPIngestion
from edge.night_weather import NightWeatherProcessor
from edge.tracker import Tracker
from edge.event_publisher import EventPublisher
from edge.visualizer import Visualizer

logger = logging.getLogger(__name__)


class CameraWorker:
    """
    Per-camera pipeline orchestrator.

    Reads frames from RTSP, preprocesses (night/weather), sends to
    DetectionService for inference, tracks objects, publishes events,
    and renders live visualization.
    """

    def __init__(
        self,
        camera_url: str,
        camera_id: str,
        fusion_url: str,
        req_queue: multiprocessing.Queue,
        res_queue: multiprocessing.Queue,
        reid_req_queue: multiprocessing.Queue,
        reid_res_queue: multiprocessing.Queue,
        target_fps: int = 10,
        display: bool = True,
        force_mode: Optional[str] = None,
        mjpeg_port: int = 8081,
    ):
        self.camera_url = camera_url
        self.camera_id = camera_id
        self.target_fps = target_fps
        self.force_mode = force_mode

        self.ingestion = RTSPIngestion(camera_url)
        self.night_weather = NightWeatherProcessor()
        self.tracker = Tracker()
        self.publisher = EventPublisher(fusion_url)
        self.visualizer = Visualizer(camera_id, mjpeg_port, enabled=display)

        self.req_queue = req_queue
        self.res_queue = res_queue
        self.reid_req_queue = reid_req_queue
        self.reid_res_queue = reid_res_queue
        self._frame_id = 0

    def _crop_detection(self, frame: np.ndarray, detection: dict) -> np.ndarray:
        """Crop bounding box from frame."""
        x1, y1, x2, y2 = detection["bbox"]
        h, w = frame.shape[:2]
        x1_int = max(0, int(x1))
        y1_int = max(0, int(y1))
        x2_int = min(w, int(x2))
        y2_int = min(h, int(y2))
        return frame[y1_int:y2_int, x1_int:x2_int].copy()

    def run(self):
        logger.info(f"Camera worker {self.camera_id} starting ({self.camera_url})")

        if not self.ingestion.connect():
            logger.error(f"Camera {self.camera_id}: Cannot connect to {self.camera_url}")
            return

        frame_interval = 1.0 / self.target_fps

        while True:
            loop_start = time.time()

            result = self.ingestion.grab_frame()
            if result is None:
                logger.warning(f"Camera {self.camera_id}: No frame, retrying...")
                time.sleep(0.5)
                continue

            timestamp, frame = result
            h, w = frame.shape[:2]
            self._frame_id += 1

            processed_frame, mode_info = self.night_weather.process(frame, self.force_mode)

            self.req_queue.put((self._frame_id, self.camera_id, processed_frame))

            detections = None
            deadline = time.time() + 0.5
            while time.time() < deadline:
                try:
                    fid, cid, dets = self.res_queue.get(timeout=0.1)
                    if cid == self.camera_id and fid == self._frame_id:
                        detections = dets
                        break
                    self.res_queue.put((fid, cid, dets))
                except Exception:
                    continue

            if detections is None:
                detections = []

            tracks = self.tracker.update(detections, (h, w))

            # Send crops to ReID service
            for track in tracks:
                crop = self._crop_detection(frame, {"bbox": track.bbox})
                object_type = "person" if track.class_name == "person" else "vehicle"
                self.reid_req_queue.put((self._frame_id, self.camera_id, track.track_id, crop, object_type))

            # Collect ReID embeddings (with timeout)
            reid_embeddings = {}
            for _ in range(len(tracks)):
                try:
                    fid, cid, tid, embedding, obj_type = self.reid_res_queue.get(timeout=0.2)
                    if cid == self.camera_id:
                        reid_embeddings[(fid, tid)] = embedding
                except Exception:
                    continue

            # Publish events with embeddings
            ts_iso = timestamp.isoformat() + "Z"
            for track in tracks:
                object_type = "person" if track.class_name == "person" else "vehicle"
                embedding = reid_embeddings.get((self._frame_id, track.track_id))
                event = self.publisher.build_event(
                    camera_id=self.camera_id,
                    timestamp=ts_iso,
                    object_type=object_type,
                    track_id=str(track.track_id),
                    bbox_pixels=track.bbox,
                    frame_shape=(h, w),
                    confidence=track.confidence,
                    embedding=embedding,
                )
                self.publisher.publish(event)

            if not self.visualizer.render(frame, tracks, mode_info):
                logger.info(f"Camera {self.camera_id}: Quit signal received")
                break

            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.ingestion.release()
        self.visualizer.shutdown()
        logger.info(f"Camera worker {self.camera_id} stopped")
