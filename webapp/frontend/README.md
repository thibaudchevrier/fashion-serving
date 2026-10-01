# Front end

React 19 + TypeScript + Vite, styled with Tailwind CSS 4, data from the webapp's JSON API
(`/api`, see `/docs`) through TanStack Query. The production build (`dist/`) is served by the
FastAPI app (`FRONTEND_DIR`); the Docker image builds it in its first stage.

| File | Role |
|------|------|
| `src/api.ts` | Typed client of the API (types mirror `fashion_webapp.api`) |
| `src/rle.ts` | Decodes the contract's masks (column-major runs) into row-major pixels |
| `src/components/UploadPanel.tsx` | Drop or pick a photo, or paste an image URL |
| `src/components/Board.tsx` | The board (home): view and arrange modes, auto-arrange, saved on each move or resize ([react-grid-layout](https://github.com/react-grid-layout/react-grid-layout); a plain grid below 1024 px) |
| `src/components/BoardTile.tsx` | One tile: framed photo, photo with masks, or cutouts; label overlay on hover |
| `src/components/DetailsPanel.tsx` | A photo's details in a side panel over the board (Esc closes) |
| `src/components/Gallery.tsx` | Uploaded photos (full view) |
| `src/components/Explorer.tsx` | A photo's garments: confidence slider, grouped list with colors, cutouts; side by side or stacked depending on its container |
| `src/components/MaskCanvas.tsx` | Masks drawn over the photo (one canvas), hover detection, "peek" with masks hidden |
| `src/crop.ts` | Where to place a photo in a tile to frame its outfit (headroom, limited zoom, no gaps) |
| `src/layout.ts` | Tile sizes by orientation, auto-arrange, grid layout to tiles |
| `src/App.tsx` | Views and routes: `#/` board, `#/board/<id>` board with details, `#/images/<id>` full view |

Every detection from `min_score` (0.3) is loaded once: the threshold slider, the toggles and the
hover work in the browser, without calling the model again.

```bash
make front-check   # types, lint, unit tests, build (npm, or Node in Docker if npm is missing)
make up            # the whole stack, front end included, on :8000
make front-dev     # hot reload on :5173 against the API of `make up` (needs Node 24 locally)
```

The board's layout is saved on the server (`PUT /api/board`), so it is the same in every
browser.

Checks: `tsc` in strict mode (with `noUncheckedIndexedAccess`), typescript-eslint's
`strictTypeChecked` rules plus the React hooks rules, Vitest for the pure modules.
