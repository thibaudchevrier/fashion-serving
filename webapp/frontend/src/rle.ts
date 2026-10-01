// Masks as the contract encodes them (fashion_seg_contract.rle): space-separated "start length"
// pairs, 1-indexed starts, pixels enumerated column by column (top to bottom, then left to right).
// The browser draws row by row, so runs are converted to row-major pixel indices.

/** Row-major indices (`y * width + x`) of the pixels covered by a mask. */
export function maskPixels(rle: string, height: number, width: number): Int32Array {
  const values = rle.trim() === "" ? [] : rle.trim().split(/\s+/).map(Number);
  if (values.length % 2 !== 0) throw new Error("RLE must hold start/length pairs");
  let total = 0;
  for (let i = 1; i < values.length; i += 2) total += values[i] ?? 0;
  const pixels = new Int32Array(total);
  let n = 0;
  for (let i = 0; i < values.length; i += 2) {
    const start = (values[i] ?? 1) - 1;
    const length = values[i + 1] ?? 0;
    for (let p = start; p < start + length; p++) {
      const x = Math.floor(p / height);
      const y = p % height;
      if (x < width) pixels[n++] = y * width + x;
    }
  }
  return n === total ? pixels : pixels.slice(0, n);
}

/** The mask as a row-major 0/1 array of `height * width` pixels. */
export function decodeMask(rle: string, height: number, width: number): Uint8Array {
  const mask = new Uint8Array(height * width);
  for (const p of maskPixels(rle, height, width)) mask[p] = 1;
  return mask;
}
