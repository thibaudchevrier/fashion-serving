import { describe, expect, it } from "vitest";
import { decodeMask, maskPixels } from "./rle";

describe("RLE masks (fashion_seg_contract.rle)", () => {
  it("decodes column-major runs like the Python contract", () => {
    // Same example as fashion_seg_contract.rle.decode's docstring: [[1, 1], [1, 0], [0, 0]].
    expect(Array.from(decodeMask("1 2 4 1", 3, 2))).toEqual([1, 1, 1, 0, 0, 0]);
  });

  it("covers the whole image", () => {
    expect(decodeMask("1 16", 4, 4).every((v) => v === 1)).toBe(true);
  });

  it("lists row-major pixel indices", () => {
    // 3 rows x 2 columns: the second column's middle pixel is row 1, column 1.
    expect(Array.from(maskPixels("5 1", 3, 2))).toEqual([3]);
  });

  it("accepts empty masks and rejects odd lists", () => {
    expect(maskPixels("", 3, 2).length).toBe(0);
    expect(() => maskPixels("1 2 3", 3, 2)).toThrow();
  });
});
