import io

import numpy as np
import pytest
from fashion_seg_contract import rle, schema
from PIL import Image

from fashion_webapp import create_app
from fashion_webapp.inference import InferenceError
from fashion_webapp.rendering import render_overlay


def _jpeg(width=120, height=80, color=(200, 180, 160)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="JPEG")
    return buffer.getvalue()


class FakeClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def predict(self, image_bytes, min_score):
        self.calls.append(min_score)
        if self.fail:
            raise InferenceError("down")
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.size
        mask = np.zeros((height, width), dtype=bool)
        mask[10:30, 20:60] = True
        response = {
            "height": height,
            "width": width,
            "instances": [
                {
                    "class_id": 24,
                    "label": "dress",
                    "score": 0.93,
                    "box": [10, 20, 30, 60],
                    "mask_rle": rle.encode(mask),
                },
            ],
        }
        # The fake must honour the contract, or these tests prove nothing about the real model.
        schema.validate(response)
        return response


@pytest.fixture
def make_client(tmp_path):
    def _make(fake):
        app = create_app({"TESTING": True, "UPLOAD_DIR": tmp_path, "INFERENCE_CLIENT": fake})
        return app.test_client()

    return _make


def _upload(client, data=None, name="photo.jpg"):
    return client.post(
        "/upload",
        data={"file": (io.BytesIO(data or _jpeg()), name)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def test_upload_predicts_and_renders_overlay(make_client, tmp_path):
    client = make_client(FakeClient())
    page = _upload(client)
    assert page.status_code == 200
    assert b"dress" in page.data

    [image_id] = [p.stem for p in tmp_path.glob("*.jpg")]
    overlay = client.get(f"/images/{image_id}/overlay.png")
    assert overlay.status_code == 200
    with Image.open(io.BytesIO(overlay.data)) as img:
        assert img.size == (120, 80)


def test_upload_is_downscaled_before_inference(make_client, tmp_path):
    client = make_client(FakeClient())
    _upload(client, _jpeg(width=3000, height=1500))
    [path] = tmp_path.glob("*.jpg")
    with Image.open(path) as img:
        assert max(img.size) == 800


def test_inference_failure_keeps_image_and_allows_retry(make_client, tmp_path):
    fake = FakeClient(fail=True)
    client = make_client(fake)
    page = _upload(client)
    assert b"model is unavailable" in page.data
    assert b"Not analysed yet" in page.data

    [image_id] = [p.stem for p in tmp_path.glob("*.jpg")]
    fake.fail = False
    page = client.post(f"/images/{image_id}/predict", follow_redirects=True)
    assert b"dress" in page.data


def test_rejects_non_images(make_client, tmp_path):
    client = make_client(FakeClient())
    page = _upload(client, b"not an image", name="notes.jpg")
    assert b"Could not read" in page.data
    page = _upload(client, b"x", name="script.sh")
    assert b"Unsupported file type" in page.data
    assert not list(tmp_path.iterdir())


def test_delete_and_invalid_ids(make_client, tmp_path):
    client = make_client(FakeClient())
    _upload(client)
    [image_id] = [p.stem for p in tmp_path.glob("*.jpg")]
    assert client.get("/images/..%2Fsecret.jpg").status_code == 404
    client.post(f"/images/{image_id}/delete")
    assert not list(tmp_path.iterdir())


def test_render_overlay_rejects_size_mismatch():
    with pytest.raises(ValueError):
        render_overlay(Image.new("RGB", (10, 10)), {"height": 5, "width": 5, "instances": []})
