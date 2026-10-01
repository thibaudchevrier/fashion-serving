import { describe, expect, it } from "vitest";
import { frame } from "./crop";

const covers = (p: ReturnType<typeof frame>, tile: { width: number; height: number }) =>
  p.left <= 0 && p.top <= 0 && p.left + p.width >= tile.width - 1e-9 && p.top + p.height >= tile.height - 1e-9;

describe("framing a photo in a tile", () => {
  it("covers the tile, centred, without an outfit", () => {
    const p = frame({ width: 100, height: 100 }, { width: 400, height: 200 }, null);
    expect(p).toEqual({ width: 200, height: 100, left: -50, top: 0 });
  });

  it("zooms on a small outfit, centred, within the zoom limit", () => {
    const tile = { width: 100, height: 100 };
    const p = frame(tile, { width: 1000, height: 1000 }, [450, 450, 550, 550], { margin: 0, headroom: 0, maxZoom: 2 });
    expect(p.width).toBe(200); // the 100 px outfit would need 10x: capped at 2x cover (0.1)
    expect([p.left, p.top]).toEqual([-50, -50]);
    expect(covers(p, tile)).toBe(true);
  });

  it("keeps room above the outfit for the head", () => {
    const tile = { width: 100, height: 100 };
    const photo = { width: 1000, height: 1000 };
    const outfit = [400, 400, 600, 600] as const;
    const withHead = frame(tile, photo, outfit, { margin: 0, headroom: 0.5, maxZoom: 10 });
    const without = frame(tile, photo, outfit, { margin: 0, headroom: 0, maxZoom: 10 });
    expect(withHead.top).toBeGreaterThan(without.top); // the photo sits lower: more above shows
  });

  it("never leaves gaps, even for an outfit at the photo's edge", () => {
    const tile = { width: 300, height: 200 };
    const p = frame(tile, { width: 600, height: 400 }, [0, 0, 50, 50]);
    expect(covers(p, tile)).toBe(true);
    expect([p.left, p.top]).toEqual([0, 0]);
  });
});
