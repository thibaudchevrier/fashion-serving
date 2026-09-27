# `lint` runs the pre-commit hooks on every file: the same checks as the git hooks and CI.
WEBAPP = uv run --project webapp

.PHONY: install hooks format lint test check model up smoke down

install:
	uv sync --locked
	uv sync --locked --project webapp

hooks:
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

format:
	$(WEBAPP) ruff format .
	$(WEBAPP) ruff check --fix .

lint:
	uv run pre-commit run --all-files --show-diff-on-failure

test:
	cd webapp && uv run pytest

check: lint test

model:
	uv run dvc pull

up:
	docker compose up -d --build --wait

smoke:
	$(WEBAPP) python scripts/smoke_test.py

down:
	docker compose down
