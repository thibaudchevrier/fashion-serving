"""JSON API tests (FastAPI test client), with a fake model and a fake URL fetcher."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tests.conftest import DRESS_BOX, FakeFetcher, FakeModel, jpeg

URL = "https://shop.example/outfit.jpg"


@pytest.fixture
def client(make_app, model):
    """Build a test client with a healthy model and one downloadable image."""
    return TestClient(make_app(model, FakeFetcher({URL: jpeg()})))


def _upload(client, data=None, name="photo.jpg"):
    """Upload a file through the API."""
    return client.post("/api/images", files={"file": (name, data or jpeg(), "image/jpeg")})


def test_config_describes_thresholds_and_limits(client):
    """The config gives the stored floor, the default threshold and the upload limit."""
    assert client.get("/api/config").json() == {
        "min_score": 0.3,
        "default_threshold": 0.7,
        "max_upload_bytes": 20 * 2**20,
    }


def test_upload_returns_garments_with_masks_and_colors(client, model):
    """An upload is analysed at once: garments, most confident first, with their palette."""
    response = _upload(client)
    assert response.status_code == 201 and "X-Model-Unavailable" not in response.headers
    image = response.json()
    assert (image["analysed"], image["width"], image["height"]) == (True, 120, 80)
    assert [g["label"] for g in image["garments"]] == ["dress", "belt"]
    dress = image["garments"][0]
    assert dress["index"] == 1 and dress["box"] == DRESS_BOX and dress["mask_rle"]
    assert [g["group"] for g in image["garments"]] == ["garment", "accessory"]
    assert dress["color"].startswith("#") and len(dress["color"]) == 7
    assert dress["palette"][0]["name"] == "navy" and dress["palette"][0]["share"] > 0.9
    assert model.calls == [0.3]  # every detection above the stored floor is kept
    assert client.get(f"/api/images/{image['id']}").json() == image


def test_gallery_counts_garments_above_the_default_threshold(client):
    """The gallery lists images, counting only the detections shown by default."""
    image_id = _upload(client).json()["id"]
    assert client.get("/api/images").json() == [
        {
            "id": image_id,
            "analysed": True,
            "garment_count": 1,
            "width": 120,
            "height": 80,
            "outfit": DRESS_BOX,  # the belt is below the default threshold
        }
    ]


def test_upload_is_kept_when_the_model_is_down(make_app):
    """Without the model the image is kept and flagged; analysing again works once it is back."""
    down = FakeModel(fail=True)
    client = TestClient(make_app(down))
    response = _upload(client)
    assert response.status_code == 201 and response.headers["X-Model-Unavailable"] == "true"
    image = response.json()
    assert (image["analysed"], image["garments"]) == (False, [])
    assert client.post(f"/api/images/{image['id']}/analyse").status_code == 503
    down.fail = False
    assert client.post(f"/api/images/{image['id']}/analyse").json()["analysed"]


@pytest.mark.parametrize(
    ("data", "name", "status"),
    [(b"#!/bin/sh", "script.sh", 415), (b"not an image", "photo.jpg", 422)],
)
def test_bad_uploads_are_refused_and_not_stored(client, tmp_path, data, name, status):
    """Unsupported types and unreadable files are refused with their own status."""
    assert _upload(client, data, name).status_code == status
    assert not list(tmp_path.iterdir())


def test_uploads_over_the_limit_are_refused(make_app, model):
    """A file larger than the limit gets 413."""
    client = TestClient(make_app(model, MAX_UPLOAD_BYTES=100))
    assert _upload(client).status_code == 413


def test_upload_from_url(client):
    """An image URL is downloaded and analysed like an upload; refused URLs get 400."""
    response = client.post("/api/images/from-url", json={"url": URL})
    assert response.status_code == 201 and response.json()["analysed"]
    refused = client.post("/api/images/from-url", json={"url": "http://169.254.169.254/"})
    assert refused.status_code == 400 and "not public" in refused.json()["detail"]


def test_url_that_is_not_an_image_is_refused(make_app, model):
    """A downloaded file that does not decode as an image gets 422."""
    client = TestClient(make_app(model, FakeFetcher({URL: b"<html>"})))
    assert client.post("/api/images/from-url", json={"url": URL}).status_code == 422


def test_image_overlay_and_cutout(client):
    """The photo, its overlay and each garment's transparent cutout are served."""
    image_id = _upload(client).json()["id"]
    assert client.get(f"/api/images/{image_id}/image.jpg").headers["content-type"] == "image/jpeg"
    overlay = client.get(f"/api/images/{image_id}/overlay.png")
    assert overlay.content.startswith(b"\x89PNG")
    cutout = client.get(f"/api/images/{image_id}/garments/1/cutout.png")
    with Image.open(io.BytesIO(cutout.content)) as img:
        y1, x1, y2, x2 = DRESS_BOX
        assert (img.mode, img.size) == ("RGBA", (x2 - x1, y2 - y1))
        assert img.getpixel((5, 5))[3] == 255  # inside the mask: opaque
    assert client.get(f"/api/images/{image_id}/garments/7/cutout.png").status_code == 404


