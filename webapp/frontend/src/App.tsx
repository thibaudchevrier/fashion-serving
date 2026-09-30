// The page: add a photo, pick one in the gallery, explore its garments.
// The selected photo lives in the URL (#/images/<id>), so links and back/forward work.
import { useQuery } from "@tanstack/react-query";
import { Shirt } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "./api";
import { Explorer } from "./components/Explorer";
import { Gallery } from "./components/Gallery";
import { UploadPanel } from "./components/UploadPanel";

const ROUTE = /^#\/images\/([0-9a-f]{32})$/;

function useSelectedImage(): [string | null, (id: string | null) => void] {
  const read = () => ROUTE.exec(window.location.hash)?.[1] ?? null;
  const [id, setId] = useState(read);
  useEffect(() => {
    const onChange = () => {
      setId(read());
    };
    window.addEventListener("hashchange", onChange);
    return () => {
      window.removeEventListener("hashchange", onChange);
    };
  }, []);
  const select = (next: string | null) => {
    window.location.hash = next ? `/images/${next}` : "";
  };
  return [id, select];
}

export function App() {
  const config = useQuery({ queryKey: ["config"], queryFn: api.config, staleTime: Infinity });
  const [selected, select] = useSelectedImage();
  const [notice, setNotice] = useState<string | null>(null);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <header className="mb-6 space-y-4">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-indigo-600 text-white">
            <Shirt className="size-5" />
          </span>
          <div>
            <h1 className="text-xl font-semibold">Fashion segmentation</h1>
            <p className="text-sm text-stone-500">
              Find every garment in a photo: its shape, its colors, a cutout.{" "}
              <a href="/docs" className="text-indigo-600 hover:underline">
                API
              </a>
            </p>
          </div>
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
              select(image.id);
            }}
          />
        )}
        {notice && <p className="rounded-xl bg-amber-50 px-4 py-2 text-sm text-amber-800">{notice}</p>}
      </header>

      <main className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <nav aria-label="Photos" className="order-2 lg:order-1">
          <Gallery selected={selected} onSelect={select} />
        </nav>
        <div className="order-1 lg:order-2">
          {selected && config.data ? (
            <Explorer
              key={selected}
              id={selected}
              config={config.data}
              onDeleted={() => {
                select(null);
              }}
            />
          ) : (
            <div className="grid min-h-80 place-items-center rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">
              Add a photo above, or pick one on the left, to see its garments.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
