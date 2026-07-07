import sqlite3, os
db = "data/fixfinder.db"
try:
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    wal = db + "-wal"
    shm = db + "-shm"
    for f in (wal, shm):
        if os.path.exists(f):
            size = os.path.getsize(f)
            print(f"  {f}: {size} bytes")
        else:
            print(f"  {f}: not found")
    print("WAL checkpoint complete.")
except Exception as e:
    print(f"Error: {e}")
