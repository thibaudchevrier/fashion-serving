# `lint` runs the pre-commit hooks on every file: the same checks as the git hooks and CI.
WEBAPP = uv run --project webapp
# npm for the front end: the local one if Node is installed, otherwise the same Node in Docker.
NPM = $(if $(shell command -v npm),npm --prefix webapp/frontend,docker run --rm \
	-e NPM_CONFIG_UPDATE_NOTIFIER=false -v $(CURDIR)/webapp/frontend:/app -w /app node:24-alpine npm)

.PHONY: install hooks format lint test front-check front-dev check model up smoke down deploy

install:
	uv sync --locked
	uv sync --locked --project webapp
	$(NPM) ci --no-audit --no-fund

hooks:
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

format:
	$(WEBAPP) ruff format .
	$(WEBAPP) ruff check --fix .

lint:
	uv run pre-commit run --all-files --show-diff-on-failure

test:
	cd webapp && uv run pytest

# Front end: types, lint (typescript-eslint, strict), unit tests, production build.
front-check:
	$(NPM) run typecheck
	$(NPM) run lint
	$(NPM) test
	$(NPM) run build

# Front end with hot reload on :5173, calling the API of a running `make up` (needs Node locally).
front-dev:
	npm --prefix webapp/frontend run dev

check: lint test front-check

model:
	uv run dvc pull

up:
	docker compose up -d --build --wait

smoke:
	$(WEBAPP) python scripts/smoke_test.py

down:
	docker compose down

# Run released images from ghcr.io instead of building them (no source or model needed):
# make deploy TAG=0.2.0 (default: latest).
TAG ?= latest
deploy:
	TAG=$(TAG) docker compose pull
	TAG=$(TAG) docker compose up -d --no-build --wait
