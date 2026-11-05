"""Vercel serverless entrypoint.

Vercel's Python runtime looks for an ASGI `app` in api/index.py.
The real application lives in app/main.py; this shim puts the project
root on sys.path and re-exports it. All requests are rewritten to this
function by vercel.json, so FastAPI serves both the API and the static
UI exactly as it does locally — just without a always-on server.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app  # noqa: E402,F401
