"""FastAPI entrypoint for the PoC detector."""
from __future__ import annotations

import logging
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse
import asyncio
from typing import Any
from statistics import mean
from pydantic import parse_obj_as

from poc.detector.logging_config import configure_logging
from poc.detector.pdf_parser import PDFParser
from poc.detector.renderer import PDFRenderer
from poc.detector.ocr import OCRClient
from poc.detector.discrepancy import DiscrepancyEngine
from poc.detector.llm_verifier import LLMVerifier
from poc.detector.risk_engine import RiskEngine
from poc.detector.models import AnalysisResponse

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Resume Prompt Injection Detector")


def get_pdf_parser() -> PDFParser:
    return PDFParser()


def get_renderer() -> PDFRenderer:
    return PDFRenderer()


def get_ocr_client() -> OCRClient:
    return OCRClient()


def get_discrepancy_engine() -> DiscrepancyEngine:
    return DiscrepancyEngine()


def get_llm_verifier() -> LLMVerifier:
    return LLMVerifier()


def get_risk_engine() -> RiskEngine:
    return RiskEngine()


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    file: UploadFile = File(...),
    parser: PDFParser = Depends(get_pdf_parser),
    renderer: PDFRenderer = Depends(get_renderer),
    ocr_client: OCRClient = Depends(get_ocr_client),
    discrepancy: DiscrepancyEngine = Depends(get_discrepancy_engine),
    llm: LLMVerifier = Depends(get_llm_verifier),
    risk_engine: RiskEngine = Depends(get_risk_engine),
) -> Any:
    """Analyze an uploaded PDF for prompt-injection indicators."""
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty upload")
    # Run CPU-bound tasks in threadpool
    parsed = await asyncio.to_thread(parser.parse, contents)

    # Render first page for OCR as a simple example (offload to thread)
    page_count = parsed.get("metadata", {}).get("page_count", 0)
    page_img = b""
    if page_count > 0:
        page_img = await asyncio.to_thread(renderer.render_page, contents, 0)

    ocr_result = {"text": "", "confidence": 0.0}
    if page_img:
        ocr_result = await ocr_client.analyze_image(page_img)

    discrepancies = await asyncio.to_thread(discrepancy.analyze, parsed, ocr_result)

    llm_result = await llm.verify({"parsed": parsed, "discrepancies": discrepancies, "ocr": ocr_result, "rendered_image": page_img})

    # Derive normalized inputs for RiskEngine
    # OCR discrepancy score (0..100)
    ocr_discrepancy_score = float(discrepancies.get("discrepancy_score", 0))
    # Hidden text score: presence of missing/different segments
    suspicious_segments = discrepancies.get("suspicious_segments", []) or []
    hidden_text_score = 100.0 if any(s.get("type") in ("missing_in_ocr", "different_in_ocr") for s in suspicious_segments) else 0.0
    # PDF anomaly score: aggregate per-page anomaly flags if present
    page_anomalies = parsed.get("metadata", {}).get("page_anomalies", [])
    pdf_anomaly_score = 0.0
    if page_anomalies:
        vals = []
        for pa in page_anomalies:
            vals.append(1.0 if pa.get("very_small_font") or pa.get("white_text_detected") or pa.get("text_outside_page") else 0.0)
        pdf_anomaly_score = mean(vals) * 100.0

    llm_score = 0.0
    if isinstance(llm_result, dict):
        llm_score = float(llm_result.get("confidence", 0.0)) * 100.0

    risk_input = {
        "hidden_text_score": hidden_text_score,
        "ocr_discrepancy_score": ocr_discrepancy_score,
        "pdf_anomaly_score": pdf_anomaly_score,
        "llm_score": llm_score,
    }

    risk = await asyncio.to_thread(risk_engine.score, risk_input)

    resp = {"discrepancies": discrepancies, "llm_verification": llm_result, "risk": risk}
    # validate/serialize via pydantic
    return parse_obj_as(AnalysisResponse, resp).dict()
