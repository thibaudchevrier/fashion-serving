"""Dominant colors of a garment: its pixels quantized into a few colors, each with a name.

Pure image math (numpy and Pillow on arrays): no web framework, no I/O.
"""

from dataclasses import dataclass

import numpy as np
from PIL import Image

# Pixels sampled per garment: plenty for a palette, and fast whatever the mask size.
MAX_SAMPLES = 4096
# Colors covering less than this share of the garment are left out.
MIN_SHARE = 0.08

# Names given to colors: the nearest of these references wins.
NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "black": (20, 20, 20),
    "charcoal": (64, 64, 64),
    "grey": (128, 128, 128),
    "silver": (192, 192, 192),
    "white": (245, 245, 245),
    "cream": (240, 230, 200),
    "beige": (215, 195, 160),
    "khaki": (160, 150, 100),
    "brown": (110, 70, 40),
    "tan": (190, 140, 90),
    "red": (200, 30, 40),
    "burgundy": (110, 20, 40),
    "pink": (240, 150, 180),
    "orange": (240, 130, 30),
    "yellow": (240, 210, 40),
    "olive": (110, 110, 40),
    "green": (40, 140, 60),
    "teal": (20, 120, 120),
    "turquoise": (60, 200, 200),
    "light blue": (150, 190, 230),
    "blue": (40, 80, 200),
    "navy": (25, 35, 80),
    "purple": (110, 50, 150),
    "lavender": (180, 160, 220),
}


@dataclass(frozen=True)
class Swatch:
    """One dominant color of a garment.

    Attributes
    ----------
    hex : str
        The color, ``#rrggbb``.
    name : str
        The nearest named color.
    share : float
        Fraction of the garment's pixels closest to this color, between 0 and 1.
    """

    hex: str
    name: str
    share: float


def color_name(rgb: tuple[int, int, int]) -> str:
    """Name a color: the nearest reference of ``NAMED_COLORS``.

    Distance is the "redmean" approximation of perceived color difference, better than plain
    RGB distance for a few lines of code.

    Parameters
    ----------
    rgb : tuple[int, int, int]
        The color, each channel between 0 and 255.

    Returns
    -------
    str
        The name of the nearest reference color.

    Examples
    --------
    >>> color_name((30, 40, 90)), color_name((250, 250, 250)), color_name((190, 30, 50))
    ('navy', 'white', 'red')
    """
    r, g, b = rgb

    def distance(ref: tuple[int, int, int]) -> float:
        """Measure the redmean distance to a reference color.

        Parameters
        ----------
        ref : tuple[int, int, int]
            The reference color.

        Returns
        -------
        float
            The squared distance (only compared, never shown).
        """
        mean_red = (r + ref[0]) / 2
        dr, dg, db = r - ref[0], g - ref[1], b - ref[2]
        return (2 + mean_red / 256) * dr * dr + 4 * dg * dg + (2 + (255 - mean_red) / 256) * db * db

    return min(NAMED_COLORS, key=lambda name: distance(NAMED_COLORS[name]))


def dominant_colors(pixels: np.ndarray, count: int = 3) -> list[Swatch]:
    """Find the main colors of a set of pixels.

    Parameters
    ----------
    pixels : np.ndarray
        ``(n, 3)`` uint8 RGB pixels, e.g. the pixels under a garment's mask.
    count : int
        Most colors to return. By default 3.

    Returns
    -------
    list[Swatch]
        The colors covering at least ``MIN_SHARE`` of the pixels, most common first; empty if
        there are no pixels.

    Examples
    --------
    >>> px = np.array([[20, 30, 80]] * 70 + [[250, 250, 250]] * 30, dtype=np.uint8)
    >>> [(s.name, round(s.share, 1)) for s in dominant_colors(px)]
    [('navy', 0.7), ('white', 0.3)]
    """
    if len(pixels) == 0:
        return []
    if len(pixels) > MAX_SAMPLES:
        rng = np.random.default_rng(0)  # the same garment always gives the same palette
        pixels = pixels[rng.choice(len(pixels), MAX_SAMPLES, replace=False)]
    strip = Image.fromarray(np.ascontiguousarray(pixels.reshape(1, -1, 3), dtype=np.uint8))
    quantized = strip.quantize(colors=count + 1, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    # Quantization may split one color into near-identical shades: shades with the same name
    # are merged, keeping the most common shade's value.
    by_name: dict[str, Swatch] = {}
    for pixel_count, index in sorted(quantized.getcolors() or [], reverse=True):
        rgb = (palette[3 * index], palette[3 * index + 1], palette[3 * index + 2])
        name, share = color_name(rgb), pixel_count / len(pixels)
        if name in by_name:
            share += by_name[name].share
            rgb = _rgb(by_name[name].hex)
        by_name[name] = Swatch(hex=f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}", name=name, share=share)
    swatches = sorted(by_name.values(), key=lambda s: s.share, reverse=True)
    return [s for s in swatches if s.share >= MIN_SHARE][:count]


def _rgb(hex_color: str) -> tuple[int, int, int]:
    """Parse a ``#rrggbb`` color.

    Parameters
    ----------
    hex_color : str
        The color.

    Returns
    -------
    tuple[int, int, int]
        Its channels.

    Examples
    --------
    >>> _rgb("#1f2a4d")
    (31, 42, 77)
    """
    return int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
