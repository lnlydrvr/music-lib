"""Web UI — локальный FastAPI-сервер + браузерный фронтенд."""
from __future__ import annotations

from .server import create_app

__all__ = ["create_app"]