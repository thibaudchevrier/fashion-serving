// The page: add photos, then compose them on the board or inspect them one by one.
// Routes (in the URL, so links and back/forward work):
//   #/              the board
//   #/board/<id>    the board, with a photo's details open
//   #/images/<id>   the full view of a photo, next to the gallery
import { useQuery } from "@tanstack/react-query";
import { LayoutDashboard, ScanSearch, Shirt } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "./api";
import { Board } from "./components/Board";
import { DetailsPanel } from "./components/DetailsPanel";
import { Explorer } from "./components/Explorer";
import { Gallery } from "./components/Gallery";
import { UploadPanel } from "./components/UploadPanel";

type Route = { view: "board"; open: string | null } | { view: "explore"; id: string | null };

function parse(hash: string): Route {
  const board = /^#\/board\/([0-9a-f]{32})$/.exec(hash);
  if (board) return { view: "board", open: board[1] ?? null };
  const image = /^#\/images(?:\/([0-9a-f]{32}))?$/.exec(hash);
  if (image) return { view: "explore", id: image[1] ?? null };
  return { view: "board", open: null };
}

function go(route: Route) {
  window.location.hash =
    route.view === "board"
      ? route.open ? `/board/${route.open}` : "/"
      : route.id ? `/images/${route.id}` : "/images";
}

function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const onChange = () => {
      setRoute(parse(window.location.hash));
    };
    window.addEventListener("hashchange", onChange);
    return () => {
      window.removeEventListener("hashchange", onChange);
    };
  }, []);
  return route;
}

export function App() {
  const config = useQuery({ queryKey: ["config"], queryFn: api.config, staleTime: Infinity });
  const images = useQuery({ queryKey: ["images"], queryFn: api.images });
  const route = useRoute();
  const [notice, setNotice] = useState<string | null>(null);
  // The full view opens the most recent photo when none is chosen.
  const exploring = route.view === "explore" ? (route.id ?? images.data?.[0]?.id ?? null) : null;

  const tab = (active: boolean) =>
    `inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition ${
      active ? "bg-white shadow-sm" : "text-stone-600 hover:text-stone-900"
    }`;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <header className="mb-6 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-indigo-600 text-white">
            <Shirt className="size-5" />
          </span>
          <div className="mr-auto">
            <h1 className="text-xl font-semibold">Fashion segmentation</h1>
            <p className="text-sm text-stone-500">
              Find every garment in a photo: its shape, its colors, a cutout.{" "}
              <a href="/docs" className="text-indigo-600 hover:underline">
                API
              </a>
            </p>
          </div>
          <nav aria-label="Views" className="flex gap-1 rounded-xl bg-stone-200/70 p-1">
            <button type="button" className={tab(route.view === "board")} onClick={() => { go({ view: "board", open: null }); }}>
              <LayoutDashboard className="size-4" /> Board
            </button>
            <button type="button" className={tab(route.view === "explore")} onClick={() => { go({ view: "explore", id: null }); }}>
              <ScanSearch className="size-4" /> Explore
            </button>
          </nav>
        </div>
        {config.data && (
          <UploadPanel
            maxBytes={config.data.max_upload_bytes}
            onUploaded={({ image, modelUnavailable }) => {
              setNotice(
                modelUnavailable
                  ? "The model is unavailable right now: the photo was kept, analyse it later."
                  : null,
              );
              go(route.view === "board" ? { view: "board", open: image.id } : { view: "explore", id: image.id });
            }}
          />
        )}
        {notice && <p className="rounded-xl bg-amber-50 px-4 py-2 text-sm text-amber-800">{notice}</p>}
      </header>

      {config.data && route.view === "board" && (
        <>
          <Board config={config.data} onOpen={(id) => { go({ view: "board", open: id }); }} />
          {route.open && (
            <DetailsPanel
              id={route.open}
              config={config.data}
              onClose={() => { go({ view: "board", open: null }); }}
              onFullView={() => { go({ view: "explore", id: route.open }); }}
            />
          )}
        </>
      )}

      {config.data && route.view === "explore" && (
        <main className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
          <nav aria-label="Photos" className="order-2 lg:order-1">
            <Gallery selected={exploring} onSelect={(id) => { go({ view: "explore", id }); }} />
          </nav>
          <div className="order-1 lg:order-2">
            {exploring ? (
              <Explorer
                key={exploring}
                id={exploring}
                config={config.data}
                onDeleted={() => { go({ view: "explore", id: null }); }}
              />
            ) : (
              <div className="grid min-h-80 place-items-center rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">
                Add a photo above to explore its garments.
              </div>
            )}
          </div>
        </main>
      )}
    </div>
  );
}
