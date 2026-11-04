"""Pure deterministic synthetic file generator, with no audit/oracle dependency."""

import csv
import io
import json
from datetime import UTC, date, datetime, time, timedelta
from importlib.resources import files
from zoneinfo import ZoneInfo

from propane_demo.contracts import CSV_FIELDS, SCENARIOS

DEFAULT_DATE = date(2026, 11, 3)
DEFAULT_SEED = 20261104


def business_window(business_date):
    """Half-open Denver day, including 23/25-hour DST transition days."""
    zone = ZoneInfo("America/Denver")
    start = datetime.combine(business_date, time(), zone)
    end = datetime.combine(business_date + timedelta(days=1), time(), zone)
    return start.astimezone(UTC), end.astimezone(UTC)


def generate(scenario="clean", seed=DEFAULT_SEED, business_date=DEFAULT_DATE):
    """Return ordered UTF-8 file bytes. No filesystem writes or wall clock reads.

    Seed namespaces run IDs, not the frozen hand-calculated financial values.
    Date shifts all relative timestamps; oracle dates refer to the default date.
    """
    if scenario not in SCENARIOS:
        raise ValueError("Unknown synthetic scenario")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Seed must be an unsigned 32-bit integer")
    if type(business_date) is not date:
        raise ValueError("Business date must be a date")
    if not date(2020, 1, 1) <= business_date < date(2035, 1, 1):
        raise ValueError("Business date outside fictional price coverage")
    start, end = business_window(business_date)
    template = json.loads(
        files("propane_demo").joinpath("data/template.json").read_text(encoding="utf-8")
    )
    data = template["clean"]
    selected = (
        [f"P{i:02}" for i in range(1, 15)] if scenario == "issues" else [scenario]
    )
    for name in selected:
        for patch in template["mutations"].get(name, []):
            rows = data[patch["file"]]
            if "collection" in patch:
                rows = rows[patch["collection"]]
            if "append" in patch:
                rows.append(patch["append"])
            else:
                rows[patch["index"]].update(patch["changes"])
    for manifest in data["manifests.json"]:
        if manifest["status"] == "success":
            content = data[manifest["file_id"]]
            manifest["row_count"] = str(
                sum(len(rows) for rows in content.values())
                if manifest["file_id"] == "qbo.json"
                else len(content)
            )

    # Templates contain explicit relative instants, never locale-dependent dates.
    def materialize(value):
        if isinstance(value, dict):
            return {key: materialize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [materialize(item) for item in value]
        if isinstance(value, str):
            if value.startswith("@hour:"):
                return (end + timedelta(hours=int(value[6:]))).isoformat()
            return (
                value.replace(
                    "@previous_date", (business_date - timedelta(days=1)).isoformat()
                )
                .replace("@date", business_date.isoformat())
                .replace(
                    "@run", f"synthetic-{seed}-{business_date.isoformat()}-{scenario}"
                )
                .replace("@start", start.isoformat())
                .replace("@end", end.isoformat())
            )
        return value

    data = materialize(data)
    output = {}
    for name, content in sorted(data.items()):
        if name in CSV_FIELDS:
            stream = io.StringIO(newline="")
            writer = csv.DictWriter(
                stream, fieldnames=CSV_FIELDS[name], lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(content)
            output[name] = stream.getvalue().encode("utf-8")
        else:
            output[name] = (
                json.dumps(content, indent=2, sort_keys=True) + "\n"
            ).encode()
    if "P11" in selected:
        output["pos.csv"] = b"transaction_id,line_id\nT-MALFORMED\n"
    return output
