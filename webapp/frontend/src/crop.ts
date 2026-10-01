// Where to place a photo inside a tile so that its outfit is framed: centred on the outfit, with
// room above it for the head, zoomed in only moderately, and always covering the tile.

export interface Size {
  width: number;
  height: number;
}

/** Position and size of the photo, in pixels, relative to the tile's top-left corner. */
export interface Placement {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface FrameOptions {
  /** Margin around the outfit, as a fraction of its size. */
  margin: number;
  /** Room kept above the outfit (heads are not garments), as a fraction of its height. */
  headroom: number;
  /** Most zoom, relative to simply covering the tile with the whole photo. */
  maxZoom: number;
}

const DEFAULTS: FrameOptions = { margin: 0.12, headroom: 0.25, maxZoom: 1.6 };

/**
 * Place a photo in a tile, framing an outfit box (`[y1, x1, y2, x2]`).
 * Without an outfit, the photo simply covers the tile, centred.
 */
export function frame(
  tile: Size,
  photo: Size,
  outfit: readonly [number, number, number, number] | null,
  options: Partial<FrameOptions> = {},
): Placement {
  const { margin, headroom, maxZoom } = { ...DEFAULTS, ...options };
  const cover = Math.max(tile.width / photo.width, tile.height / photo.height);
  let scale = cover;
  let cx = photo.width / 2;
  let cy = photo.height / 2;
  if (outfit) {
    const [y1, x1, y2, x2] = outfit;
    const top = Math.max(0, y1 - (y2 - y1) * headroom);
    const w = (x2 - x1) * (1 + 2 * margin);
    const h = (y2 - top) * (1 + 2 * margin);
    // Zoom so the outfit fits, within limits, never so little that the photo leaves gaps.
    scale = Math.min(Math.max(Math.min(tile.width / w, tile.height / h), cover), cover * maxZoom);
    cx = (x1 + x2) / 2;
    cy = (top + y2) / 2;
  }
  const width = photo.width * scale;
  const height = photo.height * scale;
  const clamp = (value: number, min: number) => Math.min(0, Math.max(min, value));
  return {
    width,
    height,
    left: clamp(tile.width / 2 - cx * scale, tile.width - width),
    top: clamp(tile.height / 2 - cy * scale, tile.height - height),
  };
}
