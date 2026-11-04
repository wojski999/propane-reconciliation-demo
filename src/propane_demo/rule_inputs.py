"""SQLite boundary adapter; the rules themselves consume ordinary Python values."""

import json

from propane_demo.ingestion import dependencies, dump, unavailable
from propane_demo.rules import reconcile


def from_database(db, blocked=None):
    """Detach validated scaled records, provenance and import eligibility.

    `blocked` optionally supplies caller eligibility restrictions. The pure engine
    evaluates actual freshness; reconcile_database owns alert persistence.
    """
    run = json.loads(db.execute("SELECT metadata FROM run").fetchone()[0])
    policy = json.loads(
        db.execute("SELECT raw FROM files WHERE file_id='policies.json'").fetchone()[0]
    )
    records = {
        key: json.loads(payload)
        for key, payload in db.execute("SELECT record_key,payload FROM records")
    }
    occurrences = [
        dict(row)
        for row in db.execute(
            "SELECT ref,file_id,record_key,version FROM occurrences ORDER BY ref"
        )
    ]
    scopes = unavailable(db)
    scopes.update(blocked or {})
    return {
        "manifests": [
            dict(row) | {"metadata": json.loads(row["raw"])}
            for row in db.execute("SELECT * FROM manifests ORDER BY file_id")
        ],
        "alerts": [
            dict(row)
            | {
                "source_refs": json.loads(row["source_refs"]),
                "related_refs": json.loads(row["related_refs"]),
            }
            for row in db.execute("SELECT * FROM alerts ORDER BY alert_id")
        ],
        "dependencies": dependencies(records),
        "run": run,
        "policy": policy,
        "records": records,
        "occurrences": occurrences,
        "pointers": dict(db.execute("SELECT record_key,occurrence_ref FROM records")),
        "blocked": scopes,
        "unavailable_sources": {
            row[0]: json.loads(row[1])[0]
            for row in db.execute(
                "SELECT source,source_refs FROM alerts WHERE check_id='C10'"
            )
        },
    }


def reconcile_database(db):
    """Run the pure engine and persist its deduplicated source/run alerts."""
    result = reconcile(from_database(db))
    for alert in result["alerts"]:
        db.execute(
            "INSERT OR IGNORE INTO alerts VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                alert["alert_id"],
                alert["run_id"],
                alert["source"],
                alert["check_id"],
                alert["severity"],
                alert["reason_code"],
                dump(alert["source_refs"]),
                dump(alert["related_refs"]),
                alert["observed_at"],
                alert["status"],
            ),
        )
    if result["alerts"] or result["not_evaluated"]:
        db.execute("UPDATE run SET status='incomplete'")
    db.commit()
    return result
