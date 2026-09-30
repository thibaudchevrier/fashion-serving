"""Server-rendered page tests (FastAPI test client), with a fake model."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeModel, jpeg


@pytest.fixture
def client(make_app, model):
    """Build a test client with a healthy model."""
    return TestClient(make_app(model))


def _upload(client, data=None, name="photo.jpg"):
    """Post the upload form and follow the redirect to the page."""
    return client.post("/upload", files={"file": (name, data or jpeg(), "image/jpeg")})


def test_empty_gallery(client):
    """With no uploads, the page invites to upload one."""
    page = client.get("/")
    assert page.status_code == 200 and "No photos yet" in page.text


def test_upload_lists_garments_above_the_default_threshold(client):
    """An uploaded photo shows its overlay and its confident garments only."""
    page = _upload(client)
    assert page.status_code == 200 and "/overlay.png" in page.text
    assert "dress" in page.text and "belt" not in page.text  # the belt scores 0.42 < 0.7


def test_model_down_then_analyse(make_app, tmp_path):
    """Without the model the photo is kept with a message; Analyse works once it is back."""
    down = FakeModel(fail=True)
    client = TestClient(make_app(down))
    page = _upload(client)
    assert "model is unavailable" in page.text and "Not analysed yet" in page.text
    [image_id] = [p.stem for p in tmp_path.glob("*.jpg")]
    down.fail = False
    assert "dress" in client.post(f"/images/{image_id}/predict").text


def test_bad_uploads_show_a_message(client, tmp_path):
    """Unsupported or unreadable files are refused with a message, and not stored."""
    assert "Unsupported file type" in _upload(client, b"x", "script.sh").text
    assert "Could not read" in _upload(client, b"x", "photo.jpg").text
    assert not list(tmp_path.iterdir())


def test_delete(client, tmp_path):
    """Deleting a photo removes it from the page and the disk."""
    _upload(client)
    [image_id] = [p.stem for p in tmp_path.glob("*.jpg")]
    page = client.post(f"/images/{image_id}/delete", data={"overlay": "0"})
    assert "No photos yet" in page.text and page.url.params["overlay"] == "0"
    assert not list(tmp_path.iterdir())
