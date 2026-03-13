import time

import cv2
import numpy as np

from ..config import MATCH_THRESHOLD, TOP_K
from ..models import MatchResult
from ..pipeline import FacePipeline
from ..repositories.base import MetadataRepository, VectorRepository
from ..utils import get_logger

logger = get_logger(__name__)


class MatchService:
    """
    Servizio di match: riceve un'immagine (o un frame numpy), genera l'embedding
    e cerca il soggetto più simile nel vector store.

    Può essere chiamato da CLI, WebSocket server, worker asincrono — senza modifiche.

    Strategia top-k:
    - Recupera i k embedding più vicini
    - Raggruppa per nome
    - Per ogni nome usa il punteggio MASSIMO come discriminatore
    """

    def __init__(
        self,
        pipeline: FacePipeline,
        vector_repo: VectorRepository,
        metadata_repo: MetadataRepository,
    ) -> None:
        self._pipeline = pipeline
        self._vector_repo = vector_repo
        self._metadata_repo = metadata_repo

    # ─────────────────────────────────────────────────────────────────────────
    def execute_frame(self, img: np.ndarray) -> MatchResult:
        """
        Cerca il soggetto più simile al volto nell'array numpy BGR.

        Metodo core usato da WebSocket server e chiamate dirette.

        Args:
            img: Frame BGR già decodificato (es. output cv2.imdecode).

        Returns:
            MatchResult con esito, score e nome del soggetto trovato.
        """
        logger.info("MatchService: avvio match da frame numpy.")
        t_start = time.perf_counter()

        # ── Step 1: pipeline (detection + alignment + embedding) ─────────────
        t0 = time.perf_counter()
        embedding = self._pipeline.process_frame(img, quality_check=False)
        time_pipeline_ms = (time.perf_counter() - t0) * 1000

        if embedding is None:
            logger.warning("MatchService: nessun volto rilevato nel frame.")
            return MatchResult(matched=False, score=0.0)

        if self._vector_repo.size == 0:
            logger.warning("MatchService: indice vuoto.")
            return MatchResult(matched=False, score=0.0)

        # ── Step 2: ricerca FAISS ────────────────────────────────────────────
        t0 = time.perf_counter()
        k = min(TOP_K, self._vector_repo.size)
        scores, indices = self._vector_repo.search(embedding, k=k)
        time_search_ms = (time.perf_counter() - t0) * 1000

        # ── Step 3: lookup metadata top-k ────────────────────────────────────
        t0 = time.perf_counter()
        name_scores: dict[str, list[float]] = {}
        for raw_score, record_id in zip(scores, indices):
            if record_id < 0:
                continue
            record = self._metadata_repo.get_by_id(int(record_id))
            if record is None:
                continue
            name_scores.setdefault(record.name, []).append(float(raw_score))
        time_lookup_ms = (time.perf_counter() - t0) * 1000

        time_total_ms = (time.perf_counter() - t_start) * 1000

        logger.info(
            f"MatchService timing — "
            f"pipeline={time_pipeline_ms:.1f}ms, "
            f"search={time_search_ms:.2f}ms, "
            f"lookup={time_lookup_ms:.1f}ms, "
            f"total={time_total_ms:.1f}ms"
        )

        if not name_scores:
            return MatchResult(matched=False, score=0.0, time_total_ms=time_total_ms)

        # Discriminatore: max score per nome → chi ha il campione più vicino vince
        best_name = max(name_scores, key=lambda n: max(name_scores[n]))
        best_list = name_scores[best_name]
        best_score = max(best_list)
        avg_score = sum(best_list) / len(best_list)
        count = len(best_list)

        logger.info(
            f"MatchService: '{best_name}' — "
            f"max={best_score:.4f}, avg={avg_score:.4f}, campioni={count}/{k}"
        )

        if best_score >= MATCH_THRESHOLD:
            return MatchResult(
                matched=True,
                score=best_score,
                name=best_name,
                avg_score=avg_score,
                sample_count=count,
                time_pipeline_ms=time_pipeline_ms,
                time_search_ms=time_search_ms,
                time_lookup_ms=time_lookup_ms,
                time_total_ms=time_total_ms,
            )

        return MatchResult(
            matched=False,
            score=best_score,
            time_pipeline_ms=time_pipeline_ms,
            time_search_ms=time_search_ms,
            time_lookup_ms=time_lookup_ms,
            time_total_ms=time_total_ms,
        )

    # ─────────────────────────────────────────────────────────────────────────
    def execute(self, image_path: str) -> MatchResult:
        """
        Wrapper per CLI: legge l'immagine da disco e chiama execute_frame().

        Args:
            image_path: Percorso assoluto dell'immagine da interrogare.

        Returns:
            MatchResult con esito, score e nome del soggetto trovato.
        """
        logger.info(f"MatchService: avvio match da '{image_path}'.")
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"MatchService: impossibile caricare '{image_path}'.")
            return MatchResult(matched=False, score=0.0)
        return self.execute_frame(img)
