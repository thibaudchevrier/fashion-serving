// Every uploaded photo, most recent first; the selected one is outlined.
import { useQuery } from "@tanstack/react-query";
import { api, urls } from "../api";

interface Props {
  selected: string | null;
  onSelect: (id: string) => void;
}

export function Gallery({ selected, onSelect }: Props) {
  const images = useQuery({ queryKey: ["images"], queryFn: api.images });
  if (images.isPending) return null;
  if (images.isError) return <p className="text-sm text-red-700">{images.error.message}</p>;
  if (images.data.length === 0) {
    return <p className="text-sm text-stone-500">No photos yet.</p>;
  }
  return (
    <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-2">
      {images.data.map((image) => (
        <li key={image.id}>
          <button
            type="button"
            onClick={() => {
              onSelect(image.id);
            }}
            className={`relative block w-full overflow-hidden rounded-xl ring-2 transition ${
              image.id === selected ? "ring-indigo-500" : "ring-transparent hover:ring-stone-300"
            }`}
          >
            <img
              src={urls.photo(image.id)}
              alt=""
              loading="lazy"
              className="aspect-square w-full object-cover"
            />
            <span className="absolute bottom-1 right-1 rounded-full bg-stone-900/75 px-2 py-0.5 text-xs text-white">
              {image.analysed ? `${String(image.garment_count)} items` : "not analysed"}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
