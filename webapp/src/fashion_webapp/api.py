"""JSON API (``/api``): FastAPI routes translating requests into use cases (``service``).

Routes hold no logic of their own: they call a use case and turn its outcome, or its error, into
a response. The models below are the API's schema (served at ``/docs``).
"""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from fashion_webapp import service
from fashion_webapp.service import Group, ImageFetcher, ImageStore, Inference, Settings

JPEG, PNG = "image/jpeg", "image/png"


class Config(BaseModel):
    """What a client needs to know about this server.

    Attributes
    ----------
    min_score : float
        Lowest confidence stored: a threshold below it shows nothing more.
    default_threshold : float
        Confidence threshold shown by default.
    max_upload_bytes : int
        Largest accepted upload or download.
    """

    min_score: float
    default_threshold: float
    max_upload_bytes: int


class Swatch(BaseModel):
    """One dominant color of a garment.

    Attributes
    ----------
    hex : str
        The color, ``#rrggbb``.
    name : str
        The nearest named color.
    share : float
        Fraction of the garment's pixels, between 0 and 1.
    """

    hex: str = Field(examples=["#1f2a4d"])
    name: str = Field(examples=["navy"])
    share: float


class Garment(BaseModel):
    """One detected garment.

    Attributes
    ----------
    index : int
        Identifies the garment within its image.
    class_id : int
        Model class id.
    label : str
        Class name.
    group : Group
        Kind of item: a whole garment, an accessory, or a garment part or decoration.
    score : float
        Detection confidence, between 0 and 1.
    box : list[int]
        ``[y1, x1, y2, x2]`` in image pixels, ``(y2, x2)`` excluded.
    mask_rle : str
        Run-length encoded mask: space-separated ``start length`` pairs, 1-indexed, pixels
        enumerated column by column.
    color : str
        The class's display color, ``#rrggbb``.
    palette : list[Swatch]
        The garment's dominant colors, most common first.
    """

    index: int
    class_id: int
    label: str
    group: Group
    score: float
    box: list[int]
    mask_rle: str
    color: str
    palette: list[Swatch]


class ImageSummary(BaseModel):
    """An image in the gallery.

    Attributes
    ----------
    id : str
        Image id.
    analysed : bool
        Whether the model has answered for this image.
    garment_count : int
        Detections above the default threshold.
    """

    id: str
    analysed: bool
    garment_count: int


class ImageDetails(BaseModel):
    """An image and its garments.

    Attributes
    ----------
    id : str
        Image id.
    analysed : bool
        Whether the model has answered for this image.
    width : int | None
        Width in pixels, once analysed.
    height : int | None
        Height in pixels, once analysed.
    garments : list[Garment]
        Detected garments, most confident first.
    """

    id: str
    analysed: bool
    width: int | None
    height: int | None
    garments: list[Garment]


class UrlUpload(BaseModel):
    """An image to download.

    Attributes
    ----------
    url : str
        The image's address: http or https, on a public host.
    """

    url: str = Field(examples=["https://example.com/outfit.jpg"])


def _details(details: service.ImageDetails) -> ImageDetails:
    """Convert the use case's record into the API model.

    Parameters
    ----------
    details : service.ImageDetails
        The use case's record.

    Returns
    -------
    ImageDetails
        The API model.
    """
    return ImageDetails(
        id=details.image_id,
        analysed=details.analysed,
        width=details.width,
        height=details.height,
        garments=[
            Garment(
                index=g.index,
                class_id=g.instance["class_id"],
                label=g.instance["label"],
                group=g.group,
                score=g.instance["score"],
                box=list(g.instance["box"]),
                mask_rle=g.instance["mask_rle"],
                color=g.color,
                palette=[Swatch(hex=s.hex, name=s.name, share=s.share) for s in g.palette],
            )
            for g in details.garments
        ],
    )


