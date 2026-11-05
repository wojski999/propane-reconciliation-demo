"""Enforce a small, explicit import graph, including any newly added modules."""

import ast
from pathlib import Path

import pytest

# Add real modules here when introduced; do not create empty layers in advance.
ALLOWED_INTERNAL_IMPORTS = {
    "__init__": set(),
    "smoke": set(),
    "cli": {"smoke"},
    "contracts": set(),
    "generator": {"contracts"},
    "validation": {"contracts"},
    "ingestion": {"contracts", "generator", "validation"},
    "rule_inputs": {"ingestion", "rules"},
    "rules": set(),
    "kpis": {"rules"},
    "report": set(),
    "narrative": {"report"},
    "business": {
        "contracts",
        "generator",
        "ingestion",
        "kpis",
        "narrative",
        "report",
        "rule_inputs",
    },
    "__main__": {"business"},
}


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
            if module in {"rules", "kpis"}:
                assert all(
                    name
                    in {
                        "collections",
                        "datetime",
                        "decimal",
                        "zoneinfo",
                        "propane_demo.rules",
                    }
                    for name in imports
                ), "Rules must remain pure"
            for imported in imports:
                if imported == "propane_demo" or imported.startswith("propane_demo."):
                    target = imported.removeprefix("propane_demo.")
                    assert target in ALLOWED_INTERNAL_IMPORTS[module], (
                        f"Forbidden dependency: {module} -> {target}"
                    )
            if module in {"rules", "kpis"} and isinstance(node, ast.Call):
                assert not (
                    isinstance(node.func, ast.Name)
                    and node.func.id in {"open", "exec", "eval", "compile"}
                ), "Rules must not perform IO or dynamically load code"
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


@pytest.mark.parametrize("source", ["import pathlib", "open('forbidden')"])
@pytest.mark.parametrize("module", ["rules.py", "kpis.py"])
def test_rules_purity_guard_rejects_forbidden_import_and_call(
    monkeypatch, source, module
):
    original = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda path, *args, **kwargs: source
        if path.name == module
        else original(path, *args, **kwargs),
    )
    with pytest.raises(AssertionError, match="Rules must"):
        check_application_dependency_direction()
