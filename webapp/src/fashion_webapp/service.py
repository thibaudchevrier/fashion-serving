"""The webapp's use cases, independent of Flask, HTTP and files: upload, analyse, draw, delete.

They drive two ports, implemented by the adapters and wired by ``create_app``:

- ``Inference``: the model (``fashion_webapp.inference.InferenceClient``, over HTTP);
- ``ImageStore``: uploaded images and their predictions (``fashion_webapp.storage``, on disk).

The web layer (``fashion_webapp.web``) only translates HTTP requests into these calls and their
outcomes into pages, redirects and messages.
"""

from dataclasses import dataclass
from pathlib import PurePath
from typing import Protocol

from fashion_seg_contract.schema import Prediction

from fashion_webapp.rendering import render_overlay

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


class InferenceUnavailable(RuntimeError):
    """The model is unreachable or answered with an unexpected response."""


class UnsupportedFile(ValueError):
    """The uploaded file's extension is not an image format the app accepts."""


class UnreadableImage(ValueError):
    """The uploaded file could not be decoded as an image."""


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
        Minimum detection confidence asked to the model.
    max_image_side : int
        Uploads are downscaled so their largest side is at most this, in pixels.
    """

    min_score: float
    max_image_side: int


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
    image_id, _ = store.save_upload(data, settings.max_image_side)
    return Upload(image_id, analyse(store, inference, image_id, settings))


def overlay(store: ImageStore, image_id: str) -> bytes | None:
    """Draw an image's predictions on it.

    Parameters
    ----------
    store : ImageStore
        Stored images.
    image_id : str
        Image id (untrusted).

    Returns
    -------
    bytes | None
        The annotated image (PNG), or ``None`` if the image is unknown or not analysed yet.
    """
    stored, image = store.get(image_id), store.read(image_id)
    if stored is None or image is None or stored.predictions is None:
        return None
    return render_overlay(image, stored.predictions)
