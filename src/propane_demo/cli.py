"""Smoke command; the business demo CLI will be implemented separately."""

import argparse
import sys
from pathlib import Path

from propane_demo.smoke import sample_html


def main(argv: list[str] | None = None) -> int:
    """Write the infrastructure-only report, reporting filesystem failures safely."""
    parser = argparse.ArgumentParser(description="Generate a foundation smoke report")
    parser.add_argument("--output", type=Path, default=Path("artifacts/smoke.html"))
    args = parser.parse_args(argv)
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(sample_html(), encoding="utf-8")
    except OSError:
        print("Unable to write smoke report.", file=sys.stderr)
        return 1
    print(f"Foundation smoke report: {args.output}")
    return 0
