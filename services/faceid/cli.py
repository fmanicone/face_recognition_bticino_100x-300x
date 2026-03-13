import argparse
import os
import sys

from .config import FAISS_INDEX_PATH, METADATA_DB_PATH
from .pipeline import FacePipeline
from .repositories.faiss_repo import FaissVectorRepository
from .repositories.sqlite_repo import SqliteMetadataRepository
from .services.import_service import ImportService
from .services.match_service import MatchService
from .utils import get_logger

logger = get_logger(__name__)


def _build_services() -> tuple[ImportService, MatchService]:
    """Costruisce pipeline e repository condivisi tra i service."""
    pipeline = FacePipeline()
    vector_repo = FaissVectorRepository()
    metadata_repo = SqliteMetadataRepository()
    import_svc = ImportService(pipeline, vector_repo, metadata_repo)
    match_svc = MatchService(pipeline, vector_repo, metadata_repo)
    return import_svc, match_svc


# ---------------------------------------------------------------------------
# Handlers — responsabilità: input/output CLI soltanto
# ---------------------------------------------------------------------------

def cmd_import(args: argparse.Namespace) -> None:
    image_path = os.path.abspath(args.image_path)
    import_svc, _ = _build_services()

    result = import_svc.execute(
        image_path=image_path,
        name=args.name,
        quality_check=not args.skip_quality,
    )

    if not result.success:
        print(f"ERRORE: {result.error}")
        if not args.skip_quality and "quality gate" in (result.error or "").lower():
            print("  Usa --skip-quality per forzare l'import.")
        sys.exit(1)

    print(f"OK\nImportato: {result.name}  (faiss_id={result.faiss_id})")


def cmd_match(args: argparse.Namespace) -> None:
    image_path = os.path.abspath(args.image_path)
    _, match_svc = _build_services()

    result = match_svc.execute(image_path=image_path)

    if result.matched:
        print(
            f"MATCH\n"
            f"name: {result.name}\n"
            f"score: {result.score:.4f}  "
            f"(best su {result.sample_count} campioni, media={result.avg_score:.4f})"
        )
    else:
        print(f"NO MATCH\nscore: {result.score:.4f}")

    print(
        f"\ntiming: pipeline={result.time_pipeline_ms:.0f}ms  "
        f"search={result.time_search_ms:.1f}ms  "
        f"lookup={result.time_lookup_ms:.0f}ms  "
        f"total={result.time_total_ms:.0f}ms"
    )


def cmd_reset(args: argparse.Namespace) -> None:
    files = [
        (FAISS_INDEX_PATH, "index FAISS"),
        (METADATA_DB_PATH, "metadata SQLite"),
    ]
    existing = [(p, label) for p, label in files if p.exists()]

    if not existing:
        print("L'indice è già vuoto.")
        return

    if not args.yes:
        print("Stai per eliminare:")
        for p, label in existing:
            print(f"  - {p}  ({label})")
        risposta = input("Confermi? [s/N] ").strip().lower()
        if risposta not in ("s", "si", "sì", "y", "yes"):
            print("Operazione annullata.")
            return

    vector_repo = FaissVectorRepository()
    metadata_repo = SqliteMetadataRepository()
    vector_repo.clear()
    metadata_repo.clear()
    print(
        "Indice svuotato (FAISS + SQLite). "
        "Il file JSONL legacy non e' stato toccato."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="faceid",
        description="Sistema locale di face recognition (InsightFace + FAISS).",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMANDO")

    # ---- import ----
    import_parser = subparsers.add_parser("import", help="Importa un'immagine nell'indice.")
    import_parser.add_argument("image_path", help="Percorso dell'immagine.")
    import_parser.add_argument("--name", required=True, help="Nome della persona.")
    import_parser.add_argument(
        "--skip-quality", action="store_true", default=False,
        help="Salta il quality gate (sconsigliato).",
    )

    # ---- match ----
    match_parser = subparsers.add_parser("match", help="Cerca il volto più simile nell'indice.")
    match_parser.add_argument("image_path", help="Percorso dell'immagine.")

    # ---- reset ----
    reset_parser = subparsers.add_parser("reset", help="Svuota l'indice FAISS e i metadata.")
    reset_parser.add_argument("--yes", "-y", action="store_true", default=False,
                              help="Salta la conferma interattiva.")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)
    elif args.command == "import":
        cmd_import(args)
    elif args.command == "match":
        cmd_match(args)
    elif args.command == "reset":
        cmd_reset(args)


if __name__ == "__main__":
    main()
