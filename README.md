# fashion-serving

Deployment of the fashion segmentation model: upload a photo, see the detected clothes. Each
release is published as Docker images on ghcr.io.

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

The only coupling is the **contract** (request and response), a released package shared with fashion-seg-train:
[fashion-seg-contract](https://github.com/thibaudchevrier/fashion-seg-contract) (JSON Schema, RLE
decoding, labels). The webapp decodes masks with it, and its tests and the smoke test validate
responses with it. A new model (for example PyTorch instead of TensorFlow) is a swap as long as
fashion-seg-train packages it with the same contract version: `dvc update`, then rebuild the
inference image.

### What is in the repository

| Path | Content |
|------|---------|
| `models/fashion-maskrcnn.dvc` | Import pointer: source repo, `rev` (branch/tag) and `rev_lock` (exact commit) |
| `inference/Dockerfile` | Model server image (the model is copied in at build time) |
| `webapp/` | Flask app (uv project): `src/fashion_webapp/` (use cases in `service.py`, adapters for the model and the storage, routes in `web.py`, wiring in `create_app`), tests, Dockerfile. Depends on `fashion-seg-contract`, referenced by its release wheel URL in `[tool.uv.sources]` |
| `compose.yaml` | Runs `inference` + `webapp`; uploads persist in the `uploads` volume |
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
| `MIN_SCORE` | the contract's (`0.7`) | Minimum detection confidence shown |
| `TAG` | `latest` | Version of the released images `make deploy` runs |
| `SECRET_KEY` | `dev-only-change-me` | Flask session key; set a real one outside your machine |

## Deploy a new model version

When fashion-seg-train has merged a new model into `main`, meaning a new `dvc.lock` pushed to Drive:

```bash
uv run dvc update --rev main models/fashion-maskrcnn.dvc   # moves rev_lock to main's latest commit
make up && make smoke                                      # rebuild the inference image, check it
git commit -am "feat(model): deploy fashion-seg-train@<short-sha> (model vN)"
```

Use `feat(model)` for a model that predicts differently, `fix(model)` for a re-packaging. Both
release a new version on merge, which publishes new images: each image version serves one model.
To roll back, revert that commit (as `fix(model): roll back ...`); the release republishes the
previous model under a new version.

## Released images

Every release publishes two images to the GitHub Container Registry, built from the release tag:

| Image | Content |
|-------|---------|
| `ghcr.io/thibaudchevrier/fashion-serving-inference` | `mlflow models serve` with the pinned model baked in (~0.7 GB compressed, PyTorch CPU) |
| `ghcr.io/thibaudchevrier/fashion-serving-webapp` | The Flask app (gunicorn, ~0.1 GB compressed) |

Tags: `X.Y.Z`, `X.Y`, `X`, `latest` and `sha-<commit>`, for `linux/amd64` and `linux/arm64`
(Apple Silicon runs them natively). Releases up to 0.2.0 were published as
`fashion-serving/{inference,webapp}`, for amd64 only. The inference image carries
the model's name, registry version and source commit as labels:

```bash
docker inspect ghcr.io/thibaudchevrier/fashion-serving-inference:latest \
  --format '{{ json .Config.Labels }}'
```

Run a release anywhere Docker runs, without the source or the model:

```bash
make deploy TAG=0.2.0     # docker compose pull + up, no build
```

## Development

```bash
make install      # both environments
make hooks        # once: pre-commit and commit-msg git hooks
make format       # ruff format + autofix
make check        # lint (all pre-commit hooks, exactly what CI runs) + tests (incl. doctests)
cd webapp && INFERENCE_URL=http://localhost:5001 \
  uv run flask --app "fashion_webapp.app:create_app()" run --debug     # webapp with hot reload
```

Code quality is defined once, in `.pre-commit-config.yaml`: ruff (format, lint, numpy docstrings),
pydoclint (every parameter, return and exception documented), pylint (10/10), hadolint for the
Dockerfiles and hygiene checks. The git hooks, `make lint` and CI all run it. Conventions for
contributors (and for Claude Code) are in [`CLAUDE.md`](CLAUDE.md).

The webapp tests use a fake inference client, which is itself validated against the contract, so
they run without the model or Docker.

### Commits, versions and releases

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `feat(webapp): ...`,
`fix: ...`, `feat(model): deploy ...`, `docs: ...`. They are checked by the `commit-msg` hook and on
every PR by CI. `uv run cz commit` writes one interactively.

Releases are automatic. On every merge to `main`, [commitizen](https://commitizen-tools.github.io/commitizen/)
reads the commits since the last tag. A `feat` (minor), `fix`/`perf`/`refactor` (patch) or breaking change
(minor while < 1.0) bumps the version in `pyproject.toml` and `uv.lock`, updates `CHANGELOG.md`,
tags `vX.Y.Z`, publishes a GitHub Release and pushes the images of that version (see
[Released images](#released-images)). Other types never release.

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request and on `main`:

| Job | What it checks |
|-----|----------------|
| **Lint** | All pre-commit hooks (`make lint`): ruff, pydoclint, pylint, hadolint, hygiene |
| **Webapp and contract tests** | `make test` |
| **Webapp image** | Builds the webapp image |
| **End-to-end** | Pulls the pinned model, `docker compose up`, `make smoke` |

The **End-to-end** job and the release's **inference image** need Drive access (to fetch the
model): the first is skipped and the second fails until the repository secret
`GDRIVE_CREDENTIALS_DATA` is set. It uses the same service account JSON key as fashion-seg-train's CI:
create it and share the Drive folder with it as described in that repo's README, then add the key
here under **Settings → Secrets and variables → Actions**.

## License

[MIT](LICENSE). The served model is trained on the iMaterialist Fashion 2020 (Kaggle FGVC7) data,
whose terms target research and non-commercial use.
