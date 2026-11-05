"""Standalone read-only evidence document. All dynamic "
"strings are escaped."""

import hashlib
import html
import json
from datetime import timedelta
from decimal import Decimal


def escaped(value):
    return html.escape(str(value), quote=True)


def anchor(key):
    return "e-" + hashlib.sha256(key.encode()).hexdigest()


def collect_refs(value):
    if isinstance(value, dict):
        refs = set(value.get("source_refs", [])) | set(value.get("related_refs", []))
        for item in value.values():
            refs.update(collect_refs(item))
        return refs
    if isinstance(value, list):
        return set().union(*(collect_refs(item) for item in value))
    return set()


def evidence(db, refs):
    """Resolve current/historical/derived refs to immutable "
    "files and raw pointers."""
    files = {
        row[0]: bytes(row[1]).decode("utf-8", errors="replace")
        for row in db.execute("SELECT file_id,raw FROM files")
    }
    occurrences = {row[0]: dict(row) for row in db.execute("SELECT * FROM occurrences")}
    pointers = dict(db.execute("SELECT record_key,occurrence_ref FROM records"))
    versions = {
        key.split(":")[0]
        + ":version:"
        + key.split(":", 2)[2]
        + ":"
        + str(version): pointer
        for key, version, pointer in db.execute(
            "SELECT record_key,version,occurrence_ref FROM versions"
        )
    }
    records = {
        row[0]: json.loads(row[1])
        for row in db.execute("SELECT record_key,payload FROM records")
    }
    manifests = {
        "manifest:" + row["manifest_id"]: dict(row)
        for row in db.execute("SELECT * FROM manifests")
    }
    result = {}
    for ref in sorted(refs):
        if ref in pointers or ref in versions:
            row = occurrences[(pointers | versions)[ref]]
            result[ref] = {
                "file_id": row["file_id"],
                "pointer": row["pointer"],
                "raw": json.loads(row["raw"]),
            }
        elif ref in manifests:
            row = manifests[ref]
            result[ref] = {
                "file_id": "manifests.json",
                "pointer": "manifest_id=" + row["manifest_id"],
                "raw": json.loads(row["raw"]),
                "import_status": row["status"],
                "error_code": row["error_code"],
                "failure_pointer": row["pointer"],
            }
        elif ref.startswith("file:"):
            name, _, pointer = ref[5:].partition("#")
            if name not in files:
                candidates = [file for file in files if ref[5:].startswith(file + ":")]
                if candidates:
                    name = max(candidates, key=len)
                    pointer = ref[5 + len(name) :]
            result[ref] = (
                {"file_id": name, "pointer": "#" + pointer, "raw": files[name]}
                if name in files
                else {"missing_lookup_key": ref}
            )
        elif ref.startswith(("run:", "policy:")):
            name = "run.json" if ref.startswith("run:") else "policies.json"
            result[ref] = {"file_id": name, "pointer": "#", "raw": files[name]}
        else:
            # Derived keys retain the exact raw owning records, not synthesized rows.
            matches = []
            for key, row in sorted(records.items()):
                if (
                    ref == "cargas:meter_ticket:" + str(row.get("meter_ticket_id", ""))
                    or ref
                    == "pos:external_reference:"
                    + str(row.get("external_reference", ""))
                    or ref
                    == "qbo:external_reference:"
                    + str(row.get("DocNumber", row.get("PaymentRefNum", "")))
                    or ref
                    in {
                        "pos:fee:" + str(row.get("batch_id", "")) + ":fees",
                        *[
                            "pos:component:"
                            + str(row.get("batch_id", ""))
                            + ":"
                            + field
                            for field in ("gross", "refunds", "fees", "net")
                        ],
                    }
                    or ref
                    == "qbo:version:"
                    + str(row.get("Id", ""))
                    + ":"
                    + str(row.get("SyncToken", ""))
                    or (
                        ref.startswith("qbo:account:")
                        and ref[12:]
                        in {
                            row.get("JournalEntryLineDetail", {})
                            .get("AccountRef", {})
                            .get("value"),
                            row.get("DepositLineDetail", {})
                            .get("AccountRef", {})
                            .get("value"),
                        }
                    )
                ):
                    matches.append(pointers[key])
            result[ref] = (
                {
                    "derived_from": [
                        {
                            "file_id": occurrences[p]["file_id"],
                            "pointer": occurrences[p]["pointer"],
                            "raw": json.loads(occurrences[p]["raw"]),
                        }
                        for p in sorted(set(matches))
                    ]
                }
                if matches
                else {"missing_lookup_key": ref}
            )
    return result


