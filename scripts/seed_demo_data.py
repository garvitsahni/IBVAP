#!/usr/bin/env python3
"""
Seed demo data into the IBVAP fusion server.
Creates cameras, ROIs, and watchlist entries for demo purposes.
"""
import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"


def wait_for_server(timeout=30):
    """Wait for fusion server to be ready."""
    print("Waiting for fusion server...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                print("  Server is ready")
                return True
        except Exception:
            pass
        time.sleep(1)
    print("  Server not reachable")
    return False


def seed_cameras():
    """Register demo cameras."""
    cameras = [
        {"camera_id": "cam1", "name": "North Gate", "source_type": "rtsp",
         "rtsp_url": "rtsp://127.0.0.1:8554/cam1", "location": "North Entrance", "zone": "A"},
        {"camera_id": "cam2", "name": "Watch Tower A", "source_type": "rtsp",
         "rtsp_url": "rtsp://127.0.0.1:8554/cam2", "location": "Tower A", "zone": "B"},
        {"camera_id": "cam3", "name": "East Fence", "source_type": "rtsp",
         "rtsp_url": "rtsp://127.0.0.1:8554/cam3", "location": "East Perimeter", "zone": "C"},
    ]

    print("Seeding cameras...")
    for cam in cameras:
        try:
            r = requests.post(f"{BASE_URL}/api/v1/cameras", json=cam, timeout=5)
            if r.status_code in (200, 201):
                print(f"  + {cam['camera_id']}: {cam['name']}")
            elif r.status_code == 409:
                print(f"  = {cam['camera_id']}: already exists")
            else:
                print(f"  ! {cam['camera_id']}: {r.status_code} {r.text[:100]}")
        except Exception as e:
            print(f"  ! {cam['camera_id']}: {e}")


def seed_rois():
    """Create demo ROIs (regions of interest / virtual fences)."""
    rois = [
        {
            "roi_id": "roi-perimeter-north",
            "name": "North Perimeter",
            "camera_id": "cam1",
            "polygon": [[100, 100], [500, 100], [500, 400], [100, 400]],
            "alert_on_crossing": True,
        },
        {
            "roi_id": "roi-gate-entry",
            "name": "Gate Entry Zone",
            "camera_id": "cam1",
            "polygon": [[200, 200], [400, 200], [400, 350], [200, 350]],
            "alert_on_crossing": True,
        },
        {
            "roi_id": "roi-tower-view",
            "name": "Tower Viewshed",
            "camera_id": "cam2",
            "polygon": [[50, 50], [590, 50], [590, 430], [50, 430]],
            "alert_on_crossing": False,
        },
    ]

    print("Seeding ROIs...")
    for roi in rois:
        try:
            r = requests.post(f"{BASE_URL}/api/v1/rois", json=roi, timeout=5)
            if r.status_code in (200, 201):
                print(f"  + {roi['roi_id']}: {roi['name']}")
            elif r.status_code == 409:
                print(f"  = {roi['roi_id']}: already exists")
            else:
                print(f"  ! {roi['roi_id']}: {r.status_code} {r.text[:100]}")
        except Exception as e:
            print(f"  ! {roi['roi_id']}: {e}")


def seed_watchlist():
    """Create demo watchlist entries (face + plate)."""
    import numpy as np

    entries = [
        {
            "watchlist_type": "face",
            "reference_id": "person-of-interest-1",
            "embedding": np.random.randn(512).tolist(),
            "metadata": {"name": "Unknown Subject Alpha", " threat_level": "high"},
        },
        {
            "watchlist_type": "plate",
            "reference_id": "plate-blacklist-1",
            "embedding": np.random.randn(512).tolist(),
            "metadata": {"plate_text": "DL 01 AB 1234", "reason": "stolen vehicle report"},
        },
    ]

    print("Seeding watchlist...")
    for entry in entries:
        try:
            r = requests.post(f"{BASE_URL}/api/v1/watchlist", json=entry, timeout=5)
            if r.status_code in (200, 201):
                print(f"  + {entry['watchlist_type']}: {entry['reference_id']}")
            else:
                print(f"  ! {entry['reference_id']}: {r.status_code} {r.text[:100]}")
        except Exception as e:
            print(f"  ! {entry['reference_id']}: {e}")


def main():
    print("=" * 50)
    print("IBVAP Demo Data Seeder")
    print("=" * 50)

    if not wait_for_server():
        print("Start the fusion server first: python -m fusion_server.main")
        sys.exit(1)

    seed_cameras()
    seed_rois()
    seed_watchlist()

    print("\nDone! Demo data seeded.")


if __name__ == "__main__":
    main()
