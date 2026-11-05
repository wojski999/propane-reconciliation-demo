"""Standalone read-only evidence document. All dynamic "
"strings are escaped."""

import hashlib
import html
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo


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


def technical_report(result, raw_evidence, *, narrative_status=None):
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
        "<h2>Run and evidence record</h2>",
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


LABELS = {
    "delivered": "Delivered gallons",
    "retail": "Retail gallons",
    "total_gallons": "Total gallons sold",
    "revenue": "Net revenue",
    "AR": "Accounts receivable",
}
SYSTEMS = {
    "qbo": "QuickBooks",
    "cargas": "Cargas deliveries",
    "pos": "POS",
    "readings": "Tank readings",
    "inventory": "Inventory movements",
    "settlements": "Card settlements",
    "prices": "Price list",
    "identity": "Customer and item mappings",
    "ar": "Opening receivables",
    "optional_empty": "Optional supporting records",
}
TITLES = {
    "C01": "Delivered gallons remain unbilled in QuickBooks",
    "C02": "Billed gallons have no matching delivery",
    "C03": "Possible duplicate sale records",
    "C04": "Sale amount differs from the approved price",
    "C05": "Credit, refund or discount needs review",
    "C06": "Payment needs allocation review",
    "C07": "Card settlement differs from the QuickBooks deposit",
    "C08": "Tank inventory needs review",
    "C09": "Source coverage is out of date",
    "C10": "Source import failed",
    "C11": "Supporting records are missing",
    "C12": "Accounting postings need review",
}
ACTIONS = {
    "C01": "Check the delivery ticket and confirm billing with the office.",
    "C02": "Confirm the delivery ticket before accepting the invoice.",
    "C03": "Compare both source records before reversing any sale.",
    "C04": "Confirm the effective price and approved discount with billing.",
    "C05": "Confirm the original sale and approval with the accounting team.",
    "C06": "Ask accounting to confirm the payment allocation.",
    "C07": "Compare the processor statement, fees and bank deposit with accounting.",
    "C08": "Verify the tank readings and movement log with operations.",
    "C09": "Refresh the source export, then rerun the report.",
    "C10": "Repair or re-export the source file, then rerun the report.",
    "C11": "Supply the missing records or mapping, then rerun the report.",
    "C12": "Ask accounting to review the linked posting and clearing account.",
}
SHORT = {
    "C01": "Not billed",
    "C02": "Billed without delivery",
    "C03": "Possible duplicate",
    "C04": "Price differs",
    "C05": "Credit to review",
    "C06": "Payment allocation",
    "C07": "Deposit differs",
    "C08": "Tank variance",
    "C09": "Source out of date",
    "C10": "Import failed",
    "C11": "Records missing",
    "C12": "Posting to review",
}
PREFIXES = {
    "cargas": "Cargas",
    "qbo": "QuickBooks",
    "pos": "POS",
    "prices": "Price list",
    "identity": "Mappings",
    "ar": "Opening receivables",
    "inventory": "Inventory movements",
}
# Money-flow stages: the authoritative KPI shown and the checks that flag it.
STAGES = (
    ("Delivered", "delivered", ("C02",)),
    ("Billed", "revenue", ("C01", "C04", "C05")),
    ("Paid", "AR", ("C03", "C06")),
    ("Deposited", None, ("C07", "C12")),
)
PILOT_NAV = (
    "Deliveries",
    "Customers",
    "Inventory &amp; tanks",
    "Weekly &amp; monthly",
    "Receivables",
    "Checks &amp; rules",
)
SEVERITIES = ("critical", "high", "medium")
BUSINESS_STYLE = """
body{background:#f1f5f9;color:#0f172a;font:14px/1.45 -apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
main#top{max-width:none;margin:0;padding:0}
.app{display:grid;grid-template-columns:216px minmax(0,1fr);min-height:100vh}
.side{background:#0b1220;color:#cbd5e1;padding:16px 12px;flex-direction:column;
flex-wrap:nowrap;gap:2px}.brand{display:flex;align-items:center;gap:10px;
color:#fff;font-weight:700;padding:4px 8px 18px}.logo{width:28px;height:28px;
border-radius:7px;background:#0369a1;display:grid;place-items:center;font-size:13px}
.brand small{display:block;font-weight:400;color:#94a3b8;font-size:11px}
.side .sec{font-size:10px;letter-spacing:.08em;text-transform:uppercase;
color:#94a3b8;padding:14px 10px 6px;margin:0}.side a,.side .off{display:flex;
align-items:center;gap:8px;color:#cbd5e1;text-decoration:none;padding:7px 10px;
border-radius:7px;font-size:13px}.side a.on{background:#1e293b;color:#fff}
.side .n{margin-left:auto;background:#b91c1c;color:#fff;border-radius:999px;
font-size:11px;padding:0 7px}.side .off{color:#94a3b8;cursor:not-allowed}
.side .off small{margin-left:auto;font-size:10px;color:#94a3b8;
border:1px solid #334155;border-radius:4px;padding:0 4px}
.side .bottom{margin-top:auto;border-top:1px solid #1e293b;padding:12px 10px 0;
font-size:12px;color:#94a3b8}.shell{display:flex;flex-direction:column;min-width:0}
.top{display:flex;align-items:center;flex-wrap:wrap;gap:10px;background:#fff;
border-bottom:1px solid #e2e8f0;padding:10px 20px}.crumb{color:#64748b;font-size:13px}
.crumb b{color:#0f172a}.sp{flex:1}.pill{display:inline-flex;align-items:center;
gap:6px;border:1px solid #e2e8f0;border-radius:8px;padding:6px 10px;font-size:13px;
background:#fff;color:#334155}.dot{width:8px;height:8px;border-radius:50%;
background:#16a34a;flex:none}.dot.stale{background:#d97706}
.dot.failed{background:#b91c1c}.b{display:inline-flex;align-items:center;
border-radius:8px;padding:7px 12px;font-size:13px;font-weight:600;
border:1px solid #e2e8f0;background:#fff;color:#334155;cursor:not-allowed}
.b.p{background:#0369a1;border-color:#0369a1;color:#fff}.mock{font-size:11px;
color:#92400e;background:#fffbeb;border:1px solid #fde68a;border-radius:6px;
padding:2px 8px}.content{padding:20px;display:grid;gap:16px;min-width:0}
.greet h1{font-size:22px;line-height:1.3;margin:0}.greet p{margin:4px 0 0;
color:#334155;max-width:none}.greet .headline{font-size:15px;color:#0f172a}
.greet b{color:#b91c1c}.card{background:#fff;border:1px solid #e2e8f0;
border-radius:10px;min-width:0}.ch{display:flex;align-items:center;flex-wrap:wrap;
gap:4px 10px;padding:12px 16px;border-bottom:1px solid #e2e8f0}
.ch h2,.ch h3{font-size:14px;line-height:1.4;margin:0}.m{color:#64748b;font-size:12px}
.flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}
.st{padding:14px 16px;border-right:1px solid #e2e8f0}.st:last-child{border-right:0}
.k{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
color:#64748b;margin:0}.v{font-size:22px;font-weight:700;line-height:1.3;
margin:6px 0 2px;font-variant-numeric:tabular-nums}.v.unavailable{font-size:14px;
color:#b91c1c;font-weight:650}.v.alert{color:#b91c1c}.s{color:#64748b;
font-size:12px;margin:0}.s a{color:#0369a1}.chip{display:inline-flex;
margin:8px 6px 0 0;font-size:12px;font-weight:600;border-radius:6px;padding:2px 8px;
background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;text-decoration:none}
.chip.ok{background:#f0fdf4;color:#15803d;border-color:#bbf7d0}
.chip.warn{background:#fffbeb;color:#92400e;border-color:#fde68a}
.kp{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.kp .card{padding:12px 16px}.kp .v{font-size:20px}
.kp .v.unavailable{font-size:14px}.note{color:#64748b;
font-size:12px;margin:0}.split{display:grid;
grid-template-columns:minmax(0,1fr) 380px;gap:16px;align-items:start}
.tabs{display:flex;gap:4px;margin-left:auto}.tabs a{font-size:12px;padding:4px 10px;
border-radius:999px;color:#334155;text-decoration:none}.ft{display:none}
.ex:not(:has(.ft:target)) .tabs a.all{background:#0f172a;color:#fff}
.ex th{text-align:left;font-size:11px;letter-spacing:.05em;text-transform:uppercase;
color:#64748b;font-weight:600;padding:8px 16px;background:#f8fafc;
border-bottom:1px solid #e2e8f0}.ex td{padding:10px 16px;
border-bottom:1px solid #e2e8f0;vertical-align:middle}.ex tr:last-child td{
border-bottom:0}.ex .num{text-align:right}.pr{font-size:11px;font-weight:700;
border-radius:5px;padding:2px 7px;background:#fef2f2;color:#b91c1c;white-space:nowrap}
.pr.medium{background:#fffbeb;color:#92400e}.tag{font-size:11px;
color:#334155;border:1px solid #cbd5e1;border-radius:4px;padding:0 5px}
.it a{font-weight:600;color:#0f172a}
.it small{display:block;color:#64748b;font-size:12px}.src,.stt{font-size:12px;
color:#334155;white-space:nowrap}.amt{text-align:right;font-weight:700;
white-space:nowrap;font-variant-numeric:tabular-nums}
.split:not(:has(.drawer:target)) .r-0 td{background:#f0f9ff}
.split:not(:has(.drawer:target)) .r-0 td:first-child{box-shadow:inset 3px 0 0 #0369a1}
.drawer{display:none;scroll-margin-top:16px}.drawer:target,
.split:not(:has(.drawer:target)) .drawer:first-child{display:block}
.drawer .body{padding:14px 16px;display:grid;gap:12px}.drawer h4{font-size:11px;
text-transform:uppercase;letter-spacing:.05em;color:#64748b;margin:0 0 4px}
.drawer p{margin:0}.docs{display:grid;gap:8px}.doc{border:1px solid #e2e8f0;
border-radius:8px;padding:10px 12px;font-size:12px}.doc .t{display:flex;
justify-content:space-between;gap:8px;font-weight:700;font-size:11px;
text-transform:uppercase;color:#64748b;margin-bottom:4px}.doc .t a{
text-transform:none;font-weight:600;color:#0369a1}.doc dl{
grid-template-columns:7rem minmax(0,1fr);gap:2px 8px;margin:6px 0 0}
.doc dt{color:#64748b;font-weight:400;overflow-wrap:anywhere}.doc dd{margin:0}
.doc.miss{border-style:dashed;
border-color:#fca5a5;background:#fef2f2;color:#b91c1c}.acts{display:flex;
flex-wrap:wrap;align-items:center;gap:8px;border-top:1px solid #e2e8f0;
padding:12px 16px}.pills{display:flex;flex-wrap:wrap;align-items:center;gap:8px;
padding:12px 16px}.pills>.technical{order:2;margin-left:auto}.pills>.coverage{order:3;
flex-basis:100%}.pills>details[open]{flex-basis:100%;margin-left:0}
.pills>details>summary{display:inline-flex;border:1px solid #e2e8f0;
border-radius:8px;padding:7px 12px;font-size:13px;font-weight:600;color:#0f172a}
.pills>.coverage>summary{border:0;padding:0;font-size:12px;color:#0369a1}
.times{margin:8px 0 0;padding-left:18px;font-size:13px}
.tech{font-size:15px;line-height:1.6;padding:8px 4px}.tech h2{font-size:1.25rem;
margin-top:2rem}footer{margin-top:2rem;color:#334155;font-size:.9rem}
@media(max-width:1100px){.split{grid-template-columns:minmax(0,1fr)}}
@media(max-width:760px){.app{grid-template-columns:minmax(0,1fr)}.side,
.top .wide{display:none}.content{padding:12px}.flow{grid-template-columns:1fr 1fr}
.st:nth-child(2){border-right:0}.st:nth-child(-n+2){border-bottom:1px solid #e2e8f0}
.kp{grid-template-columns:minmax(0,1fr)}.ex table{display:table}
.ex thead{display:table-header-group}.ex tbody{display:table-row-group}
.ex tr{display:table-row;margin:0}.ex th,.ex td{display:table-cell;padding:10px 8px}
.ex .src,.ex .stt{display:none}.tabs{margin-left:0}}
@media print{body{background:#fff}.app{display:block}.side,.top .b,.tabs,.acts{
display:none}.split{grid-template-columns:1fr}.drawer{display:block;
break-inside:avoid}.card{break-inside:avoid}}
"""


