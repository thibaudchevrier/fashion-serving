"""Use-case tests with in-memory adapters: no Flask, no HTTP, no files."""

import io

import pytest
from PIL import Image

from fashion_webapp import service
from fashion_webapp.service import (
    InferenceUnavailable,
    Settings,
    StoredImage,
    UnreadableImage,
    UnsupportedFile,
)

SETTINGS = Settings(min_score=0.5, max_image_side=100)


def _png(width=4, height=3) -> bytes:
    """Encode a small PNG."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height)).save(buffer, format="PNG")
    return buffer.getvalue()


class MemoryStore:
    """ImageStore keeping images and predictions in dictionaries."""

    def __init__(self):
        """Start empty."""
        self.images, self.predictions = {}, {}

    def save_upload(self, data, max_side):  # pylint: disable=unused-argument  # port signature
        """Store the bytes as they are, or refuse non-images."""
        if not data.startswith(b"\x89PNG"):
            raise UnreadableImage("not a PNG")
        image_id = f"{len(self.images):032x}"
        self.images[image_id] = data
        return image_id, data

    def save_predictions(self, image_id, predictions):
        """Store predictions."""
        self.predictions[image_id] = predictions

    def get(self, image_id):
        """Return the stored image, if any."""
        if image_id not in self.images:
            return None
        return StoredImage(image_id, self.predictions.get(image_id))

    def read(self, image_id):
        """Return the stored bytes, if any."""
        return self.images.get(image_id)

    def list(self):
        """List stored images."""
        return [self.get(i) for i in self.images]

    def delete(self, image_id):
        """Forget an image."""
        self.images.pop(image_id, None)


class FakeModel:
    """Inference returning an empty prediction sized 4x3, or failing on demand."""

    def __init__(self, fail=False):
        """Start healthy (or failing) with no call."""
        self.fail, self.calls = fail, []

    def predict(self, image, min_score):
        """Record the call, then answer or fail."""
        self.calls.append((image, min_score))
        if self.fail:
            raise InferenceUnavailable("down")
        return {"height": 3, "width": 4, "instances": []}


def test_upload_stores_and_analyses_with_the_settings():
    """An upload is stored, sent to the model with min_score, and its prediction kept."""
    store, model = MemoryStore(), FakeModel()
    outcome = service.upload(store, model, ("a.png", _png()), SETTINGS)
    assert outcome.analysed
    assert model.calls == [(_png(), 0.5)]
    assert store.get(outcome.image_id).predictions["instances"] == []


def test_upload_keeps_the_image_when_the_model_is_down():
    """A failed prediction keeps the image, not analysed, for a later retry."""
    store = MemoryStore()
    outcome = service.upload(store, FakeModel(fail=True), ("a.png", _png()), SETTINGS)
    assert not outcome.analysed
    assert store.get(outcome.image_id).predictions is None
    assert service.analyse(store, FakeModel(), outcome.image_id, SETTINGS)


def test_upload_refuses_unsupported_and_unreadable_files():
    """Unsupported extensions and non-images are refused, nothing is stored."""
    store = MemoryStore()
    with pytest.raises(UnsupportedFile):
        service.upload(store, FakeModel(), ("a.sh", _png()), SETTINGS)
    with pytest.raises(UnreadableImage):
        service.upload(store, FakeModel(), ("a.png", b"text"), SETTINGS)
    assert not store.images


def test_analyse_and_overlay_of_unknown_images():
    """Unknown images can't be analysed and have no overlay."""
    with pytest.raises(LookupError):
        service.analyse(MemoryStore(), FakeModel(), "nope", SETTINGS)
    assert service.overlay(MemoryStore(), "nope") is None


def test_overlay_draws_only_analysed_images():
    """The overlay exists once the image has predictions, at the image size."""
    store = MemoryStore()
    image_id = service.upload(store, FakeModel(fail=True), ("a.png", _png()), SETTINGS).image_id
    assert service.overlay(store, image_id) is None
    service.analyse(store, FakeModel(), image_id, SETTINGS)
    with Image.open(io.BytesIO(service.overlay(store, image_id))) as img:
        assert img.size == (4, 3)
