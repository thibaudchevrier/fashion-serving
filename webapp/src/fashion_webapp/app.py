"""The composition root of the web front-end: ``create_app``.

``create_app`` reads the settings, builds the adapters (the HTTP inference client, the image store
on disk, the URL fetcher) and binds them to the JSON API (``fashion_webapp.api``, under ``/api``)
and the page (``fashion_webapp.pages``), which call the use cases (``fashion_webapp.service``).
Served by uvicorn: ``uvicorn --factory fashion_webapp.app:create_app``.
"""

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from fashion_webapp import api, pages
from fashion_webapp.fetching import UrlFetcher
from fashion_webapp.inference import InferenceClient
from fashion_webapp.service import Settings
from fashion_webapp.storage import FileImageStore

# Detections stored for each image: enough to lower the threshold in the browser.
DEFAULT_STORED_MIN_SCORE = 0.3


def settings_from(env: dict[str, Any]) -> tuple[Settings, int]:
    """Read the use-case settings and the upload limit.

    Parameters
    ----------
    env : dict[str, Any]
        Environment variables, possibly overridden (e.g. in tests).

    Returns
    -------
    tuple[Settings, int]
        The use-case settings, and the largest accepted upload in bytes.

    Examples
    --------
    >>> settings, limit = settings_from({"MIN_SCORE": "0.5"})
    >>> settings.min_score, settings.display_min_score, limit
    (0.5, 0.7, 20971520)
    """
    defaults = Settings(min_score=DEFAULT_STORED_MIN_SCORE, max_image_side=800)
    settings = Settings(
        min_score=float(env.get("MIN_SCORE", defaults.min_score)),
        max_image_side=int(env.get("MAX_IMAGE_SIDE", defaults.max_image_side)),
        display_min_score=float(env.get("DISPLAY_MIN_SCORE", defaults.display_min_score)),
    )
    return settings, int(env.get("MAX_UPLOAD_BYTES", 20 * 2**20))


def create_app(config: dict[str, Any] | None = None) -> FastAPI:
    """Build the web app.

    Settings come from environment variables: ``INFERENCE_URL``, ``UPLOAD_DIR``, ``MIN_SCORE``
    (lowest confidence stored), ``DISPLAY_MIN_SCORE`` (default threshold shown),
    ``MAX_IMAGE_SIDE`` and ``MAX_UPLOAD_BYTES``.

    Parameters
    ----------
    config : dict[str, Any] | None
        Overrides of the settings, e.g. in tests; ``INFERENCE_CLIENT`` replaces the HTTP client
        (any ``fashion_webapp.service.Inference``), ``IMAGE_FETCHER`` the URL fetcher (any
        ``fashion_webapp.service.ImageFetcher``). By default ``None``.

    Returns
    -------
    FastAPI
        The configured application.
    """
    env: dict[str, Any] = {**os.environ, **(config or {})}
    settings, max_upload_bytes = settings_from(env)
    store = FileImageStore(env.get("UPLOAD_DIR", "uploads"))
    inference = env.get("INFERENCE_CLIENT") or InferenceClient(
        env.get("INFERENCE_URL", "http://localhost:5001")
    )
    fetcher = env.get("IMAGE_FETCHER") or UrlFetcher(max_bytes=max_upload_bytes)

    app = FastAPI(
        title="Fashion segmentation",
        description="Upload a photo or an image URL; get its garments, their masks and colors.",
    )
    app.include_router(
        api.build_router(store, inference, fetcher, settings, max_upload_bytes), prefix="/api"
    )
    app.include_router(pages.build_router(store, inference, settings, max_upload_bytes))
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Report that the app is up (used by Docker healthchecks and the smoke test).

        Returns
        -------
        dict[str, str]
            ``{"status": "ok"}``.
        """
        return {"status": "ok"}

    return app
