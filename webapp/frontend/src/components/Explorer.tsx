// One photo and its garments: masks over the photo, a confidence slider, the garment list.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, EyeOff, Layers, RefreshCw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { api, urls, type Config, type Garment } from "../api";
import { MaskCanvas } from "./MaskCanvas";

interface Props {
  id: string;
  config: Config;
  onDeleted: () => void;
}

export function Explorer({ id, config, onDeleted }: Props) {
  const queryClient = useQueryClient();
  const image = useQuery({ queryKey: ["image", id], queryFn: () => api.image(id) });
  const [threshold, setThreshold] = useState(config.default_threshold);
  const [hidden, setHidden] = useState<Set<number>>(new Set());
  const [hovered, setHovered] = useState<number | null>(null);
  const [showMasks, setShowMasks] = useState(true);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["images"] });
  const analyse = useMutation({
    mutationFn: () => api.analyse(id),
    onSuccess: (details) => {
      queryClient.setQueryData(["image", id], details);
      void refresh();
    },
  });
  const remove = useMutation({
    mutationFn: () => api.remove(id),
    onSuccess: () => {
      void refresh();
      onDeleted();
    },
  });

  const garments = useMemo(
    () => (image.data?.garments ?? []).filter((g) => g.score >= threshold),
    [image.data, threshold],
  );
  const visible = useMemo(
    () => new Set(garments.filter((g) => !hidden.has(g.index)).map((g) => g.index)),
    [garments, hidden],
  );

  if (image.isPending) return <p className="p-8 text-stone-500">Loading…</p>;
  if (image.isError) return <p className="p-8 text-red-700">{image.error.message}</p>;
  const details = image.data;
  const focused = details.garments.find((g) => g.index === hovered);

  const toggle = (index: number) => {
    setHidden((current) => {
      const next = new Set(current);
      if (!next.delete(index)) next.add(index);
      return next;
    });
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="min-w-0">
        {/* Sized by the photo (at most 75% of the window height): the masks cover it exactly. */}
        <div className="relative mx-auto w-fit overflow-hidden rounded-2xl bg-stone-200 shadow-sm">
          <img
            src={urls.photo(id)}
            alt="Uploaded"
            className="block max-h-[75vh] w-auto max-w-full select-none"
          />
          {showMasks && details.width !== null && details.height !== null && (
            <MaskCanvas
              width={details.width}
              height={details.height}
              garments={details.garments}
              visible={visible}
              hovered={hovered}
              onHover={setHovered}
            />
          )}
          {focused && (
            <span className="pointer-events-none absolute left-3 top-3 rounded-full bg-stone-900/80 px-3 py-1 text-sm text-white backdrop-blur">
              {focused.label} · {Math.round(focused.score * 100)}%
            </span>
          )}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setShowMasks(!showMasks);
            }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-100"
          >
            <Layers className="size-4" /> {showMasks ? "Hide masks" : "Show masks"}
          </button>
          {!details.analysed && (
            <button
              type="button"
              disabled={analyse.isPending}
              onClick={() => {
                analyse.mutate();
              }}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              <RefreshCw className="size-4" /> Analyse
            </button>
          )}
          <button
            type="button"
            disabled={remove.isPending}
            onClick={() => {
              remove.mutate();
            }}
            className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50"
          >
            <Trash2 className="size-4" /> Delete
          </button>
        </div>
        {analyse.isError && <p className="mt-2 text-sm text-red-700">{analyse.error.message}</p>}
      </section>

      <aside className="space-y-4">
        {details.analysed ? (
          <>
            <label className="block rounded-2xl bg-white p-4 shadow-sm">
              <span className="flex justify-between text-sm font-medium">
                Confidence threshold <span>{Math.round(threshold * 100)}%</span>
              </span>
              <input
                type="range"
                min={config.min_score}
                max={1}
                step={0.01}
                value={threshold}
                onChange={(e) => {
                  setThreshold(Number(e.target.value));
                }}
                className="mt-2 w-full accent-indigo-600"
              />
              <span className="text-xs text-stone-500">
                {garments.length} of {details.garments.length} detections shown
              </span>
            </label>
            <ul className="space-y-2">
              {garments.map((g) => (
                <GarmentRow
                  key={g.index}
                  imageId={id}
                  garment={g}
                  shown={!hidden.has(g.index)}
                  highlighted={hovered === g.index}
                  onToggle={() => {
                    toggle(g.index);
                  }}
                  onHover={setHovered}
                />
              ))}
              {garments.length === 0 && (
                <li className="rounded-2xl bg-white p-4 text-sm text-stone-500 shadow-sm">
                  No garment above this threshold.
                </li>
              )}
            </ul>
          </>
        ) : (
          <p className="rounded-2xl bg-white p-4 text-sm text-stone-600 shadow-sm">
            Not analysed yet: the model was unavailable. Retry with <strong>Analyse</strong>.
          </p>
        )}
      </aside>
    </div>
  );
}

interface RowProps {
  imageId: string;
  garment: Garment;
  shown: boolean;
  highlighted: boolean;
  onToggle: () => void;
  onHover: (index: number | null) => void;
}

function GarmentRow({ imageId, garment, shown, highlighted, onToggle, onHover }: RowProps) {
  return (
    <li
      onPointerEnter={() => {
        onHover(garment.index);
      }}
      onPointerLeave={() => {
        onHover(null);
      }}
      className={`rounded-2xl bg-white p-3 shadow-sm ring-2 transition ${
        highlighted ? "ring-indigo-400" : "ring-transparent"
      } ${shown ? "" : "opacity-50"}`}
    >
      <div className="flex items-center gap-2">
        <span className="size-3 shrink-0 rounded-full" style={{ background: garment.color }} />
        <span className="font-medium capitalize">{garment.label}</span>
        <span className="text-sm text-stone-500">{Math.round(garment.score * 100)}%</span>
        <span className="ml-auto flex gap-1">
          <button
            type="button"
            onClick={onToggle}
            title={shown ? "Hide" : "Show"}
            className="rounded-md p-1 text-stone-500 hover:bg-stone-100"
          >
            {shown ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
          </button>
          <a
            href={urls.cutout(imageId, garment.index)}
            download={`${garment.label}.png`}
            title="Download the cutout"
            className="rounded-md p-1 text-stone-500 hover:bg-stone-100"
          >
            <Download className="size-4" />
          </a>
        </span>
      </div>
      <div className="mt-2 flex h-2 overflow-hidden rounded-full" title="Dominant colors">
        {garment.palette.map((s) => (
          <span key={s.hex} style={{ background: s.hex, flexGrow: s.share }} />
        ))}
      </div>
      <p className="mt-1 text-xs text-stone-500">
        {garment.palette.map((s) => `${s.name} ${String(Math.round(s.share * 100))}%`).join(" · ")}
      </p>
    </li>
  );
}
