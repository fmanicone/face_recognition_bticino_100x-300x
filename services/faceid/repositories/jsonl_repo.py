import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..config import METADATA_PATH
from ..models import FaceRecord
from ..utils import get_logger
from .base import MetadataRepository

logger = get_logger(__name__)


class JsonlMetadataRepository(MetadataRepository):
    """
    Implementazione di MetadataRepository su file JSONL.

    Ogni riga = un FaceRecord serializzato.
    L'ID vettoriale (faiss_id) è la chiave di lookup.

    Per sostituire con SQLite, Postgres ecc.:
    implementare MetadataRepository e passare la nuova istanza ai service.
    """

    def __init__(self, path: Path = METADATA_PATH) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, faiss_id: int, name: str, image_path: str) -> FaceRecord:
        record = FaceRecord(
            faiss_id=faiss_id,
            name=name,
            image_path=image_path,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "faiss_id": record.faiss_id,
                "name": record.name,
                "image_path": record.image_path,
                "created_at": record.created_at,
            }) + "\n")
        logger.info(f"Metadata salvati: faiss_id={faiss_id}, name='{name}'.")
        return record

    def get_by_id(self, record_id: int) -> Optional[FaceRecord]:
        for record in self.load_all():
            if record.faiss_id == record_id:
                return record
        return None

    def load_all(self) -> List[FaceRecord]:
        if not self._path.exists():
            return []
        records: List[FaceRecord] = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(FaceRecord(**json.loads(line)))
        return records

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()
            logger.info(f"Metadata eliminati: {self._path}")
