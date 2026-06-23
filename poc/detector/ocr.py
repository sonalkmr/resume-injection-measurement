"""Offline OCR client using pytesseract."""
from __future__ import annotations

import logging
import asyncio
from typing import Dict, Any
from io import BytesIO

from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)


class OCRClient:
    """Simple async wrapper around pytesseract.

    `analyze_image` accepts image bytes (e.g., PNG bytes from PyMuPDF render)
    and returns {"text": str, "confidence": float, "raw": dict}.
    """

    def __init__(self, oem: int = 3, psm: int = 3) -> None:
        self.oem = oem
        self.psm = psm

    async def analyze_image(self, image_bytes: bytes) -> Dict[str, Any]:
        return await asyncio.to_thread(self._analyze_sync, image_bytes)

    def _analyze_sync(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            logger.error("Failed to open image for OCR: %s", e)
            return {"text": "", "confidence": 0.0, "raw": {}}

        # Use tesseract to get text and confidences via TSV data
        try:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            text = "\n".join([str(s).strip() for s in data.get("text", []) if str(s).strip()])
            confs = [int(c) for c in data.get("conf", []) if isinstance(c, (int, float)) or (isinstance(c, str) and c.strip().lstrip('-').isdigit())]
            # convert confidences to 0..100 integers, filter -1 values
            confs = [c for c in confs if c >= 0]
            avg_conf = float(sum(confs) / len(confs)) if confs else 0.0
            raw = {"tsv": data}
            return {"text": text, "confidence": avg_conf, "raw": raw}
        except Exception as e:
            logger.error("pytesseract OCR failed: %s", e)
            try:
                # fallback to simple string extraction
                text = pytesseract.image_to_string(img)
                return {"text": text, "confidence": 0.0, "raw": {}}
            except Exception:
                return {"text": "", "confidence": 0.0, "raw": {}}

