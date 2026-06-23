"""Heuristic LLM verifier to run entirely offline.

This module replaces the previous Azure OpenAI verifier with a deterministic
heuristic-based verifier that inspects extracted text and discrepancy data
to decide whether a document appears suspicious.
"""
from __future__ import annotations

import asyncio
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class LLMVerifier:
    """Offline heuristic verifier.

    `verify(context)` is async to keep compatibility with the rest of the
    async pipeline. It inspects `context["parsed"]` and `context["discrepancies"]`.
    """

    SUSPICIOUS_KEYWORDS = [
        "ignore previous", "disregard previous", "do not", "secret", "password", "token",
        "hidden", "prompt injection", "prompt-injection", "follow these instructions",
        "system:", "assistant:", "you are to", "respond with",
    ]

    def __init__(self, *args, **kwargs) -> None:
        # Accept arbitrary args/kwargs for backward compatibility
        return None

    async def verify(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # run sync heuristics in thread
        return await asyncio.to_thread(self._verify_sync, context)

    def _verify_sync(self, context: Dict[str, Any]) -> Dict[str, Any]:
        parsed = context.get("parsed", {}) or {}
        discrepancies = context.get("discrepancies", {}) or {}
        parsed_text = "\n".join(p.get("text", "") for p in parsed.get("pages", []))

        score = 0.0
        findings = []

        # 1) Suspicious keywords
        lowered = parsed_text.lower()
        for kw in self.SUSPICIOUS_KEYWORDS:
            if kw in lowered:
                score += 0.3
                findings.append(f"keyword:{kw}")

        # 2) discrepancies: suspicious segments
        segs = discrepancies.get("suspicious_segments", []) or []
        if segs:
            score += min(0.5, 0.2 * len(segs))
            findings.append(f"suspicious_segments:{len(segs)}")

        # 3) hidden text detection flag or layout anomalies
        if discrepancies.get("hidden_text_detected"):
            score += 0.25
            findings.append("hidden_text_detected")

        layout = discrepancies.get("layout_anomalies") or {}
        if layout:
            score += 0.1
            findings.append("layout_anomalies")

        # normalize
        confidence = max(0.0, min(1.0, score))
        suspicious = confidence >= 0.5

        explanation = ", ".join(findings) if findings else "no suspicious heuristics matched"

        return {"suspicious": suspicious, "explanation": explanation, "confidence": float(confidence)}

