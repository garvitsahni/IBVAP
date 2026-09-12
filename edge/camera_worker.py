"""
Per-camera processing pipeline: ingest -> preprocess -> detect -> track -> publish -> visualize.
"""
import time
import logging
import multiprocessing
from typing import Optional, Dict

import numpy as np

from edge.ingestion import RTSPIngestion
from edge.night_weather import NightWeatherProcessor
from edge.tracker import Tracker
from edge.event_publisher import EventPublisher
from edge.visualizer import Visualizer
from edge.camera_health import CameraHealthService
from edge.detector import SWITCH_MODEL

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
        face_det_req_queue: multiprocessing.Queue = None,
        face_det_res_queue: multiprocessing.Queue = None,
        face_emb_req_queue: multiprocessing.Queue = None,
        face_emb_res_queue: multiprocessing.Queue = None,
        plate_det_req_queue: multiprocessing.Queue = None,
        plate_det_res_queue: multiprocessing.Queue = None,
        plate_ocr_req_queue: multiprocessing.Queue = None,
        plate_ocr_res_queue: multiprocessing.Queue = None,
        target_fps: int = 10,
        display: bool = True,
        force_mode: Optional[str] = None,
        mjpeg_port: int = 8081,
        health_check_interval: int = 30,
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

        self.face_det_req_queue = face_det_req_queue
        self.face_det_res_queue = face_det_res_queue
        self.face_emb_req_queue = face_emb_req_queue
        self.face_emb_res_queue = face_emb_res_queue
        self._face_available = all(q is not None for q in [
            face_det_req_queue, face_det_res_queue,
            face_emb_req_queue, face_emb_res_queue,
        ])

        self.plate_det_req_queue = plate_det_req_queue
        self.plate_det_res_queue = plate_det_res_queue
        self.plate_ocr_req_queue = plate_ocr_req_queue
        self.plate_ocr_res_queue = plate_ocr_res_queue
        self._plate_available = all(q is not None for q in [
            plate_det_req_queue, plate_det_res_queue,
            plate_ocr_req_queue, plate_ocr_res_queue,
        ])

        # Night mode model switching
        self._current_mode = "normal"
        self._night_model_paths: Dict[str, str] = {
            "normal": "yolov8n.pt",
            "night": "yolov8n_night.pt",
            "hazy": "yolov8n.pt",
        }

        self._frame_id = 0

        self.health_check_interval = health_check_interval
        self._health_service = CameraHealthService(camera_id)
        self._prev_frame = None
        self._frame_count = 0

    def _crop_detection(self, frame: np.ndarray, detection: dict) -> np.ndarray:
        """Crop bounding box from frame."""
        x1, y1, x2, y2 = detection["bbox"]
        h, w = frame.shape[:2]
        x1_int = max(0, int(x1))
        y1_int = max(0, int(y1))
        x2_int = min(w, int(x2))
        y2_int = min(h, int(y2))
        return frame[y1_int:y2_int, x1_int:x2_int].copy()

    def _check_health(self, frame: np.ndarray):
        """Run camera health checks and publish status to fusion server."""
        import requests

        if self._health_service._reference_frame is None:
            self._health_service.set_reference_frame(frame)

        darkness = self._health_service.check_darkness(frame)
        blur = self._health_service.check_blur(frame)

        frozen_result = {"status": "ok", "metric": 0.0}
        if self._prev_frame is not None:
            frozen_result = self._health_service.check_frozen(self._prev_frame, frame)

        statuses = [darkness["status"], blur["status"], frozen_result["status"]]
        if "blinding" in statuses:
            overall = "blinding"
        elif "obscured" in statuses:
            overall = "obscured"
        elif "frozen" in statuses:
            overall = "frozen"
        else:
            overall = "ok"

        try:
            requests.post(
                f"{self.publisher.fusion_url}/api/v1/cameras/{self.camera_id}/health",
                json={
                    "status": overall,
                    "ssim": 0.0,
                    "metric": darkness["metric"],
                },
                timeout=1.0,
            )
        except Exception as e:
            logger.debug(f"Health publish failed: {e}")

        self._prev_frame = frame.copy()

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

            # Detect mode change and switch detection model
            new_mode = mode_info["mode"]
            if new_mode != self._current_mode:
                self._current_mode = new_mode
                model_path = self._night_model_paths.get(new_mode, "yolov8n.pt")
                try:
                    self.req_queue.put((SWITCH_MODEL, model_path))
                    logger.info(f"Camera {self.camera_id}: Mode changed to {new_mode}, switching model to {model_path}")
                except Exception as e:
                    logger.warning(f"Failed to send SWITCH_MODEL: {e}")

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

            # Face detection + embedding for person tracks
            face_embeddings = {}
            if self._face_available:
                person_tracks = [t for t in tracks if t.class_name == "person"]
                if person_tracks:
                    # Send person crops to face detector
                    for track in person_tracks:
                        crop = self._crop_detection(frame, {"bbox": track.bbox})
                        self.face_det_req_queue.put(
                            (self._frame_id, self.camera_id, track.track_id, crop)
                        )

                    # Collect face detections
                    face_dets = {}
                    for _ in range(len(person_tracks)):
                        try:
                            fid, cid, tid, faces = self.face_det_res_queue.get(timeout=0.2)
                            if cid == self.camera_id:
                                face_dets[(fid, tid)] = faces
                        except Exception:
                            continue

                    # For each person with faces, crop largest face and send to embed
                    embed_requests = []
                    for track in person_tracks:
                        faces = face_dets.get((self._frame_id, track.track_id), [])
                        if faces:
                            # Pick the largest face by area
                            best = max(faces, key=lambda f: (f["bbox"][2] - f["bbox"][0]) * (f["bbox"][3] - f["bbox"][1]))
                            person_crop = self._crop_detection(frame, {"bbox": track.bbox})
                            fx1, fy1, fx2, fy2 = best["bbox"]
                            face_crop = person_crop[fy1:fy2, fx1:fx2]
                            if face_crop.size > 0:
                                self.face_emb_req_queue.put(
                                    (self._frame_id, self.camera_id, track.track_id, face_crop)
                                )
                                embed_requests.append(track.track_id)

                    # Collect face embeddings
                    for _ in range(len(embed_requests)):
                        try:
                            fid, cid, tid, emb = self.face_emb_res_queue.get(timeout=0.2)
                            if cid == self.camera_id:
                                face_embeddings[(fid, tid)] = emb
                        except Exception:
                            continue

            # Plate detection + OCR for vehicle tracks
            plate_texts = {}
            if self._plate_available:
                vehicle_tracks = [t for t in tracks if t.class_name in ("car", "bus", "truck", "motorcycle")]
                if vehicle_tracks:
                    # Send vehicle crops to plate detector
                    for track in vehicle_tracks:
                        crop = self._crop_detection(frame, {"bbox": track.bbox})
                        self.plate_det_req_queue.put(
                            (self._frame_id, self.camera_id, track.track_id, crop)
                        )

                    # Collect plate detections
                    plate_dets = {}
                    for _ in range(len(vehicle_tracks)):
                        try:
                            fid, cid, tid, plates = self.plate_det_res_queue.get(timeout=0.2)
                            if cid == self.camera_id:
                                plate_dets[(fid, tid)] = plates
                        except Exception:
                            continue

                    # For each vehicle with detected plate, crop plate and send to OCR
                    ocr_requests = []
                    for track in vehicle_tracks:
                        plates = plate_dets.get((self._frame_id, track.track_id), [])
                        if plates:
                            # Pick the largest plate by area
                            best_plate = max(plates, key=lambda p: (p["bbox"][2] - p["bbox"][0]) * (p["bbox"][3] - p["bbox"][1]))
                            vehicle_crop = self._crop_detection(frame, {"bbox": track.bbox})
                            px1, py1, px2, py2 = best_plate["bbox"]
                            plate_crop = vehicle_crop[py1:py2, px1:px2]
                            if plate_crop.size > 0:
                                self.plate_ocr_req_queue.put(
                                    (self._frame_id, self.camera_id, track.track_id, plate_crop)
                                )
                                ocr_requests.append(track.track_id)

                    # Collect plate OCR results
                    for _ in range(len(ocr_requests)):
                        try:
                            fid, cid, tid, text = self.plate_ocr_res_queue.get(timeout=0.2)
                            if cid == self.camera_id:
                                plate_texts[(fid, tid)] = text
                        except Exception:
                            continue

            # Publish events with embeddings
            ts_iso = timestamp.isoformat() + "Z"
            for track in tracks:
                object_type = "person" if track.class_name == "person" else "vehicle"
                embedding = reid_embeddings.get((self._frame_id, track.track_id))
                face_emb = face_embeddings.get((self._frame_id, track.track_id))
                plate_text = plate_texts.get((self._frame_id, track.track_id))
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
                if face_emb is not None:
                    event["face_embedding"] = face_emb.tolist()
                if plate_text is not None:
                    event["plate_text"] = plate_text
                self.publisher.publish(event)

            if not self.visualizer.render(frame, tracks, mode_info):
                logger.info(f"Camera {self.camera_id}: Quit signal received")
                break

            self._frame_count += 1
            if self._frame_count % self.health_check_interval == 0:
                self._check_health(processed_frame)

            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.ingestion.release()
        self.visualizer.shutdown()
        logger.info(f"Camera worker {self.camera_id} stopped")
