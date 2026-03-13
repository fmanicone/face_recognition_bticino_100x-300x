import faiss
import numpy as np
from pathlib import Path
from typing import Tuple

from ..config import FAISS_INDEX_PATH, EMBEDDING_DIM
from ..utils import get_logger
from .base import VectorRepository

logger = get_logger(__name__)


class FaissVectorRepository(VectorRepository):
    """
    Implementazione di VectorRepository su FAISS IndexFlatIP.

    Usa cosine similarity (prodotto scalare su vettori L2-normalizzati).
    Persiste su disco dopo ogni inserimento.

    Per sostituire con un altro vector DB (Qdrant, Chroma, Pinecone...):
    implementare VectorRepository e passare la nuova istanza ai service.
    """

    def __init__(self, index_path: Path = FAISS_INDEX_PATH) -> None:
        self._path = index_path
        self._index: faiss.IndexFlatIP = self._load_or_create()

    def _load_or_create(self) -> faiss.IndexFlatIP:
        if self._path.exists():
            logger.info(f"Caricamento indice FAISS da {self._path}")
            return faiss.read_index(str(self._path))
        logger.info("Indice FAISS non trovato. Creazione nuovo indice.")
        return faiss.IndexFlatIP(EMBEDDING_DIM)

    def add(self, embedding: np.ndarray) -> int:
        record_id = self._index.ntotal
        self._index.add(embedding.reshape(1, -1))
        self._persist()
        logger.info(f"Embedding aggiunto con id={record_id} (totale={self._index.ntotal}).")
        return record_id

    def search(self, embedding: np.ndarray, k: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        scores, indices = self._index.search(embedding.reshape(1, -1), k)
        return scores[0], indices[0]

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()
            logger.info(f"Indice FAISS eliminato: {self._path}")
        self._index = faiss.IndexFlatIP(EMBEDDING_DIM)

    @property
    def size(self) -> int:
        return self._index.ntotal

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._path))
        logger.debug(f"Indice FAISS persistito in {self._path}.")
