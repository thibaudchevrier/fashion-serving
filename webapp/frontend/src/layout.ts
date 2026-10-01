// Board layouts: tiles <-> the grid library's layout items, and automatic arrangement.
import type { ImageSummary, Tile } from "./api";

export const COLUMNS = 12;

/** Tile size for a photo, after its orientation (as the server sizes new tiles). */
export function sizeFor(image: Pick<ImageSummary, "width" | "height">): { w: number; h: number } {
  if (image.width === null || image.height === null) return { w: 3, h: 6 };
  const ratio = image.height / image.width;
  if (ratio > 1.15) return { w: 3, h: 8 };
  return ratio < 0.87 ? { w: 4, h: 5 } : { w: 3, h: 6 };
}

/** Rearrange the tiles neatly: sized by orientation, filling rows left to right, in order. */
export function autoArrange(tiles: Tile[], images: Map<string, ImageSummary>): Tile[] {
  const ordered = [...tiles].sort((a, b) => a.y - b.y || a.x - b.x);
  const arranged: Tile[] = [];
  let x = 0;
  let top = 0;
  let rowHeight = 0;
  for (const tile of ordered) {
    const image = images.get(tile.id);
    const { w, h } = image ? sizeFor(image) : { w: tile.w, h: tile.h };
    if (x + w > COLUMNS) {
      top += rowHeight;
      x = 0;
      rowHeight = 0;
    }
    arranged.push({ ...tile, x, y: top, w, h });
    x += w;
    rowHeight = Math.max(rowHeight, h);
  }
  return arranged;
}

/** Apply a layout from the grid (positions and sizes by id) to the tiles, keeping their view. */
export function applyLayout(
  tiles: Tile[],
  layout: readonly { i: string; x: number; y: number; w: number; h: number }[],
): Tile[] {
  const byId = new Map(layout.map((item) => [item.i, item]));
  return tiles.map((tile) => {
    const item = byId.get(tile.id);
    return item ? { ...tile, x: item.x, y: item.y, w: item.w, h: item.h } : tile;
  });
}
