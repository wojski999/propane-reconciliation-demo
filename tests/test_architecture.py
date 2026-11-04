"""Enforce a small, explicit import graph, including any newly added modules."""

import ast
from pathlib import Path

import pytest

# Add real modules here when introduced; do not create empty layers in advance.
ALLOWED_INTERNAL_IMPORTS = {"__init__": set(), "smoke": set(), "cli": {"smoke"}}


def check_application_dependency_direction():
    root = Path(__file__).resolve().parents[1] / "src" / "propane_demo"
    modules = list(root.rglob("*.py"))
    assert modules, "No application modules discovered"
    for path in modules:
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


@pytest.mark.parametrize("foreign_cwd", [False, True])
def test_application_dependency_direction(tmp_path, monkeypatch, foreign_cwd):
    if foreign_cwd:
        monkeypatch.chdir(tmp_path)
    check_application_dependency_direction()


def test_dependency_check_is_not_vacuous_from_foreign_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delitem(ALLOWED_INTERNAL_IMPORTS, "smoke")
    with pytest.raises(AssertionError, match="Declare dependencies for smoke"):
        check_application_dependency_direction()


def test_dependency_check_rejects_empty_discovery(monkeypatch):
    monkeypatch.setattr(Path, "rglob", lambda self, pattern: iter(()))
    with pytest.raises(AssertionError, match="No application modules discovered"):
        check_application_dependency_direction()
