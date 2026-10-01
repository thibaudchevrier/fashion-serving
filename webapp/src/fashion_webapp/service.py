"""The webapp's use cases, independent of the web framework, HTTP and files.

Upload (a file or an image URL), analyse, describe the garments (with their colors), cut a garment
out, draw the overlay. They drive three ports, implemented by the adapters and wired by
``create_app``:

- ``Inference``: the model (``fashion_webapp.inference.InferenceClient``, over HTTP);
- ``ImageStore``: uploaded images and their predictions (``fashion_webapp.storage``, on disk);
- ``ImageFetcher``: images downloaded from a URL (``fashion_webapp.fetching``).

The web layers (``fashion_webapp.api``, ``fashion_webapp.pages``) only translate HTTP requests
into these calls and their outcomes into responses.
"""

from dataclasses import dataclass
from pathlib import PurePath
from typing import Literal, Protocol

from fashion_seg_contract.request import DEFAULT_MIN_SCORE
from fashion_seg_contract.schema import Instance, Prediction

from fashion_webapp.palette import Swatch
from fashion_webapp.rendering import class_color, garment_colors, render_cutout, render_overlay

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
# The iMaterialist classes come in three blocks (model class id = dataset category + 1): whole
# garments, then accessories, then garment parts and decorations.
LAST_GARMENT_CLASS, LAST_ACCESSORY_CLASS = 13, 27
Group = Literal["garment", "accessory", "part"]


class InferenceUnavailable(RuntimeError):
    """The model is unreachable or answered with an unexpected response."""


class UnsupportedFile(ValueError):
    """The uploaded file's extension is not an image format the app accepts."""


class UnreadableImage(ValueError):
    """The uploaded file could not be decoded as an image."""


class UrlRejected(ValueError):
    """An image URL was refused or could not be downloaded; the message says why."""


@dataclass(frozen=True)
class StoredImage:
    """An uploaded image and its predictions.

    Attributes
    ----------
    image_id : str
        Image id.
    predictions : Prediction | None
        The model's response, or ``None`` until the model has answered.
    """

    image_id: str
    predictions: Prediction | None


@dataclass(frozen=True)
class Settings:
    """What the use cases need to know.

    Attributes
    ----------
    min_score : float
        Minimum detection confidence asked to the model: every detection above it is stored, so
        a viewer can lower its own threshold without asking the model again.
    max_image_side : int
        Uploads are downscaled so their largest side is at most this, in pixels.
    display_min_score : float
        Default confidence threshold for showing a detection. By default the contract's.
    """

    min_score: float
    max_image_side: int
    display_min_score: float = DEFAULT_MIN_SCORE


@dataclass(frozen=True)
class Upload:
    """Outcome of an upload.

    Attributes
    ----------
    image_id : str
        Id of the stored image.
    analysed : bool
        Whether the model answered; ``False`` keeps the image for a later ``analyse``.
    """

    image_id: str
    analysed: bool


@dataclass(frozen=True)
class Garment:
    """One detected garment: the model's instance, and what the webapp adds to it.

    Attributes
    ----------
    index : int
        Position in the model's response (identifies the garment within its image).
    instance : Instance
        The model's detection: class, label, score, box and mask (see the contract).
    group : Group
        ``"garment"``, ``"accessory"`` or ``"part"`` (see ``group_of``).
    color : str
        The class's display color, ``#rrggbb``.
    palette : list[Swatch]
        The garment's dominant colors.
    """

    index: int
    instance: Instance
    group: Group
    color: str
    palette: list[Swatch]


@dataclass(frozen=True)
class ImageDetails:
    """An image and its garments.

    Attributes
    ----------
    image_id : str
        Image id.
    analysed : bool
        Whether the model has answered for this image.
    width : int | None
        Width in pixels, once analysed.
    height : int | None
        Height in pixels, once analysed.
    garments : list[Garment]
        Detected garments, most confident first (empty until analysed).
    """

    image_id: str
    analysed: bool
    width: int | None
    height: int | None
    garments: list[Garment]


class Inference(Protocol):
    """The model: one encoded image in, its prediction out."""

    def predict(self, image: bytes, min_score: float) -> Prediction:
        """Segment the garments in one encoded image.

        Parameters
        ----------
        image : bytes
            Encoded image (JPEG or PNG).
        min_score : float
            Minimum detection confidence to return.

        Returns
        -------
        Prediction
            The model's response (see ``fashion_seg_contract.schema``); raises
            ``InferenceUnavailable`` when the model can't answer.
        """


