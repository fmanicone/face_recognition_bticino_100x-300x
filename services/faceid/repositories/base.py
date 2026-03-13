from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import numpy as np

from ..models import FaceRecord


class VectorRepository(ABC):
    """
    Interfaccia astratta per il vector store.

    Cambiare implementazione (FAISS → Qdrant, Chroma, ecc.)
    significa solo creare una nuova classe che implementa questa interfaccia
    e passarla ai service — zero modifiche al business logic.
    """

    @abstractmethod
    def add(self, embedding: np.ndarray) -> int:
        """
        Aggiunge un embedding e restituisce l'ID assegnato.

        Args:
            embedding: Vettore float32 normalizzato (512,).

        Returns:
            ID univoco nell'indice (0-based).
        """
        ...

    @abstractmethod
    def search(self, embedding: np.ndarray, k: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """
        Cerca i k nearest neighbor.

        Args:
            embedding: Vettore float32 normalizzato (512,).
            k: Numero di risultati.

        Returns:
            Tuple (scores, indices) come array numpy 1D.
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Svuota completamente l'indice."""
        ...

    @property
    @abstractmethod
    def size(self) -> int:
        """Numero di vettori nell'indice."""
        ...


class MetadataRepository(ABC):
    """
    Interfaccia astratta per il metadata store.

    Cambiare storage (JSONL → SQLite, Postgres, ecc.) significa
    solo una nuova implementazione — zero modifiche ai service.
    """

    @abstractmethod
    def append(self, faiss_id: int, name: str, image_path: str) -> FaceRecord:
        """Aggiunge un nuovo record e lo restituisce."""
        ...

    @abstractmethod
    def get_by_id(self, record_id: int) -> Optional[FaceRecord]:
        """Recupera un record tramite il suo ID vettoriale."""
        ...

    @abstractmethod
    def load_all(self) -> List[FaceRecord]:
        """Carica tutti i record."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Svuota lo store."""
        ...
