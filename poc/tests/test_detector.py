"""Basic unit tests for detector PoC starters."""
from __future__ import annotations

from poc.detector.pdf_parser import PDFParser
from poc.detector.discrepancy import DiscrepancyEngine


def test_pdf_parser_empty():
    parser = PDFParser()
    # empty PDF bytes should raise or return minimal structure; ensure no crash
    try:
        res = parser.parse(b"")
    except Exception:
        # PyMuPDF will raise on invalid PDF; that's acceptable for PoC
        return
    assert isinstance(res, dict)


def test_discrepancy_basic():
    engine = DiscrepancyEngine()
    parsed = {"pages": [{"text": "hello world"}], "metadata": {"page_count": 1}}
    ocr = {"text": "hello world"}
    out = engine.analyze(parsed, ocr)
    assert out["similarity_score"] == 1.0
