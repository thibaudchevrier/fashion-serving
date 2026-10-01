// One photo on the board: framed around its outfit, with its masks, or as its garments cut out.
import { useQuery } from "@tanstack/react-query";
import { Image as ImageIcon, Layers, Scissors } from "lucide-react";
import { api, urls, type Config, type ImageSummary, type TileView } from "../api";
import { frame } from "../crop";
import { useSize } from "../useSize";
import { MaskCanvas } from "./MaskCanvas";

interface Props {
  image: ImageSummary;
  view: TileView;
  config: Config;
  /** In arrange mode the tile is only moved and resized: no menu, no details on click. */
  arranging: boolean;
  onOpen: () => void;
  onView: (view: TileView) => void;
}

const VIEWS: { view: TileView; label: string; icon: typeof Layers }[] = [
  { view: "photo", label: "Photo", icon: ImageIcon },
  { view: "masks", label: "Masks", icon: Layers },
  { view: "cutouts", label: "Cutouts", icon: Scissors },
];
const NONE = new Set<number>();

/** Size of each cutout: one fills the tile, several share it. */
function cutoutSize(count: number): string {
  if (count === 1) return "max-h-[85%] max-w-[85%]";
  if (count === 2) return "max-h-[80%] max-w-[46%]";
  return count <= 4 ? "max-h-[46%] max-w-[46%]" : "max-h-[46%] max-w-[30%]";
}

export function BoardTile({ image, view, config, arranging, onOpen, onView }: Props) {
  const [ref, size] = useSize<HTMLDivElement>();
  const details = useQuery({
    queryKey: ["image", image.id],
    queryFn: () => api.image(image.id),
    enabled: image.analysed,
  });
  const shown = (details.data?.garments ?? []).filter((g) => g.score >= config.default_threshold);
  const items = shown.filter((g) => g.group !== "part");
  const photo = image.width !== null && image.height !== null ? { width: image.width, height: image.height } : null;
  const placement = photo && size.width > 0 ? frame(size, photo, image.outfit) : null;

  return (
    <div
      ref={ref}
      onClick={arranging ? undefined : onOpen}
      className={`group relative h-full w-full overflow-hidden rounded-2xl bg-stone-200 shadow-sm ${
        arranging ? "cursor-move ring-2 ring-indigo-300" : "cursor-pointer"
      }`}
    >
      {view === "cutouts" && items.length > 0 ? (
        <div className="flex h-full w-full flex-wrap content-center items-center justify-center gap-2 bg-stone-100 p-3">
          {items.slice(0, 6).map((g) => (
            <img
              key={g.index}
              src={urls.cutout(image.id, g.index)}
              alt={g.label}
              title={g.label}
              draggable={false}
              className={`${cutoutSize(Math.min(items.length, 6))} object-contain drop-shadow`}
            />
          ))}
        </div>
      ) : placement ? (
        <div className="absolute" style={placement}>
          <img src={urls.photo(image.id)} alt="" draggable={false} className="h-full w-full select-none" />
          {view === "masks" && details.data && photo && (
            <MaskCanvas
              width={photo.width}
              height={photo.height}
              garments={details.data.garments}
              visible={new Set(shown.map((g) => g.index))}
              showAll
              highlighted={NONE}
              onHover={() => undefined}
            />
          )}
        </div>
      ) : (
        <img src={urls.photo(image.id)} alt="" draggable={false} className="h-full w-full object-cover" />
      )}

      {!arranging && (
        <>
          <div className="absolute right-2 top-2 flex gap-1 rounded-lg bg-white/90 p-1 opacity-0 shadow transition group-hover:opacity-100">
            {VIEWS.map(({ view: v, label, icon: Icon }) => (
              <button
                key={v}
                type="button"
                title={label}
                onClick={(e) => {
                  e.stopPropagation();
                  onView(v);
                }}
                className={`rounded-md p-1 ${v === view ? "bg-indigo-600 text-white" : "text-stone-600 hover:bg-stone-100"}`}
              >
                <Icon className="size-4" />
              </button>
            ))}
          </div>
          {items.length > 0 && (
            <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-wrap items-center gap-1.5 bg-gradient-to-t from-stone-900/75 to-transparent px-3 pb-2 pt-8 opacity-0 transition group-hover:opacity-100">
              {items.slice(0, 4).map((g) => (
                <span key={g.index} className="flex items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-xs capitalize">
                  <span className="size-2 rounded-full" style={{ background: g.palette[0]?.hex ?? g.color }} />
                  {g.label.split(",")[0]}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
