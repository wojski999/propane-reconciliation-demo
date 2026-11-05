"""Offline business command boundary: configuration, "
"files, SQLite and safe exits."""

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from propane_demo.contracts import SCENARIOS
from propane_demo.generator import DEFAULT_DATE, DEFAULT_SEED, generate
from propane_demo.ingestion import ingest
from propane_demo.kpis import calculate
from propane_demo.narrative import build
from propane_demo.presentation import card_deposits, exposures, prior_changes
from propane_demo.report import collect_refs, evidence, render, summary
from propane_demo.rule_inputs import from_database, reconcile_database


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("Invalid command configuration")


def display(instant):
    return (
        datetime.fromisoformat(instant)
        .astimezone(ZoneInfo("America/Denver"))
        .isoformat()
    )


def compute(db):
    inputs = from_database(db)
    checks = reconcile_database(db)
    kpis = calculate(inputs, checks)
    scopes = {
        scope: {"status": "evaluated"}
        for scope in sorted(inputs["dependencies"])
        if scope.startswith("C")
    }
    scopes.update(
        {k: v for k, v in checks["not_evaluated"].items() if k.startswith("C")}
    )
    for check in ("C09", "C10", "C11"):
        scopes[check] = {"status": "evaluated"}
    scopes = dict(sorted(scopes.items()))
    exception_checks = {f["check_id"] for f in checks["findings"]}
    counts = {
        "evaluated": sum(s["status"] == "evaluated" for s in scopes.values()),
        "not_evaluated": sum(s["status"] != "evaluated" for s in scopes.values()),
        "passed": sum(
            state["status"] == "evaluated"
            and scope.split(":")[0] not in exception_checks
            for scope, state in scopes.items()
        ),
        "core_checks": 12,
    }
    severity = {"critical": 0, "high": 1, "medium": 2}
    freshness = []
    stale = {a["source"] for a in checks["alerts"] if a["check_id"] == "C09"}
    for m in inputs["manifests"]:
        raw = m["metadata"]
        freshness.append(
            {
                "source": m["source"],
                "status": "stale" if m["source"] in stale else m["status"],
                "source_refs": ["manifest:" + m["manifest_id"]],
                **{
                    target: display(raw[field])
                    for target, field in [
                        ("window_start", "expected_window_start"),
                        ("window_end", "expected_window_end"),
                        ("covered_through", "covered_through"),
                        ("extracted_at", "extracted_at"),
                    ]
                    if field in raw
                },
            }
        )
    digest = hashlib.sha256()
    for name, sha in db.execute("SELECT file_id,sha256 FROM files ORDER BY file_id"):
        digest.update((name + ":" + sha + "\n").encode())
    return {
        "status": "incomplete"
        if checks["alerts"]
        or checks["not_evaluated"]
        or any(k["status"] != "complete" for k in kpis.values())
        else "complete",
        "run": inputs["run"],
        "display_as_of": display(inputs["run"]["as_of"]),
        "source_digest": digest.hexdigest(),
        "rule_version": inputs["policy"]["version"],
        "policy_version": inputs["policy"]["version"],
        "gallon_basis": inputs["policy"]["basis"],
        "exposure_estimates": exposures(inputs, checks),
        "card_deposits": card_deposits(inputs, checks),
        "checks": checks,
        "kpis": kpis,
        "alerts": checks["alerts"],
        "prioritized_alerts": sorted(
            checks["alerts"], key=lambda a: (severity[a["severity"]], a["alert_id"])
        ),
        "coverage": counts,
        "check_scopes": scopes,
        "freshness": freshness,
        "prioritized_findings": sorted(
            checks["findings"],
            key=lambda f: (severity[f["severity"]], f["check_id"], f["finding_id"]),
        ),
    }


def baseline(seed, business_date):
    """Synthetic prior business day: the clean scenario, computed by the same code."""
    day = business_date - timedelta(days=1)
    if day < date(2020, 1, 1):
        return None
    db = ingest(generate("clean", seed, day).__getitem__)
    try:
        return compute(db)
    finally:
        db.close()


def write_json(path, value):
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def execute(files, output, *, narrative=False, client=None, prior=None):
    """Preserve computed artifacts before rendering, never "
    "retain an old report."""
    db = ingest(files.__getitem__)
    try:
        result = compute(db)
        raw = evidence(db, collect_refs(result))
    finally:
        db.close()
    output.mkdir(parents=True, exist_ok=True)
    report = output / "report.html"
    report.unlink(missing_ok=True)
    inputs = output / "inputs"
    inputs.mkdir(exist_ok=True)
    for name, content in files.items():
        (inputs / name).write_bytes(content)
    write_json(output / "results.json", result)
    write_json(output / "alerts.json", result["alerts"])
    write_json(output / "evidence.json", raw)
    (output / "summary.txt").write_text(summary(result) + "\n", encoding="utf-8")
    text = build(
        result, enabled=narrative, **({} if client is None else {"client": client})
    )
    write_json(output / "narrative.json", text)
    try:
        report.write_text(
            render(
                result,
                raw,
                narrative_status=text,
                changes=prior_changes(result, prior),
            ),
            encoding="utf-8",
        )
    except (ValueError, TypeError, OSError):
        report.unlink(missing_ok=True)
        raise
    return 0 if result["status"] == "complete" else 2


def main(argv=None):
    parser = Parser(
        description="Generate an offline synthetic propane evidence report."
    )
    parser.add_argument(
        "--narrative",
        action="store_true",
        help="Opt in to paid Claude text; requires key and model environment values",
    )
    parser.add_argument("--scenario", choices=SCENARIOS, default="issues")
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--business-date", default=DEFAULT_DATE.isoformat())
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--as-of",
        help="Offset-aware ISO cutoff, must be >= business-day end (the default)",
    )
    try:
        args = parser.parse_args(argv)
        day = date.fromisoformat(args.business_date)
        files = generate(args.scenario, args.seed, day)
        if args.as_of is not None:
            instant = datetime.fromisoformat(args.as_of)
            if instant.utcoffset() is None:
                raise ValueError("Offset required")
            run = json.loads(files["run.json"])
            run["as_of"] = instant.isoformat()
            files["run.json"] = (
                json.dumps(run, indent=2, sort_keys=True) + "\n"
            ).encode()
        status = execute(
            files,
            args.output,
            narrative=args.narrative,
            prior=baseline(args.seed, day),
        )
    except (ValueError, TypeError, OSError, sqlite3.Error, UnicodeError):
        print(
            (
                "Report failed: invalid configuration, rendering or "
                "filesystem boundary. No successful report is claimed; "
                "inspect any preserved computed artifacts."
            ),
            file=sys.stderr,
        )
        return 1
    print(
        "Report written: "
        + ("complete" if status == 0 else "incomplete; inspect source/support warnings")
    )
    return status
