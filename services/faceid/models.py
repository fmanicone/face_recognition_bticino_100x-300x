from dataclasses import dataclass
from typing import Optional


@dataclass
class FaceRecord:
    """Record persistito nel metadata store."""
    faiss_id: int
    name: str
    image_path: str
    created_at: str


@dataclass
class ImportResult:
    """Risultato dell'operazione di import."""
    success: bool
    faiss_id: Optional[int] = None
    name: Optional[str] = None
    image_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class MatchResult:
    """Risultato di una ricerca nell'indice vettoriale."""
    matched: bool
    score: float
    name: Optional[str] = None
    faiss_id: Optional[int] = None
    avg_score: Optional[float] = None
    sample_count: Optional[int] = None
    # Timing per step (millisecondi)
    time_pipeline_ms: Optional[float] = None   # detection + alignment + embedding
    time_search_ms: Optional[float] = None     # ricerca FAISS
    time_lookup_ms: Optional[float] = None     # lookup metadata top-k
    time_total_ms: Optional[float] = None      # totale end-to-end
