"""Serving the built dashboard from the API process.

One container serves both the React app and the API, which means one URL, one
deployment and no CORS at all: the browser origin is already correct for every
call the dashboard makes.

The mount is conditional. A checkout with no `frontend/dist` still runs the API
normally, which is what local backend development and the test suite need.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import config

log = logging.getLogger(__name__)

DIST_DIR = config.ROOT / "frontend" / "dist"
# Prefixes that belong to the API. Anything else is handed to the single page
# app so client side routes survive a refresh or a pasted deep link.
API_PREFIXES = ("health", "model", "datasets", "telemetry", "recommendations",
                "docs", "redoc", "openapi.json")


def mount_dashboard(app: FastAPI) -> bool:
    """Serve frontend/dist if it was built. Returns whether anything mounted."""
    index = DIST_DIR / "index.html"
    if not index.is_file():
        log.info("no built dashboard at %s, serving the API only", DIST_DIR)
        return False

    # Hashed filenames, so these are safe to cache hard. Mounted at /static
    # rather than /assets because /assets/:id belongs to the dashboard's own
    # routing; see frontend/vite.config.js.
    built = DIST_DIR / "static"
    if built.is_dir():
        app.mount("/static", StaticFiles(directory=built), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard_root() -> FileResponse:
        return FileResponse(index)

    @app.get("/{path:path}", include_in_schema=False)
    def dashboard_catch_all(path: str):
        # Never swallow an API path: a wrong URL under the API should still 404
        # as itself rather than silently returning the dashboard HTML.
        if path.split("/", 1)[0] in API_PREFIXES:
            from fastapi import HTTPException
            raise HTTPException(404, f"no such API route: /{path}")
        candidate = (DIST_DIR / path).resolve()
        if candidate.is_file() and candidate.is_relative_to(DIST_DIR.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)

    log.info("dashboard mounted from %s", DIST_DIR)
    return True
