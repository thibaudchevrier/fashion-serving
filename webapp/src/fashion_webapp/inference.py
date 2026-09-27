"""HTTP client for the MLflow inference service (``mlflow models serve``)."""

import base64
from typing import Any

import requests


class InferenceError(RuntimeError):
    """The inference service is unreachable or returned an unexpected response."""


class InferenceClient:
    """Calls ``POST /invocations`` with one base64 image per request."""

    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def predict(self, image_bytes: bytes, min_score: float) -> dict[str, Any]:
        """Return ``{"height", "width", "instances": [...]}`` for one encoded image."""
        payload = {
            "dataframe_records": [{"image": base64.b64encode(image_bytes).decode("ascii")}],
            "params": {"min_score": min_score},
        }
        try:
            response = requests.post(
                f"{self.base_url}/invocations", json=payload, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()["predictions"][0]
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            raise InferenceError(f"Inference service call failed: {exc}") from exc
