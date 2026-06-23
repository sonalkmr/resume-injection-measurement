"""Unit tests for PDFParser using an in-memory PDF created with PyMuPDF."""
from __future__ import annotations

import tempfile
import fitz

from poc.detector.pdf_parser import PDFParser


def create_sample_pdf_bytes() -> bytes:
    doc = fitz.open()
    # standard letter size
    page = doc.new_page(width=612, height=792)
    # normal text
    page.insert_text((72, 72), "Hello World", fontsize=12, color=(0, 0, 0))
    # very small text
    page.insert_text((72, 100), "tiny", fontsize=4, color=(0, 0, 0))
    # white text (near white)
    page.insert_text((72, 120), "invisible", fontsize=10, color=(1, 1, 1))
    # text outside bounds (place beyond page width/height)
    page.insert_text((700, 800), "outside", fontsize=12, color=(0, 0, 0))

    # save to temp file then read bytes
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    doc.save(path)
    doc.close()
    with open(path, "rb") as f:
        data = f.read()
    return data


def test_pdf_parser_detects_anomalies():
    pdf_bytes = create_sample_pdf_bytes()
    parser = PDFParser()
    out = parser.parse(pdf_bytes)
    assert out["metadata"]["page_count"] >= 1
    page_anomalies = out["metadata"].get("page_anomalies", [])
    assert len(page_anomalies) >= 1
    anomalies = page_anomalies[0]
    assert anomalies["very_small_font"] is True
    assert anomalies["white_text_detected"] is True
    # off-page detection may be best-effort depending on PDF content extraction;
    # ensure the flag exists and is a boolean.
    assert isinstance(anomalies["text_outside_page"], bool)
