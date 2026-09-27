"""Draw predicted masks, boxes and labels on top of an image."""

import colorsys
import io
from typing import Any

import numpy as np
from fashion_seg_contract import rle
from PIL import Image, ImageDraw

MASK_ALPHA = 0.45


def class_color(class_id: int) -> tuple[int, int, int]:
    """Stable, well-spread color per class (golden-ratio hue steps)."""
    hue = (class_id * 0.618033988749895) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.75, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


def render_overlay(image: Image.Image, predictions: dict[str, Any]) -> bytes:
    """Return a PNG of ``image`` with every predicted instance drawn on it."""
    rgb = np.asarray(image.convert("RGB"))
    if rgb.shape[:2] != (predictions["height"], predictions["width"]):
        raise ValueError("Predictions were made on an image of a different size")

    out = Image.fromarray(_blend_masks(rgb, predictions["instances"]))
    _draw_boxes(ImageDraw.Draw(out), predictions["instances"])
    buffer = io.BytesIO()
    out.save(buffer, format="PNG")
    return buffer.getvalue()


def _blend_masks(rgb: np.ndarray, instances: list[dict[str, Any]]) -> np.ndarray:
    canvas = rgb.astype(np.float32)
    height, width = canvas.shape[:2]
    for inst in instances:
        mask = rle.decode(inst["mask_rle"], height, width)
        color = np.array(class_color(inst["class_id"]), dtype=np.float32)
        canvas[mask] = canvas[mask] * (1 - MASK_ALPHA) + color * MASK_ALPHA
    return canvas.astype(np.uint8)


def _draw_boxes(draw: ImageDraw.ImageDraw, instances: list[dict[str, Any]]) -> None:
    for inst in instances:
        y1, x1, y2, x2 = inst["box"]
        color = class_color(inst["class_id"])
        draw.rectangle([x1, y1, x2 - 1, y2 - 1], outline=color, width=2)
        caption = f"{inst['label']} {inst['score']:.2f}"
        left, top, right, bottom = draw.textbbox((x1 + 3, y1 + 2), caption)
        draw.rectangle([left - 3, top - 2, right + 3, bottom + 2], fill=color)
        draw.text((x1 + 3, y1 + 2), caption, fill=(0, 0, 0))
