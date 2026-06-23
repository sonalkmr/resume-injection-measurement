"""Pydantic models for detector I/O."""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class PageText(BaseModel):
    page_number: int
    text: str
    fonts: Optional[Dict[str, float]] = None
    colors: Optional[List[str]] = None
    spans: Optional[List[Dict[str, Any]]] = None


class ParseResult(BaseModel):
    pages: List[PageText]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OCRResult(BaseModel):
    text: str
    confidence: Optional[float] = None
    raw: Optional[Dict[str, Any]] = None


class DiscrepancyResult(BaseModel):
    text_diff: Optional[str]
    similarity_score: float = 0.0
    hidden_text_detected: bool = False
    layout_anomalies: Optional[Dict[str, Any]] = None


class AnalysisResponse(BaseModel):
    discrepancies: DiscrepancyResult
    llm_verification: Optional[Dict[str, Any]] = None
    risk: Dict[str, Any]
