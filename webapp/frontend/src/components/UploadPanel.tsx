// Add a photo: drop or pick a file, or paste an image URL.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ImageUp, Link2, LoaderCircle } from "lucide-react";
import { useRef, useState } from "react";
import { api, type Uploaded } from "../api";

interface Props {
  maxBytes: number;
  onUploaded: (result: Uploaded) => void;
}

export function UploadPanel({ maxBytes, onUploaded }: Props) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [dragging, setDragging] = useState(false);
  const [tooLarge, setTooLarge] = useState(false);

  const done = (result: Uploaded) => {
    queryClient.setQueryData(["image", result.image.id], result.image);
    void queryClient.invalidateQueries({ queryKey: ["images"] });
    onUploaded(result);
  };
  const upload = useMutation({ mutationFn: api.upload, onSuccess: done });
  const fromUrl = useMutation({
    mutationFn: api.uploadUrl,
    onSuccess: (result) => {
      setUrl("");
      done(result);
    },
  });
  const busy = upload.isPending || fromUrl.isPending;
  const error = tooLarge
    ? `Files are limited to ${String(Math.round(maxBytes / 2 ** 20))} MB.`
    : (upload.error ?? fromUrl.error)?.message;

  const send = (file: File | undefined) => {
    if (!file) return;
    setTooLarge(file.size > maxBytes);
    if (file.size <= maxBytes) upload.mutate(file);
  };

  return (
    <div className="grid gap-3 md:grid-cols-[1fr_1.2fr]">
      <button
        type="button"
        disabled={busy}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => {
          setDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          send(e.dataTransfer.files[0]);
        }}
        className={`flex items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-5 text-sm transition ${
          dragging ? "border-indigo-500 bg-indigo-50" : "border-stone-300 bg-white hover:border-stone-400"
        } disabled:opacity-50`}
      >
        {upload.isPending ? (
          <LoaderCircle className="size-5 animate-spin" />
        ) : (
          <ImageUp className="size-5" />
        )}
        <span>
          <strong>Drop a photo</strong> or click to choose one
        </span>
      </button>
      <input
        ref={input}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          send(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (url.trim()) fromUrl.mutate(url.trim());
        }}
        className="flex items-center gap-2 rounded-2xl bg-white px-3 py-2 shadow-sm"
      >
        <Link2 className="size-5 shrink-0 text-stone-400" />
        <input
          type="url"
          required
          placeholder="…or paste an image URL"
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
          }}
          className="min-w-0 flex-1 bg-transparent py-2 text-sm outline-none"
        />
        <button
          type="submit"
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {fromUrl.isPending && <LoaderCircle className="size-4 animate-spin" />} Analyse
        </button>
      </form>
      {error && <p className="text-sm text-red-700 md:col-span-2">{error}</p>}
    </div>
  );
}
