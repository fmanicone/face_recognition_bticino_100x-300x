import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..config import METADATA_DB_PATH, METADATA_PATH
from ..models import FaceRecord
from ..utils import get_logger
from .base import MetadataRepository

logger = get_logger(__name__)


class SqliteMetadataRepository(MetadataRepository):
    """
    Implementazione di MetadataRepository su SQLite.

    Al primo avvio migra automaticamente i record dal JSONL legacy
    (se presente) quando il DB è vuoto.
    """

    def __init__(
        self,
        path: Path = METADATA_DB_PATH,
        legacy_jsonl_path: Path = METADATA_PATH,
    ) -> None:
        self._path = path
        self._legacy_jsonl_path = legacy_jsonl_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._migrate_from_jsonl_if_needed()

    def append(self, faiss_id: int, name: str, image_path: str) -> FaceRecord:
        record = FaceRecord(
            faiss_id=faiss_id,
            name=name,
            image_path=image_path,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO faces (faiss_id, name, image_path, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (record.faiss_id, record.name, record.image_path, record.created_at),
            )
            conn.commit()
        logger.info(f"Metadata SQLite salvati: faiss_id={faiss_id}, name='{name}'.")
        return record

    def get_by_id(self, record_id: int) -> Optional[FaceRecord]:
        with sqlite3.connect(self._path) as conn:
            row = conn.execute(
                """
                SELECT faiss_id, name, image_path, created_at
                FROM faces
                WHERE faiss_id = ?
                """,
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return FaceRecord(
            faiss_id=int(row[0]),
            name=str(row[1]),
            image_path=str(row[2]),
            created_at=str(row[3]),
        )

    def load_all(self) -> List[FaceRecord]:
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(
                """
                SELECT faiss_id, name, image_path, created_at
                FROM faces
                ORDER BY faiss_id ASC
                """
            ).fetchall()
        return [
            FaceRecord(
                faiss_id=int(row[0]),
                name=str(row[1]),
                image_path=str(row[2]),
                created_at=str(row[3]),
            )
            for row in rows
        ]

    def clear(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute("DELETE FROM faces")
            conn.commit()
        logger.info(f"Metadata SQLite svuotati: {self._path}")

    def _init_schema(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS faces (
                    faiss_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_faces_name ON faces(name)"
            )
            conn.commit()

    def _migrate_from_jsonl_if_needed(self) -> None:
        if not self._legacy_jsonl_path.exists():
            return

        with sqlite3.connect(self._path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM faces").fetchone()
            current_count = int(row[0]) if row else 0
            if current_count > 0:
                return

            imported = 0
            with open(self._legacy_jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO faces (faiss_id, name, image_path, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            int(data["faiss_id"]),
                            str(data["name"]),
                            str(data["image_path"]),
                            str(data["created_at"]),
                        ),
                    )
                    imported += 1
            conn.commit()
        logger.info(
            "Migrazione metadata completata: %s record importati da %s a %s.",
            imported,
            self._legacy_jsonl_path,
            self._path,
        )
