"""The webapp's layers: use cases and pure modules free of the web framework and of HTTP."""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parents[1] / "src" / "fashion_webapp"

WEB = {"fastapi", "starlette"}
# Top-level packages each module may not import (besides these, anything is allowed).
FORBIDDEN = {
    "service": WEB | {"requests", "PIL"},  # use cases: no web framework, no HTTP, no I/O
    "rendering": WEB | {"requests"},
    "palette": WEB | {"requests"},
    "inference": WEB,
    "storage": WEB | {"requests"},
    "fetching": WEB,
}
# Which of the app's own modules each may import: adapters depend on the use cases, never the
# reverse; only the composition root (app) sees the adapters.
ALLOWED = {
    "service": {"rendering", "palette"},
    "rendering": {"palette"},
    "palette": set(),
    "inference": {"service"},
    "storage": {"service"},
    "fetching": {"service"},
    "api": {"service"},
    "app": {"api", "fetching", "inference", "service", "storage"},
}


def _imports(path: Path) -> set[str]:
    """List the modules a file imports (``from a import b`` gives ``a.b``)."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize("module", sorted(ALLOWED))
def test_modules_respect_the_layers(module):
    """Each module imports only the layers and libraries its role allows."""
    imports = _imports(PACKAGE / f"{module}.py")
    own = {n.split(".")[1] for n in imports if n.startswith("fashion_webapp.")} - {module}
    assert own <= ALLOWED[module], f"{module} imports {own - ALLOWED[module]}"
    assert not {n.split(".")[0] for n in imports} & FORBIDDEN.get(module, set())
