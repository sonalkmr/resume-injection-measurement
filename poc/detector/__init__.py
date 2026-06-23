"""Detector package for resume prompt-injection PoC."""

from .pdf_parser import PDFParser
from .renderer import PDFRenderer
from .ocr import OCRClient
from .discrepancy import DiscrepancyEngine
from .risk_engine import RiskEngine
from .llm_verifier import LLMVerifier

__all__ = [
    "PDFParser",
    "PDFRenderer",
    "OCRClient",
    "DiscrepancyEngine",
    "RiskEngine",
    "LLMVerifier",
]