def formatted(value, unit):
    """Format computed values only; never substitute a known partial amount."""
    number = Decimal(value)
    return (
        (f"-${abs(number):,.2f}" if number < 0 else f"${number:,.2f}")
        if unit == "USD"
        else f"{number:,.0f} gal"
    )


def unavailable_reason(sheet, result):
    refs = set().union(*(set(g["source_refs"]) for g in sheet["gaps"]))
    reasons = []
    for source in result["freshness"]:
        if refs.intersection(source["source_refs"]) and source["status"] != "success":
            name = SYSTEMS.get(source["source"], source["source"])
            reason = name + (
                " coverage is out of date"
                if source["status"] == "stale"
                else " import failed"
            )
            if reason not in reasons:
                reasons.append(reason)
    return "; ".join(reasons) or "Required source records or mappings are missing"


def headline(result):
    day = date.fromisoformat(result["run"]["business_date"])
    count = len(result["checks"]["findings"])
    noun = "item needs" if count == 1 else "items need"
    text = f"{day.strftime('%A, %b')} {day.day}: {count} {noun} your attention. "
    problems = sorted(
        {
            SYSTEMS.get(s["source"], s["source"])
            + (
                " coverage is out of date"
                if s["status"] == "stale"
                else " import failed"
            )
            for s in result["freshness"]
            if s["status"] != "success"
        }
    )
    text += "; ".join(problems) + ". " if problems else "All sources up to date. "
    missing = [LABELS[k] for k, s in result["kpis"].items() if s["value"] is None]
    if missing:
        text += "Totals unavailable: " + ", ".join(missing) + ". "
    if result["status"] != "complete":
        text += "Report incomplete; some checks could not reach a conclusion."
    return text.strip()


