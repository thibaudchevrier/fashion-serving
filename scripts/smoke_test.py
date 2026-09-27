"""End-to-end check of a running stack (``docker compose up``).

1. Calls the inference service directly and validates the response against the contract.
2. Uploads the same image through the webapp and checks the page and the overlay render.

Usage: uv run --project webapp python scripts/smoke_test.py [--inference URL] [--webapp URL]
"""

import argparse
import base64
import io
import re
import sys
import time

import numpy as np
import requests
from fashion_seg_contract import schema
from PIL import Image


def wait_until_up(url: str, timeout: float = 180) -> None:
    """Poll ``url`` until it answers 200 or ``timeout`` seconds have passed."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if requests.get(url, timeout=5).ok:
                return
        except requests.ConnectionError:
            pass
        time.sleep(3)
    sys.exit(f"FAIL: {url} not up after {timeout}s")


def sample_jpeg() -> bytes:
    """A synthetic 'person': checks the plumbing, not the model quality."""
    rng = np.random.default_rng(0)
    image = rng.integers(90, 160, size=(400, 300, 3), dtype=np.uint8)
    image[60:380, 90:210] = (40, 60, 150)
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="JPEG")
    return buffer.getvalue()


def main() -> None:
    """Run both checks; exit non-zero on the first failure."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--inference", default="http://localhost:5001")
    parser.add_argument("--webapp", default="http://localhost:8000")
    args = parser.parse_args()
    jpeg = sample_jpeg()

    wait_until_up(f"{args.inference}/ping")
    response = requests.post(
        f"{args.inference}/invocations",
        json={
            "dataframe_records": [{"image": base64.b64encode(jpeg).decode()}],
            "params": {"min_score": 0.7},
        },
        timeout=120,
    )
    response.raise_for_status()
    [prediction] = response.json()["predictions"]
    schema.validate(prediction)
    print(
        f"OK inference: {len(prediction['instances'])} instance(s), response matches contract"
    )

    wait_until_up(f"{args.webapp}/healthz")
    session = requests.Session()
    page = session.post(
        f"{args.webapp}/upload",
        files={"file": ("smoke.jpg", jpeg, "image/jpeg")},
        timeout=120,
    )
    page.raise_for_status()
    if "model is unavailable" in page.text:
        sys.exit("FAIL: webapp could not reach the inference service")
    image_id = re.search(r"/images/([0-9a-f]{32})/overlay\.png", page.text)
    if not image_id:
        sys.exit("FAIL: uploaded image has no predictions on the page")
    overlay = session.get(f"{args.webapp}/images/{image_id[1]}/overlay.png", timeout=30)
    overlay.raise_for_status()
    session.post(f"{args.webapp}/images/{image_id[1]}/delete", timeout=30)
    print("OK webapp: upload -> inference -> overlay")


if __name__ == "__main__":
    main()
