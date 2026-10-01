"""Shared test doubles: images, a fake model that honours the contract, a fake URL fetcher."""

import io

import numpy as np
import pytest
from fashion_seg_contract import rle, schema
from PIL import Image

from fashion_webapp.app import create_app
from fashion_webapp.service import InferenceUnavailable, UrlRejected

NAVY = (25, 35, 80)
# The fake model's garments: a confident navy dress, and a belt below the display threshold.
DRESS_BOX = [10, 20, 30, 60]
BELT_BOX = [40, 20, 44, 60]


def jpeg(width: int = 120, height: int = 80) -> bytes:
    """Encode a beige JPEG with a navy rectangle where the fake model finds the dress."""
    pixels = np.full((height, width, 3), (200, 180, 160), dtype=np.uint8)
    y1, x1, y2, x2 = DRESS_BOX
    pixels[y1:y2, x1:x2] = NAVY
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def _mask(height: int, width: int, box: list[int]) -> str:
    """Encode a rectangular mask filling a box."""
    mask = np.zeros((height, width), dtype=bool)
    y1, x1, y2, x2 = box
    mask[y1:y2, x1:x2] = True
    return rle.encode(mask)


class FakeModel:
    """Stand-in for ``InferenceClient``: a dress and a belt per image, or failures on demand.

    Attributes
    ----------
    fail : bool
        Whether ``predict`` raises ``InferenceUnavailable``.
    calls : list[float]
        The ``min_score`` of each call.
    """

    def __init__(self, fail: bool = False):
        """Start healthy (or failing) with no recorded calls."""
        self.fail = fail
        self.calls: list[float] = []

    def predict(self, image: bytes, min_score: float) -> dict:
        """Return a contract-valid prediction sized to the image, or raise if failing."""
        self.calls.append(min_score)
        if self.fail:
            raise InferenceUnavailable("down")
        with Image.open(io.BytesIO(image)) as img:
            width, height = img.size
        response = {
            "height": height,
            "width": width,
            "instances": [
                {
                    "class_id": 20,
                    "label": "belt",
                    "score": 0.42,
                    "box": BELT_BOX,
                    "mask_rle": _mask(height, width, BELT_BOX),
                },
                {
                    "class_id": 11,
                    "label": "dress",
                    "score": 0.93,
                    "box": DRESS_BOX,
                    "mask_rle": _mask(height, width, DRESS_BOX),
                },
            ],
        }
        # The fake must honour the contract, or these tests prove nothing about the real model.
        schema.validate(response)
        return response


class FakeFetcher:
    """Stand-in for ``UrlFetcher``: serves a dictionary of URLs, refuses the others."""

    def __init__(self, files: dict[str, bytes]):
        """Serve these files by URL."""
        self.files = files

    def fetch(self, url: str) -> bytes:
        """Return the file for a known URL, refuse any other."""
        if url not in self.files:
            raise UrlRejected(f"This address is not public: {url}")
        return self.files[url]


@pytest.fixture
def model():
    """Provide a healthy fake model."""
    return FakeModel()


@pytest.fixture
def make_app(tmp_path):
    """Build the app around given fakes, with uploads in a temporary directory."""

    def _make(model, fetcher=None, **config):
        """Create the app; extra keyword arguments override settings."""
        return create_app(
            {
                "UPLOAD_DIR": tmp_path,
                "INFERENCE_CLIENT": model,
                "IMAGE_FETCHER": fetcher or FakeFetcher({}),
                "FRONTEND_DIR": tmp_path / "no-frontend",  # never a local build
                **config,
            }
        )

    return _make