def impact(finding):
    check, delta = finding["check_id"], finding["delta"]
    if delta is None:
        return "No dollar or gallon conclusion is supported by the available records."
    if check == "C01":
        return formatted(delta, "gal") + " delivered but not allocated to billing."
    if check == "C02":
        return formatted(delta, "gal") + " billed without a matching delivery."
    if check in {"C07", "C08"}:
        direction = "below" if Decimal(delta) < 0 else "above"
        amount = formatted(abs(Decimal(delta)), "USD" if check == "C07" else "gal")
        subject = "Deposit" if check == "C07" else "Tank reading"
        return f"{subject} is {amount} {direction} the expected amount."
    if check == "C05" and any(
        ref.startswith(("qbo:CreditMemo:", "qbo:RefundReceipt:"))
        for ref in finding["source_refs"]
    ):
        return formatted(finding["actual"], "USD") + " adjustment flagged for review."
    if check in {"C04", "C06", "C12"}:
        return formatted(delta, "USD") + " difference in the computed reconciliation."
    if check == "C09":
        return "Source coverage is incomplete. Affected totals are unavailable."
    if check == "C03":
        return (
            f"{finding['actual']} records share a source or external "
            "transaction reference. "
            "Confirm whether this is a repeated import or a duplicate sale."
        )
    return finding["explanation"]


