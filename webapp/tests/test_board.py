"""Board use-case tests with in-memory adapters: placement of new images, saving, clamping."""

from fashion_webapp import board
from fashion_webapp.board import Tile
from fashion_webapp.service import StoredImage

PORTRAIT = {"width": 400, "height": 800, "instances": []}


class Images:
    """ImageStore listing given images (most recent first, like the real one)."""

    def __init__(self, *images):
        """Hold these images."""
        self.images = list(images)

    def list(self):
        """List the images."""
        return self.images


class Boards:
    """BoardStore in memory."""

    def __init__(self, tiles=None):
        """Start with these tiles."""
        self.tiles = list(tiles or [])

    def load(self):
        """Return the saved tiles."""
        return list(self.tiles)

    def save(self, tiles):
        """Replace the saved tiles."""
        self.tiles = list(tiles)


def _image(n, predictions="portrait"):
    """Build a stored image with a recognizable id (a portrait photo by default)."""
    return StoredImage(f"{n:032x}", PORTRAIT if predictions == "portrait" else predictions)


def test_new_images_fill_rows_in_upload_order():
    """New images are placed oldest first, left to right, wrapping at the grid's width."""
    images = [_image(n) for n in range(5)]  # portraits: 3 columns each, 4 per row
    tiles = board.board(Images(*reversed(images)), Boards())
    assert [(t.x, t.y) for t in tiles] == [(0, 0), (3, 0), (6, 0), (9, 0), (0, 8)]
    assert [t.image_id for t in tiles] == [img.image_id for img in images]


def test_new_images_go_below_the_saved_tiles():
    """Images without a tile are placed under the arranged ones; deleted images' tiles go."""
    kept, new = _image(1), _image(2, None)
    saved = [Tile(kept.image_id, 2, 0, 6, 10), Tile(_image(9).image_id, 0, 30, 4, 4)]
    tiles = board.board(Images(new, kept), Boards(saved))
    assert tiles == [Tile(kept.image_id, 2, 0, 6, 10), Tile(new.image_id, 0, 10, 3, 6)]


def test_saving_clamps_tiles_and_ignores_unknown_images():
    """Saved tiles stay inside the grid; unknown or repeated images are dropped."""
    image = _image(1)
    boards = Boards()
    saved = board.save_board(
        Images(image),
        boards,
        [
            Tile(image.image_id, 11, -3, 20, 99, "masks"),
            Tile(image.image_id, 0, 0, 1, 1),
            Tile("x", 0, 0, 1, 1),
        ],
    )
    assert saved == boards.tiles == [Tile(image.image_id, 0, 0, 12, board.MAX_ROWS, "masks")]
