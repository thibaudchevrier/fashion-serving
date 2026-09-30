"""The server-rendered page (``/``): the gallery, with forms to upload, analyse and delete.

Routes hold no logic of their own: they call a use case, then redirect to the page with a message
when something went wrong. Detections below the default threshold are not listed.
"""

from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from fashion_webapp import service
from fashion_webapp.rendering import class_color
from fashion_webapp.service import ImageStore, Inference, Settings

UNAVAILABLE = "The model is unavailable right now; the image was kept, retry later."
TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")


def back(message: str | None = None, overlay: str = "1") -> RedirectResponse:
    """Redirect to the page (303: the browser then loads it with a GET).

    Parameters
    ----------
    message : str | None
        Error to show on the page. By default ``None``.
    overlay : str
        ``"1"`` to show the predictions, ``"0"`` the original photos. By default ``"1"``.

    Returns
    -------
    RedirectResponse
        The redirect.
    """
    query = {"overlay": overlay} | ({"error": message} if message else {})
    return RedirectResponse(f"/?{urlencode(query)}", status_code=303)


def build_router(
    store: ImageStore, inference: Inference, settings: Settings, max_upload_bytes: int
) -> APIRouter:
    """Build the page's routes, bound to the given adapters.

    Parameters
    ----------
    store : ImageStore
        Stored images.
    inference : Inference
        The model.
    settings : Settings
        Use-case settings.
    max_upload_bytes : int
        Largest accepted upload.

    Returns
    -------
    APIRouter
        The routes.
    """
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    def index(request: Request, overlay: str = "1", error: str | None = None) -> Response:
        """Show every uploaded photo, with its predictions unless ``?overlay=0``.

        Parameters
        ----------
        request : Request
            The request (the template builds URLs from it).
        overlay : str
            ``"1"`` to show the predictions, ``"0"`` the original photos. By default ``"1"``.
        error : str | None
            Message of a failed action. By default ``None``.

        Returns
        -------
        Response
            The rendered page.
        """
        images = [
            {
                "image_id": img.image_id,
                "analysed": img.predictions is not None,
                "instances": [
                    i
                    for i in (img.predictions or {"instances": []})["instances"]
                    if i["score"] >= settings.display_min_score
                ],
            }
            for img in store.list()
        ]
        context = {"images": images, "overlay": overlay == "1", "error": error}
        context["class_color"] = class_color
        return TEMPLATES.TemplateResponse(request, "index.html", context)

    @router.post("/upload")
    def upload(
        file: Annotated[UploadFile, File()], overlay: Annotated[str, Form()] = "1"
    ) -> RedirectResponse:
        """Store an uploaded photo, then ask the model for its predictions.

        Parameters
        ----------
        file : Annotated[UploadFile, File()]
            The photo.
        overlay : Annotated[str, Form()]
            The page's overlay choice, kept across the redirect. By default ``"1"``.

        Returns
        -------
        RedirectResponse
            Redirect to the page, with a message if something went wrong.
        """
        data = file.file.read(max_upload_bytes + 1)
        if len(data) > max_upload_bytes:
            return back("The file is too large.", overlay)
        try:
            outcome = service.upload(store, inference, (file.filename or "", data), settings)
        except service.UnsupportedFile:
            return back(f"Unsupported file type: {file.filename}", overlay)
        except service.UnreadableImage:
            return back(f"Could not read {file.filename} as an image.", overlay)
        return back(None if outcome.analysed else UNAVAILABLE, overlay)

    @router.post("/images/{image_id}/predict")
    def predict(image_id: str) -> Response:
        """Ask the model again, e.g. after it was unavailable during the upload.

        Parameters
        ----------
        image_id : str
            Image id.

        Returns
        -------
        Response
            Redirect to the page, or 404 for an unknown image.
        """
        try:
            answered = service.analyse(store, inference, image_id, settings)
        except LookupError:
            return Response("Unknown image.", status_code=404)
        return back(None if answered else UNAVAILABLE)

    @router.post("/images/{image_id}/delete")
    def delete(image_id: str, overlay: Annotated[str, Form()] = "1") -> RedirectResponse:
        """Delete a photo and its predictions.

        Parameters
        ----------
        image_id : str
            Image id.
        overlay : Annotated[str, Form()]
            The page's overlay choice, kept across the redirect. By default ``"1"``.

        Returns
        -------
        RedirectResponse
            Redirect to the page.
        """
        store.delete(image_id)
        return back(overlay=overlay)

    return router
