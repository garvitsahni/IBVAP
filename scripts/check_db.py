import sqlite3
conn = sqlite3.connect('ibvap.db')
cursor = conn.execute("SELECT sql FROM sqlite_master WHERE name='detection_events'")
print(cursor.fetchone()[0])
print()
cursor = conn.execute("PRAGMA table_info(detection_events)")
for row in cursor.fetchall():
    print(row)
conn.close()
