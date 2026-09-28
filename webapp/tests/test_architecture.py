"""The webapp's layers: use cases free of Flask and HTTP, adapters free of Flask."""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parents[1] / "src" / "fashion_webapp"

# Top-level packages each module may import, besides the standard library and the contract.
FORBIDDEN = {
    "service": {"flask", "requests", "PIL"},  # use cases: no web framework, no HTTP, no I/O
    "rendering": {"flask", "requests"},
    "inference": {"flask"},
    "storage": {"flask", "requests"},
}
# Which of the app's own modules each may import: adapters depend on the use cases, never the
# reverse; only the composition root (__init__) and the web layer see the adapters.
ALLOWED = {
    "service": {"rendering"},
    "rendering": set(),
    "inference": {"service"},
    "storage": {"service"},
    "web": {"service", "rendering"},
    "__init__": {"inference", "service", "storage", "web"},
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
