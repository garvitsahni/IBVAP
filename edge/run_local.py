#!/usr/bin/env python3
"""
Local footage edge runner — starts DetectionService + ReIDService + CameraWorker(s)
using local video files instead of RTSP.
"""
import argparse
import multiprocessing
import logging
import time
import signal
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("run_local")

LOCAL_FOOTAGE = {
    "cam1": "footage/cam1.mp4",
    "cam2": "footage/cam2.mp4",
    "cam3": "footage/cam3.mp4",
}


def parse_args():
    parser = argparse.ArgumentParser(description="IBVAP Edge Pipeline — Local Footage")
    parser.add_argument("--cameras", default="cam1", help="Comma-separated camera IDs")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="CAMERA_ID:SRC",
        help="Override source for a camera, e.g. laptop-webcam:0 (webcam device index) or cam1:rtsp://...; repeatable. Default: footage/<camera_id>.mp4",
    )
    parser.add_argument("--fusion-server", default="http://127.0.0.1:8000", help="Fusion server URL")
    parser.add_argument("--target-fps", type=int, default=10, help="Target FPS per camera")
    parser.add_argument("--no-display", action="store_true", help="Disable cv2 display")
    parser.add_argument("--enable-face", action="store_true", help="Enable face detection + embedding")
    parser.add_argument("--enable-plate", action="store_true", help="Enable plate detection + OCR")
    return parser.parse_args()


def main():
    args = parse_args()
    camera_ids = [c.strip() for c in args.cameras.split(",")]

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    reid_req_queue = multiprocessing.Queue()
    reid_res_queue = multiprocessing.Queue()

    from edge.detector import DetectionService
    detector = DetectionService(req_queue, res_queue)
    detector_proc = multiprocessing.Process(target=detector.run, daemon=True)
    detector_proc.start()
    logger.info("Detection service started")

    from edge.reid_service import ReIDService
    reid_service = ReIDService(reid_req_queue, reid_res_queue, model_path="models/osnet_ain_x1_0.onnx")
    reid_proc = multiprocessing.Process(target=reid_service.run, daemon=True)
    reid_proc.start()
    logger.info("ReID service started")

    # Face sub-services (optional)
    face_det_req_queue = multiprocessing.Queue() if args.enable_face else None
    face_det_res_queue = multiprocessing.Queue() if args.enable_face else None
    face_emb_req_queue = multiprocessing.Queue() if args.enable_face else None
    face_emb_res_queue = multiprocessing.Queue() if args.enable_face else None
    face_procs = []
    if args.enable_face:
        from edge.face_detector import FaceDetectorService
        face_det_svc = FaceDetectorService(face_det_req_queue, face_det_res_queue)
        face_det_proc = multiprocessing.Process(target=face_det_svc.run, daemon=True)
        face_det_proc.start()
        face_procs.append(face_det_proc)
        from edge.face_embedding import FaceEmbeddingService
        face_emb_svc = FaceEmbeddingService(face_emb_req_queue, face_emb_res_queue)
        face_emb_proc = multiprocessing.Process(target=face_emb_svc.run, daemon=True)
        face_emb_proc.start()
        face_procs.append(face_emb_proc)
        logger.info("Face detection + embedding services started")

    # Plate sub-services (optional)
    plate_det_req_queue = multiprocessing.Queue() if args.enable_plate else None
    plate_det_res_queue = multiprocessing.Queue() if args.enable_plate else None
    plate_ocr_req_queue = multiprocessing.Queue() if args.enable_plate else None
    plate_ocr_res_queue = multiprocessing.Queue() if args.enable_plate else None
    plate_procs = []
    if args.enable_plate:
        from edge.plate_detector import PlateDetectorService
        plate_det_svc = PlateDetectorService(plate_det_req_queue, plate_det_res_queue)
        plate_det_proc = multiprocessing.Process(target=plate_det_svc.run, daemon=True)
        plate_det_proc.start()
        plate_procs.append(plate_det_proc)
        from edge.plate_ocr import PlateOCRService
        plate_ocr_svc = PlateOCRService(plate_ocr_req_queue, plate_ocr_res_queue)
        plate_ocr_proc = multiprocessing.Process(target=plate_ocr_svc.run, daemon=True)
        plate_ocr_proc.start()
        plate_procs.append(plate_ocr_proc)
        logger.info("Plate detection + OCR services started")

    time.sleep(3)

    from edge.camera_worker import CameraWorker
    source_overrides = {}
    for pair in args.source:
        if ":" not in pair:
            raise SystemExit(f"--source expects CAMERA_ID:SRC, got: {pair!r}")
        cam_id, src = pair.split(":", 1)
        source_overrides[cam_id.strip()] = src.strip()
    workers = []
    for i, cam_id in enumerate(camera_ids):
        url = source_overrides.get(cam_id) or LOCAL_FOOTAGE.get(cam_id, f"footage/{cam_id}.mp4")
        port = 8081 + i

        worker = CameraWorker(
            camera_url=url,
            camera_id=cam_id,
            fusion_url=args.fusion_server,
            req_queue=req_queue,
            res_queue=res_queue,
            reid_req_queue=reid_req_queue,
            reid_res_queue=reid_res_queue,
            face_det_req_queue=face_det_req_queue,
            face_det_res_queue=face_det_res_queue,
            face_emb_req_queue=face_emb_req_queue,
            face_emb_res_queue=face_emb_res_queue,
            plate_det_req_queue=plate_det_req_queue,
            plate_det_res_queue=plate_det_res_queue,
            plate_ocr_req_queue=plate_ocr_req_queue,
            plate_ocr_res_queue=plate_ocr_res_queue,
            target_fps=args.target_fps,
            display=not args.no_display,
            force_mode=None,
            mjpeg_port=port,
        )
        proc = multiprocessing.Process(target=worker.run, daemon=True)
        proc.start()
        workers.append(proc)
        logger.info(f"Camera worker {cam_id} started (MJPEG: http://localhost:{port}/stream) - source: {url}")

    def shutdown(signum, frame):
        logger.info("Shutting down...")
        req_queue.put(None)
        reid_req_queue.put(None)
        for p in workers:
            p.terminate()
        detector_proc.terminate()
        reid_proc.terminate()
        for p in face_procs:
            p.terminate()
        for p in plate_procs:
            p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        detector_proc.join()
        for p in workers:
            p.join()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()