# Front end

React 19 + TypeScript + Vite, styled with Tailwind CSS 4, data from the webapp's JSON API
(`/api`, see `/docs`) through TanStack Query. The production build (`dist/`) is served by the
FastAPI app (`FRONTEND_DIR`); the Docker image builds it in its first stage.

| File | Role |
|------|------|
| `src/api.ts` | Typed client of the API (types mirror `fashion_webapp.api`) |
| `src/rle.ts` | Decodes the contract's masks (column-major runs) into row-major pixels |
| `src/components/UploadPanel.tsx` | Drop or pick a photo, or paste an image URL |
| `src/components/Gallery.tsx` | Uploaded photos |
| `src/components/Explorer.tsx` | A photo's garments: confidence slider, list with colors, cutouts |
| `src/components/MaskCanvas.tsx` | Masks drawn over the photo (one canvas), hover detection |
| `src/App.tsx` | Layout; the selected photo lives in the URL (`#/images/<id>`) |

Every detection from `min_score` (0.3) is loaded once: the threshold slider, the toggles and the
hover work in the browser, without calling the model again.

```bash
make front-check   # types, lint, unit tests, build (npm, or Node in Docker if npm is missing)
make up            # the whole stack, front end included, on :8000
make front-dev     # hot reload on :5173 against the API of `make up` (needs Node 24 locally)
```

Checks: `tsc` in strict mode (with `noUncheckedIndexedAccess`), typescript-eslint's
`strictTypeChecked` rules plus the React hooks rules, Vitest for the pure modules.
