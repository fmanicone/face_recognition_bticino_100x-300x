import math
import numpy as np
import cv2
from dataclasses import dataclass
from typing import Optional

from insightface.app import FaceAnalysis
from insightface.utils.face_align import norm_crop

from .config import (
    DET_SIZE,
    MIN_DET_SCORE,
    MIN_FACE_AREA_RATIO,
    MIN_EYE_DISTANCE_PX,
    MIN_EYE_SYMMETRY,
)
from .utils import get_logger

logger = get_logger(__name__)

# Dimensione attesa dal modello ArcFace ResNet50
ARCFACE_INPUT_SIZE = 112


@dataclass
class QualityReport:
    """Risultato del quality gate su un singolo volto."""

    passed: bool
    det_score: float
    face_area_ratio: float
    eye_distance_px: float
    eye_symmetry: float
    rejection_reason: Optional[str] = None


class FacePipeline:
    """
    Pipeline di elaborazione volti.

    Responsabilità:
    - caricamento InsightFace (ArcFace su CPU)
    - face detection e face alignment
    - quality gate (det_score, area, occhi, simmetria)
    - estrazione embedding (512 dim)
    - selezione del volto con bounding box più grande
    - normalizzazione embedding (L2)
    """

    def __init__(self) -> None:
        logger.info("Inizializzazione FacePipeline (CPU)...")
        self.app = FaceAnalysis(providers=["CPUExecutionProvider"])
        self.app.prepare(ctx_id=0, det_size=DET_SIZE)
        logger.info("FacePipeline pronta.")

    def _quality_check(self, face, img_h: int, img_w: int) -> QualityReport:
        """
        Valuta la qualità di un volto rilevato.

        Keypoints InsightFace (kps) — ordine standard:
          0: occhio sinistro
          1: occhio destro
          2: naso
          3: bocca angolo sinistro
          4: bocca angolo destro
        """
        x1, y1, x2, y2 = face.bbox
        det_score = float(face.det_score)
        face_w = x2 - x1
        face_h = y2 - y1
        face_area_ratio = (face_w * face_h) / max(img_h * img_w, 1)

        # --- det_score ---
        if det_score < MIN_DET_SCORE:
            return QualityReport(
                passed=False,
                det_score=det_score,
                face_area_ratio=face_area_ratio,
                eye_distance_px=0.0,
                eye_symmetry=0.0,
                rejection_reason=f"det_score={det_score:.3f} < {MIN_DET_SCORE}",
            )

        # --- area volto ---
        if face_area_ratio < MIN_FACE_AREA_RATIO:
            return QualityReport(
                passed=False,
                det_score=det_score,
                face_area_ratio=face_area_ratio,
                eye_distance_px=0.0,
                eye_symmetry=0.0,
                rejection_reason=f"face_area_ratio={face_area_ratio:.4f} < {MIN_FACE_AREA_RATIO}",
            )

        # --- keypoints occhi ---
        kps = face.kps  # shape (5, 2)
        if kps is None or len(kps) < 2:
            return QualityReport(
                passed=False,
                det_score=det_score,
                face_area_ratio=face_area_ratio,
                eye_distance_px=0.0,
                eye_symmetry=0.0,
                rejection_reason="keypoints oculari non disponibili",
            )

        left_eye = kps[0]  # (x, y)
        right_eye = kps[1]  # (x, y)

        dx = float(right_eye[0] - left_eye[0])
        dy = float(right_eye[1] - left_eye[1])
        eye_distance_px = math.sqrt(dx**2 + dy**2)

        # --- distanza occhi ---
        if eye_distance_px < MIN_EYE_DISTANCE_PX:
            return QualityReport(
                passed=False,
                det_score=det_score,
                face_area_ratio=face_area_ratio,
                eye_distance_px=eye_distance_px,
                eye_symmetry=0.0,
                rejection_reason=f"eye_distance={eye_distance_px:.1f}px < {MIN_EYE_DISTANCE_PX}px",
            )

        # --- simmetria occhi (quanto gli occhi sono allineati orizzontalmente) ---
        # Ratio |dy| / dist: 0 = perfettamente orizzontali, 1 = completamente verticali
        tilt_ratio = abs(dy) / max(eye_distance_px, 1e-6)
        eye_symmetry = 1.0 - tilt_ratio  # 1 = perfetto, ~0 = profilo

        if eye_symmetry < MIN_EYE_SYMMETRY:
            return QualityReport(
                passed=False,
                det_score=det_score,
                face_area_ratio=face_area_ratio,
                eye_distance_px=eye_distance_px,
                eye_symmetry=eye_symmetry,
                rejection_reason=f"eye_symmetry={eye_symmetry:.3f} < {MIN_EYE_SYMMETRY} (volto troppo di lato)",
            )

        return QualityReport(
            passed=True,
            det_score=det_score,
            face_area_ratio=face_area_ratio,
            eye_distance_px=eye_distance_px,
            eye_symmetry=eye_symmetry,
        )

    def process_frame(
        self, img: np.ndarray, quality_check: bool = True
    ) -> Optional[np.ndarray]:
        """
        Pipeline completa su numpy array BGR già caricato in memoria.

        Usato da WebSocket server, webcam producer e come core di process().

        Step:
          1. Face detection (SCRFD — det_10g.onnx)
          2. Selezione volto più grande
          3. Quality gate (solo se quality_check=True)
          4. Face alignment → crop 112×112 (norm_crop via keypoints)
          5. Estrazione embedding (ArcFace ResNet50 — w600k_r50.onnx)
          6. Normalizzazione L2

        Args:
            img: Array BGR numpy (H, W, 3) già caricato.
            quality_check: Se True applica il quality gate.

        Returns:
            Array float32 (512,) normalizzato, oppure None se nessun volto valido.
        """
        img_h, img_w = img.shape[:2]

        # ── STEP 1: Face detection ────────────────────────────────────────────
        faces = self.app.get(img)
        if not faces:
            logger.warning("[1] Nessun volto rilevato.")
            return None
        logger.info(
            f"[1] Face detection: {len(faces)} volto/i rilevati ({img_w}x{img_h})."
        )

        # ── STEP 2: Selezione volto più grande ───────────────────────────────
        face = max(
            faces,
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        )
        x1, y1, x2, y2 = face.bbox
        logger.info(
            f"[2] Volto selezionato: bbox=[{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}], det_score={face.det_score:.3f}"
        )

        # ── STEP 3: Quality gate ──────────────────────────────────────────────
        if quality_check:
            report = self._quality_check(face, img_h, img_w)
            if not report.passed:
                logger.warning(
                    f"[3] Quality gate FALLITO — {report.rejection_reason} "
                    f"[det={report.det_score:.3f}, area={report.face_area_ratio:.4f}, "
                    f"eye_dist={report.eye_distance_px:.1f}px, symmetry={report.eye_symmetry:.3f}]"
                )
                return None
            logger.info(
                f"[3] Quality gate OK — det={report.det_score:.3f}, "
                f"area={report.face_area_ratio:.4f}, "
                f"eye_dist={report.eye_distance_px:.1f}px, "
                f"symmetry={report.eye_symmetry:.3f}"
            )
        else:
            logger.info("[3] Quality gate saltato (modalità match).")

        # ── STEP 4: Face alignment + crop 112×112 ────────────────────────────
        kps = face.kps  # shape (5, 2): [occhio_sx, occhio_dx, naso, bocca_sx, bocca_dx]
        aligned_face = norm_crop(img, kps, image_size=ARCFACE_INPUT_SIZE)
        logger.info(
            f"[4] Face alignment: crop {aligned_face.shape[1]}×{aligned_face.shape[0]}px (ArcFace input)."
        )

        # ── STEP 5: Estrazione embedding ─────────────────────────────────────
        rec_model = self.app.models.get("recognition")
        if rec_model is None:
            logger.info(
                "[5] Modello recognition non accessibile direttamente, uso embedding precomputed."
            )
            embedding = face.embedding.astype(np.float32)
        else:
            embedding = rec_model.get_feat([aligned_face])[0].astype(np.float32)
        logger.info(
            f"[5] Embedding estratto: shape={embedding.shape}, norm={np.linalg.norm(embedding):.4f}"
        )

        # ── STEP 6: Normalizzazione L2 ────────────────────────────────────────
        norm = float(np.linalg.norm(embedding))
        if norm > 0:
            embedding = embedding / norm
        logger.info(
            f"[6] Embedding normalizzato (norma finale={np.linalg.norm(embedding):.6f})."
        )

        return embedding

    def process(
        self, image_path: str, quality_check: bool = True
    ) -> Optional[np.ndarray]:
        """
        Wrapper per CLI/import: legge l'immagine da disco e chiama process_frame().

        Args:
            image_path: Percorso dell'immagine.
            quality_check: Se True applica il quality gate.

        Returns:
            Array float32 (512,) normalizzato, oppure None se nessun volto valido.

        Raises:
            ValueError: Se l'immagine non può essere caricata.
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Impossibile caricare l'immagine: {image_path}")
        logger.info(
            f"Immagine caricata da disco: {image_path} ({img.shape[1]}x{img.shape[0]})"
        )
        return self.process_frame(img, quality_check=quality_check)
