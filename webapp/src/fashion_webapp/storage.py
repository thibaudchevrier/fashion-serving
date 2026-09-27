"""Uploaded images and their predictions, stored as ``<id>.jpg`` + ``<id>.json`` files."""

import io
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True)
class StoredImage:
    """An uploaded image and its predictions (``None`` until the model has answered)."""

    image_id: str
    image_path: Path
    predictions: dict[str, Any] | None


class ImageStore:
    """Flat directory of ``<id>.jpg`` images and ``<id>.json`` predictions."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_upload(self, data: bytes, max_side: int) -> tuple[str, bytes]:
        """Normalize an upload (EXIF rotation, RGB, downscale) and save it as JPEG.

        Returns the new image id and the JPEG bytes that were stored, which are
        exactly what gets sent to the model so masks line up with the stored file.
        """
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            img.thumbnail((max_side, max_side))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=90)
        image_id = uuid.uuid4().hex
        jpeg = buffer.getvalue()
        self.image_path(image_id).write_bytes(jpeg)
        return image_id, jpeg

    def save_predictions(self, image_id: str, predictions: dict[str, Any]) -> None:
        """Store the model response for an image."""
        self._predictions_path(image_id).write_text(json.dumps(predictions))

    def get(self, image_id: str) -> StoredImage | None:
        """Return the image with its predictions, or ``None`` if the id is invalid or unknown."""
        if not self.is_valid_id(image_id) or not self.image_path(image_id).exists():
            return None
        path = self._predictions_path(image_id)
        predictions = json.loads(path.read_text()) if path.exists() else None
        return StoredImage(image_id, self.image_path(image_id), predictions)

    def list(self) -> list[StoredImage]:
        """Most recent first."""
        paths = sorted(self.root.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [img for p in paths if (img := self.get(p.stem)) is not None]

    def delete(self, image_id: str) -> None:
        """Remove an image and its predictions; unknown ids are ignored."""
        if self.is_valid_id(image_id):
            self.image_path(image_id).unlink(missing_ok=True)
            self._predictions_path(image_id).unlink(missing_ok=True)

    def image_path(self, image_id: str) -> Path:
        """Location of the JPEG for ``image_id`` (which must be a valid id)."""
        return self.root / f"{image_id}.jpg"

    def _predictions_path(self, image_id: str) -> Path:
        return self.root / f"{image_id}.json"

    @staticmethod
    def is_valid_id(image_id: str) -> bool:
        """Ids are uuid4 hex strings; this also rules out path traversal."""
        return bool(_ID_PATTERN.match(image_id))
