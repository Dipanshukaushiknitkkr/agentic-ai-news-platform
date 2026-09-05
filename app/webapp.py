"""
Backward-compatibility root proxy for ASGI web servers (e.g. Render/Uvicorn calling app.webapp:app).
Re-exports the FastAPI app from backend.app.webapp.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.app.webapp import app