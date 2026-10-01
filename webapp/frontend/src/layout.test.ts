import { describe, expect, it } from "vitest";
import type { ImageSummary, Tile } from "./api";
import { applyLayout, autoArrange, sizeFor } from "./layout";

const image = (id: string, width: number, height: number): ImageSummary => ({
  id, analysed: true, garment_count: 1, width, height, outfit: null,
});
const tile = (id: string, x: number, y: number): Tile => ({ id, x, y, w: 2, h: 2, view: "photo" });

describe("board layouts", () => {
  it("sizes tiles after the photo's orientation", () => {
    expect(sizeFor(image("p", 400, 800))).toEqual({ w: 3, h: 8 });
    expect(sizeFor(image("l", 800, 400))).toEqual({ w: 4, h: 5 });
    expect(sizeFor({ width: null, height: null })).toEqual({ w: 3, h: 6 });
  });

  it("arranges tiles in reading order, wrapping at the grid's width", () => {
    const tiles = ["a", "b", "c", "d", "e"].map((id, n) => tile(id, 0, n));
    const images = new Map(tiles.map((t) => [t.id, image(t.id, 400, 800)]));
    const arranged = autoArrange(tiles, images);
    expect(arranged.map((t) => [t.id, t.x, t.y])).toEqual([
      ["a", 0, 0], ["b", 3, 0], ["c", 6, 0], ["d", 9, 0], ["e", 0, 8],
    ]);
  });

  it("applies the grid's positions and keeps each tile's view", () => {
    const tiles: Tile[] = [{ ...tile("a", 0, 0), view: "cutouts" }];
    expect(applyLayout(tiles, [{ i: "a", x: 5, y: 1, w: 4, h: 3 }])).toEqual([
      { id: "a", x: 5, y: 1, w: 4, h: 3, view: "cutouts" },
    ]);
  });
});
