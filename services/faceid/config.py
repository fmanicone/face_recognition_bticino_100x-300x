from pathlib import Path

# Cartella radice dati
DATA_DIR = Path("data")

# Percorsi file persistenti
FAISS_INDEX_PATH = DATA_DIR / "index.faiss"
METADATA_PATH = DATA_DIR / "metadata.jsonl"
METADATA_DB_PATH = DATA_DIR / "metadata.db"

# Dimensione embedding ArcFace
EMBEDDING_DIM: int = 512

# Soglia cosine similarity per il match (sul punteggio aggregato top-k)
MATCH_THRESHOLD: float = 0.45

# Numero di candidati top-k da recuperare per il voting
# Serve quando ci sono più persone nell'indice: confronta il miglior campione
# di ogni persona e vince chi ha lo score massimo più alto.
TOP_K: int = 10

# InsightFace detection size
DET_SIZE: tuple[int, int] = (640, 640)

# -------------------------
# Quality gate (import)
# -------------------------

# Confidenza minima della face detection (InsightFace det_score, 0–1)
MIN_DET_SCORE: float = 0.50

# Area minima del volto rispetto all'immagine (0–1)
# Scarta volti troppo piccoli/lontani dalla fotocamera
MIN_FACE_AREA_RATIO: float = 0.02

# Distanza minima tra gli occhi in pixel
# Scarta volti di lato o con occhi non rilevabili
MIN_EYE_DISTANCE_PX: int = 20

# Simmetria minima degli occhi rispetto all'asse orizzontale (0–1)
# 1.0 = occhi perfettamente allineati, 0 = completamente sbilanciati
# Scarta profili e volti ruotati
MIN_EYE_SYMMETRY: float = 0.65
