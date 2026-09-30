"""Images made from predictions: the annotated overlay, garment cutouts, garment colors."""

import colorsys
import io

import numpy as np
from fashion_seg_contract import rle
from fashion_seg_contract.schema import Instance, Prediction
from PIL import Image, ImageDraw

from fashion_webapp.palette import Swatch, dominant_colors

MASK_ALPHA = 0.45


def class_color(class_id: int) -> tuple[int, int, int]:
    """Pick a stable, well-spread color for a class (golden-ratio hue steps).

    Parameters
    ----------
    class_id : int
        Model class id.

    Returns
    -------
    tuple[int, int, int]
        RGB color, each channel between 0 and 255.

    Examples
    --------
    >>> class_color(24) == class_color(24)
    True
    """
    hue = (class_id * 0.618033988749895) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.75, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


def render_overlay(image: bytes, predictions: Prediction) -> bytes:
    """Draw every predicted instance (mask, box, label and score) on an image.

    Parameters
    ----------
    image : bytes
        The encoded image the predictions were made on.
    predictions : Prediction
        The model's response for that image.

    Returns
    -------
    bytes
        The annotated image, PNG-encoded. Raises ``ValueError`` (from ``_decode``) if the
        predictions were made on an image of a different size.
    """
    rgb = _decode(image, predictions)
    out = Image.fromarray(_blend_masks(rgb, predictions["instances"]))
    _draw_boxes(ImageDraw.Draw(out), predictions["instances"])
    buffer = io.BytesIO()
    out.save(buffer, format="PNG")
    return buffer.getvalue()


def _blend_masks(rgb: np.ndarray, instances: list[Instance]) -> np.ndarray:
    """Tint each instance's mask with its class color.

    Parameters
    ----------
    rgb : np.ndarray
        Image, shape ``(height, width, 3)``, uint8.
    instances : list[Instance]
        Predicted instances.

    Returns
    -------
    np.ndarray
        Tinted copy of the image, same shape, uint8.
    """
    canvas = rgb.astype(np.float32)
    height, width = canvas.shape[:2]
    for inst in instances:
        mask = rle.decode(inst["mask_rle"], height, width)
        color = np.array(class_color(inst["class_id"]), dtype=np.float32)
        canvas[mask] = canvas[mask] * (1 - MASK_ALPHA) + color * MASK_ALPHA
    return canvas.astype(np.uint8)


def _draw_boxes(draw: ImageDraw.ImageDraw, instances: list[Instance]) -> None:
    """Draw each instance's box with a ``label score`` caption.

    Parameters
    ----------
    draw : ImageDraw.ImageDraw
        Drawing context of the output image.
    instances : list[Instance]
        Predicted instances.
    """
    for inst in instances:
        y1, x1, y2, x2 = inst["box"]
        color = class_color(inst["class_id"])
        draw.rectangle([x1, y1, x2 - 1, y2 - 1], outline=color, width=2)
        caption = f"{inst['label']} {inst['score']:.2f}"
        left, top, right, bottom = draw.textbbox((x1 + 3, y1 + 2), caption)
        draw.rectangle([left - 3, top - 2, right + 3, bottom + 2], fill=color)
        draw.text((x1 + 3, y1 + 2), caption, fill=(0, 0, 0))


def render_cutout(image: bytes, predictions: Prediction, index: int) -> bytes:
    """Cut one garment out of its image: its box, transparent outside its mask.

    Parameters
    ----------
    image : bytes
        The encoded image the predictions were made on.
    predictions : Prediction
        The model's response for that image.
    index : int
        Position of the garment in ``predictions["instances"]``.

    Returns
    -------
    bytes
        RGBA PNG of the garment's box. Raises ``ValueError`` (from ``_decode``) if the image
        size does not match, and ``IndexError`` for an unknown garment.
    """
    rgb = _decode(image, predictions)
    inst = predictions["instances"][index]
    mask = rle.decode(inst["mask_rle"], predictions["height"], predictions["width"])
    y1, x1, y2, x2 = inst["box"]
    alpha = mask[y1:y2, x1:x2].astype(np.uint8) * 255
    rgba = np.dstack([rgb[y1:y2, x1:x2], alpha])
    buffer = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buffer, format="PNG")
    return buffer.getvalue()


def garment_colors(image: bytes, predictions: Prediction) -> list[list[Swatch]]:
    """Find the dominant colors of every predicted garment.

    Parameters
    ----------
    image : bytes
        The encoded image the predictions were made on.
    predictions : Prediction
        The model's response for that image.

    Returns
    -------
    list[list[Swatch]]
        One palette per instance, in the order of ``predictions["instances"]``. Raises
        ``ValueError`` (from ``_decode``) if the image size does not match.
    """
    rgb = _decode(image, predictions)
    height, width = rgb.shape[:2]
    return [
        dominant_colors(rgb[rle.decode(inst["mask_rle"], height, width)])
        for inst in predictions["instances"]
    ]


def _decode(image: bytes, predictions: Prediction) -> np.ndarray:
    """Decode an image and check it is the one the predictions were made on.

    Parameters
    ----------
    image : bytes
        The encoded image.
    predictions : Prediction
        The model's response for an image.

    Returns
    -------
    np.ndarray
        RGB pixels, shape ``(height, width, 3)``, uint8.

    Raises
    ------
    ValueError
        If the predictions were made on an image of a different size.
    """
    with Image.open(io.BytesIO(image)) as img:
        rgb = np.asarray(img.convert("RGB"))
    if rgb.shape[:2] != (predictions["height"], predictions["width"]):
        raise ValueError("Predictions were made on an image of a different size")
    return rgb