class ImageStore(Protocol):
    """Uploaded images and their predictions."""

    def save_upload(self, data: bytes, max_side: int) -> tuple[str, bytes]:
        """Normalize and store an uploaded image.

        Parameters
        ----------
        data : bytes
            The uploaded file.
        max_side : int
            Largest allowed width or height; bigger images are downscaled.

        Returns
        -------
        tuple[str, bytes]
            The new image id, and the stored image's bytes (what the model must see); raises
            ``UnreadableImage`` if ``data`` is not an image.
        """

    def save_predictions(self, image_id: str, predictions: Prediction) -> None:
        """Store the model's response for an image.

        Parameters
        ----------
        image_id : str
            Id of a stored image.
        predictions : Prediction
            The model's response.
        """

    def get(self, image_id: str) -> StoredImage | None:
        """Look up an image.

        Parameters
        ----------
        image_id : str
            Image id (untrusted).

        Returns
        -------
        StoredImage | None
            The image, or ``None`` if the id is invalid or unknown.
        """

    def read(self, image_id: str) -> bytes | None:
        """Read a stored image's bytes.

        Parameters
        ----------
        image_id : str
            Image id (untrusted).

        Returns
        -------
        bytes | None
            The stored image, or ``None`` if the id is invalid or unknown.
        """

    def list(self) -> list[StoredImage]:
        """List every stored image.

        Returns
        -------
        list[StoredImage]
            Stored images, most recent first.
        """

    def delete(self, image_id: str) -> None:
        """Remove an image and its predictions; unknown or invalid ids are ignored.

        Parameters
        ----------
        image_id : str
            Image id (untrusted).
        """


class ImageFetcher(Protocol):
    """Images downloaded from the web."""

    def fetch(self, url: str) -> bytes:
        """Download an image.

        Parameters
        ----------
        url : str
            Image URL (untrusted).

        Returns
        -------
        bytes
            The downloaded file; raises ``UrlRejected`` when the URL is refused or the download
            fails.
        """


def group_of(class_id: int) -> Group:
    """Tell which kind of item a class is: a whole garment, an accessory, or a garment part.

    Parameters
    ----------
    class_id : int
        Model class id (dataset category + 1).

    Returns
    -------
    Group
        ``"garment"`` (shirt to cape), ``"accessory"`` (glasses to umbrella) or ``"part"`` (hood
        to tassel: parts, closures and decorations).

    Examples
    --------
    >>> group_of(2), group_of(24), group_of(32)  # top, shoe, sleeve
    ('garment', 'accessory', 'part')
    """
    if class_id <= LAST_GARMENT_CLASS:
        return "garment"
    return "accessory" if class_id <= LAST_ACCESSORY_CLASS else "part"


