import urllib.request, json, time

print("Checking pipeline status...")
for i in range(6):
    try:
        r = urllib.request.urlopen("http://localhost:8000/api/v1/events/")
        data = json.load(r)
        print(f"  Events so far: {len(data)}")
        for e in data[:5]:
            print(f"    {e['event_type']} on {e['camera_id']}")
        break
    except Exception as ex:
        print(f"  Waiting... ({i}) {ex}")
        time.sleep(5)

print("\nCamera statuses:")
try:
    r = urllib.request.urlopen("http://localhost:8000/api/v1/cameras/")
    for c in json.load(r):
        print(f"  {c['camera_id']}: {c['status']} (last_seen: {c['last_seen']})")
except Exception as ex:
    print(f"  Error: {ex}")
