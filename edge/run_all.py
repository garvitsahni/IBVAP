"""
Entry point: start detection service + multiple camera workers.

Usage:
    python -m edge.run_all --cameras cam1,cam2 --fusion-server http://localhost:8000
"""
import argparse
import multiprocessing
import logging
import time
import signal
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("run_all")

DEFAULT_CAMERA_URLS = {
    "cam1": "rtsp://localhost:8554/cam1",
    "cam2": "rtsp://localhost:8554/cam2",
    "cam3": "rtsp://localhost:8554/cam3",
}


def parse_args():
    parser = argparse.ArgumentParser(description="IBVAP Edge Pipeline — All-in-One")
    parser.add_argument("--cameras", default="cam1", help="Comma-separated camera IDs")
    parser.add_argument("--fusion-server", default="http://localhost:8000", help="Fusion server URL")
    parser.add_argument("--target-fps", type=int, default=10, help="Target FPS per camera")
    parser.add_argument("--no-display", action="store_true", help="Disable cv2 display")
    parser.add_argument("--night-mode", action="store_true", help="Force night mode")
    parser.add_argument("--haze-mode", action="store_true", help="Force haze mode")
    return parser.parse_args()


def main():
    args = parse_args()
    camera_ids = [c.strip() for c in args.cameras.split(",")]

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()

    from edge.detector import DetectionService
    detector = DetectionService(req_queue, res_queue)
    detector_proc = multiprocessing.Process(target=detector.run, daemon=True)
    detector_proc.start()
    logger.info("Detection service started")

    time.sleep(3)

    force_mode = None
    if args.night_mode:
        force_mode = "night"
    elif args.haze_mode:
        force_mode = "hazy"

    from edge.camera_worker import CameraWorker
    workers = []
    for i, cam_id in enumerate(camera_ids):
        url = DEFAULT_CAMERA_URLS.get(cam_id, f"rtsp://localhost:8554/{cam_id}")
        port = 8081 + i

        worker = CameraWorker(
            camera_url=url,
            camera_id=cam_id,
            fusion_url=args.fusion_server,
            req_queue=req_queue,
            res_queue=res_queue,
            target_fps=args.target_fps,
            display=not args.no_display,
            force_mode=force_mode,
            mjpeg_port=port,
        )
        proc = multiprocessing.Process(target=worker.run, daemon=True)
        proc.start()
        workers.append(proc)
        logger.info(f"Camera worker {cam_id} started (MJPEG: http://localhost:{port}/stream)")

    def shutdown(signum, frame):
        logger.info("Shutting down...")
        req_queue.put(None)
        for p in workers:
            p.terminate()
        detector_proc.terminate()
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
