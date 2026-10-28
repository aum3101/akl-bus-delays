import os, time, sqlite3, logging
import requests
from dotenv import load_dotenv

load_dotenv(override=True)
KEY = os.getenv("AT_API_KEY")
URL = "https://api.at.govt.nz/realtime/legacy/"
DB = "bus_delays.db"
POLL_SECONDS = 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

SCHEMA = """
CREATE TABLE IF NOT EXISTS trip_delays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    polled_at INTEGER,
    feed_ts INTEGER,
    trip_id TEXT,
    route_id TEXT,
    direction_id INTEGER,
    start_date TEXT,
    start_time TEXT,
    vehicle_id TEXT,
    stop_sequence INTEGER,
    stop_id TEXT,
    trip_delay INTEGER,
    stop_delay INTEGER,
    schedule_rel INTEGER,
    UNIQUE (trip_id, start_date, feed_ts)
);
CREATE INDEX IF NOT EXISTS idx_route_ts ON trip_delays (route_id, feed_ts);
"""

INSERT = """
INSERT OR IGNORE INTO trip_delays
(polled_at, feed_ts, trip_id, route_id, direction_id, start_date, start_time,
 vehicle_id, stop_sequence, stop_id, trip_delay, stop_delay, schedule_rel)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

def parse(entities, polled_at):
    rows = []
    for e in entities:
        tu = e.get("trip_update")
        if not tu:
            continue
        trip = tu.get("trip") or {}
        stu = tu.get("stop_time_update") or {}
        if isinstance(stu, list):
            stu = stu[0] if stu else {}
        ev = stu.get("arrival") or stu.get("departure") or {}
        veh = tu.get("vehicle") or {}
        rows.append((
            polled_at, tu.get("timestamp"), trip.get("trip_id"),
            trip.get("route_id"), trip.get("direction_id"),
            trip.get("start_date"), trip.get("start_time"),
            veh.get("id"), stu.get("stop_sequence"), stu.get("stop_id"),
            tu.get("delay"), ev.get("delay"), trip.get("schedule_relationship"),
        ))
    return rows

def main():
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    logging.info("Collector started. Press Ctrl+C to stop.")
    while True:
        start = time.time()
        try:
            r = requests.get(URL, headers={"Ocp-Apim-Subscription-Key": KEY}, timeout=30)
            r.raise_for_status()
            entities = (r.json().get("response") or {}).get("entity") or []
            rows = parse(entities, int(start))
            con.executemany(INSERT, rows)
            con.commit()
            logging.info("Saved %d trip updates", len(rows))
        except Exception as ex:
            logging.warning("Poll failed: %s", ex)
        time.sleep(max(1, POLL_SECONDS - (time.time() - start)))

if __name__ == "__main__":
    main()
