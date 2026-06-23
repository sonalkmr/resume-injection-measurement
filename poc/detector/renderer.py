"""PDF rendering utilities."""
from __future__ import annotations

from typing import Optional
import fitz
import logging
from io import BytesIO

logger = logging.getLogger(__name__)


class PDFRenderer:
    """Render PDF pages to images.

    Provides a minimal wrapper around PyMuPDF rendering. Returns PNG bytes.
    """

    def render_page(self, pdf_bytes: bytes, page_number: int, zoom: int = 2) -> bytes:
        logger.debug("Rendering page %s", page_number)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[page_number]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        logger.debug("Rendered page %s -> %d bytes", page_number, len(img_bytes))
        return img_bytes
