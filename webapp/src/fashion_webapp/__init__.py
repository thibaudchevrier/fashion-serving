"""Web front-end: upload photos, segment clothes with the inference service, show results.

``create_app`` is the composition root: it reads the settings, builds the adapters (the HTTP
inference client, the image store on disk) and binds them to the routes (``fashion_webapp.web``),
which call the use cases (``fashion_webapp.service``).
"""

import os
from typing import Any

from fashion_seg_contract.request import DEFAULT_MIN_SCORE
from flask import Flask

from fashion_webapp.inference import InferenceClient
from fashion_webapp.service import Settings
from fashion_webapp.storage import FileImageStore
from fashion_webapp.web import register_routes


def create_app(config: dict[str, Any] | None = None) -> Flask:
    """Build the web app.

    Settings come from environment variables: ``SECRET_KEY``, ``INFERENCE_URL``, ``UPLOAD_DIR``,
    ``MIN_SCORE`` and ``MAX_IMAGE_SIDE``.

    Parameters
    ----------
    config : dict[str, Any] | None
        Overrides of the settings, e.g. in tests; ``INFERENCE_CLIENT`` replaces the HTTP client
        (any ``fashion_webapp.service.Inference``). By default ``None``.

    Returns
    -------
    Flask
        The configured application.
    """
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        INFERENCE_URL=os.environ.get("INFERENCE_URL", "http://localhost:5001"),
        UPLOAD_DIR=os.environ.get("UPLOAD_DIR", "uploads"),
        MIN_SCORE=float(os.environ.get("MIN_SCORE", DEFAULT_MIN_SCORE)),
        MAX_IMAGE_SIDE=int(os.environ.get("MAX_IMAGE_SIDE", "800")),
        MAX_CONTENT_LENGTH=20 * 1024 * 1024,
    )
    app.config.update(config or {})

    inference = app.config.get("INFERENCE_CLIENT") or InferenceClient(app.config["INFERENCE_URL"])
    settings = Settings(
        min_score=app.config["MIN_SCORE"], max_image_side=app.config["MAX_IMAGE_SIDE"]
    )
    register_routes(app, FileImageStore(app.config["UPLOAD_DIR"]), inference, settings)
    return app
