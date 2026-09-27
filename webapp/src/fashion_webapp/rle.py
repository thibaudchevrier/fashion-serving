"""Decoding of the masks returned by the inference service.

Same encoding as the iMaterialist annotations (``fashion_seg.rle`` in fashion-seg-train):
space-separated ``start length`` pairs, 1-indexed, column-major pixel order.
"""

import numpy as np


def decode(rle: str, height: int, width: int) -> np.ndarray:
    """Decode an RLE string into a boolean mask of shape ``(height, width)``."""
    flat = np.zeros(height * width, dtype=bool)
    values = np.array(rle.split(), dtype=np.int64)
    for start, length in zip(values[::2] - 1, values[1::2], strict=True):
        flat[start : start + length] = True
    return flat.reshape((height, width), order="F")
