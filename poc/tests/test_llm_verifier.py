"""Tests for LLMVerifier fallback behavior when Azure SDK or creds are missing."""
from __future__ import annotations

import asyncio

from poc.detector.llm_verifier import LLMVerifier


def test_llm_verifier_fallback_sync():
    verifier = LLMVerifier(endpoint=None, key=None)
    # call verify and ensure the fallback dict shape
    coro = verifier.verify({"parsed": {"pages": [{"text": "hello"}]}})
    res = asyncio.get_event_loop().run_until_complete(coro)
    assert isinstance(res, dict)
    assert "suspicious" in res and "explanation" in res and "confidence" in res
    assert res["suspicious"] is False