def denver_time(instant, fallback="time unavailable"):
    """Use the same local, labeled display for extraction and coverage timestamps."""
    return (
        datetime.fromisoformat(instant)
        .astimezone(ZoneInfo("America/Denver"))
        .strftime("%b %d, %Y %I:%M %p %Z")
        if instant
        else fallback
    )


def business_impact(finding, result):
    text = impact(finding)
    estimate = result.get("exposure_estimates", {}).get(finding["finding_id"])
    if estimate:
        amount = formatted(estimate["value"], "USD")
        text += (
            f" Approximately {amount} not billed at the effective list price "
            "(estimate before discounts; not booked revenue)."
            if estimate["kind"] == "unbilled_at_list_price"
            else f" Potential duplicate net sales: {amount}, pending review."
        )
    if finding["check_id"] == "C08" and finding["delta"] is not None:
        text += " No unit cost is supplied; dollar value is unavailable."
    return text


def source_groups(result):
    groups = {
        "QuickBooks": {"qbo"},
        "Cargas": {"cargas"},
        "POS": {"pos"},
        "Card processor": {"settlements"},
        "Tank readings": {"readings", "inventory"},
    }
    output = []
    for label, systems in groups.items():
        members = [s for s in result["freshness"] if s["source"] in systems]
        if not members:
            continue
        state = max(
            members, key=lambda s: {"success": 0, "stale": 1}.get(s["status"], 2)
        )
        group = {"label": label, "status": state["status"]}
        for field in ("extracted_at", "covered_through"):
            values = [s.get(field) for s in members]
            group[field] = (
                min(values, key=datetime.fromisoformat) if all(values) else None
            )
        output.append(group)
    return output


def record_names(finding, result):
    labels = result["run"].get("report_labels", {})
    names = [labels[ref] for ref in finding["source_refs"] if ref in labels] or [
        SYSTEMS.get(source["source"], source["source"])
        for source in result["freshness"]
        if set(source["source_refs"]) & set(finding["source_refs"])
    ]
    return list(dict.fromkeys(names))


def business_title(finding, result):
    names = record_names(finding, result)
    title = TITLES[finding["check_id"]]
    return "; ".join(names) + ": " + title[0].lower() + title[1:] if names else title


def short_time(instant, as_of):
    """Compact Denver time; the date is shown unless it is the report morning."""
    if not instant:
        return "time unavailable"
    zone = ZoneInfo("America/Denver")
    moment = datetime.fromisoformat(instant).astimezone(zone)
    clock = moment.strftime("%I:%M %p").lstrip("0")
    if moment.date() == datetime.fromisoformat(as_of).astimezone(zone).date():
        return clock
    return f"{moment.strftime('%b')} {moment.day}, {clock}"


def system_name(ref, result):
    for source in result["freshness"]:
        if ref in source["source_refs"]:
            return SYSTEMS.get(source["source"], source["source"])
    if ref.startswith("pos:batch:"):
        return "Card processor"
    if ref.startswith("cargas:reading:"):
        return "Tank readings"
    prefix = ref.split(":")[0]
    return PREFIXES.get(prefix, prefix)


def finding_systems(finding, result):
    refs = list(finding["source_refs"])
    if finding.get("missing_reference"):
        refs.append(finding["missing_reference"]["system"] + ":")
    return " → ".join(dict.fromkeys(system_name(ref, result) for ref in refs))


def impact_amount(finding, result):
    """Table impact: a computed dollar amount when supported, otherwise gallons."""
    estimate = result.get("exposure_estimates", {}).get(finding["finding_id"])
    if estimate:
        return "~" + formatted(estimate["value"], "USD"), Decimal(estimate["value"])
    check, delta = finding["check_id"], finding["delta"]
    if delta is None:
        return "—", None
    if check in {"C01", "C02", "C08"}:
        return formatted(abs(Decimal(delta)), "gal"), None
    if check == "C05" and any(
        ref.startswith(("qbo:CreditMemo:", "qbo:RefundReceipt:"))
        for ref in finding["source_refs"]
    ):
        amount = abs(Decimal(finding["actual"]))
    elif check in {"C04", "C06", "C07", "C12"}:
        amount = abs(Decimal(delta))
    else:
        return "—", None
    return formatted(amount, "USD"), amount