def test_unknown_and_malformed_ids_are_not_found(client):
    """Unknown or malformed ids get 404 on every image route."""
    for path in ("", "/image.jpg", "/overlay.png", "/garments/0/cutout.png"):
        assert client.get(f"/api/images/{'0' * 32}{path}").status_code == 404
    assert client.get("/api/images/..%2Fsecret/image.jpg").status_code == 404


def test_delete(client, tmp_path):
    """Deleting removes the image and its predictions."""
    image_id = _upload(client).json()["id"]
    assert client.delete(f"/api/images/{image_id}").status_code == 204
    assert client.get(f"/api/images/{image_id}").status_code == 404
    assert not list(tmp_path.iterdir())


def test_openapi_documents_the_api(client):
    """The API schema is served (the interactive docs read it)."""
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/images", "/api/images/from-url", "/api/images/{image_id}"} <= set(paths)


def test_front_end_is_served_when_built(make_app, model, tmp_path):
    """The built front end is served at /, behind the API; without it / points to the docs."""
    assert "not built" in TestClient(make_app(model)).get("/").text
    built = tmp_path / "dist"
    built.mkdir()
    (built / "index.html").write_text("<div id=root></div>")
    client = TestClient(make_app(model, FRONTEND_DIR=built))
    assert client.get("/").text == "<div id=root></div>"
    assert client.get("/api/config").json()["default_threshold"] == 0.7
    assert client.get("/healthz").json() == {"status": "ok"}


def test_board_places_new_images_and_saves_arrangements(client):
    """Each image gets a tile; a saved arrangement is kept, clamped to the grid."""
    first, second = (_upload(client).json()["id"] for _ in range(2))
    tiles = client.get("/api/board").json()["tiles"]
    assert [t["id"] for t in tiles] == [first, second]  # upload order
    assert tiles[0] | {"view": "photo"} == {
        "id": first,
        "x": 0,
        "y": 0,
        "w": 4,
        "h": 5,
        "view": "photo",
    }
    saved = client.put(
        "/api/board",
        json={"tiles": [{"id": second, "x": 10, "y": 2, "w": 6, "h": 4, "view": "cutouts"}]},
    ).json()["tiles"]
    assert saved[0] == {"id": second, "x": 6, "y": 2, "w": 6, "h": 4, "view": "cutouts"}
    assert saved[1]["id"] == first and saved[1]["y"] == 6  # placed again, below
    client.delete(f"/api/images/{second}")
    assert [t["id"] for t in client.get("/api/board").json()["tiles"]] == [first]


def test_board_rejects_impossible_tiles(client):
    """Tiles wider than the grid or with an unknown view are refused."""
    bad = [
        {"id": "a" * 32, "x": 0, "y": 0, "w": 13, "h": 4},
        {"id": "a" * 32, "x": 0, "y": 0, "w": 2, "h": 4, "view": "x"},
    ]
    for tile in bad:
        assert client.put("/api/board", json={"tiles": [tile]}).status_code == 422