def links(refs):
    return " ".join(
        f'<a href="#{anchor(ref)}">{escaped(ref)}</a>' for ref in sorted(set(refs))
    )


def duration(hours):
    """Decimal C09 hours may repeat; show the exact "
    "microsecond source duration."""
    micros = int((Decimal(hours) * 3600000000).to_integral_value())
    return str(timedelta(microseconds=micros))


def summary(result):
    counts = result["coverage"]
    header = (
        f"{result['status'].capitalize()} synthetic run. "
        f"{len(result['checks']['findings'])} findings; "
        f"{len(result['alerts'])} source alerts. "
        f"{counts['evaluated']} check scopes evaluated; "
        f"{counts['not_evaluated']} not evaluated. "
        "Review critical and high exceptions first, then inspect "
        "their source evidence. "
        "Offline computed summary; deterministic calculations only."
    )
    lines = [header]
    for key, sheet in result["kpis"].items():
        value = sheet["value"] if sheet["value"] is not None else "Not available"
        lines.append(f"{key}: {value} {sheet['unit']} ({sheet['status']}).")
    for finding in result["prioritized_findings"]:
        lines.append(
            f"[{finding['finding_id']}] {finding['severity']}; "
            f"delta {finding['delta']}; threshold {finding['threshold']}."
        )
    for alert in result["prioritized_alerts"]:
        lines.append(f"Quality warning: {alert['reason_code']}.")
    return "\n".join(lines)


STYLE = """
:root{color-scheme:light;--ink:#182b40;--muted:#405366;--link:#004d99;
--line:#b8c7d5;--paper:#fff;--wash:#f1f5f9;--danger:#8e1717}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font:1rem/1.6 system-ui,sans-serif}main{max-width:76rem;margin:auto;padding:2rem}
h1{font-size:2rem;line-height:1.2}h2{margin-top:3rem;font-size:1.5rem}
h3{margin-top:1.5rem}p{max-width:74ch}a{color:var(--link);text-underline-offset:.2em}
a:hover{text-decoration-thickness:.15em}:focus-visible{outline:3px solid var(--link);
outline-offset:3px}::selection{background:#c6e3ff;color:var(--ink)}
.status{font-size:1.25rem;font-weight:700;padding:1rem;background:var(--wash)}
.incomplete,.critical,.high{color:var(--danger)}
article{border-top:1px solid var(--line);
padding:1rem 0}dl{display:grid;grid-template-columns:minmax(11rem,1fr) 2fr;
gap:.6rem 1rem}dt{font-weight:650}dd{margin:0;font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);
padding:.6rem}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--wash);padding:1rem;
font: .875rem/1.55 ui-monospace,monospace}summary{cursor:pointer;font-weight:650}
small{color:var(--muted)}p,li,td,dd,article,summary{overflow-wrap:anywhere}
nav{display:flex;flex-wrap:wrap;gap:1rem}section{scroll-margin-top:1rem}
@media(max-width:40rem){main{padding:1rem}dl{grid-template-columns:1fr}
dd{margin-bottom:1rem}
table,tbody,tr,th,td{display:block}thead{display:none}tr{margin-bottom:1.5rem}}
@media print{main{max-width:none;padding:0}details{break-inside:avoid}a{color:inherit}}
"""


