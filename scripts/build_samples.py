"""Rebuild the committed synthetic samples; never call a narrative provider."""

import json
from pathlib import Path

from propane_demo.business import baseline, compute
from propane_demo.generator import DEFAULT_DATE, DEFAULT_SEED, generate
from propane_demo.ingestion import ingest
from propane_demo.narrative import build
from propane_demo.presentation import prior_changes
from propane_demo.report import collect_refs, evidence, render, summary


def main():
    root = Path(__file__).resolve().parents[1] / "samples"
    prior = baseline(DEFAULT_SEED, DEFAULT_DATE)
    for scenario in ("clean", "issues", "showcase"):
        db = ingest(generate(scenario).__getitem__)
        try:
            result = compute(db)
            raw = evidence(db, collect_refs(result))
        finally:
            db.close()
        kwargs = (
            {
                "illustrative": json.loads(
                    (root / "issues-illustrative-narrative.json").read_text()
                )
            }
            if scenario == "issues"
            else {}
        )
        text = build(result, **kwargs)
        (root / f"{scenario}-report.html").write_text(
            render(
                result,
                raw,
                narrative_status=text,
                changes=prior_changes(result, prior),
            ),
            encoding="utf-8",
        )
        (root / f"{scenario}-results.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (root / f"{scenario}-summary.txt").write_text(
            summary(result) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
