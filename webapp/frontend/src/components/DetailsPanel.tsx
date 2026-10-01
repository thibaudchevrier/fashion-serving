// A photo's details over the board: a panel from the right, the board staying visible behind.
import { Maximize2, X } from "lucide-react";
import { useEffect } from "react";
import type { Config } from "../api";
import { Explorer } from "./Explorer";

interface Props {
  id: string;
  config: Config;
  onClose: () => void;
  onFullView: () => void;
}

export function DetailsPanel({ id, config, onClose, onFullView }: Props) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true" aria-label="Photo details">
      <button type="button" aria-label="Close" onClick={onClose} className="absolute inset-0 bg-stone-900/30 backdrop-blur-[2px]" />
      <div className="relative flex h-full w-full max-w-2xl flex-col bg-stone-50 shadow-2xl">
        <div className="flex items-center gap-2 border-b border-stone-200 px-4 py-3">
          <h2 className="mr-auto font-semibold">Details</h2>
          <button
            type="button"
            onClick={onFullView}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm hover:bg-stone-200"
          >
            <Maximize2 className="size-4" /> Full view
          </button>
          <button type="button" onClick={onClose} title="Close (Esc)" className="rounded-lg p-1.5 hover:bg-stone-200">
            <X className="size-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <Explorer key={id} id={id} config={config} onDeleted={onClose} />
        </div>
      </div>
    </div>
  );
}
