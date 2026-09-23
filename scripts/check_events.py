import urllib.request, json

try:
    r = urllib.request.urlopen("http://localhost:8000/api/v1/events?limit=5", timeout=5)
    data = json.loads(r.read().decode())
    print(f"Events count (last 5): {len(data)}")
    for e in data:
        print(f"  id={e['id']} type={e['object_type']} cam={e['camera_id']} conf={e['confidence']:.2f}")
except Exception as ex:
    print(f"Error: {ex}")

try:
    r = urllib.request.urlopen("http://localhost:8000/api/v1/cameras", timeout=5)
    data = json.loads(r.read().decode())
    print(f"\nCameras: {len(data)}")
    for c in data:
        print(f"  {c['camera_id']}: status={c['status']} last_seen={c.get('last_seen', 'N/A')}")
except Exception as ex:
    print(f"Error: {ex}")
