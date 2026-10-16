import json, sqlite3
from datetime import datetime, timezone
from . import config

def _db():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DATA_DIR / "history.db")
    c.execute("CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY, ts TEXT, files INT, findings INT, severity TEXT)")
    return c

def save_scan(files, findings, severity_counts):
    with _db() as c:  # no source code or secrets stored
        c.execute("INSERT INTO scans(ts,files,findings,severity) VALUES(?,?,?,?)",
                  (datetime.now(timezone.utc).isoformat(), files, findings, json.dumps(severity_counts)))

def list_scans():
    with _db() as c:
        return c.execute("SELECT ts,files,findings,severity FROM scans ORDER BY id DESC LIMIT 50").fetchall()

def clear_history():
    with _db() as c:
        c.execute("DELETE FROM scans")
