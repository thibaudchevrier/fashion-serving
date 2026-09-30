// Garment masks drawn over the photo, with hover detection.
// Each mask is decoded once per image; repainting (hover, threshold, toggles) only fills pixels.
import { useEffect, useMemo, useRef } from "react";
import type { Garment } from "../api";
import { maskPixels } from "../rle";

interface Props {
  width: number;
  height: number;
  garments: Garment[];
  /** Indices of the garments to draw. */
  visible: Set<number>;
  hovered: number | null;
  onHover: (index: number | null) => void;
}

const ALPHA = { normal: 115, hovered: 175, dimmed: 35 };

function rgb(hex: string): [number, number, number] {
  const value = Number.parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

export function MaskCanvas({ width, height, garments, visible, hovered, onHover }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  // Which garment is drawn on top at each pixel (-1: none), for hover lookups.
  const owner = useRef<Int16Array>(new Int16Array(0));

  const layers = useMemo(
    () =>
      garments.map((g) => ({
        garment: g,
        pixels: maskPixels(g.mask_rle, height, width),
        color: rgb(g.color),
      })),
    [garments, height, width],
  );

  useEffect(() => {
    const context = canvas.current?.getContext("2d");
    if (!context) return;
    const image = context.createImageData(width, height);
    const top = new Int16Array(width * height).fill(-1);
    // Least confident first: the most confident garment ends up on top.
    const drawn = layers
      .filter((l) => visible.has(l.garment.index))
      .sort((a, b) => a.garment.score - b.garment.score);
    for (const { garment, pixels, color } of drawn) {
      const alpha =
        hovered === null
          ? ALPHA.normal
          : hovered === garment.index
            ? ALPHA.hovered
            : ALPHA.dimmed;
      for (const p of pixels) {
        const o = p * 4;
        image.data[o] = color[0];
        image.data[o + 1] = color[1];
        image.data[o + 2] = color[2];
        image.data[o + 3] = alpha;
        top[p] = garment.index;
      }
    }
    context.putImageData(image, 0, 0);
    owner.current = top;
    const focus = drawn.find((l) => l.garment.index === hovered);
    if (focus) {
      const [y1, x1, y2, x2] = focus.garment.box;
      context.lineWidth = Math.max(2, Math.round(width / 300));
      context.strokeStyle = focus.garment.color;
      context.strokeRect(x1, y1, x2 - x1, y2 - y1);
    }
  }, [layers, visible, hovered, width, height]);

  function pick(event: React.PointerEvent<HTMLCanvasElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.floor(((event.clientX - rect.left) / rect.width) * width);
    const y = Math.floor(((event.clientY - rect.top) / rect.height) * height);
    const index = x >= 0 && y >= 0 && x < width && y < height ? owner.current[y * width + x] : -1;
    const next = index === undefined || index < 0 ? null : index;
    if (next !== hovered) onHover(next);
  }

  return (
    <canvas
      ref={canvas}
      width={width}
      height={height}
      className="absolute inset-0 h-full w-full cursor-crosshair"
      onPointerMove={pick}
      onPointerLeave={() => {
        onHover(null);
      }}
    />
  );
}
