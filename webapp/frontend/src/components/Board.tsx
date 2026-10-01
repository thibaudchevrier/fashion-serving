// The board: the photos as a composition, arranged and resized at will, saved on the server.
// View mode: a click opens the photo's details. Arrange mode: tiles move and resize.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LayoutGrid, Lock, LockOpen } from "lucide-react";
import { useMemo, useState } from "react";
import ReactGridLayout, { useContainerWidth } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import { api, type Config, type ImageSummary, type Tile } from "../api";
import { applyLayout, autoArrange, COLUMNS } from "../layout";
import { BoardTile } from "./BoardTile";

interface Props {
  config: Config;
  onOpen: (id: string) => void;
}

// Below this width the board is a simple two-column list: dragging on a phone is clumsy.
const WIDE = 1024;
const ROW_HEIGHT = 44;

export function Board({ config, onOpen }: Props) {
  const queryClient = useQueryClient();
  const board = useQuery({ queryKey: ["board"], queryFn: api.board });
  const images = useQuery({ queryKey: ["images"], queryFn: api.images });
  const [arranging, setArranging] = useState(false);
  const { width, containerRef, mounted } = useContainerWidth();

  const save = useMutation({
    mutationFn: api.saveBoard,
    onMutate: (tiles) => {
      queryClient.setQueryData(["board"], tiles);
    },
    onSuccess: (tiles) => {
      queryClient.setQueryData(["board"], tiles);
    },
  });
  const byId = useMemo(
    () => new Map<string, ImageSummary>((images.data ?? []).map((i) => [i.id, i])),
    [images.data],
  );
  const tiles = (board.data ?? []).filter((t) => byId.has(t.id));
  const setTiles = (next: Tile[]) => {
    save.mutate(next);
  };

  if (board.isPending || images.isPending) return <p className="p-8 text-stone-500">Loading…</p>;
  if (board.isError) return <p className="p-8 text-red-700">{board.error.message}</p>;
  if (tiles.length === 0) {
    return (
      <div className="grid min-h-80 place-items-center rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">
        Add photos above to compose your board.
      </div>
    );
  }

  const tile = (t: Tile) => {
    const image = byId.get(t.id);
    return image ? (
      <BoardTile
        image={image}
        view={t.view}
        config={config}
        arranging={arranging}
        onOpen={() => {
          onOpen(t.id);
        }}
        onView={(view) => {
          setTiles(tiles.map((other) => (other.id === t.id ? { ...other, view } : other)));
        }}
      />
    ) : null;
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="mr-auto text-sm text-stone-500">
          {arranging
            ? "Drag tiles to move them, drag a corner to resize them."
            : "Click a photo for its details; hover it to change what it shows."}
        </p>
        {arranging && (
          <button
            type="button"
            onClick={() => {
              setTiles(autoArrange(tiles, byId));
            }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm hover:bg-stone-100"
          >
            <LayoutGrid className="size-4" /> Auto-arrange
          </button>
        )}
        <button
          type="button"
          onClick={() => {
            setArranging(!arranging);
          }}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm ${
            arranging ? "bg-indigo-600 text-white hover:bg-indigo-500" : "border border-stone-300 bg-white hover:bg-stone-100"
          }`}
        >
          {arranging ? <LockOpen className="size-4" /> : <Lock className="size-4" />}
          {arranging ? "Done" : "Arrange"}
        </button>
      </div>

      <div ref={containerRef}>
        {mounted && width >= WIDE ? (
          <ReactGridLayout
            width={width}
            layout={tiles.map((t) => ({ i: t.id, x: t.x, y: t.y, w: t.w, h: t.h, minW: 2, minH: 3 }))}
            gridConfig={{ cols: COLUMNS, rowHeight: ROW_HEIGHT, margin: [12, 12], containerPadding: [0, 0] }}
            dragConfig={{ enabled: arranging }}
            resizeConfig={{ enabled: arranging, handles: ["se"] }}
            onDragStop={(layout) => {
              setTiles(applyLayout(tiles, layout));
            }}
            onResizeStop={(layout) => {
              setTiles(applyLayout(tiles, layout));
            }}
          >
            {tiles.map((t) => (
              <div key={t.id}>{tile(t)}</div>
            ))}
          </ReactGridLayout>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {[...tiles]
              .sort((a, b) => a.y - b.y || a.x - b.x)
              .map((t) => (
                <div key={t.id} className="aspect-[3/4]">
                  {tile(t)}
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
