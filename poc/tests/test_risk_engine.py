"""Unit tests for RiskEngine weighted scoring model."""
from __future__ import annotations

from poc.detector.risk_engine import RiskEngine


def test_risk_engine_low():
    engine = RiskEngine()
    out = engine.score({"hidden_text_score": 0.0, "ocr_discrepancy_score": 0.0, "pdf_anomaly_score": 0.0, "llm_score": 0.0})
    assert out["severity"] == "low"
    assert out["risk_score"] == 0.0


def test_risk_engine_medium():
    engine = RiskEngine()
    out = engine.score({"hidden_text_score": 50, "ocr_discrepancy_score": 40, "pdf_anomaly_score": 20, "llm_score": 10})
    assert 30 <= out["risk_score"] <= 60
    assert out["severity"] in ("low", "medium")


def test_risk_engine_high():
    engine = RiskEngine()
    out = engine.score({"hidden_text_score": 90, "ocr_discrepancy_score": 80, "pdf_anomaly_score": 70, "llm_score": 90})
    assert out["severity"] == "high"
    assert out["risk_score"] >= 75