def build_router(  # pylint: disable=too-many-locals  # one nested function per route
    store: ImageStore,
    inference: Inference,
    fetcher: ImageFetcher,
    settings: Settings,
    max_upload_bytes: int,
) -> APIRouter:
    """Build the API's routes, bound to the given adapters.

    Parameters
    ----------
    store : ImageStore
        Stored images.
    inference : Inference
        The model.
    fetcher : ImageFetcher
        Downloads images from URLs.
    settings : Settings
        Use-case settings.
    max_upload_bytes : int
        Largest accepted upload.

    Returns
    -------
    APIRouter
        The routes, to mount under ``/api``.
    """
    router = APIRouter()

    def found(image_id: str) -> ImageDetails:
        """Describe an image, or answer 404.

        Parameters
        ----------
        image_id : str
            Image id (untrusted).

        Returns
        -------
        ImageDetails
            The image and its garments.

        Raises
        ------
        HTTPException
            404 if the image is unknown.
        """
        details = service.details(store, image_id)
        if details is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown image.")
        return _details(details)

    def stored(upload: service.Upload) -> Response:
        """Answer an upload: the new image, 201, with a header when the model was unavailable.

        Parameters
        ----------
        upload : service.Upload
            Outcome of the upload.

        Returns
        -------
        Response
            JSON of the image's details.
        """
        body = found(upload.image_id).model_dump_json()
        headers = {} if upload.analysed else {"X-Model-Unavailable": "true"}
        return Response(body, status.HTTP_201_CREATED, headers, media_type="application/json")

    @router.get("/config")
    def config() -> Config:
        """Describe this server's settings.

        Returns
        -------
        Config
            Thresholds and limits.
        """
        return Config(
            min_score=settings.min_score,
            default_threshold=settings.display_min_score,
            max_upload_bytes=max_upload_bytes,
        )

    @router.get("/images")
    def list_images() -> list[ImageSummary]:
        """List the stored images, most recent first.

        Returns
        -------
        list[ImageSummary]
            The gallery.
        """
        return [
            ImageSummary(
                id=img.image_id,
                analysed=img.predictions is not None,
                garment_count=sum(
                    inst["score"] >= settings.display_min_score
                    for inst in (img.predictions or {"instances": []})["instances"]
                ),
            )
            for img in store.list()
        ]

    @router.post("/images", status_code=status.HTTP_201_CREATED, response_model=ImageDetails)
    def upload(file: Annotated[UploadFile, File()]) -> Response:
        """Store an uploaded photo, then ask the model for its garments.

        Parameters
        ----------
        file : Annotated[UploadFile, File()]
            The photo (multipart form field ``file``).

        Returns
        -------
        Response
            The new image (201); header ``X-Model-Unavailable`` if the model did not answer
            (the image is kept: retry with ``POST /api/images/{id}/analyse``).

        Raises
        ------
        HTTPException
            413 if too large, 415 for an unsupported type, 422 if not an image.
        """
        data = file.file.read(max_upload_bytes + 1)
        if len(data) > max_upload_bytes:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The file is too large.")
        try:
            outcome = service.upload(store, inference, (file.filename or "", data), settings)
        except service.UnsupportedFile as exc:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported file type."
            ) from exc
        except service.UnreadableImage as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Not a readable image."
            ) from exc
        return stored(outcome)

    @router.post(
        "/images/from-url", status_code=status.HTTP_201_CREATED, response_model=ImageDetails
    )
    def upload_url(body: UrlUpload) -> Response:
        """Download an image from the web, store it, then ask the model for its garments.

        Parameters
        ----------
        body : UrlUpload
            The image URL.

        Returns
        -------
        Response
            The new image (201), as for ``POST /api/images``.

        Raises
        ------
        HTTPException
            400 if the URL is refused or the download fails, 422 if it is not an image.
        """
        try:
            outcome = service.upload_from_url(store, inference, fetcher, body.url, settings)
        except service.UrlRejected as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        except service.UnreadableImage as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Not a readable image."
            ) from exc
        return stored(outcome)

    @router.get("/images/{image_id}")
    def get_image(image_id: str) -> ImageDetails:
        """Describe an image's garments, with their colors.

        Parameters
        ----------
        image_id : str
            Image id.

        Returns
        -------
        ImageDetails
            The image and its garments, most confident first.
        """
        return found(image_id)

    @router.post("/images/{image_id}/analyse")
    def analyse(image_id: str) -> ImageDetails:
        """Ask the model again, e.g. after it was unavailable during the upload.

        Parameters
        ----------
        image_id : str
            Image id.

        Returns
        -------
        ImageDetails
            The image and its garments.

        Raises
        ------
        HTTPException
            404 for an unknown image, 503 if the model is still unavailable.
        """
        try:
            answered = service.analyse(store, inference, image_id, settings)
        except LookupError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown image.") from exc
        if not answered:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The model is unavailable.")
        return found(image_id)

    @router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete(image_id: str) -> None:
        """Delete an image and its predictions (unknown ids are ignored).

        Parameters
        ----------
        image_id : str
            Image id.
        """
        store.delete(image_id)

    @router.get("/images/{image_id}/image.jpg", response_class=Response)
    def image(image_id: str) -> Response:
        """Serve a stored photo.

        Parameters
        ----------
        image_id : str
            Image id.

        Returns
        -------
        Response
            The JPEG.

        Raises
        ------
        HTTPException
            404 for an unknown image.
        """
        jpeg = store.read(image_id)
        if jpeg is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown image.")
        return Response(jpeg, media_type=JPEG)

    @router.get("/images/{image_id}/overlay.png", response_class=Response)
    def overlay(image_id: str) -> Response:
        """Serve a photo with its detections above the default threshold drawn on it.

        Parameters
        ----------
        image_id : str
            Image id.

        Returns
        -------
        Response
            The PNG.

        Raises
        ------
        HTTPException
            404 for an unknown image or one not analysed yet.
        """
        png = service.overlay(store, image_id, settings.display_min_score)
        if png is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown or unanalysed image.")
        return Response(png, media_type=PNG)

    @router.get("/images/{image_id}/garments/{index}/cutout.png", response_class=Response)
    def cutout(image_id: str, index: int) -> Response:
        """Serve one garment cut out of its photo (transparent PNG of its box).

        Parameters
        ----------
        image_id : str
            Image id.
        index : int
            Garment index (``Garment.index``).

        Returns
        -------
        Response
            The PNG.

        Raises
        ------
        HTTPException
            404 for an unknown image or garment.
        """
        png = service.cutout(store, image_id, index)
        if png is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown image or garment.")
        return Response(png, media_type=PNG)

    return router
