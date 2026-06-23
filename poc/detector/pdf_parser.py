"""PDF parsing utilities using PyMuPDF (fitz)."""
from __future__ import annotations

from typing import Dict, Any, List, Tuple
import fitz  # PyMuPDF
import logging

from poc.detector.models import ParseResult, PageText

logger = logging.getLogger(__name__)


def _color_to_rgb(color: Any) -> Tuple[int, int, int] | None:
    """Normalize PyMuPDF color value to an (r,g,b) tuple of ints 0-255.

    PyMuPDF span.color may be an int or a tuple of floats in 0..1.
    """
    if color is None:
        return None
    if isinstance(color, tuple) or isinstance(color, list):
        try:
            r, g, b = color[:3]
            # values often in 0..1
            if max(r, g, b) <= 1.0:
                return (int(r * 255), int(g * 255), int(b * 255))
            return (int(r), int(g), int(b))
        except Exception:
            return None
    if isinstance(color, int):
        # color encoded as 0xRRGGBB or 0xAARRGGBB
        try:
            hexv = color & 0xFFFFFF
            r = (hexv >> 16) & 0xFF
            g = (hexv >> 8) & 0xFF
            b = hexv & 0xFF
            return (r, g, b)
        except Exception:
            return None
    return None


def _is_white(rgb: Tuple[int, int, int] | None, threshold: int = 250) -> bool:
    if not rgb:
        return False
    r, g, b = rgb
    return r >= threshold and g >= threshold and b >= threshold


def _span_outside_bounds(bbox: List[float], page_rect: fitz.Rect) -> bool:
    x0, y0, x1, y1 = bbox
    # consider outside if any coordinate is negative or exceeds page size
    if x0 < 0 or y0 < 0:
        return True
    if x1 > page_rect.width or y1 > page_rect.height:
        return True
    return False


class PDFParser:
    """PDF parser extracting text, font sizes, colors and coordinates.

    Public methods are small and unit-testable: `extract_spans` and `detect_anomalies`.
    """

    SMALL_FONT_THRESHOLD: float = 6.0

    def extract_spans(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """Extract spans from a PyMuPDF page as dictionaries.

        Each span contains: text, font, size, color (rgb tuple), bbox.
        """
        spans_out: List[Dict[str, Any]] = []
        blocks = page.get_text("dict").get("blocks", [])
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    font = span.get("font")
                    size = float(span.get("size", 0.0) or 0.0)
                    color_raw = span.get("color")
                    rgb = _color_to_rgb(color_raw)
                    bbox = span.get("bbox") or span.get("origin") or []
                    # bbox from span is usually [x0,y0,x1,y1]
                    spans_out.append({
                        "text": text,
                        "font": font,
                        "size": size,
                        "color": rgb,
                        "bbox": bbox,
                    })

        # Additionally, include word-level boxes which capture text inserted
        # at arbitrary coordinates (e.g., outside page bounds) that may not
        # appear in the span structure above.
        try:
            words = page.get_text("words")  # list of tuples
            for w in words:
                x0, y0, x1, y1, word_text = w[0], w[1], w[2], w[3], w[4]
                spans_out.append({
                    "text": word_text,
                    "font": None,
                    "size": 0.0,
                    "color": None,
                    "bbox": [x0, y0, x1, y1],
                })
        except Exception:
            # best-effort: continue if words extraction fails
            pass
        return spans_out

    def detect_anomalies(self, spans: List[Dict[str, Any]], page_rect: fitz.Rect) -> Dict[str, Any]:
        """Detect anomalies in a page given its spans and page rectangle.

        Returns a dict with flags for very_small_font, white_text_detected, text_outside_bounds.
        """
        very_small = False
        white_text = False
        outside = False
        for s in spans:
            size = float(s.get("size") or 0.0)
            if size > 0 and size < self.SMALL_FONT_THRESHOLD:
                very_small = True
            if _is_white(s.get("color")):
                white_text = True
            bbox = s.get("bbox") or []
            if bbox and _span_outside_bounds(bbox, page_rect):
                outside = True

        return {
            "very_small_font": very_small,
            "white_text_detected": white_text,
            "text_outside_page": outside,
        }

    def parse(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """Parse PDF bytes and return a structured ParseResult dict.

        The returned dict is compatible with `poc.detector.models.ParseResult`.
        """
        logger.debug("Starting PDF parse")
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages: List[PageText] = []
        anomalies_list: List[Dict[str, Any]] = []
        for i, page in enumerate(doc):
            page_spans = self.extract_spans(page)
            text = page.get_text("text")
            fonts: Dict[str, float] = {}
            colors_set = set()
            for s in page_spans:
                key = f"{s.get('font')}@{s.get('size')}"
                fonts[key] = float(s.get("size") or 0.0)
                rgb = s.get("color")
                if rgb:
                    colors_set.add(f"{rgb[0]},{rgb[1]},{rgb[2]}")


            anomalies = self.detect_anomalies(page_spans, page.rect)

            page_model = PageText(
                page_number=i,
                text=text,
                fonts=fonts,
                colors=list(colors_set),
                spans=page_spans,
            )
            # attach anomalies per-page inside metadata for convenience
            pages.append(page_model)
            anomalies_list.append(anomalies)

        metadata = {"page_count": len(doc)}
        logger.debug("Finished PDF parse: %s pages", len(doc))
        result = ParseResult(pages=pages, metadata=metadata)
        # Convert to dict for compatibility with existing callers
        out = result.dict()
        # embed per-page anomalies
        out["metadata"]["page_anomalies"] = anomalies_list
        return out
