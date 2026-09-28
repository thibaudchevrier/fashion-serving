"""Uploaded images and their predictions, stored as ``<id>.jpg`` + ``<id>.json`` files.

Implements ``fashion_webapp.service.ImageStore`` on a local directory.
"""

import io
import json
import re
import uuid
from pathlib import Path

from fashion_seg_contract.schema import Prediction
from PIL import Image, ImageOps, UnidentifiedImageError

from fashion_webapp.service import StoredImage, UnreadableImage

_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class FileImageStore:
    """Flat directory of ``<id>.jpg`` images and ``<id>.json`` predictions.

    Parameters
    ----------
    root : str | Path
        Directory holding the files; created if missing.

    Attributes
    ----------
    root : Path
        Directory holding the files.
    """

    root: Path

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_upload(self, data: bytes, max_side: int) -> tuple[str, bytes]:
        """Normalize an upload (EXIF rotation, RGB, downscale) and save it as JPEG.

        Parameters
        ----------
        data : bytes
            The uploaded file.
        max_side : int
            Largest allowed width or height in pixels; bigger images are downscaled.

        Returns
        -------
        tuple[str, bytes]
            The new image id, and the JPEG bytes that were stored: exactly what gets sent to the
            model, so the returned masks line up with the stored file.

        Raises
        ------
        UnreadableImage
            If ``data`` is not an image Pillow can decode.
        """
        buffer = io.BytesIO()
        try:
            with Image.open(io.BytesIO(data)) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                img.thumbnail((max_side, max_side))
                img.save(buffer, format="JPEG", quality=90)
        except (UnidentifiedImageError, OSError) as exc:
            raise UnreadableImage(str(exc)) from exc
        image_id = uuid.uuid4().hex
        jpeg = buffer.getvalue()
        self._image_path(image_id).write_bytes(jpeg)
        return image_id, jpeg

    def save_predictions(self, image_id: str, predictions: Prediction) -> None:
        """Store the model's response for an image.

        Parameters
        ----------
        image_id : str
            Id of a stored image.
        predictions : Prediction
            The model's response for that image.
        """
        self._predictions_path(image_id).write_text(json.dumps(predictions))

    def get(self, image_id: str) -> StoredImage | None:
        """Look up an image and its predictions.

        Parameters
        ----------
        image_id : str
            Image id, as found in URLs (untrusted).

        Returns
        -------
        StoredImage | None
            The image, or ``None`` if the id is invalid or unknown.
        """
        if not self._exists(image_id):
            return None
        path = self._predictions_path(image_id)
        predictions = json.loads(path.read_text()) if path.exists() else None
        return StoredImage(image_id, predictions)

    def read(self, image_id: str) -> bytes | None:
        """Read a stored image's JPEG.

        Parameters
        ----------
        image_id : str
            Image id, as found in URLs (untrusted).

        Returns
        -------
        bytes | None
            The JPEG, or ``None`` if the id is invalid or unknown.
        """
        return self._image_path(image_id).read_bytes() if self._exists(image_id) else None

    def list(self) -> list[StoredImage]:
        """List every stored image.

        Returns
        -------
        list[StoredImage]
            Stored images, most recent first.
        """
        paths = sorted(self.root.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [img for p in paths if (img := self.get(p.stem)) is not None]

    def delete(self, image_id: str) -> None:
        """Remove an image and its predictions; unknown or invalid ids are ignored.

        Parameters
        ----------
        image_id : str
            Image id, as found in URLs (untrusted).
        """
        if self.is_valid_id(image_id):
            self._image_path(image_id).unlink(missing_ok=True)
            self._predictions_path(image_id).unlink(missing_ok=True)

    def _exists(self, image_id: str) -> bool:
        """Tell whether an id is valid and its image stored.

        Parameters
        ----------
        image_id : str
            Image id (untrusted).

        Returns
        -------
        bool
            Whether ``<id>.jpg`` exists for a well-formed id.
        """
        return self.is_valid_id(image_id) and self._image_path(image_id).exists()

    def _image_path(self, image_id: str) -> Path:
        """Locate the JPEG of an image.

        Parameters
        ----------
        image_id : str
            A valid image id.

        Returns
        -------
        Path
            Path of ``<id>.jpg``, whether or not it exists.
        """
        return self.root / f"{image_id}.jpg"

    def _predictions_path(self, image_id: str) -> Path:
        """Locate the predictions of an image.

        Parameters
        ----------
        image_id : str
            A valid image id.

        Returns
        -------
        Path
            Path of ``<id>.json``, whether or not it exists.
        """
        return self.root / f"{image_id}.json"

    @staticmethod
    def is_valid_id(image_id: str) -> bool:
        """Check that an id is a uuid4 hex string, which also rules out path traversal.

        Parameters
        ----------
        image_id : str
            Candidate image id.

        Returns
        -------
        bool
            Whether the id is well formed.

        Examples
        --------
        >>> FileImageStore.is_valid_id("0" * 32), FileImageStore.is_valid_id("../etc/passwd")
        (True, False)
        """
        return bool(_ID_PATTERN.match(image_id))
