"""Detect discrepancies between PDF-extracted text and OCR results.

Implements both surface diffs (difflib) and semantic similarity using
TF-IDF + cosine similarity (scikit-learn). Returns a normalized
discrepancy score (0..100) where higher indicates greater discrepancy.
"""
from __future__ import annotations

from typing import Dict, Any, List
import difflib
import logging

logger = logging.getLogger(__name__)


def _difflib_similarity(a: str, b: str) -> float:
    seq = difflib.SequenceMatcher(None, a, b)
    return float(seq.ratio())


def _diff_text(a: str, b: str) -> str:
    return "\n".join(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm=""))


def _semantic_similarity(a: str, b: str) -> float:
    """Compute semantic similarity using TF-IDF + cosine similarity.

    Falls back to difflib similarity if sklearn is unavailable.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except Exception:
        logger.debug("sklearn not available; falling back to difflib for semantic similarity")
        return _difflib_similarity(a, b)

    texts = [a or "", b or ""]
    vec = TfidfVectorizer().fit_transform(texts)
    if vec.shape[0] < 2:
        return 0.0
    sim = cosine_similarity(vec[0:1], vec[1:2])[0][0]
    return float(sim)


def _find_hidden_segments(parsed: str, ocr: str) -> List[Dict[str, Any]]:
    """Identify segments present in parsed PDF text but missing or different in OCR.

    Returns a list of suspicious segments with their type.
    """
    sm = difflib.SequenceMatcher(None, parsed, ocr)
    ops = sm.get_opcodes()
    segments = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "delete":
            seg = parsed[i1:i2].strip()
            if seg:
                segments.append({"type": "missing_in_ocr", "text": seg})
        elif tag == "replace":
            seg_a = parsed[i1:i2].strip()
            seg_b = ocr[j1:j2].strip()
            if seg_a:
                segments.append({"type": "different_in_ocr", "pdf_text": seg_a, "ocr_text": seg_b})
        elif tag == "insert":
            seg = ocr[j1:j2].strip()
            if seg:
                segments.append({"type": "extra_in_ocr", "text": seg})

    return segments


class DiscrepancyEngine:
    """Engine to compute discrepancies and suspicious segments.

    Public API:
      - analyze(parsed: Dict, ocr: Dict) -> Dict

    The returned dict contains:
      - text_diff (unified diff)
      - difflib_score (0..1)
      - semantic_score (0..1)
      - discrepancy_score (0..100)
      - suspicious_segments (list)
    """

    def analyze(self, parsed: Dict[str, Any], ocr: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug("Running discrepancy analysis")
        parsed_text = "\n".join(p.get("text", "") for p in parsed.get("pages", []))
        ocr_text = (ocr.get("text") if isinstance(ocr, dict) else ocr) or ""

        dif_score = _difflib_similarity(parsed_text, ocr_text)
        sem_score = _semantic_similarity(parsed_text, ocr_text)
        diff = _diff_text(parsed_text, ocr_text)

        # Combine scores: prefer semantic similarity but include surface similarity
        combined = 0.6 * sem_score + 0.4 * dif_score

        # Discrepancy score: invert similarity -> higher = more discrepancy
        discrepancy_score = int(round((1.0 - combined) * 100))

        suspicious = _find_hidden_segments(parsed_text, ocr_text)

        logger.debug(
            "difflib=%.3f semantic=%.3f combined=%.3f discrepancy=%d",
            dif_score,
            sem_score,
            combined,
            discrepancy_score,
        )

        return {
            "text_diff": diff,
            "difflib_score": dif_score,
            "semantic_score": sem_score,
            "combined_similarity": combined,
            "similarity_score": combined,
            "discrepancy_score": discrepancy_score,
            "suspicious_segments": suspicious,
        }
