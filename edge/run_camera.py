"""
Entry point: start a single camera worker.

Usage:
    python -m edge.run_camera --camera-url rtsp://127.0.0.1:8554/cam1 --camera-id cam1
"""
import argparse
import multiprocessing
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


def parse_args():
    parser = argparse.ArgumentParser(description="IBVAP Camera Worker")
    parser.add_argument("--camera-url", required=True, help="RTSP stream URL")
    parser.add_argument("--camera-id", required=True, help="Camera identifier")
    parser.add_argument("--fusion-server", default="http://127.0.0.1:8000", help="Fusion server URL (use 127.0.0.1, not localhost — IPv6 loopback is dropped on this host)")
    parser.add_argument("--target-fps", type=int, default=10, help="Target FPS")
    parser.add_argument("--display", action="store_true", default=True, help="Enable cv2 display")
    parser.add_argument("--no-display", dest="display", action="store_false", help="Disable cv2 display")
    parser.add_argument("--night-mode", action="store_true", help="Force night mode")
    parser.add_argument("--haze-mode", action="store_true", help="Force haze mode")
    parser.add_argument("--mjpeg-port", type=int, default=8081, help="MJPEG server port")
    parser.add_argument("--enable-face", action="store_true", help="Enable face detection + embedding")
    parser.add_argument("--enable-plate", action="store_true", help="Enable plate detection + OCR")
    return parser.parse_args()


def main():
    args = parse_args()

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    reid_req_queue = multiprocessing.Queue()
    reid_res_queue = multiprocessing.Queue()

    force_mode = None
    if args.night_mode:
        force_mode = "night"
    elif args.haze_mode:
        force_mode = "hazy"

    # Face sub-services (optional)
    face_det_req_queue = multiprocessing.Queue() if args.enable_face else None
    face_det_res_queue = multiprocessing.Queue() if args.enable_face else None
    face_emb_req_queue = multiprocessing.Queue() if args.enable_face else None
    face_emb_res_queue = multiprocessing.Queue() if args.enable_face else None
    if args.enable_face:
        from edge.face_detector import FaceDetectorService
        face_det_svc = FaceDetectorService(face_det_req_queue, face_det_res_queue)
        multiprocessing.Process(target=face_det_svc.run, daemon=True).start()
        from edge.face_embedding import FaceEmbeddingService
        face_emb_svc = FaceEmbeddingService(face_emb_req_queue, face_emb_res_queue)
        multiprocessing.Process(target=face_emb_svc.run, daemon=True).start()

    # Plate sub-services (optional)
    plate_det_req_queue = multiprocessing.Queue() if args.enable_plate else None
    plate_det_res_queue = multiprocessing.Queue() if args.enable_plate else None
    plate_ocr_req_queue = multiprocessing.Queue() if args.enable_plate else None
    plate_ocr_res_queue = multiprocessing.Queue() if args.enable_plate else None
    if args.enable_plate:
        from edge.plate_detector import PlateDetectorService
        plate_det_svc = PlateDetectorService(plate_det_req_queue, plate_det_res_queue)
        multiprocessing.Process(target=plate_det_svc.run, daemon=True).start()
        from edge.plate_ocr import PlateOCRService
        plate_ocr_svc = PlateOCRService(plate_ocr_req_queue, plate_ocr_res_queue)
        multiprocessing.Process(target=plate_ocr_svc.run, daemon=True).start()

    from edge.camera_worker import CameraWorker
    worker = CameraWorker(
        camera_url=args.camera_url,
        camera_id=args.camera_id,
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
        display=args.display,
        force_mode=force_mode,
        mjpeg_port=args.mjpeg_port,
    )
    worker.run()


if __name__ == "__main__":
    main()