def check_extension(filename: str) -> None:
    """Refuse files whose extension is not a supported image format.

    Parameters
    ----------
    filename : str
        Name of the uploaded file.

    Raises
    ------
    UnsupportedFile
        If the extension is not in ``SUPPORTED_EXTENSIONS``.

    Examples
    --------
    >>> check_extension("photo.JPG")
    """
    if PurePath(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFile(filename)


def analyse(store: ImageStore, inference: Inference, image_id: str, settings: Settings) -> bool:
    """Ask the model for an image's predictions and store them.

    Parameters
    ----------
    store : ImageStore
        Stored images.
    inference : Inference
        The model.
    image_id : str
        Image id (untrusted).
    settings : Settings
        Minimum detection confidence.

    Returns
    -------
    bool
        ``True`` if the model answered, ``False`` if it is unavailable (the image is kept).

    Raises
    ------
    LookupError
        If the image is unknown.
    """
    image = store.read(image_id)
    if image is None:
        raise LookupError(image_id)
    try:
        store.save_predictions(image_id, inference.predict(image, settings.min_score))
    except InferenceUnavailable:
        return False
    return True


def upload(
    store: ImageStore, inference: Inference, file: tuple[str, bytes], settings: Settings
) -> Upload:
    """Store an uploaded image, then ask the model for its predictions.

    Parameters
    ----------
    store : ImageStore
        Stored images.
    inference : Inference
        The model.
    file : tuple[str, bytes]
        The uploaded file's name and content.
    settings : Settings
        Upload size limit and minimum detection confidence.

    Returns
    -------
    Upload
        The new image's id, and whether the model answered. Unsupported or unreadable files
        raise ``UnsupportedFile`` or ``UnreadableImage`` (from the store), and nothing is stored.
    """
    filename, data = file
    check_extension(filename)
    return _store_and_analyse(store, inference, data, settings)


def upload_from_url(
    store: ImageStore, inference: Inference, fetcher: ImageFetcher, url: str, settings: Settings
) -> Upload:
    """Download an image from the web, store it, then ask the model for its predictions.

    Parameters
    ----------
    store : ImageStore
        Stored images.
    inference : Inference
        The model.
    fetcher : ImageFetcher
        Downloads the image.
    url : str
        Image URL (untrusted).
    settings : Settings
        Upload size limit and minimum detection confidence.

    Returns
    -------
    Upload
        The new image's id, and whether the model answered. A refused or failed download raises
        ``UrlRejected`` (from the fetcher), a non-image ``UnreadableImage`` (from the store).
    """
    return _store_and_analyse(store, inference, fetcher.fetch(url), settings)


def _store_and_analyse(
    store: ImageStore, inference: Inference, data: bytes, settings: Settings
) -> Upload:
    """Store an image, then ask the model for its predictions.

    Parameters
    ----------
    store : ImageStore
        Stored images.
    inference : Inference
        The model.
    data : bytes
        The image file.
    settings : Settings
        Upload size limit and minimum detection confidence.

    Returns
    -------
    Upload
        The new image's id, and whether the model answered.
    """
    image_id, _ = store.save_upload(data, settings.max_image_side)
    return Upload(image_id, analyse(store, inference, image_id, settings))


def details(store: ImageStore, image_id: str) -> ImageDetails | None:
    """Describe an image's garments, with their colors.

    Parameters
    ----------
    store : ImageStore
        Stored images.
    image_id : str
        Image id (untrusted).

    Returns
    -------
    ImageDetails | None
        The image and its garments (none until analysed), or ``None`` if the image is unknown.
    """
    stored, image = store.get(image_id), store.read(image_id)
    if stored is None or image is None:
        return None
    predictions = stored.predictions
    if predictions is None:
        return ImageDetails(image_id, analysed=False, width=None, height=None, garments=[])
    palettes = garment_colors(image, predictions)
    garments = [
        Garment(
            index,
            inst,
            group_of(inst["class_id"]),
            _hex(class_color(inst["class_id"])),
            palettes[index],
        )
        for index, inst in enumerate(predictions["instances"])
    ]
    garments.sort(key=lambda g: g.instance["score"], reverse=True)
    return ImageDetails(
        image_id,
        analysed=True,
        width=predictions["width"],
        height=predictions["height"],
        garments=garments,
    )


def cutout(store: ImageStore, image_id: str, index: int) -> bytes | None:
    """Cut one garment out of its image (transparent PNG of its box).

    Parameters
    ----------
    store : ImageStore
        Stored images.
    image_id : str
        Image id (untrusted).
    index : int
        Garment index, as in ``Garment.index`` (untrusted).

    Returns
    -------
    bytes | None
        The cutout, or ``None`` if the image is unknown, not analysed, or has no such garment.
    """
    stored, image = store.get(image_id), store.read(image_id)
    if stored is None or image is None or stored.predictions is None:
        return None
    if not 0 <= index < len(stored.predictions["instances"]):
        return None
    return render_cutout(image, stored.predictions, index)


def overlay(store: ImageStore, image_id: str, min_score: float = 0.0) -> bytes | None:
    """Draw an image's predictions on it.

    Parameters
    ----------
    store : ImageStore
        Stored images.
    image_id : str
        Image id (untrusted).
    min_score : float
        Only detections at least this confident are drawn. By default 0 (all of them).

    Returns
    -------
    bytes | None
        The annotated image (PNG), or ``None`` if the image is unknown or not analysed yet.
    """
    stored, image = store.get(image_id), store.read(image_id)
    if stored is None or image is None or stored.predictions is None:
        return None
    shown = [i for i in stored.predictions["instances"] if i["score"] >= min_score]
    return render_overlay(image, {**stored.predictions, "instances": shown})


def _hex(rgb: tuple[int, int, int]) -> str:
    """Write a color as ``#rrggbb``.

    Parameters
    ----------
    rgb : tuple[int, int, int]
        The color's channels.

    Returns
    -------
    str
        The color.

    Examples
    --------
    >>> _hex((31, 42, 77))
    '#1f2a4d'
    """
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"