def result_digest(result):
    return hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def render(result, raw_evidence, *, narrative_status=None):
    """Escape source text, keys and optional untrusted narrative."""
    if narrative_status is not None and narrative_status["digest"] != result_digest(
        result
    ):
        narrative_status = {
            "status": "computed_fallback",
            "reason": "digest_mismatch",
            "text": summary(result),
            "digest": result_digest(result),
        }
    run, checks = result["run"], result["checks"]
    out = [
        '<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        (
            '<meta http-equiv="Content-Security-Policy" '
            "content=\"default-src 'none'; style-src 'unsafe-inline'; "
            "base-uri 'none'; form-action 'none'\">"
        ),
        "<title>Synthetic propane morning report</title>",
        f'<style>{STYLE}</style><body><main id="top">',
        "<h1>Propane morning report</h1>",
        f"<p>Business date: {escaped(run['business_date'])} "
        f"· America/Denver · synthetic data only</p>",
        f'<p class="status {escaped(result["status"])}">Run '
        f"status: {escaped(result['status'].upper())}</p>",
        f"<p>Run: {escaped(run['run_id'])}<br>As of: "
        f"{escaped(result['display_as_of'])}<br>Source "
        f"digest: {escaped(result['source_digest'])}</p>",
        (
            '<nav aria-label="Report sections"><a href="#alerts">'
            'Alerts</a><a href="#kpis">KPIs</a><a href="#exceptions">'
            'Exceptions</a><a href="#coverage">Coverage</a><a '
            'href="#worksheets">Worksheets</a><a href="#evidence">'
            "Evidence</a></nav>"
        ),
        '<section id="alerts"><h2>Source alerts</h2>',
    ]
    if not result["alerts"]:
        out.append("<p>No source alerts.</p>")
    for alert in result["prioritized_alerts"]:
        out.append(
            f'<article class="{escaped(alert["severity"])}"><h3>'
            f"{escaped(alert['severity'].upper())}: "
            f"{escaped(alert['reason_code'])}</h3><p>"
            f"{escaped(alert['source'])} · "
            f"{escaped(alert['check_id'])} · "
            f"{escaped(alert['status'])}</p><p>"
            f"{links(alert['source_refs'] + alert['related_refs'])}</p>"
            f"</article>"
        )
    out.append(
        '</section><section id="kpis"><h2>Business KPIs</h2><p>'
        "Completed customer deliveries plus other retail volume. "
        "Revenue uses posting dates and net QBO lines; taxes, "
        "container deposits, payments and deposits are excluded. "
        "AR replays gross invoices and applied allocations after "
        "the opening cutoff. Partial known amounts are not full "
        "totals.</p><dl>"
    )
    labels = {
        "delivered": "Delivered gallons",
        "retail": "Other retail gallons",
        "total_gallons": "Total gallons sold",
        "revenue": "Net revenue",
        "AR": "Accounts receivable",
    }
    out.append(
        "<dt>Volume measurement basis</dt><dd>"
        + escaped(result["gallon_basis"])
        + " · scope: completed Cargas-style deliveries and crosswalked POS retail"
        + "</dd>"
    )
    for key, sheet in result["kpis"].items():
        value = sheet["value"] if sheet["value"] is not None else "Not available"
        out.append(
            f"<dt>{labels[key]}</dt><dd>{escaped(value)} "
            f"{escaped(sheet['unit'])} — "
            f"{escaped(sheet['status'])}<br><a "
            f'href="#{anchor("worksheet:" + key)}">Inspect '
            f"calculation</a></dd>"
        )
    out.append(
        (
            "</dl></section><section><h2>Computed summary</h2><p>"
            "Deterministic results remain authoritative.</p><pre>"
        )
        + escaped(summary(result))
        + '</pre></section><section id="exceptions"><h2>Prioritized exceptions</h2>'
    )
    if narrative_status is not None:
        out.append(
            "<aside><h2>Optional narrative</h2><p>Narrative status: "
            + escaped(narrative_status["status"])
            + " · "
            + escaped(narrative_status["reason"])
            + "</p><p>AI-generated text is untrusted; illustrative text is not a live "
            "Claude response. Only shape and cited finding IDs are validated, not "
            "sentence accuracy, numbers, causes or remedies. Computed results remain "
            "authoritative.</p><pre>"
            + escaped(narrative_status["text"])
            + "</pre></aside>"
        )
    if not checks["findings"]:
        out.append(
            "<p>No business exceptions. All listed core check scopes "
            "were evaluated.</p>"
        )
    for finding in result["prioritized_findings"]:
        out.append(
            f'<article class="{escaped(finding["severity"])}">'
            f"<h3>{escaped(finding['severity'].upper())} · "
            f"{escaped(finding['check_id'])} · "
            f"{escaped(finding['status'])}</h3><p>"
            f"{escaped(finding['explanation'])}</p><p>Finding: "
            f"{escaped(finding['finding_id'])}</p>"
        )
        if finding["check_id"] == "C09":
            values = (
                f"Coverage gap {duration(finding['actual'])}; "
                f"allowed {duration(finding['expected'])} "
                f"(hours policy: {finding['threshold']})."
            )
        else:
            values = " · ".join(
                f"{k}: {finding[k]}"
                for k in ("actual", "expected", "delta", "threshold")
            )
        out.append(
            "<p>"
            + escaped(values)
            + "</p><p>"
            + links(finding["source_refs"] + finding["related_refs"])
            + "</p>"
        )
        if finding["missing_reference"]:
            out.append(
                "<p>Missing reference: "
                + escaped(json.dumps(finding["missing_reference"], sort_keys=True))
                + "</p>"
            )
        out.append("</article>")
    out.append(
        ('</section><section id="coverage"><h2>Check coverage and freshness</h2><p>')
        + escaped(json.dumps(result["coverage"], sort_keys=True))
        + "</p><p>Rule version: "
        + escaped(result["rule_version"])
        + " · Policy version: "
        + escaped(result["policy_version"])
        + "</p>"
    )
    for scope, state in result["check_scopes"].items():
        out.append(
            "<p><strong>"
            + escaped(scope)
            + "</strong>: "
            + escaped(state["status"])
            + " "
            + escaped(state.get("reason", state.get("missing_lookup_key", "")))
            + " "
            + links(state.get("source_refs", []))
            + "</p>"
        )
    out.append(
        "<table><caption>Source windows and coverage watermarks "
        '(America/Denver)</caption><thead><tr><th scope="col">'
        'Source</th><th scope="col">State</th><th scope="col">'
        "Window / watermark / extracted</th></tr></thead><tbody>"
    )
    for source in result["freshness"]:
        out.append(
            '<tr><th scope="row">'
            + links(source["source_refs"])
            + "</th><td>"
            + escaped(source["status"])
            + "</td><td>"
            + "<br>".join(
                escaped(source.get(k, "Missing"))
                for k in (
                    "window_start",
                    "window_end",
                    "covered_through",
                    "extracted_at",
                )
            )
            + "</td></tr>"
        )
    out.append(
        '</tbody></table></section><section id="worksheets"><h2>'
        "Signed calculation worksheets</h2>"
    )
    for key, sheet in result["kpis"].items():
        out.append(
            f'<article id="{anchor("worksheet:" + key)}"><h3>'
            f"{labels[key]} — {escaped(sheet['status'])}</h3><p>"
            f"Known contributions: "
            f"{escaped(sheet['known_value'])} "
            f"{escaped(sheet['unit'])}</p>"
        )
        for contribution in sheet["contributions"]:
            out.append(
                "<p>"
                + escaped(contribution["kind"])
                + ": "
                + escaped(contribution["amount"])
                + " "
                + links(contribution["source_refs"])
                + "</p>"
            )
        for gap in sheet["gaps"]:
            out.append(
                "<p>Missing support: "
                + escaped(gap["missing_lookup_key"])
                + " "
                + links(gap["source_refs"])
                + "</p>"
            )
        if key == "AR":
            for kind in ("unapplied_cash", "unapplied_credits"):
                separate = sheet[kind]
                out.append(
                    "<h4>"
                    + escaped(kind)
                    + " (separate)</h4><p>"
                    + escaped(
                        separate["value"]
                        if separate["value"] is not None
                        else "Not available"
                    )
                    + " USD</p>"
                )
                for c in separate["contributions"]:
                    out.append(
                        "<p>"
                        + escaped(c["amount"])
                        + " "
                        + links(c["source_refs"])
                        + "</p>"
                    )
            out.append("<h4>Reported Balance comparison (never added to AR)</h4>")
            for comparison in sheet["reported_balance_comparisons"]:
                out.append(
                    "<p>"
                    + escaped(
                        json.dumps(
                            {k: v for k, v in comparison.items() if k != "source_refs"},
                            sort_keys=True,
                        )
                    )
                    + " "
                    + links(comparison["source_refs"])
                    + "</p>"
                )
        out.append("</article>")
    for asset, sheet in checks["inventory"].items():
        out.append(
            "<h3>Inventory: "
            + escaped(asset)
            + "</h3><pre>"
            + escaped(json.dumps(sheet, indent=2, sort_keys=True))
            + "</pre><p>"
            + links(collect_refs(sheet))
            + "</p>"
        )
    out.append(
        "<h3>Whole-business inventory (internal transfers eliminated)</h3><pre>"
        + escaped(json.dumps(checks["consolidation"], indent=2, sort_keys=True))
        + "</pre><p>"
        + links(collect_refs(checks["consolidation"]))
        + (
            '</p></section><section id="evidence"><h2>Immutable source '
            "evidence</h2><p>Raw synthetic inputs retain original "
            "values, file IDs and pointers; normalized numeric values "
            "use scaled integers internally. Missing references are "
            "explicit lookups, never invented records.</p>"
        )
    )
    for key, record in sorted(raw_evidence.items()):
        out.append(
            f'<details id="{anchor(key)}"><summary>'
            f"{escaped(key)}</summary><pre>"
            f"{escaped(json.dumps(record, indent=2, sort_keys=True))}</pre>"
            f"</details>"
        )
    out.append(
        "</section><footer><p>Synthetic decision-support "
        "demonstration. Fictional policies require client "
        "confirmation before real use. No certified audit, "
        'accounting writes or live integrations.</p><a href="#top">'
        "Back to top</a></footer></main></body></html>"
    )
    return "\n".join(out) + "\n"
