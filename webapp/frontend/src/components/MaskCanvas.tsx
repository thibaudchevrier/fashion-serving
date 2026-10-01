// Garment masks drawn over the photo, with hover detection.
// Each mask is decoded once per image; repainting (hover, threshold, toggles) only fills pixels.
// What is drawn and what can be hovered are separate: with masks hidden, nothing is drawn but the
// garment under the pointer can still be found and shown ("peek").
import { useEffect, useMemo, useRef } from "react";
import type { Garment } from "../api";
import { maskPixels } from "../rle";

interface Props {
  width: number;
  height: number;
  garments: Garment[];
  /** Garments that can be hovered: shown by the threshold and not hidden. */
  visible: Set<number>;
  /** Whether every visible mask is drawn; otherwise only the highlighted ones are. */
  showAll: boolean;
  /** Garments to emphasise (one hovered garment, or a hovered group); empty for none. */
  highlighted: Set<number>;
  onHover: (index: number | null) => void;
}

const ALPHA = { normal: 115, highlighted: 175, dimmed: 35 };

function rgb(hex: string): [number, number, number] {
  const value = Number.parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

export function MaskCanvas({ width, height, garments, visible, showAll, highlighted, onHover }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  // Which visible garment is on top at each pixel (-1: none), for hover lookups.
  const owner = useRef<Int16Array>(new Int16Array(0));

  const layers = useMemo(
    () =>
      garments
        .map((g) => ({ garment: g, pixels: maskPixels(g.mask_rle, height, width), color: rgb(g.color) }))
        // Least confident first: the most confident garment ends up on top.
        .sort((a, b) => a.garment.score - b.garment.score),
    [garments, height, width],
  );

  useEffect(() => {
    const top = new Int16Array(width * height).fill(-1);
    for (const { garment, pixels } of layers) {
      if (!visible.has(garment.index)) continue;
      for (const p of pixels) top[p] = garment.index;
    }
    owner.current = top;
  }, [layers, visible, width, height]);

  useEffect(() => {
    const context = canvas.current?.getContext("2d");
    if (!context) return;
    const image = context.createImageData(width, height);
    const focusing = highlighted.size > 0;
    const drawn = layers.filter(
      ({ garment }) =>
        visible.has(garment.index) && (showAll || highlighted.has(garment.index)),
    );
    for (const { garment, pixels, color } of drawn) {
      const alpha = !focusing
        ? ALPHA.normal
        : highlighted.has(garment.index)
          ? ALPHA.highlighted
          : ALPHA.dimmed;
      for (const p of pixels) {
        const o = p * 4;
        image.data[o] = color[0];
        image.data[o + 1] = color[1];
        image.data[o + 2] = color[2];
        image.data[o + 3] = alpha;
      }
    }
    context.putImageData(image, 0, 0);
    context.lineWidth = Math.max(2, Math.round(width / 300));
    for (const { garment } of drawn) {
      if (!highlighted.has(garment.index)) continue;
      const [y1, x1, y2, x2] = garment.box;
      context.strokeStyle = garment.color;
      context.strokeRect(x1, y1, x2 - x1, y2 - y1);
    }
  }, [layers, visible, showAll, highlighted, width, height]);

  function pick(event: React.PointerEvent<HTMLCanvasElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.floor(((event.clientX - rect.left) / rect.width) * width);
    const y = Math.floor(((event.clientY - rect.top) / rect.height) * height);
    const index = x >= 0 && y >= 0 && x < width && y < height ? owner.current[y * width + x] : -1;
    const next = index === undefined || index < 0 ? null : index;
    const current = highlighted.size === 1 ? [...highlighted][0] : null;
    if (next !== current) onHover(next);
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
