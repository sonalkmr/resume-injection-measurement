"""Minimal UI stub for the PoC (placeholder).

This module is a simple script that can be extended to provide a web UI
or Streamlit-based interface. For the PoC we expose a tiny helper.
"""
from __future__ import annotations

from fastapi import FastAPI


def create_ui_app() -> FastAPI:
    app = FastAPI()

    @app.get("/")
    async def index():
        return {"message": "Resume Prompt Injection Detector UI placeholder"}

    return app
