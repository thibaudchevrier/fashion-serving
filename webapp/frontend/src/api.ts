// Typed client of the webapp's JSON API (fashion_webapp.api, documented at /docs).

export interface Config {
  /** Lowest confidence stored: a threshold below it shows nothing more. */
  min_score: number;
  /** Confidence threshold shown by default. */
  default_threshold: number;
  /** Largest accepted upload or download. */
  max_upload_bytes: number;
}

export interface Swatch {
  hex: string;
  name: string;
  share: number;
}

/** Kind of item: a whole garment, an accessory, or a garment part or decoration. */
export type Group = "garment" | "accessory" | "part";

export interface Garment {
  /** Identifies the garment within its image (cutout URL). */
  index: number;
  class_id: number;
  label: string;
  group: Group;
  score: number;
  /** [y1, x1, y2, x2] in image pixels, (y2, x2) excluded. */
  box: [number, number, number, number];
  /** The contract's run-length encoded mask (see rle.ts). */
  mask_rle: string;
  /** The class's display color, #rrggbb. */
  color: string;
  palette: Swatch[];
}

export interface ImageSummary {
  id: string;
  analysed: boolean;
  garment_count: number;
  width: number | null;
  height: number | null;
  /** [y1, x1, y2, x2]: the area covered by the garments shown by default (to crop around). */
  outfit: [number, number, number, number] | null;
}

/** What a board tile shows. */
export type TileView = "photo" | "masks" | "cutouts";

/** One photo on the board, on a 12-column grid. */
export interface Tile {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  view: TileView;
}

export interface ImageDetails {
  id: string;
  analysed: boolean;
  width: number | null;
  height: number | null;
  /** Most confident first. */
  garments: Garment[];
}

/** An upload, and whether the model answered (the image is kept either way). */
export interface Uploaded {
  image: ImageDetails;
  modelUnavailable: boolean;
}

/** A failed API call, with the server's explanation. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Not JSON: keep the status text.
    }
    throw new ApiError(response.status, detail);
  }
  return response;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  return (await (await call(path, init)).json()) as T;
}

async function uploaded(response: Response): Promise<Uploaded> {
  return {
    image: (await response.json()) as ImageDetails,
    modelUnavailable: response.headers.get("X-Model-Unavailable") === "true",
  };
}

export const api = {
  config: () => json<Config>("/config"),
  images: () => json<ImageSummary[]>("/images"),
  image: (id: string) => json<ImageDetails>(`/images/${id}`),
  upload: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return uploaded(await call("/images", { method: "POST", body: form }));
  },
  uploadUrl: async (url: string) =>
    uploaded(
      await call("/images/from-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      }),
    ),
  analyse: (id: string) => json<ImageDetails>(`/images/${id}/analyse`, { method: "POST" }),
  board: async () => (await json<{ tiles: Tile[] }>("/board")).tiles,
  saveBoard: async (tiles: Tile[]) =>
    (
      await json<{ tiles: Tile[] }>("/board", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tiles }),
      })
    ).tiles,
  remove: async (id: string) => {
    await call(`/images/${id}`, { method: "DELETE" });
  },
};

export const urls = {
  photo: (id: string) => `/api/images/${id}/image.jpg`,
  cutout: (id: string, index: number) => `/api/images/${id}/garments/${String(index)}/cutout.png`,
};
