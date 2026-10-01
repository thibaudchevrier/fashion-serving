"""The board: the uploaded photos arranged as a composition, saved on the server.

A board is a list of tiles on a ``COLUMNS``-column grid. Reading it keeps it in step with the
images: tiles of deleted images are dropped, new images are placed below the others. Each image
also gets its outfit box, the area its garments cover, so a tile can crop around the outfit.

Use cases only, like ``fashion_webapp.service``: the board itself is stored by a ``BoardStore``
(``fashion_webapp.storage.FileBoardStore``).
"""

from dataclasses import dataclass, replace
from typing import Literal, Protocol

from fashion_seg_contract.schema import Prediction

from fashion_webapp.service import ImageStore

COLUMNS = 12
MAX_ROWS = 40  # tallest tile, in grid rows
TileView = Literal["photo", "masks", "cutouts"]


@dataclass(frozen=True)
class Tile:
    """One photo on the board.

    Attributes
    ----------
    image_id : str
        The photo.
    x : int
        Left column, from 0.
    y : int
        Top row, from 0.
    w : int
        Width in columns.
    h : int
        Height in rows.
    view : TileView
        What the tile shows: the photo, the photo with its masks, or its garments cut out.
    """

    image_id: str
    x: int
    y: int
    w: int
    h: int
    view: TileView = "photo"


class BoardStore(Protocol):
    """Where the board is kept."""

    def load(self) -> list[Tile]:
        """Read the saved tiles.

        Returns
        -------
        list[Tile]
            The tiles, empty if no board was saved yet.
        """

    def save(self, tiles: list[Tile]) -> None:
        """Replace the saved tiles.

        Parameters
        ----------
        tiles : list[Tile]
            The new board.
        """


def default_size(predictions: Prediction | None) -> tuple[int, int]:
    """Size a new tile after its photo's orientation.

    Parameters
    ----------
    predictions : Prediction | None
        The photo's predictions (they give its size), or ``None`` if not analysed yet.

    Returns
    -------
    tuple[int, int]
        Width in columns and height in rows.

    Examples
    --------
    >>> default_size({"width": 400, "height": 800, "instances": []}), default_size(None)
    ((3, 8), (3, 6))
    """
    if predictions is None:
        return 3, 6
    ratio = predictions["height"] / predictions["width"]
    if ratio > 1.15:
        return 3, 8
    return (4, 5) if ratio < 0.87 else (3, 6)


def outfit_box(predictions: Prediction, min_score: float) -> list[int] | None:
    """Find the area covered by an image's garments: the union of their boxes.

    Parameters
    ----------
    predictions : Prediction
        The image's predictions.
    min_score : float
        Only detections at least this confident count.

    Returns
    -------
    list[int] | None
        ``[y1, x1, y2, x2]``, or ``None`` if no detection is confident enough.

    Examples
    --------
    >>> outfit_box({"instances": [{"score": 0.9, "box": [10, 5, 50, 30]},
    ...                           {"score": 0.8, "box": [40, 20, 90, 60]},
    ...                           {"score": 0.1, "box": [0, 0, 100, 100]}]}, 0.7)
    [10, 5, 90, 60]
    """
    boxes = [i["box"] for i in predictions["instances"] if i["score"] >= min_score]
    if not boxes:
        return None
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def board(store: ImageStore, boards: BoardStore) -> list[Tile]:
    """Read the board, in step with the stored images.

    Tiles of deleted images are dropped; images without a tile get one, below the others, in
    upload order.

    Parameters
    ----------
    store : ImageStore
        Stored images.
    boards : BoardStore
        The saved board.

    Returns
    -------
    list[Tile]
        Every stored image's tile.
    """
    images = {img.image_id: img for img in store.list()}
    tiles = [t for t in boards.load() if t.image_id in images]
    placed = {t.image_id for t in tiles}
    # Oldest first among the new ones, so a batch of uploads keeps its order.
    new = [img for img in reversed(list(images.values())) if img.image_id not in placed]
    row_top = max((t.y + t.h for t in tiles), default=0)
    x, row_height = 0, 0
    for img in new:
        w, h = default_size(img.predictions)
        if x + w > COLUMNS:
            row_top, x, row_height = row_top + row_height, 0, 0
        tiles.append(Tile(img.image_id, x=x, y=row_top, w=w, h=h))
        x, row_height = x + w, max(row_height, h)
    return tiles


def save_board(store: ImageStore, boards: BoardStore, tiles: list[Tile]) -> list[Tile]:
    """Save a new arrangement of the board.

    Tiles are kept inside the grid; tiles of unknown images, and repeated ones, are ignored.

    Parameters
    ----------
    store : ImageStore
        Stored images.
    boards : BoardStore
        Where the board is saved.
    tiles : list[Tile]
        The new arrangement (untrusted).

    Returns
    -------
    list[Tile]
        The board as saved, completed like ``board`` does.
    """
    known = {img.image_id for img in store.list()}
    kept: dict[str, Tile] = {}
    for tile in tiles:
        if tile.image_id in known and tile.image_id not in kept:
            w = min(max(tile.w, 1), COLUMNS)
            kept[tile.image_id] = replace(
                tile,
                w=w,
                h=min(max(tile.h, 1), MAX_ROWS),
                x=min(max(tile.x, 0), COLUMNS - w),
                y=max(tile.y, 0),
            )
    boards.save(list(kept.values()))
    return board(store, boards)
