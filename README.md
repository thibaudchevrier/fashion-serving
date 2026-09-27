# fashion-serving

Local deployment of the fashion segmentation model: upload a photo, see the detected clothes.

The model is trained and packaged in
[fashion-seg-train](https://github.com/thibaudchevrier/fashion-seg-train). This repository only
**imports a pinned version of it and serves it**; it knows nothing about how it was trained.

## How it fits together

```
 fashion-seg-train                     fashion-serving (this repo)
 ┌──────────────────────┐           ┌──────────────────────────────────────────────────────┐
 │ models/              │ dvc       │ models/fashion-maskrcnn  (pinned: rev_lock = commit) │
 │   fashion-maskrcnn   │ import ─► │        │ copied into the image                       │
 │ (MLflow pyfunc)      │           │        ▼                                             │
 └──────────────────────┘           │ inference   mlflow models serve   :5001 ─┐           │
   files on Google Drive            │                                         │ HTTP JSON │
                                    │ webapp      Flask upload UI       :8000 ◄┘           │
                                    └──────────────────────────────────────────────────────┘
                                                    ▲
                                                 browser
```

| Layer | Role | Depends on the ML framework? |
|-------|------|------------------------------|
| **DVC** | Fetches the model folder, pinned to a fashion-seg-train commit | No |
| **inference** | Installs the model's own `requirements.txt` and runs `mlflow models serve` | No |
| **webapp** | Sends base64 images to `/invocations`, draws the returned masks | No, it only knows the JSON contract |

The only coupling is the **response contract** in `contracts/prediction.schema.json`, a copy of
the one in fashion-seg-train. A new model (for example PyTorch instead of TensorFlow) is a swap as long
as fashion-seg-train packages it with the same contract: `dvc update`, then rebuild the inference image.

### What is in the repository

| Path | Content |
|------|---------|
| `models/fashion-maskrcnn.dvc` | Import pointer: source repo, `rev` (branch/tag) and `rev_lock` (exact commit) |
| `inference/Dockerfile` | Model server image (the model is copied in at build time) |
| `webapp/` | Flask app (uv project): `src/fashion_webapp/`, tests, Dockerfile |
| `compose.yaml` | Runs `inference` + `webapp`; uploads persist in the `uploads` volume |
| `contracts/prediction.schema.json` | Model response contract (keep in sync with fashion-seg-train) |
| `scripts/smoke_test.py` | End-to-end check of a running stack |
| `Makefile` | The commands below, shared with CI |

## One-time setup

Requires [uv](https://docs.astral.sh/uv/) and Docker.

**1. Install the tooling** (DVC for the repo, Flask and dev tools for the webapp):

```bash
make install
```

**2. Give DVC access to fashion-seg-train's Google Drive remote.** DVC reads the remote from
fashion-seg-train's git config, which doesn't include credentials. Create the git-ignored file
`.dvc/fashion-seg-train.config.local` with the same OAuth client as in fashion-seg-train's
`.dvc/config.local`:

```ini
['remote "myremote"']
    gdrive_client_id = <client-id>
    gdrive_client_secret = <client-secret>
```

`models/fashion-maskrcnn.dvc` refers to this file by path, so it must exist before any `dvc` command.

**3. Fetch the pinned model** (~254 MB). If you haven't logged in to Drive with DVC on this machine
yet, a browser window asks for access.

```bash
make model        # = uv run dvc pull
```

## Run it

```bash
make up           # docker compose up -d --build --wait
open http://localhost:8000
```

- **Upload & analyse**: the photo is resized to at most 800 px, sent to the model, and shown with
  colored masks, boxes and labels. The detected items are listed below it.
- **Show original photos / Show predictions** toggles the overlay. **Delete** removes a photo.
- If the model is down, the photo is kept with an **Analyse** button to retry.
- The inference service needs ~20 s to load the model; `--wait` returns once it's healthy.

Check the whole chain, then stop:

```bash
make smoke        # calls the model, validates the response contract, uploads through the webapp
make down         # stop (add -v to docker compose down to also delete uploaded photos)
```

Call the model directly:

```bash
curl -s localhost:5001/invocations -H 'Content-Type: application/json' \
  -d "{\"dataframe_records\": [{\"image\": \"$(base64 -i photo.jpg)\"}]}"
```

Settings, as environment variables (see `compose.yaml`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `MIN_SCORE` | `0.7` | Minimum detection confidence shown |
| `SECRET_KEY` | `dev-only-change-me` | Flask session key; set a real one outside your machine |

## Deploy a new model version

When fashion-seg-train has merged a new model into `main`, meaning a new `dvc.lock` pushed to Drive:

```bash
uv run dvc update --rev main models/fashion-maskrcnn.dvc   # moves rev_lock to main's latest commit
make up && make smoke                                      # rebuild the inference image, check it
git commit -am "Deploy fashion-seg-train@<short-sha>"         # the pin is versioned: easy rollback
```

To roll back, revert that commit, then `make model` and `make up`.

## Development

```bash
make format       # ruff format + autofix
make check        # ruff, pylint, pytest
cd webapp && INFERENCE_URL=http://localhost:5001 \
  uv run flask --app "fashion_webapp:create_app()" run --debug     # webapp with hot reload
```

The webapp tests use a fake inference client, which is itself validated against the contract, so
they run without the model or Docker.

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request and on `main`:

| Job | What it checks |
|-----|----------------|
| **Lint** | `ruff format --check`, `ruff check`, `pylint` (same as `make lint`) |
| **Webapp and contract tests** | `make test` |
| **Dockerfiles** | `hadolint` on both Dockerfiles, webapp image build |
| **End-to-end** | Pulls the pinned model, `docker compose up`, `make smoke` |

The **End-to-end** job needs Drive access and is skipped until the repository secret
`GDRIVE_CREDENTIALS_DATA` is set. It uses the same service account JSON key as fashion-seg-train's CI:
create it and share the Drive folder with it as described in that repo's README, then add the key
here under **Settings → Secrets and variables → Actions**.
