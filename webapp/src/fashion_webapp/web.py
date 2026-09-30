"""HTTP layer: Flask routes translating requests into use cases (``fashion_webapp.service``).

Routes hold no logic of their own: they call a use case, then turn its outcome into a page, a
redirect, a file or a flash message.
"""

import io

from flask import Flask, abort, flash, redirect, render_template, request, send_file, url_for
from flask.typing import ResponseReturnValue

from fashion_webapp import service
from fashion_webapp.rendering import class_color
from fashion_webapp.service import ImageStore, Inference, Settings

UNAVAILABLE = "The model is unavailable right now; the image was kept, retry later."


def register_routes(
    app: Flask, store: ImageStore, inference: Inference, settings: Settings
) -> None:
    """Add the app's routes, bound to the given adapters.

    Parameters
    ----------
    app : Flask
        The application.
    store : ImageStore
        Stored images.
    inference : Inference
        The model.
    settings : Settings
        Use-case settings.
    """

    def back_to_page() -> ResponseReturnValue:
        """Redirect to the page, keeping the overlay choice of the submitted form.

        Returns
        -------
        ResponseReturnValue
            The redirect.
        """
        return redirect(url_for("index", overlay=request.form.get("overlay", "1")))

    @app.get("/")
    def index() -> ResponseReturnValue:
        """Show every uploaded photo, with its predictions unless ``?overlay=0``.

        Returns
        -------
        ResponseReturnValue
            The rendered page.
        """
        overlay = request.args.get("overlay", "1") == "1"
        return render_template(
            "index.html", images=store.list(), overlay=overlay, class_color=class_color
        )

    @app.post("/upload")
    def upload() -> ResponseReturnValue:
        """Store an uploaded photo, then ask the model for its predictions.

        Returns
        -------
        ResponseReturnValue
            Redirect to the page; problems are reported with flash messages.
        """
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Choose an image to upload.", "error")
            return back_to_page()
        try:
            outcome = service.upload(store, inference, (file.filename, file.read()), settings)
        except service.UnsupportedFile:
            flash(f"Unsupported file type: {file.filename}", "error")
        except service.UnreadableImage:
            flash(f"Could not read {file.filename} as an image.", "error")
        else:
            if not outcome.analysed:
                flash(UNAVAILABLE, "error")
        return back_to_page()

    @app.post("/images/<image_id>/predict")
    def predict(image_id: str) -> ResponseReturnValue:
        """Ask the model again, e.g. after it was unavailable during the upload.

        Parameters
        ----------
        image_id : str
            Image id from the URL.

        Returns
        -------
        ResponseReturnValue
            Redirect to the page, or 404 for an unknown image.
        """
        try:
            if not service.analyse(store, inference, image_id, settings):
                flash(UNAVAILABLE, "error")
        except LookupError:
            abort(404)
        return redirect(url_for("index"))

    @app.post("/images/<image_id>/delete")
    def delete(image_id: str) -> ResponseReturnValue:
        """Delete a photo and its predictions.

        Parameters
        ----------
        image_id : str
            Image id from the URL.

        Returns
        -------
        ResponseReturnValue
            Redirect to the page.
        """
        store.delete(image_id)
        return back_to_page()

    @app.get("/images/<image_id>.jpg")
    def image(image_id: str) -> ResponseReturnValue:
        """Serve a stored photo.

        Parameters
        ----------
        image_id : str
            Image id from the URL.

        Returns
        -------
        ResponseReturnValue
            The JPEG, or 404 for an unknown image.
        """
        jpeg = store.read(image_id) or abort(404)
        return send_file(io.BytesIO(jpeg), mimetype="image/jpeg")

    @app.get("/images/<image_id>/overlay.png")
    def overlay(image_id: str) -> ResponseReturnValue:
        """Serve a photo with its predictions drawn on it.

        Parameters
        ----------
        image_id : str
            Image id from the URL.

        Returns
        -------
        ResponseReturnValue
            The PNG, or 404 for an unknown image or one without predictions.
        """
        png = service.overlay(store, image_id) or abort(404)
        return send_file(io.BytesIO(png), mimetype="image/png")

    @app.get("/healthz")
    def healthz() -> ResponseReturnValue:
        """Report that the app is up (used by Docker healthchecks and the smoke test).

        Returns
        -------
        ResponseReturnValue
            ``{"status": "ok"}``.
        """
        return {"status": "ok"}
