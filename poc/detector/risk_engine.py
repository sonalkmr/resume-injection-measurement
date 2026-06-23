"""Risk scoring engine that aggregates evidence into a risk score."""
from __future__ import annotations

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class RiskEngine:
    """Weighted Risk Engine.

    Inputs (in `analysis` dict):
      - hidden_text_score: 0..100 or 0..1
      - ocr_discrepancy_score: 0..100 or 0..1
      - pdf_anomaly_score: 0..100 or 0..1
      - llm_score: 0..100 or 0..1

    Output:
      { risk_score: float, severity: str, findings: List[str] }

    The model normalizes inputs to 0..1 then applies weights.
    """

    # Weights must sum to 1.0
    WEIGHTS = {
        "hidden_text": 0.35,
        "ocr_discrepancy": 0.30,
        "pdf_anomaly": 0.20,
        "llm": 0.15,
    }

    def _norm(self, v: Any) -> float:
        try:
            f = float(v)
        except Exception:
            return 0.0
        # If value looks like 0..1, keep it; if >1 assume 0..100 and scale
        if f > 1.0:
            return max(0.0, min(1.0, f / 100.0))
        return max(0.0, min(1.0, f))

    def score(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug("Computing risk score from analysis: %s", analysis)

        h = self._norm(analysis.get("hidden_text_score") or analysis.get("hidden_text"))
        o = self._norm(analysis.get("ocr_discrepancy_score") or analysis.get("ocr_discrepancy"))
        p = self._norm(analysis.get("pdf_anomaly_score") or analysis.get("pdf_anomaly"))
        l = self._norm(analysis.get("llm_score") or analysis.get("llm_verification_score") or analysis.get("llm_score_confidence") or analysis.get("llm", {}).get("confidence"))

        w = self.WEIGHTS
        combined = h * w["hidden_text"] + o * w["ocr_discrepancy"] + p * w["pdf_anomaly"] + l * w["llm"]
        risk_score = round(combined * 100.0, 2)

        findings: List[str] = []
        if h >= 0.5:
            findings.append("Significant hidden-text indicators")
        if o >= 0.5:
            findings.append("High OCR/PDF text discrepancy")
        if p >= 0.5:
            findings.append("PDF layout/anomaly indicators")
        if l >= 0.5:
            findings.append("LLM flagged suspicious content")

        # Severity bands
        if risk_score >= 75:
            severity = "high"
        elif risk_score >= 35:
            severity = "medium"
        else:
            severity = "low"

        result = {"risk_score": risk_score, "severity": severity, "findings": findings}
        logger.debug("Risk result: %s", result)
        return result
