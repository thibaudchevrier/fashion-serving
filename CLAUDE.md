# CLAUDE.md

Guidance for working in this repository. Read it before changing anything.

## What this repo is

`fashion-serving`: deployment of the fashion segmentation model. It **imports a pinned model**
packaged by [fashion-seg-train](https://github.com/thibaudchevrier/fashion-seg-train), serves it,
and publishes each release as Docker images on ghcr.io; it knows nothing about how the model was
trained.

| Path | Content |
|------|---------|
| `models/fashion-maskrcnn.dvc` | `dvc import` pointer: source repo, `rev` and `rev_lock` (the deployed model version) |
| `inference/Dockerfile` | `mlflow models serve` on the model; installs the model's own `requirements.txt` |
| `webapp/` | Flask app (own uv project, Python 3.12): upload, call `/invocations`, draw masks (see below) |
| `compose.yaml` | `inference` (:5001) + `webapp` (:8000): built from source (`make up`) or pulled from ghcr.io (`make deploy TAG=...`) |
| `.github/workflows/release.yml` | Release: version bump, changelog, tag, GitHub Release, then both images pushed to `ghcr.io/thibaudchevrier/fashion-serving-{inference,webapp}` (amd64 + arm64) |
| `scripts/smoke_test.py` | End-to-end check of a running stack |

### The webapp: use cases behind ports

| Module (`webapp/src/fashion_webapp/`) | Role | May import (from the app) |
|--------|------|------|
| `service.py` | **Use cases** (upload, analyse, overlay), the ports they drive (`Inference`, `ImageStore` Protocols), the `StoredImage` record and the errors. No Flask, no HTTP, no files | `rendering` |
| `rendering.py` | Draws predictions on an image (pure) | nothing |
| `inference.py` | Adapter: `InferenceClient`, the model over HTTP (an `Inference`) | `service` |
| `storage.py` | Adapter: `FileImageStore`, images and predictions on disk (an `ImageStore`) | `service` |
| `web.py` | Flask routes: translate requests into use cases, outcomes into pages and messages | `service`, `rendering` |
| `app.py` | `create_app`, the composition root: settings, adapters, routes (gunicorn's `fashion_webapp.app:create_app()`) | all |

Adapters depend on the use cases, never the reverse; they raise the service's errors
(`InferenceUnavailable`, `UnreadableImage`), not their library's. `webapp/tests/test_architecture.py`
enforces these rules; `test_service.py` tests the use cases with in-memory adapters, `test_app.py`
the web layer with a fake model.

Two uv environments: the repo root (tooling: DVC, pre-commit, commitizen) and `webapp/` (the app,
its tests, ruff/pylint/pydoclint). `make install` syncs both.

### Rules specific to this repo

- **The only coupling to the model is the contract** (`fashion-seg-contract`). Never import
  training code or ML frameworks in the webapp; build requests with `fashion_seg_contract.request`,
  decode masks with `fashion_seg_contract.rle`, type responses with
  `fashion_seg_contract.schema.Prediction`.
- The webapp's fake inference client must return contract-valid responses (`schema.validate`),
  otherwise its tests prove nothing about the real model.
- **Deploying a model** is a commit of the pin:
  `uv run dvc update --rev main models/fashion-maskrcnn.dvc`, then `make up && make smoke`, then
  `git commit -m "feat(model): deploy fashion-seg-train@<sha> (model vN)"` for a model that
  predicts differently, `fix(model): ...` for a re-packaging or a rollback. Both release a new
  version, hence new images: the image version identifies the model it serves (also in its
  `io.github.thibaudchevrier.model.*` labels). Roll back by reverting the commit as `fix(model)`.
- **Images** are only published by the release workflow, from the release tag: `X.Y.Z`, `X.Y`,
  `latest`, `sha-<commit>`, `linux/amd64`. Never push images by hand. The inference image bakes
  the model in: its build needs the `GDRIVE_CREDENTIALS_DATA` secret.
- Never commit `models/fashion-maskrcnn/` (DVC output) or `.dvc/fashion-seg-train.config.local`
  (Google Drive credentials).
- Host port 5000 is taken by AirPlay on macOS: the inference service is published on 5001.

## Commands

```bash
make install   # both uv environments
make hooks     # once: install the pre-commit and commit-msg git hooks
make format    # ruff format + ruff --fix
make lint      # all pre-commit hooks on all files (exactly what CI runs; hadolint needs Docker)
make test      # webapp tests, including docstring examples
make check     # lint + test: run before every commit
make model     # dvc pull: fetch the pinned model
make up        # docker compose up --build --wait
make smoke     # end-to-end check of the running stack
make down      # stop the stack
make deploy TAG=X.Y.Z   # run released images from ghcr.io (no build, no model pull)
```

## Standards

These standards are the same in the four repositories of the project (fashion-seg-contract,
maskrcnn-matterport-tf2, fashion-seg-train, fashion-serving). Keep them in sync.

### Environment

- **uv only** (never `pip install`): `uv add` / `uv add --dev` change dependencies and update
  `pyproject.toml` and `uv.lock` together; commit both.
- Packages from the other repositories are referenced by their **release wheel URL** in
  `[tool.uv.sources]`, like registry packages. Upgrade by changing the URL, then `uv lock`.
- Don't edit by hand: `uv.lock`, `CHANGELOG.md`, the `version` in `pyproject.toml` (commitizen owns
  the last two).
- Never commit secrets (`.dvc/*.local`, tokens) or large files (`check-added-large-files`
  blocks files over 1 MB: data and models go to DVC).

### Code quality: `make lint` = pre-commit hooks = CI

`.pre-commit-config.yaml` is the single definition of the checks. The git hooks (`make hooks`),
`make lint` and the CI lint job all run it, so a commit that passes locally passes in CI.

- **ruff format** (line length 100) and **ruff check**: pycodestyle, pyflakes, isort, pyupgrade,
  bugbear, comprehensions, simplify, and pydocstyle (numpy convention).
- **pydoclint**: every parameter, return value, yielded value, raised exception and class attribute
  is documented, with types matching the annotations.
- **pylint**: 10/10.
- Hygiene hooks: trailing whitespace, end of files, YAML/TOML syntax, merge conflicts, large files.
- A `# noqa: <code>` or `# pylint: disable=<name>` needs a reason on the same line. Never disable a
  check globally or raise a limit to make code pass: fix the code.

### Docstrings: numpy style, everywhere

Every module, class and function, public or private, has a
[numpydoc](https://numpydoc.readthedocs.io/en/latest/format.html) docstring:

```python
def decode(rle: str, height: int, width: int = 1) -> np.ndarray:
    """Decode an RLE string into a boolean mask.

    Parameters
    ----------
    rle : str
        Space-separated ``start length`` pairs, 1-indexed, column-major.
    height : int
        Mask height in pixels.
    width : int
        Mask width in pixels. By default 1.

    Returns
    -------
    np.ndarray
        Boolean mask of shape ``(height, width)``.

    Raises
    ------
    ValueError
        If the RLE has an odd number of values.

    Examples
    --------
    >>> decode("1 2", height=2).tolist()
    [[True], [True]]
    """
```

- Summary line in the imperative mood, ending with a period, then a blank line before sections.
- Types are written exactly like the annotations (`str | Path`, `dict[str, Any]`): pydoclint
  compares them. No `, optional` suffix: state the default in the description ("By default 1.").
- `Raises` lists the exceptions the function raises itself; mention exceptions propagated from
  callees in the description.
- Classes document their constructor parameters (`Parameters`) and attributes (`Attributes`) in the
  class docstring, not in `__init__`. Instance attributes are declared in the class body
  (`timeout: float`) so they can be checked.
- `Examples` are doctests: pytest runs them (`--doctest-modules`), so they must stay correct.
- Tests: a module docstring, and a one-line docstring per test saying which behaviour it checks.

### Code style

- Type-annotate every function signature, including private helpers.
- Import submodules explicitly (`from skimage import io, transform`), not several `import
  skimage.x` lines: linters can't tell which of those is unused. No re-export blocks: import from
  the module that defines the name.
- `pathlib.Path` over `os.path`, f-strings, no mutable default arguments, `logging` rather than
  `print` in library code, error messages that say what to do.
- Keep functions small enough for pylint's limits; split them rather than raising the limits.
- No duplicated code across repositories: shared code goes in a released package
  (fashion-seg-contract for the model's request and response, maskrcnn-matterport for Matterport
  code).

### Tests

- pytest, fast and offline by default. Every behaviour change or bug fix comes with a test.
- Tests that need data, models or services skip cleanly when they are missing (and run in CI when
  the credentials are set).
- `make check` (lint + tests) before every commit.

### Commits, PRs and releases

- [Conventional Commits](https://www.conventionalcommits.org/), checked by the `commit-msg` hook and
  on every PR: `type(scope): summary`, imperative, lower case, no final period. The body explains
  *why*. One logical change per commit.
- Types and their effect on the version (commitizen, `major_version_zero = true`):

  | Type | Release |
  |------|---------|
  | `feat` | minor |
  | `fix`, `perf`, `refactor` | patch |
  | `!` after the type, or a `BREAKING CHANGE:` footer | minor while < 1.0 (then major) |
  | `docs`, `style`, `test`, `ci`, `build`, `chore` | none |

- Work on a branch, open a PR, merge only when CI is green, with a **merge commit** (not squash: the
  individual conventional commits build the changelog). Never push to `main` directly: only the
  release workflow does (bump commit + tag).
- On merge, `release.yml` bumps the version, updates `CHANGELOG.md`, tags `vX.Y.Z` and publishes a
  GitHub Release (with the wheel and sdist for libraries).