def checked(result, checks):
    return all(
        state["status"] == "evaluated"
        for scope, state in result["check_scopes"].items()
        if scope.split(":")[0] in checks
    )


def change_text(change):
    if change is None:
        return ""
    delta = Decimal(change["change"])
    day = date.fromisoformat(change["prior_business_date"])
    when = f" vs. {day.strftime('%b')} {day.day}"
    if not delta:
        return "No change" + when
    return ("▲ " if delta > 0 else "▼ ") + formatted(abs(delta), change["unit"]) + when


def stage_value(key, result):
    """Stage figure from an authoritative worksheet or check; never a partial sum."""
    if key is None:
        scopes = [
            state
            for scope, state in result["check_scopes"].items()
            if scope.split(":")[0] == "C07"
        ]
        deposits = result.get("card_deposits")
        if deposits is None or not checked(result, ("C07",)):
            gaps = [{"source_refs": s.get("source_refs", [])} for s in scopes]
            return unavailable_reason({"gaps": gaps}, result), " unavailable", "", None
        days = [date.fromisoformat(d) for d in deposits["dates"]]
        dated = " dated " + ", ".join(f"{d.strftime('%b')} {d.day}" for d in days)
        noun = "card deposit" if deposits["count"] == 1 else "card deposits"
        return (
            formatted(deposits["value"], "USD"),
            "",
            f"{deposits['count']} {noun}{dated if days else ''} in QuickBooks",
            anchor(deposits["source_refs"][0]) if deposits["source_refs"] else None,
        )
    sheet = result["kpis"][key]
    link = anchor("worksheet:" + key)
    if sheet["value"] is None:
        return unavailable_reason(sheet, result), " unavailable", "", link
    kinds = {"delivered": "completed_delivery", "revenue": "net_sale"}
    if key == "AR":
        cash = [c for c in sheet["contributions"] if c["kind"] == "allocated_cash"]
        cutoff = sheet.get("opening_cutoff")
        since = ""
        if cutoff:
            day = datetime.fromisoformat(cutoff).astimezone(ZoneInfo("America/Denver"))
            since = f" since {day.strftime('%b')} {day.day}"
        return (
            formatted(-sum(Decimal(c["amount"]) for c in cash), "USD"),
            "",
            f"{len(cash)} payment allocations{since}",
            link,
        )
    count = sum(c["kind"] == kinds[key] for c in sheet["contributions"])
    noun = {"delivered": "completed deliveries"}.get(key, "sales lines, net of credits")
    return formatted(sheet["value"], sheet["unit"]), "", f"{count} {noun}", link


def chips(checks, result):
    out = []
    for index, finding in enumerate(result["prioritized_findings"]):
        if finding["check_id"] in checks:
            amount = impact_amount(finding, result)[0]
            text = SHORT[finding["check_id"]]
            text += "" if amount == "—" else " · " + amount
            out.append(f'<a class="chip" href="#x-{index}">{escaped(text)}</a>')
    if out:
        return "".join(out)
    if checked(result, checks):
        return '<span class="chip ok">All matched</span>'
    return '<span class="chip warn">Not fully checked</span>'


FIELDS = (
    ("customer_id", "Customer", "customer"),
    ("delivered_at", "Delivered", "time"),
    ("occurred_at", "Sold", "time"),
    ("settled_at", "Settled", "time"),
    ("observed_at", "Read", "time"),
    ("gallons", "Gallons", "gal"),
    ("external_invoice_id", "Invoice", "text"),
    ("net_amount", "Net amount", "usd"),
    ("gross", "Card sales", "usd"),
    ("refunds", "Refunds", "usd"),
    ("fees", "Fees", "usd"),
    ("net", "Expected deposit", "usd"),
    ("Amount", "Amount", "usd"),
    ("quality", "Reading quality", "text"),
    ("status", "Status", "text"),
    ("error_code", "Error", "text"),
    ("extracted_at", "Exported", "time"),
    ("covered_through", "Covered through", "time"),
)
SEARCHED = {
    "Invoice.Line": "invoice lines",
    "Deposit": "deposits",
    "customer/item": "customer and item mappings",
    "closing_reading": "closing tank readings",
}


def field_value(kind, value, ref, labels):
    """Business formatting for source fields; raw values stay in the evidence."""
    if value in ("", None):
        return "—"
    if kind == "customer":
        return labels.get(ref.split(":")[0] + ":customer:" + str(value), value)
    if kind == "time":
        moment = datetime.fromisoformat(value).astimezone(ZoneInfo("America/Denver"))
        clock = moment.strftime("%I:%M %p").lstrip("0")
        return f"{moment.strftime('%b')} {moment.day}, {clock} MT"
    if kind == "gal":
        return f"{Decimal(value):,.1f}"
    if kind == "usd":
        return formatted(value, "USD")
    return value


