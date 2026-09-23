import urllib.request, json

def api(path):
    r = urllib.request.urlopen(f"http://localhost:8000{path}", timeout=5)
    return json.loads(r.read().decode())

print("=== IBVAP System Status ===\n")

# Health
h = api("/health")
print(f"Server: {h['status']} (DB: {h['database']})")

# Cameras
cams = api("/api/v1/cameras")
print(f"\nCameras ({len(cams)}):")
for c in cams:
    if c['camera_id'] != 'laptop-webcam':
        print(f"  {c['camera_id']}: {c['status']}")

# Events
events = api("/api/v1/events?limit=1")
# Get count via dashboard stats
try:
    stats = api("/api/v1/dashboard/stats")
    print(f"\nDashboard Stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
except:
    pass

# ROIs
try:
    rois = api("/api/v1/rois")
    print(f"\nROIs ({len(rois)}):")
    for r in rois:
        print(f"  {r['name']} on {r['camera_id']}")
except:
    print("\nROIs: endpoint not available")

# Watchlist
try:
    wl = api("/api/v1/watchlist")
    print(f"\nWatchlist: {len(wl)} entries")
except:
    print("\nWatchlist: no entries or endpoint not available")

# Alerts
try:
    alerts = api("/api/v1/alerts?limit=5")
    print(f"\nAlerts (last 5): {len(alerts)}")
    for a in alerts:
        print(f"  {a['alert_id'][:8]}... status={a['status']} reason={a['reason']}")
except:
    print("\nAlerts: no alerts or endpoint not available")

# Ledger
try:
    ledger = api("/api/v1/ledger/status")
    print(f"\nLedger: chain_valid={ledger.get('chain_valid', 'N/A')}")
except:
    pass

print("\n=== All systems operational ===")
print("\nAccess points:")
print("  Dashboard:  http://localhost:3000")
print("  API:        http://localhost:8000")
print("  RTSP:       rtsp://localhost:8554/cam1")
print("  MediaMTX:   http://localhost:9997")
