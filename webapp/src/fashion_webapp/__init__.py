"""Web front-end: upload photos, segment clothes with the inference service, show results."""

import io
import os

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from PIL import Image, UnidentifiedImageError

from fashion_webapp.inference import InferenceClient, InferenceError
from fashion_webapp.rendering import class_color, render_overlay
from fashion_webapp.storage import ImageStore

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def create_app(config: dict | None = None) -> Flask:
    """Build the app. Settings come from environment variables, overridable with ``config``."""
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        INFERENCE_URL=os.environ.get("INFERENCE_URL", "http://localhost:5001"),
        UPLOAD_DIR=os.environ.get("UPLOAD_DIR", "uploads"),
        MIN_SCORE=float(os.environ.get("MIN_SCORE", "0.7")),
        MAX_IMAGE_SIDE=int(os.environ.get("MAX_IMAGE_SIDE", "800")),
        MAX_CONTENT_LENGTH=20 * 1024 * 1024,
    )
    app.config.update(config or {})

    store = ImageStore(app.config["UPLOAD_DIR"])
    client = app.config.get("INFERENCE_CLIENT") or InferenceClient(app.config["INFERENCE_URL"])

    @app.get("/")
    def index():
        overlay = request.args.get("overlay", "1") == "1"
        return render_template(
            "index.html", images=store.list(), overlay=overlay, class_color=class_color
        )

    @app.post("/upload")
    def upload():
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Choose an image to upload.", "error")
            return redirect(url_for("index"))
        if os.path.splitext(file.filename)[1].lower() not in ALLOWED_EXTENSIONS:
            flash(f"Unsupported file type: {file.filename}", "error")
            return redirect(url_for("index"))
        try:
            image_id, jpeg = store.save_upload(file.read(), app.config["MAX_IMAGE_SIDE"])
        except (UnidentifiedImageError, OSError):
            flash(f"Could not read {file.filename} as an image.", "error")
            return redirect(url_for("index"))
        _predict(image_id, jpeg)
        return redirect(url_for("index", overlay=request.form.get("overlay", "1")))

    @app.post("/images/<image_id>/predict")
    def predict(image_id: str):
        stored = store.get(image_id) or abort(404)
        _predict(image_id, stored.image_path.read_bytes())
        return redirect(url_for("index"))

    @app.post("/images/<image_id>/delete")
    def delete(image_id: str):
        store.delete(image_id)
        return redirect(url_for("index", overlay=request.form.get("overlay", "1")))

    @app.get("/images/<image_id>.jpg")
    def image(image_id: str):
        stored = store.get(image_id) or abort(404)
        return send_file(stored.image_path, mimetype="image/jpeg")

    @app.get("/images/<image_id>/overlay.png")
    def overlay(image_id: str):
        stored = store.get(image_id) or abort(404)
        if stored.predictions is None:
            abort(404)
        with Image.open(stored.image_path) as img:
            png = render_overlay(img, stored.predictions)
        return send_file(io.BytesIO(png), mimetype="image/png")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    def _predict(image_id: str, jpeg: bytes) -> None:
        try:
            store.save_predictions(image_id, client.predict(jpeg, app.config["MIN_SCORE"]))
        except InferenceError as exc:
            app.logger.warning("Prediction failed for %s: %s", image_id, exc)
            flash("The model is unavailable right now; the image was kept, retry later.", "error")

    return app
