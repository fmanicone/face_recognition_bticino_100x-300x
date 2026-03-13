from ..models import FaceRecord, ImportResult
from ..pipeline import FacePipeline
from ..repositories.base import MetadataRepository, VectorRepository
from ..utils import get_logger

logger = get_logger(__name__)


class ImportService:
    """
    Servizio di import: riceve un'immagine e un nome,
    esegue l'intera pipeline e persiste il risultato nei repository.

    Può essere chiamato da CLI, API HTTP, worker asincrono — senza modifiche.

    Dipendenze iniettate: VectorRepository e MetadataRepository.
    Sostituire le implementazioni concrete non richiede toccare questo service.
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

    def execute(
        self,
        image_path: str,
        name: str,
        quality_check: bool = True,
    ) -> ImportResult:
        """
        Esegue l'import di un volto.

        Args:
            image_path: Percorso assoluto dell'immagine.
            name: Nome della persona da associare all'embedding.
            quality_check: Se True applica il quality gate prima dell'embedding.

        Returns:
            ImportResult con esito dell'operazione.
        """
        logger.info(f"ImportService: avvio import '{name}' da '{image_path}'.")

        try:
            embedding = self._pipeline.process(image_path, quality_check=quality_check)
        except ValueError as e:
            return ImportResult(success=False, error=str(e))

        if embedding is None:
            reason = (
                "Nessun volto rilevato nell'immagine."
                if not quality_check
                else "Volto rifiutato dal quality gate "
                     "(det_score basso, volto troppo piccolo, occhi non visibili o di lato)."
            )
            logger.warning(f"ImportService: {reason}")
            return ImportResult(success=False, error=reason)

        faiss_id = self._vector_repo.add(embedding)
        record: FaceRecord = self._metadata_repo.append(
            faiss_id=faiss_id,
            name=name,
            image_path=image_path,
        )

        logger.info(f"ImportService: import completato — faiss_id={faiss_id}, name='{name}'.")
        return ImportResult(
            success=True,
            faiss_id=record.faiss_id,
            name=record.name,
            image_path=record.image_path,
        )
