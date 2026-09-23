import urllib.request, urllib.error, json

def post_json(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return True, resp.read().decode()
    except urllib.error.HTTPError as e:
        # Follow 307 redirect
        if e.code == 307:
            loc = e.headers.get("Location", "")
            req2 = urllib.request.Request(loc, data=body, headers={"Content-Type": "application/json"}, method="POST")
            resp = urllib.request.urlopen(req2, timeout=10)
            return True, resp.read().decode()
        return False, e.read().decode()

cameras = [
    {"camera_id": "cam1", "name": "Front Gate", "source_type": "rtsp", "rtsp_url": "rtsp://127.0.0.1:8554/cam1", "location": "Main entrance", "zone": "perimeter", "is_active": True},
    {"camera_id": "cam2", "name": "Parking Lot", "source_type": "rtsp", "rtsp_url": "rtsp://127.0.0.1:8554/cam2", "location": "Parking area", "zone": "perimeter", "is_active": True},
    {"camera_id": "cam3", "name": "Back Door", "source_type": "rtsp", "rtsp_url": "rtsp://127.0.0.1:8554/cam3", "location": "Rear exit", "zone": "entry", "is_active": True},
]

for cam in cameras:
    ok, msg = post_json("http://127.0.0.1:8000/api/v1/cameras", cam)
    tag = "[OK]" if ok else "[FAIL]"
    print(f"{tag} Camera {cam['camera_id']}: {msg[:150]}")

rois = [
    {"name": "Restricted Zone", "polygon": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]], "camera_id": "cam1", "zone": "restricted"},
    {"name": "Entry Perimeter", "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], "camera_id": "cam2", "zone": "perimeter"},
    {"name": "Exit Lane", "polygon": [[0.3, 0.0], [0.7, 0.0], [0.7, 1.0], [0.3, 1.0]], "camera_id": "cam3", "zone": "entry"},
]

for roi in rois:
    ok, msg = post_json("http://127.0.0.1:8000/api/v1/rois", roi)
    tag = "[OK]" if ok else "[FAIL]"
    print(f"{tag} ROI {roi['name']}: {msg[:150]}")

print("\nSeed complete!")
