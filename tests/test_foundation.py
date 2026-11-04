import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from propane_demo.cli import main
from propane_demo.smoke import sample_html


def test_sample_is_deterministic_and_explicitly_not_an_audit():
    assert sample_html() == sample_html()
    assert "SYNTHETIC-SMOKE-001" in sample_html()
    assert "No audit checks or KPIs evaluated" in sample_html()


def test_source_label_is_escaped_and_sql_is_parameterized():
    label = '<script>"; DROP TABLE smoke_sample; --</script>'
    html = sample_html(label)
    assert "<script>" not in html
    assert "&lt;script&gt;&quot;; DROP TABLE smoke_sample; --&lt;/script&gt;" in html


def test_cli_creates_nested_report(tmp_path, capsys):
    output = tmp_path / "nested" / "report.html"
    assert main(["--output", str(output)]) == 0
    assert output.read_text() == sample_html()
    assert "Foundation smoke report:" in capsys.readouterr().out


def test_cli_default_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main([]) == 0
    assert Path("artifacts/smoke.html").read_text() == sample_html()


@pytest.mark.parametrize("operation", ["mkdir", "write_text"])
def test_cli_filesystem_errors_are_safe(tmp_path, capsys, operation):
    with patch.object(Path, operation, side_effect=OSError("secret internal details")):
        assert main(["--output", str(tmp_path / "report.html")]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "Unable to write smoke report.\n"


def test_invalid_cli_argument_does_not_create_a_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="2"):
        main(["--unknown"])
    assert not Path("artifacts").exists()


def test_installed_entrypoint_end_to_end(tmp_path):
    # Subprocess exercises packaging/entrypoint; unit tests above measure CLI coverage.
    output = Path(os.environ.get("SMOKE_ARTIFACT", tmp_path / "smoke.html")).resolve()
    command = Path(sys.executable).parent / "propane-smoke"
    result = subprocess.run(
        [str(command), "--output", str(output)],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    assert "Foundation smoke report:" in result.stdout
    assert output.read_text() == sample_html()
    assert '<html lang="en">' in output.read_text()
    assert "http://" not in output.read_text()
    assert "https://" not in output.read_text()


@pytest.mark.parametrize(
    ("statements", "measured_branches", "lines", "branches", "expected"),
    [
        (5000, 5000, 0, 0, 0),
        (5000, 5000, 1, 0, 1),
        (5000, 5000, 0, 1, 1),
        (0, 5000, 0, 0, 1),
        (5000, 0, 0, 0, 1),
    ],
)
def test_coverage_gates_fail_independently(
    tmp_path, statements, measured_branches, lines, branches, expected
):
    data = tmp_path / "coverage.json"
    data.write_text(
        json.dumps(
            {
                "totals": {
                    "num_statements": statements,
                    "num_branches": measured_branches,
                    "missing_lines": lines,
                    "missing_branches": branches,
                }
            }
        )
    )
    result = subprocess.run(
        [sys.executable, "scripts/check_coverage.py", str(data)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == expected
    if expected:
        assert "FAIL:" in result.stderr
    else:
        assert "PASS: line" in result.stdout
        assert "PASS: branch" in result.stdout


@pytest.mark.parametrize("label", ["", " ", "\n"])
def test_blank_sample_label_is_rejected(label):
    with pytest.raises(ValueError, match="Sample label must not be blank"):
        sample_html(label)
