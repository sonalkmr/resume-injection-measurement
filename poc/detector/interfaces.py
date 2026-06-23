"""Abstract interfaces for detector components."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IPDFParser(ABC):
    @abstractmethod
    def parse(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """Parse PDF bytes and return extracted artifacts."""


class IPDFRenderer(ABC):
    @abstractmethod
    def render_page(self, pdf_bytes: bytes, page_number: int) -> bytes:
        """Render a single PDF page to image bytes."""


class IOCRClient(ABC):
    @abstractmethod
    def analyze_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """Send image bytes to OCR service and return structured text results."""


class IDiscrepancyEngine(ABC):
    @abstractmethod
    def analyze(self, parsed: Dict[str, Any], ocr: Dict[str, Any]) -> Dict[str, Any]:
        """Return discrepancy analysis between parsed PDF and OCR."""


class ILLMVerifier(ABC):
    @abstractmethod
    def verify(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ask an LLM to verify suspicious artifacts."""


class IRiskEngine(ABC):
    @abstractmethod
    def score(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Compute a risk score from analysis results."""
