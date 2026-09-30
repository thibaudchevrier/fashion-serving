"""End-to-end check of a running stack (``docker compose up``).

1. Calls the inference service directly and validates the response against the contract.
2. Uploads the same image through the webapp's API, then checks its garments (with their colors),
   the overlay, a garment cutout and the page.

Usage: uv run --project webapp python scripts/smoke_test.py [--inference URL] [--webapp URL]
"""

import argparse
import io
import sys
import time

import numpy as np
import requests
from fashion_seg_contract import schema
from PIL import Image

from fashion_webapp.inference import InferenceClient


def wait_until_up(url: str, timeout: float = 180) -> None:
    """Poll a URL until it answers with a success status; exit with an error after ``timeout``.

    Parameters
    ----------
    url : str
        URL to poll, e.g. a health endpoint.
    timeout : float
        Seconds to wait before giving up. By default 180.
    """
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
    """Build a synthetic 'person' image: it checks the plumbing, not the model quality.

    Returns
    -------
    bytes
        A 300x400 JPEG.
    """
    rng = np.random.default_rng(0)
    image = rng.integers(90, 160, size=(400, 300, 3), dtype=np.uint8)
    image[60:380, 90:210] = (40, 60, 150)
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="JPEG")
    return buffer.getvalue()


def main() -> None:
    """Check the inference service, then the webapp; exit non-zero on the first failure."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--inference", default="http://localhost:5001")
    parser.add_argument("--webapp", default="http://localhost:8000")
    args = parser.parse_args()
    jpeg = sample_jpeg()

    wait_until_up(f"{args.inference}/ping")
    prediction = InferenceClient(args.inference, timeout=120).predict(jpeg, min_score=0.7)
    schema.validate(prediction)
    print(f"OK inference: {len(prediction['instances'])} instance(s), response matches contract")

    wait_until_up(f"{args.webapp}/healthz")
    api = f"{args.webapp}/api"
    response = requests.post(
        f"{api}/images", files={"file": ("smoke.jpg", jpeg, "image/jpeg")}, timeout=120
    )
    response.raise_for_status()
    image = response.json()
    if not image["analysed"]:
        sys.exit("FAIL: webapp could not reach the inference service")
    if any(not garment["palette"] for garment in image["garments"]):
        sys.exit("FAIL: a garment has no colors")
    for path in ["overlay.png"] + [
        f"garments/{g['index']}/cutout.png" for g in image["garments"][:1]
    ]:
        png = requests.get(f"{api}/images/{image['id']}/{path}", timeout=30)
        png.raise_for_status()
        if not png.content.startswith(b"\x89PNG"):
            sys.exit(f"FAIL: {path} is not a PNG")
    requests.get(args.webapp, timeout=30).raise_for_status()
    requests.delete(f"{api}/images/{image['id']}", timeout=30).raise_for_status()
    count = len(image["garments"])
    print(f"OK webapp: upload -> {count} garment(s) with colors -> overlay, cutout, page")


if __name__ == "__main__":
    main()
