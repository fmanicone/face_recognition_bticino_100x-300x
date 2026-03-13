import math
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "/shared_frames/faces.db")
SHARED_FRAMES = os.getenv("SHARED_FRAMES", "/shared_frames")
PER_PAGE = 48


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs(SHARED_FRAMES, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            name        TEXT PRIMARY KEY,
            auto_open   INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def list_faces(status: str = "", search: str = "", page: int = 1, per_page: int = PER_PAGE):
    conditions, params = [], []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if search:
        conditions.append("(suggested_name LIKE ? OR assigned_name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * per_page

    conn = _connect()
    total = conn.execute(f"SELECT COUNT(*) FROM detected_faces {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM detected_faces {where} ORDER BY detected_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()
    conn.close()

    total_pages = max(1, math.ceil(total / per_page))
    return [dict(r) for r in rows], total, total_pages


def get_image_path(face_id: int) -> str | None:
    conn = _connect()
    row = conn.execute("SELECT image_path FROM detected_faces WHERE id = ?", (face_id,)).fetchone()
    conn.close()
    return row["image_path"] if row else None


def get_faces_for_import(ids: list) -> list:
    """Restituisce i record necessari per l'import (read-only)."""
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    conn = _connect()
    rows = conn.execute(
        f"SELECT id, image_path, assigned_name, suggested_name "
        f"FROM detected_faces WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Persons (auto_open) ─────────────────────────────────────────────────────

def list_persons() -> list:
    conn = _connect()
    rows = conn.execute("SELECT name, auto_open FROM persons ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_auto_open(name: str, auto_open: bool) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO persons (name, auto_open) VALUES (?, ?) "
        "ON CONFLICT(name) DO UPDATE SET auto_open = excluded.auto_open",
        (name, int(auto_open)),
    )
    conn.commit()
    conn.close()


def get_known_names() -> list[str]:
    """Nomi unici dalle facce importate + dalla tabella persons."""
    conn = _connect()
    names = set()
    for row in conn.execute("SELECT DISTINCT assigned_name FROM detected_faces WHERE assigned_name IS NOT NULL"):
        names.add(row[0])
    for row in conn.execute("SELECT DISTINCT suggested_name FROM detected_faces WHERE suggested_name IS NOT NULL"):
        names.add(row[0])
    for row in conn.execute("SELECT name FROM persons"):
        names.add(row[0])
    conn.close()
    return sorted(names)
