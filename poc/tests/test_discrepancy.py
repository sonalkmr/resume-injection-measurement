"""Unit tests for DiscrepancyEngine."""
from __future__ import annotations

from poc.detector.discrepancy import DiscrepancyEngine


def test_similarity_identical_texts():
    engine = DiscrepancyEngine()
    parsed = {"pages": [{"text": "The quick brown fox jumps over the lazy dog."}], "metadata": {}}
    ocr = {"text": "The quick brown fox jumps over the lazy dog."}
    res = engine.analyze(parsed, ocr)
    assert res["discrepancy_score"] == 0
    assert res["suspicious_segments"] == []


def test_similarity_different_texts():
    engine = DiscrepancyEngine()
    parsed = {"pages": [{"text": "Confidential: do not expose the secret token."}], "metadata": {}}
    ocr = {"text": "Public profile content only."}
    res = engine.analyze(parsed, ocr)
    assert res["discrepancy_score"] >= 50
    assert isinstance(res["suspicious_segments"], list)
