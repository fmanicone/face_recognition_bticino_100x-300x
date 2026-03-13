import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "/shared_frames/faces.db")
SHARED_FRAMES = os.getenv("SHARED_FRAMES", "/shared_frames")

_ALLOWED_FIELDS = {"status", "suggested_name", "suggested_score", "assigned_name"}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    os.makedirs(SHARED_FRAMES, exist_ok=True)
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS detected_faces (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path      TEXT    NOT NULL,
            detected_at     TEXT    NOT NULL,
            session_id      TEXT    NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'pending',
            suggested_name  TEXT,
            suggested_score REAL,
            assigned_name   TEXT
        )
    """)
    conn.commit()
    conn.close()
    print(f"[collector] DB inizializzato: {DB_PATH}")


def insert_face(image_path: str, detected_at: str, session_id: str) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO detected_faces (image_path, detected_at, session_id, status) "
        "VALUES (?, ?, ?, 'pending')",
        (image_path, detected_at, session_id),
    )
    record_id = cur.lastrowid
    conn.commit()
    conn.close()
    return record_id


def update_face(record_id: int, fields: dict) -> None:
    fields = {k: v for k, v in fields.items() if k in _ALLOWED_FIELDS}
    if not fields:
        return
    set_clause = ", ".join(f"{k}=?" for k in fields)
    conn = _connect()
    conn.execute(f"UPDATE detected_faces SET {set_clause} WHERE id=?",
                 [*fields.values(), record_id])
    conn.commit()
    conn.close()


def delete_face(record_id: int, delete_file: bool = True) -> None:
    conn = _connect()
    row = conn.execute(
        "SELECT image_path FROM detected_faces WHERE id=?", (record_id,)
    ).fetchone()
    if row:
        conn.execute("DELETE FROM detected_faces WHERE id=?", (record_id,))
        conn.commit()
        if delete_file:
            try:
                os.remove(row[0])
            except OSError:
                pass
    conn.close()


def bulk_update(ids: list, fields: dict) -> None:
    fields = {k: v for k, v in fields.items() if k in _ALLOWED_FIELDS}
    if not fields or not ids:
        return
    set_clause = ", ".join(f"{k}=?" for k in fields)
    placeholders = ",".join("?" * len(ids))
    conn = _connect()
    conn.execute(
        f"UPDATE detected_faces SET {set_clause} WHERE id IN ({placeholders})",
        [*fields.values(), *ids],
    )
    conn.commit()
    conn.close()


def bulk_delete(ids: list, delete_files: bool = True) -> None:
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    conn = _connect()
    rows = conn.execute(
        f"SELECT image_path FROM detected_faces WHERE id IN ({placeholders})", ids
    ).fetchall()
    conn.execute(f"DELETE FROM detected_faces WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()
    if delete_files:
        for row in rows:
            try:
                os.remove(row[0])
            except OSError:
                pass