def threshold_text(finding):
    check, limit = finding["check_id"], finding["threshold"]
    fixed = {
        "C01": "any delivered gallons left unbilled after the grace period",
        "C02": "any billed gallons without a delivery",
        "C03": "more than one record with the same reference",
        "C10": "any import failure",
        "C11": "any missing required record",
    }
    if check in fixed:
        return fixed[check]
    if check == "C09":
        return f"source coverage older than {limit} hours"
    if check == "C08":
        return f"differences over {Decimal(limit):,.1f} gal"
    if check == "C05":
        if limit == "original required":
            return "credits or refunds without the original sale"
        return "credits or discounts over " + formatted(limit, "USD")
    return "differences over " + formatted(limit, "USD")


def record_cards(finding, result, raw_evidence):
    labels = result["run"].get("report_labels", {})
    out = []
    for ref in finding["source_refs"][:4]:
        data = raw_evidence.get(ref, {}).get("raw")
        fields = [
            (label, field_value(kind, data[key], ref, labels))
            for key, label, kind in FIELDS
            if isinstance(data, dict) and key in data
        ][:6]
        out.append(
            '<div class="doc"><p class="t"><span>'
            + escaped(
                system_name(ref, result)
                + " · "
                + (ref.split(":")[1] if ":" in ref else "record")
            )
            + '</span><a href="#'
            + anchor(ref)
            + '">Raw record</a></p><strong>'
            + escaped(labels.get(ref, ref.split(":")[-1]))
            + "</strong>"
            + (
                "<dl>"
                + "".join(
                    f"<dt>{escaped(k)}</dt><dd>{escaped(v)}</dd>" for k, v in fields
                )
                + "</dl>"
                if fields
                else ""
            )
            + "</div>"
        )
    missing = finding.get("missing_reference")
    names = record_names(finding, result)
    if missing:
        out.append(
            '<div class="doc miss"><p class="t"><span>'
            + escaped(
                PREFIXES.get(missing["system"], missing["system"])
                + " · "
                + missing["type"].replace(".", " ").lower()
            )
            + "</span></p><strong>No matching record</strong><br>Searched "
            + escaped(
                PREFIXES.get(missing["system"], missing["system"])
                + " "
                + SEARCHED.get(missing["type"], missing["type"].lower())
            )
            + escaped(
                " for " + names[0][0].lower() + names[0][1:] + "." if names else "."
            )
            + "</div>"
        )
    return "".join(out)


def selection_style(result):
    """Per-row CSS so selection and filters work without JavaScript."""
    rules = [
        f".split:has(#x-{i}:target) .r-{i} td{{background:#f0f9ff}}"
        f".split:has(#x-{i}:target) .r-{i} td:first-child"
        "{box-shadow:inset 3px 0 0 #0369a1}"
        for i in range(len(result["prioritized_findings"]))
    ]
    for severity in SEVERITIES:
        rules.append(
            f"#f-{severity}:target~.tbl tr.row:not(.s-{severity}){{display:none}}"
            f'.ex:has(#f-{severity}:target) .tabs a[href="#f-{severity}"]'
            "{background:#0f172a;color:#fff}"
        )
    return "".join(rules)


def shell(result):
    findings = result["prioritized_findings"]
    day = date.fromisoformat(result["run"]["business_date"])
    nav = "".join(
        f'<span class="off" aria-disabled="true">{item}<small>Pilot</small></span>'
        for item in PILOT_NAV
    )
    return (
        '<div class="app"><nav class="side" aria-label="Application">'
        '<div class="brand"><span class="logo" aria-hidden="true">SC</span>'
        "<span>Sun City Propane<small>Daily audit · synthetic</small></span></div>"
        '<a class="on" href="#top" aria-current="page">Morning report</a>'
        f'<a href="#attention">Exceptions<span class="n">{len(findings)}</span></a>'
        '<a href="#data-sources">Data sources</a>'
        '<a href="#technical">Technical details</a>'
        '<p class="sec">Pilot features</p>' + nav + '<p class="bottom">Owner view · '
        "synthetic demo</p></nav>"
        '<div class="shell"><header class="top"><span class="crumb">Reports / '
        '<b>Morning report</b></span><span class="sp"></span><span class="pill wide">'
        + escaped(f"{day.strftime('%a, %b')} {day.day}")
        + '</span><span class="pill wide">Data as of '
        + escaped(short_time(result["display_as_of"], result["display_as_of"]))
        + '</span><span class="b wide" aria-disabled="true">Export PDF</span>'
        '<span class="b p" aria-disabled="true">Send to team</span>'
        '<span class="mock">Pilot features · not active in this demo</span>'
        '</header><div class="content">'
    )


