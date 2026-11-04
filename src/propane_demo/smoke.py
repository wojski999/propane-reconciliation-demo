"""Exercise SQLite and static HTML without implementing reconciliation rules."""

import sqlite3
from contextlib import closing
from html import escape


def sample_html(label: str = "SYNTHETIC-SMOKE-001") -> str:
    """Generate one synthetic marker in temporary SQLite and render its evidence."""
    if not label.strip():
        raise ValueError("Sample label must not be blank")
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("CREATE TABLE smoke_sample (label TEXT NOT NULL)")
        connection.execute("INSERT INTO smoke_sample VALUES (?)", (label,))
        (stored_label,) = connection.execute(
            "SELECT label FROM smoke_sample"
        ).fetchone()
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        "<title>Foundation smoke report</title><main>"
        "<h1>Foundation smoke report</h1>"
        "<p>Synthetic infrastructure sample only. "
        "No audit checks or KPIs evaluated.</p>"
        f'<p id="sample">Sample: {escape(stored_label)}</p>'
        "</main></html>"
    )
