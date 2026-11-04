"""SQLite boundary adapter; the rules themselves consume ordinary Python values."""

import json

from propane_demo.ingestion import unavailable


def from_database(db, blocked=None):
    """Detach validated scaled records, provenance and import eligibility.

    `blocked` is an optional scope -> reason/evidence mapping for a later freshness
    engine. This adapter does not decide freshness or persist business findings.
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
