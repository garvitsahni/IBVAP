"""
Entry point: start the shared detection service.

Usage:
    python -m edge.run_detection_service
"""
import multiprocessing
import logging
import signal
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("detector")


def main():
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()

    from edge.detector import DetectionService
    svc = DetectionService(req_queue, res_queue)

    def shutdown(signum, frame):
        logger.info("Shutdown signal received")
        req_queue.put(None)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Detection service starting...")
    logger.info(f"Request queue: {req_queue}")
    logger.info(f"Result queue: {res_queue}")

    svc.run()


if __name__ == "__main__":
    main()
