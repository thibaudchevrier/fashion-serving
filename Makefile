# Same commands locally and in CI (.github/workflows/ci.yml).
WEBAPP = uv run --project webapp
PYLINT_TESTS_DISABLE = missing-module-docstring,missing-class-docstring,missing-function-docstring,unbalanced-tuple-unpacking,import-outside-toplevel,redefined-outer-name

.PHONY: install format lint test check model up smoke down

install:
	uv sync --locked
	uv sync --locked --project webapp

format:
	$(WEBAPP) ruff format webapp scripts
	$(WEBAPP) ruff check --fix webapp scripts

lint:
	$(WEBAPP) ruff format --check webapp scripts
	$(WEBAPP) ruff check webapp scripts
	$(WEBAPP) pylint --rcfile webapp/pyproject.toml webapp/src scripts
	$(WEBAPP) pylint --rcfile webapp/pyproject.toml webapp/tests --disable=$(PYLINT_TESTS_DISABLE)

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
