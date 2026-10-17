"""
C.P.S. Local Storage & Persistence Engine
==========================================
Manages local SQLite database for:
  - Security audit scan records
  - Interactive coding chat history
  - Persistent user and runtime settings

Includes automatic corruption recovery: if the SQLite database is damaged
or unreadable, it is backed up to a timestamped file and a clean database
is initialized without crashing the application.
"""
import json
import logging
import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import config

logger = logging.getLogger("cps.storage")

DB_FILENAME = "history.db"


def _get_db_path() -> Path:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return config.DATA_DIR / DB_FILENAME


def _recover_corrupt_db(db_path: Path, exc: Exception) -> sqlite3.Connection:
    """Safely isolates corrupt database file and returns a clean connection."""
    timestamp = int(time.time())
    corrupt_backup = db_path.parent / f"{DB_FILENAME}.corrupt.{timestamp}"
    logger.warning("Corrupt SQLite database detected (%s). Backing up to %s", exc, corrupt_backup)
    try:
        if db_path.exists():
            shutil.copyfile(str(db_path), str(corrupt_backup))
            db_path.unlink()
    except Exception as move_err:
        logger.error("Failed to move corrupt database file: %s", move_err)
        try:
            db_path.write_bytes(b"")
        except Exception:
            pass

    conn = sqlite3.connect(str(db_path))
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    """Initializes tables for scans, chat history, and settings."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            files INT,
            findings INT,
            severity TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            role TEXT,
            content TEXT,
            action TEXT,
            model TEXT,
            provider TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()


def _db() -> sqlite3.Connection:
    """Connects to SQLite database with automatic corruption detection and recovery."""
    db_path = _get_db_path()
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA schema_version")
        _init_schema(conn)
        return conn
    except sqlite3.DatabaseError as exc:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        import gc
        gc.collect()
        return _recover_corrupt_db(db_path, exc)


# ---------------------------------------------------------------------------
# Scans Storage
# ---------------------------------------------------------------------------

def save_scan(files: int, findings: int, severity_counts: Any) -> int:
    """Saves scan summary metadata; source code and secrets are never stored."""
    with _db() as c:
        cur = c.cursor()
        sev_str = json.dumps(severity_counts) if not isinstance(severity_counts, str) else severity_counts
        cur.execute(
            "INSERT INTO scans(ts, files, findings, severity) VALUES(?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), files, findings, sev_str),
        )
        return cur.lastrowid or 0


def list_scans(limit: int = 50) -> List[Tuple[Any, ...]]:
    """Retrieves recent scan records in descending order."""
    with _db() as c:
        return c.execute(
            "SELECT ts, files, findings, severity FROM scans ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()


def clear_history():
    """Clears all recorded scans."""
    with _db() as c:
        c.execute("DELETE FROM scans")


# ---------------------------------------------------------------------------
# Chat History Storage
# ---------------------------------------------------------------------------

def save_chat_message(
    role: str,
    content: str,
    action: str = "chat",
    model: str = "",
    provider: str = ""
) -> int:
    """Stores a chat message for conversation persistence."""
    with _db() as c:
        cur = c.cursor()
        cur.execute(
            """
            INSERT INTO chat_history (ts, role, content, action, model, provider)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (datetime.now(timezone.utc).isoformat(), role, content, action, model, provider)
        )
        return cur.lastrowid or 0


def list_chat_history(limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieves chat messages in chronological order."""
    with _db() as c:
        rows = c.execute(
            """
            SELECT id, ts, role, content, action, model, provider
            FROM chat_history
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        return [
            {
                "id": r[0],
                "ts": r[1],
                "role": r[2],
                "content": r[3],
                "action": r[4],
                "model": r[5],
                "provider": r[6],
            }
            for r in rows
        ]


def clear_chat_history():
    """Clears all saved chat history messages."""
    with _db() as c:
        c.execute("DELETE FROM chat_history")


# ---------------------------------------------------------------------------
# Settings Storage
# ---------------------------------------------------------------------------

def save_setting(key: str, value: Any):
    """Saves a setting value serialized as JSON."""
    val_str = json.dumps(value)
    now = datetime.now(timezone.utc).isoformat()
    with _db() as c:
        c.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, val_str, now)
        )


def get_setting(key: str, default: Any = None) -> Any:
    """Retrieves a setting by key, deserializing from JSON."""
    with _db() as c:
        row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                return row[0]
        return default


def get_all_settings() -> Dict[str, Any]:
    """Retrieves all stored settings as a dictionary."""
    with _db() as c:
        rows = c.execute("SELECT key, value FROM settings").fetchall()
        out = {}
        for k, v in rows:
            try:
                out[k] = json.loads(v)
            except Exception:
                out[k] = v
        return out


def clear_all_data():
    """Purges all user data: scans, chat history, and stored settings."""
    with _db() as c:
        c.execute("DELETE FROM scans")
        c.execute("DELETE FROM chat_history")
        c.execute("DELETE FROM settings")
