"""HTTP client for the MLflow inference service (``mlflow models serve``).

Implements ``fashion_webapp.service.Inference``.
"""

import requests
from fashion_seg_contract import request
from fashion_seg_contract.schema import Prediction

from fashion_webapp.service import InferenceUnavailable


class InferenceClient:
    """Client of ``POST /invocations``, one base64 image per request.

    Parameters
    ----------
    base_url : str
        URL of the inference service, e.g. ``http://inference:5000``.
    timeout : float
        Request timeout in seconds. By default 60.

    Attributes
    ----------
    base_url : str
        URL of the inference service, without trailing slash.
    timeout : float
        Request timeout in seconds.
    """

    base_url: str
    timeout: float

    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def predict(self, image: bytes, min_score: float) -> Prediction:
        """Segment the garments in one encoded image.

        Parameters
        ----------
        image : bytes
            Encoded image (JPEG or PNG).
        min_score : float
            Minimum detection confidence to return.

        Returns
        -------
        Prediction
            The model's response for the image (see ``fashion_seg_contract.schema``).

        Raises
        ------
        InferenceUnavailable
            If the service is unreachable, answers with an error status or an unexpected body.
        """
        try:
            response = requests.post(
                f"{self.base_url}/invocations",
                json=request.build([image], min_score),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()["predictions"][0]
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            raise InferenceUnavailable(f"Inference service call failed: {exc}") from exc