def business_sections(result, raw_evidence, changes=None):
    changes = changes or {}
    findings = result["prioritized_findings"]
    groups = source_groups(result)
    money = [impact_amount(f, result)[1] for f in findings]
    money = [amount for amount in money if amount is not None]
    decision = (
        "About <b>"
        + escaped(formatted(sum(money), "USD"))
        + f"</b> across {len(money)} flagged items needs a decision today "
        "(estimates and differences, not booked amounts). "
        if money
        else ""
    )
    day = date.fromisoformat(result["run"]["business_date"])
    out = [
        shell(result),
        '<header class="greet"><h1>Good morning</h1><p class="headline">'
        + escaped(headline(result))
        + "</p><p>"
        + decision
        + "Times in America/Denver.</p></header>"
        '<section class="card" aria-labelledby="money-flow"><div class="ch">'
        '<h2 id="money-flow">Yesterday&#x27;s money flow</h2><span class="m">'
        + escaped(f"{day.strftime('%b')} {day.day}")
        + " · delivered → billed → paid → deposited. Stages use different "
        "periods and units, so no conversion rate is implied.</span></div>"
        '<div class="flow">',
    ]
    for name, key, checks in STAGES:
        value, state, sub, link = stage_value(key, result)
        change = change_text(changes.get(key)) if key != "AR" else ""
        out.append(
            '<div class="st"><p class="k">'
            + name
            + '</p><p class="v'
            + state
            + '">'
            + escaped(value)
            + '</p><p class="s">'
            + escaped(" · ".join(part for part in (sub, change) if part))
            + (
                f' <a href="#{link}">'
                + ("See deposit" if key is None else "See calculation")
                + "</a>"
                if link
                else ""
            )
            + "</p>"
            + chips(checks, result)
            + "</div>"
        )
    out.append('</div></section><div class="kp">')
    for key in ("AR", "retail"):
        sheet = result["kpis"][key]
        value = sheet["value"]
        state = " unavailable" if value is None else ""
        text = (
            unavailable_reason(sheet, result)
            if value is None
            else formatted(value, sheet["unit"])
        )
        out.append(
            '<section class="card"><h2 class="k">'
            + ("Accounts receivable" if key == "AR" else "Retail gallons (POS)")
            + '</h2><p class="v'
            + state
            + '">'
            + escaped(text)
            + '</p><p class="s">'
            + escaped(change_text(changes.get(key)))
            + ' <a href="#'
            + anchor("worksheet:" + key)
            + '">See calculation</a></p></section>'
        )
    tanks = [
        (i, f)
        for i, f in enumerate(findings)
        if f["check_id"] == "C08" and f["delta"] is not None
    ]
    scopes = [s for k, s in result["check_scopes"].items() if k.startswith("C08:")]
    done = sum(state["status"] == "evaluated" for state in scopes)
    if tanks:
        value, state = (
            formatted(sum(abs(Decimal(f["delta"])) for _, f in tanks), "gal")
            + " unexplained",
            " alert",
        )
    elif done == len(scopes):
        value, state = "Reconciled", ""
    else:
        value, state = "Not fully checked", " unavailable"
    readings = [g for g in groups if g["label"] == "Tank readings"]
    sub = f"{done} of {len(scopes)} tanks and trucks checked" + (
        " · readings "
        + short_time(readings[0]["extracted_at"], result["display_as_of"])
        if readings
        else ""
    )
    out.append(
        '<section class="card"><h2 class="k">Bulk tank inventory</h2><p class="v'
        + state
        + '">'
        + escaped(value)
        + '</p><p class="s">'
        + escaped(sub)
        + (f' <a href="#x-{tanks[0][0]}">See tank check</a>' if tanks else "")
        + "</p></section></div>"
    )
    total = result["kpis"]["total_gallons"]
    total_text = (
        unavailable_reason(total, result)
        if total["value"] is None
        else formatted(total["value"], total["unit"])
    )
    out.append(
        '<p class="note">'
        + (
            ""
            if changes
            else "Prior business day comparison is not available for this run. "
        )
        + "Total gallons sold: "
        + escaped(total_text)
        + ". Measurement basis: "
        + escaped(
            {
                "net_60F": "US gallons at 60°F",
                "observed": "US gallons at observed temperature",
            }.get(result["gallon_basis"], result["gallon_basis"])
        )
        + ".</p>"
    )
    severities = [s for s in SEVERITIES if any(f["severity"] == s for f in findings)]
    tabs = "".join(
        f'<a href="#f-{s}">{s.capitalize()} '
        f"{sum(f['severity'] == s for f in findings)}</a>"
        for s in severities
    )
    out.append(
        '<div class="split"><section class="card ex" id="attention" '
        'aria-labelledby="attention-title"><div class="ch">'
        '<h2 id="attention-title">Needs attention today</h2>'
        '<span class="m">highest priority first</span>'
        f'<nav class="tabs" aria-label="Filter by priority"><a class="all" '
        f'href="#attention">All {len(findings)}</a>{tabs}</nav></div>'
        + "".join(f'<span class="ft" id="f-{s}"></span>' for s in severities)
        + '<div class="tbl">'
    )
    if not findings:
        out.append(
            '<p class="s" style="padding:16px">No business exceptions found. '
            "Review data sources for coverage.</p>"
        )
    else:
        out.append(
            "<table><thead><tr><th>Priority</th><th>Issue</th>"
            '<th class="src">Source</th><th class="num">Impact</th>'
            '<th class="stt">Status</th></tr></thead><tbody>'
        )
        for index, finding in enumerate(findings):
            names = record_names(finding, result)
            title = "; ".join(names) if names else TITLES[finding["check_id"]]
            detail = (TITLES if names else SHORT)[finding["check_id"]]
            severity = escaped(finding["severity"])
            out.append(
                f'<tr class="row r-{index} s-{severity}"><td><span class="pr '
                f'{severity}">{severity.capitalize()}</span></td><td class="it">'
                f'<a href="#x-{index}">{escaped(title)}</a><small>'
                f"{escaped(detail)}</small></td>"
                f'<td class="src">{escaped(finding_systems(finding, result))}</td>'
                f'<td class="amt">{escaped(impact_amount(finding, result)[0])}</td>'
                '<td class="stt">Open</td></tr>'
            )
        out.append("</tbody></table>")
    out.append('</div></section><div class="drawers">')
    for index, finding in enumerate(findings):
        check = finding["check_id"]
        severity = escaped(finding["severity"])
        refs = (
            finding["source_refs"]
            + finding["related_refs"]
            + result.get("exposure_estimates", {})
            .get(finding["finding_id"], {})
            .get("source_refs", [])
        )
        out.append(
            f'<aside class="card drawer" id="x-{index}" aria-labelledby="xt-{index}">'
            f'<div class="ch"><h3 id="xt-{index}">'
            + escaped(business_title(finding, result))
            + f'</h3></div><div class="body"><p><span class="pr {severity}">'
            + severity.capitalize()
            + '</span> <small class="m">Flags '
            + escaped(threshold_text(finding))
            + '</small> <span class="tag">'
            + escaped(check)
            + "</span></p><div><h4>What we found</h4><p>"
            + escaped(business_impact(finding, result))
            + '</p></div><div class="docs">'
            + record_cards(finding, result, raw_evidence)
            + "</div><div><h4>Next step</h4><p>"
            + escaped(ACTIONS[check])
            + '</p></div><details class="disclosure"><summary>See source records'
            "</summary><p>" + links(refs) + '</p></details></div><div class="acts">'
            '<span class="b" aria-disabled="true">Mark as resolved</span>'
            '<span class="b" aria-disabled="true">Assign</span>'
            '<span class="mock">Pilot feature · not saved</span></div></aside>'
        )
    out.append(
        '</div></div><section class="card" id="data-sources" '
        'aria-labelledby="sources-title"><div class="ch"><h2 id="sources-title">'
        'Data sources</h2><span class="m">last import, America/Denver</span></div>'
        '<div class="pills">'
    )
    times = []
    for group in groups:
        status = group["status"]
        when = short_time(group.get("extracted_at"), result["display_as_of"])
        text = {"success": when, "stale": "out of date · " + when}.get(
            status, "import failed"
        )
        out.append(
            f'<span class="pill"><span class="dot {escaped(status)}"></span>'
            f"{escaped(group['label'])} · {escaped(text)}</span>"
        )
        times.append(
            f"<li>{escaped(group['label'])}: last updated "
            f"{escaped(denver_time(group.get('extracted_at')))}; covered through "
            f"{escaped(denver_time(group.get('covered_through'), 'not available'))}"
            "</li>"
        )
    out.append(
        '<details class="coverage"><summary>Coverage times</summary>'
        '<ul class="times">' + "".join(times) + "</ul></details>"
    )
    return "\n".join(out)


def render(result, raw_evidence, *, narrative_status=None, changes=None):
    """Business-first view over computed results and full technical evidence."""
    changes = changes or {}
    document = technical_report(result, raw_evidence, narrative_status=narrative_status)
    document = document.replace(
        "</style>", BUSINESS_STYLE + selection_style(result) + "</style>", 1
    )
    document = document.replace(
        '<main id="top">',
        '<main id="top">'
        + business_sections(result, raw_evidence, changes)
        + '<details class="technical" id="technical">'
        '<summary>Technical details</summary><div class="tech">',
        1,
    )
    estimates = (
        "<section><h2>Exposure estimates — not KPI totals</h2><pre>"
        + escaped(
            json.dumps(result.get("exposure_estimates", {}), indent=2, sort_keys=True)
        )
        + "</pre></section><section><h2>Prior business day comparison</h2><p>"
        "Baseline: the synthetic clean scenario on the prior business day, "
        "computed by the same pipeline.</p><pre>"
        + escaped(json.dumps(changes, indent=2, sort_keys=True))
        + "</pre></section>"
    )
    return document.replace(
        "</main>",
        estimates + "</div></details></div></section></div></div></div></main>",
        1,
    )
