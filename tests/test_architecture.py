"""Enforce a small, explicit import graph, including any newly added modules."""

import ast
from pathlib import Path

# Add real modules here when introduced; do not create empty layers in advance.
ALLOWED_INTERNAL_IMPORTS = {"__init__": set(), "smoke": set(), "cli": {"smoke"}}


def test_application_dependency_direction():
    root = Path("src/propane_demo")
    for path in root.rglob("*.py"):
        module = path.relative_to(root).with_suffix("").as_posix().replace("/", ".")
        assert module in ALLOWED_INTERNAL_IMPORTS, f"Declare dependencies for {module}"
        for node in ast.walk(ast.parse(path.read_text())):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0, (
                    "Use absolute imports for dependency enforcement"
                )
                imports = [node.module or ""]
            for imported in imports:
                if imported == "propane_demo" or imported.startswith("propane_demo."):
                    target = imported.removeprefix("propane_demo.")
                    assert target in ALLOWED_INTERNAL_IMPORTS[module], (
                        f"Forbidden dependency: {module} -> {target}"
                    )
            assert not isinstance(node, ast.Call) or not (
                isinstance(node.func, ast.Name) and node.func.id == "__import__"
            ), "Use static imports"
