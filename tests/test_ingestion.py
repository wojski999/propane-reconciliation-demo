"""Source-boundary and transaction evidence; no rule engines or oracle inputs."""

import copy
import csv
import io
import json
import sqlite3
from datetime import date

import pytest

from propane_demo.contracts import CSV_FIELDS, SCENARIOS
from propane_demo.generator import generate
from propane_demo.ingestion import (
    import_file,
    ingest,
    unavailable,
)
from propane_demo.validation import Invalid, day, identifier, instant, integer, scaled


def change(files, name, mutate, count=False):
    if name in CSV_FIELDS:
        value = list(csv.DictReader(io.StringIO(files[name].decode())))
    else:
        value = json.loads(files[name])
    mutate(value)
    if name in CSV_FIELDS:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            stream, fieldnames=CSV_FIELDS[name], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(value)
        files[name] = stream.getvalue().encode()
    else:
        files[name] = json.dumps(value).encode()
    if count:
        n = (
            sum(map(len, value.values()))
            if name == "qbo.json"
            else len(value["records"])
            if name == "updates.json"
            else len(value)
        )
        change(
            files,
            "manifests.json",
            lambda ms: next(m for m in ms if m["file_id"] == name).update(
                row_count=str(n)
            ),
        )
    return files


def failed(files, name, code=None):
    db = ingest(files.__getitem__)
    m = db.execute("SELECT * FROM manifests WHERE file_id=?", (name,)).fetchone()
    assert m["status"] == "failed"
    if code:
        assert m["error_code"] == code
    assert db.execute("SELECT status FROM run").fetchone()[0] == "incomplete"
    assert (
        db.execute(
            "SELECT count(*) FROM records WHERE source=?", (m["source"],)
        ).fetchone()[0]
        == 0
    )
    return db, m


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_all_scenarios_import_without_business_verdicts(scenario):
    files = generate(scenario)
    with ingest(files.__getitem__) as db:
        assert db.execute("SELECT status FROM run").fetchone()[0] == (
            "incomplete" if scenario in {"P11", "issues"} else "complete"
        )
        assert db.execute("SELECT count(*) FROM files").fetchone()[0] == 14
        assert db.execute("SELECT count(*) FROM alerts").fetchone()[0] == (
            1 if scenario in {"P11", "issues"} else 0
        )
        for row in db.execute("SELECT file_id,raw FROM files"):
            assert row["raw"] == files[row["file_id"]]
        for row in db.execute("SELECT payload FROM records"):
            assert not any(isinstance(x, float) for x in json.loads(row[0]).values())
        assert db.execute("SELECT count(*) FROM records WHERE source='qbo'").fetchone()[
            0
        ]


def test_scaled_storage_versions_repeats_and_provenance():
    files = generate("raw-repeat")
    db = ingest(files.__getitem__)
    row = db.execute(
        "SELECT * FROM records WHERE record_key='qbo:Customer:C-1'"
    ).fetchone()
    assert row["version"] == 1
    assert json.loads(row["payload"])["DisplayName"] == "Synthetic updated customer"
    assert (
        db.execute(
            "SELECT count(*) FROM versions WHERE record_key='qbo:Customer:C-1'"
        ).fetchone()[0]
        == 2
    )
    assert (
        db.execute(
            "SELECT count(*) FROM occurrences WHERE record_key='qbo:Customer:C-1'"
        ).fetchone()[0]
        == 3
    )
    occurrences = db.execute(
        "SELECT ref FROM occurrences "
        "WHERE record_key='qbo:Invoice:I-PRICE' ORDER BY ref"
    ).fetchall()
    assert len(occurrences) == 2
    assert occurrences[0][0] == "file:qbo.json#/Invoice/0"
    payload = json.loads(
        db.execute(
            "SELECT payload FROM records WHERE record_key='cargas:delivery:D-FRACTION'"
        ).fetchone()[0]
    )
    assert payload["gallons"] == 5 and payload["net_amount"] == 1
    # Actual replay of the same physical file adds no occurrence/version/current row.
    before = {
        t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in ["records", "versions", "occurrences"]
    }
    manifest = next(
        m for m in json.loads(files["manifests.json"]) if m["file_id"] == "qbo.json"
    )
    import_file(db, "qbo.json", files["qbo.json"], manifest)
    assert before == {
        t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in before
    }
    for table, column in [("files", "raw"), ("occurrences", "raw")]:
        for sql in [f"UPDATE {table} SET {column}='tampered'", f"DELETE FROM {table}"]:
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                db.execute(sql)


def test_p11_exact_failure_and_source_dependency_contract():
    files = generate("P11")
    db, m = failed(files, "pos.csv", "CSV_SCHEMA")
    assert m["manifest_id"] == "POS-FAILED" and m["pointer"] == ":row:2"
    alerts = [dict(r) for r in db.execute("SELECT * FROM alerts")]
    assert len(alerts) == 1
    a = alerts[0]
    assert a["alert_id"] == "C10|manifest:POS-FAILED"
    assert (
        a["source"],
        a["check_id"],
        a["severity"],
        a["reason_code"],
        a["status"],
    ) == ("pos", "C10", "critical", "CSV_SCHEMA", "open")
    assert json.loads(a["source_refs"]) == ["manifest:POS-FAILED"]
    assert json.loads(a["related_refs"]) == ["file:pos.csv:row:2"]
    assert (
        db.execute("SELECT raw FROM files WHERE file_id='pos.csv'").fetchone()[0]
        == files["pos.csv"]
    )
    scopes = unavailable(db)
    assert set(scopes) == {
        "C03:pos",
        "C04:pos",
        "C05:pos",
        "C07",
        "C08:BULK-A",
        "C08:ISOLATED",
        "KPI:retail",
        "KPI:revenue",
    }
    assert all(v["source_refs"] == ["manifest:POS-FAILED"] for v in scopes.values())
    assert scopes["C04:pos"]["status"] == "not_evaluated"
    assert scopes["KPI:retail"]["status"] == "unavailable"
    assert "C12" not in scopes


def test_fresh_run_no_cached_success_and_real_failure_refs():
    clean = ingest(generate().__getitem__)
    assert unavailable(clean) == {}
    files = generate()
    del files["qbo.json"]
    db, _ = failed(files, "qbo.json", "MISSING")
    assert db is not clean
    assert (
        clean.execute("SELECT count(*) FROM records WHERE source='qbo'").fetchone()[0]
        > 0
    )
    assert "C12" in unavailable(db)
    assert set(unavailable(db)["C12"]["source_refs"]) == {
        "manifest:QBO-OK",
        "manifest:UPDATES-OK",
    }
    assert db.execute("SELECT count(*) FROM alerts").fetchone()[0] == 1


def test_update_failure_rolls_back_base_and_preserves_other_sources():
    files = generate()
    change(files, "updates.json", lambda v: v["records"][1].update(SyncToken="0"))
    db, m = failed(files, "updates.json", "VERSION_CONFLICT")
    assert m["pointer"] == "#/records/1"
    assert (
        db.execute(
            "SELECT count(*) FROM versions WHERE record_key LIKE 'qbo:%'"
        ).fetchone()[0]
        == 0
    )
    assert (
        db.execute(
            "SELECT count(*) FROM occurrences WHERE file_id='qbo.json'"
        ).fetchone()[0]
        == 0
    )
    assert (
        db.execute("SELECT count(*) FROM records WHERE source='cargas'").fetchone()[0]
        > 0
    )
    assert db.execute("SELECT count(*) FROM alerts").fetchone()[0] == 1


def test_transaction_update_removes_old_current_lines_and_older_replay_cannot_restore():
    files = generate()
    q = json.loads(files["qbo.json"])
    row = copy.deepcopy(q["JournalEntry"][0])
    row["SyncToken"] = "2"
    row["Line"] = row["Line"][:1]
    change(
        files,
        "updates.json",
        lambda v: v.update(entity="JournalEntry", records=[row]),
        count=True,
    )
    db = ingest(files.__getitem__)
    assert (
        db.execute(
            "SELECT version FROM records "
            "WHERE record_key='qbo:JournalEntry:JE-UNBALANCED:1'"
        ).fetchone()[0]
        == 2
    )
    assert (
        db.execute(
            "SELECT count(*) FROM records "
            "WHERE record_key='qbo:JournalEntry:JE-UNBALANCED:2'"
        ).fetchone()[0]
        == 0
    )
    assert (
        db.execute(
            "SELECT count(*) FROM versions "
            "WHERE record_key='qbo:JournalEntry:JE-UNBALANCED:2'"
        ).fetchone()[0]
        == 1
    )
    manifest = next(
        m for m in json.loads(files["manifests.json"]) if m["file_id"] == "qbo.json"
    )
    import_file(db, "qbo.json", files["qbo.json"], manifest)
    # Older replay must not reintroduce deleted lines.
    assert (
        db.execute(
            "SELECT count(*) FROM records "
            "WHERE record_key='qbo:JournalEntry:JE-UNBALANCED:2'"
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize(
    "name",
    [
        "qbo.json",
        "updates.json",
        "identity.json",
        "opening_ar.json",
        "empty.json",
        *CSV_FIELDS,
    ],
)
def test_missing_and_unreadable_sources_are_never_valid_empty(name):
    files = generate()
    del files[name]
    failed(files, name, "MISSING")

    def reader(key):
        if key == name:
            raise PermissionError("sensitive detail must not leak")
        return files[key]

    db = ingest(reader)
    m = db.execute("SELECT * FROM manifests WHERE file_id=?", (name,)).fetchone()
    assert m["error_code"] == "UNREADABLE"
    assert "sensitive" not in str(
        [tuple(r) for r in db.execute("SELECT * FROM manifests")]
    )


@pytest.mark.parametrize(
    "name,raw,code",
    [
        ("empty.json", b"[1]", "SCHEMA"),
        ("qbo.json", b"{", "JSON_SCHEMA"),
        ("pos.csv", b"\xff", "CSV_SCHEMA"),
        ("pos.csv", b'"unterminated', "CSV_SCHEMA"),
        ("qbo.json", b'{"Invoice":[],"Invoice":[]}', "JSON_SCHEMA"),
        ("qbo.json", b"[]", "SCHEMA"),
        ("qbo.json", b"\xff", "JSON_SCHEMA"),
        ("pos.csv", "not bytes", "UNREADABLE"),
    ],
)
def test_malformed_inputs(name, raw, code):
    files = generate()
    files[name] = raw
    failed(files, name, code)


@pytest.mark.parametrize(
    "entity,mutate",
    [
        ("Invoice", lambda r: r.pop("Balance")),
        ("Payment", lambda r: r.pop("UnappliedAmt")),
        ("Customer", lambda r: r.pop("CustomerClass")),
        ("Item", lambda r: r.update(Classification="unknown")),
        ("Invoice", lambda r: r.update(CustomerRef={})),
        ("Invoice", lambda r: r.update(Line=[])),
        ("Invoice", lambda r: r["Line"].append(copy.deepcopy(r["Line"][0]))),
        (
            "Invoice",
            lambda r: r["Line"][0]["SalesItemLineDetail"].update(
                ItemRef={"value": "bad:id"}
            ),
        ),
        ("Payment", lambda r: r["Line"][0]["LinkedTxn"][0].update(TxnType="unknown")),
        (
            "JournalEntry",
            lambda r: r["Line"][0]["JournalEntryLineDetail"].update(
                PostingType="Other"
            ),
        ),
        (
            "Deposit",
            lambda r: r["Line"][0]["DepositLineDetail"].update(TxnType="unknown"),
        ),
        ("Invoice", lambda r: r.update(TotalAmt=1.0)),
        ("Invoice", lambda r: r.update(TotalAmt="NaN")),
        ("Invoice", lambda r: r.update(TotalAmt="0.001")),
        ("Invoice", lambda r: r.update(status="unknown")),
        ("Invoice", lambda r: r.update(EventAt="2026-11-03T12:00:00")),
        ("Invoice", lambda r: r.update(TxnDate="invalid")),
        ("Invoice", lambda r: r.update(LinkedTxn={})),
        ("Customer", lambda r: r.update(SyncToken="-1")),
    ],
)
def test_entity_specific_validation_rolls_back_qbo(entity, mutate):
    files = generate()
    change(files, "qbo.json", lambda q: mutate(q[entity][0]))
    failed(files, "qbo.json")


@pytest.mark.parametrize(
    "name,field,value,code",
    [
        ("deliveries.csv", "status", "pending", "ENUM"),
        ("deliveries.csv", "gallons", "-0.001", "NEGATIVE"),
        ("deliveries.csv", "gallons", "0.0001", "PRECISION"),
        ("deliveries.csv", "gallon_basis", "guessed", "ENUM"),
        ("pos.csv", "unit", "kg", "ENUM"),
        ("pos.csv", "tender", "crypto", "ENUM"),
        ("pos.csv", "customer_id", "", "SCHEMA"),
        ("readings.csv", "gallons", "2000.001", "CAPACITY"),
        ("readings.csv", "uncertainty_gallons", "-0.001", "NEGATIVE"),
        ("readings.csv", "quality", "unknown", "ENUM"),
        ("movements.csv", "quantity", "0.000", "NEGATIVE"),
        ("movements.csv", "movement_type", "unknown", "ENUM"),
        ("prices.csv", "approved_discount_pct", "100.001", "PERCENT"),
        ("prices.csv", "effective_to", "2019-01-01", "INTERVAL"),
        ("deliveries.csv", "delivered_at", "2026-11-05T00:00:00+00:00", "WINDOW"),
    ],
)
def test_csv_entity_validation(name, field, value, code):
    files = generate()
    change(files, name, lambda rs: rs[0].update({field: value}))
    failed(files, name, code)


@pytest.mark.parametrize(
    "name", ["deliveries.csv", "identity.json", "opening_ar.json", "prices.csv"]
)
def test_duplicate_keys_are_rejected(name):
    files = generate()

    def mutation(v):
        if name == "identity.json":
            v["assets"].append(copy.deepcopy(v["assets"][0]))
        elif name == "opening_ar.json":
            v["balances"].append(copy.deepcopy(v["balances"][0]))
        else:
            row = copy.deepcopy(v[0])
            row["unit_price"] = "99.00"
            v.append(row)

    change(files, name, mutation, count=True)
    failed(files, name, "DUPLICATE_KEY")


def test_price_overlap_and_adjacent_intervals():
    files = generate()

    def mutation(rs):
        row = copy.deepcopy(rs[0])
        row["price_id"] = "NEW"
        rs.append(row)

    change(files, "prices.csv", mutation, count=True)
    failed(files, "prices.csv", "PRICE_OVERLAP")
    change(
        files,
        "prices.csv",
        lambda rs: rs[-1].update(
            effective_from="2035-01-01", effective_to="2036-01-01"
        ),
    )
    db = ingest(files.__getitem__)
    assert db.execute("SELECT status FROM run").fetchone()[0] == "complete"


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("row_count", "999", "ROW_COUNT"),
        ("row_count", "-1", "SCHEMA"),
        ("status", "unknown", "MANIFEST_STATUS"),
        ("run_id", "other", "SCHEMA"),
        ("source", "other", "SCHEMA"),
        ("extracted_at", "2026-11-04T07:05:01+00:00", "WINDOW"),
        ("covered_through", "2030-01-01T00:00:00+00:00", "WINDOW"),
        ("expected_window_start", "2026-11-04T00:00:00+00:00", "WINDOW"),
        ("error_code", "raw secret", "ERROR_CODE"),
    ],
)
def test_manifest_metadata_validation(field, value, code):
    files = generate()
    change(files, "manifests.json", lambda ms: ms[3].update({field: value}))
    failed(files, "pos.csv", code)


def test_failed_extraction_authoritative_and_valid_empty_different():
    files = generate()
    change(
        files,
        "manifests.json",
        lambda ms: ms[3].update(status="failed", error_code="EXTRACTION_FAILED"),
    )
    failed(files, "pos.csv", "EXTRACTION_FAILED")
    change(files, "manifests.json", lambda ms: ms[3].update(error_code="secret trace"))
    failed(files, "pos.csv", "ERROR_CODE")
    files = generate()
    change(files, "pos.csv", lambda rs: rs.clear(), count=True)
    db = ingest(files.__getitem__)
    assert db.execute("SELECT status FROM run").fetchone()[0] == "complete"
    assert (
        db.execute("SELECT count(*) FROM records WHERE source='pos'").fetchone()[0] == 0
    )


@pytest.mark.parametrize(
    "mode", ["missing", "malformed", "duplicate", "unknown", "wrongtype"]
)
def test_manifest_index_failure_survives_as_safe_failure(mode):
    files = generate()
    if mode == "missing":
        del files["manifests.json"]
    elif mode == "malformed":
        files["manifests.json"] = b"{"
    elif mode == "duplicate":
        change(files, "manifests.json", lambda ms: ms.append(copy.deepcopy(ms[0])))
    elif mode == "unknown":
        change(files, "manifests.json", lambda ms: ms[0].update(file_id="unknown"))
    else:
        files["manifests.json"] = b"{}"
    db, _ = failed(files, "pos.csv", "SCHEMA")
    assert db.execute("SELECT count(*) FROM alerts").fetchone()[0] == 10
    assert "C12" in unavailable(db)


def test_missing_support_is_preserved_for_c11_not_fabricated():
    files = generate("P12")
    db = ingest(files.__getitem__)
    assert db.execute("SELECT status FROM run").fetchone()[0] == "complete"
    change(
        files,
        "qbo.json",
        lambda q: q["Invoice"][0]["CustomerRef"].update(value="ABSENT"),
    )
    db = ingest(files.__getitem__)
    assert db.execute("SELECT status FROM run").fetchone()[0] == "complete"
    assert (
        db.execute(
            "SELECT target_key FROM references_needed "
            "WHERE target_key='qbo:Customer:ABSENT'"
        ).fetchone()[0]
        == "qbo:Customer:ABSENT"
    )


@pytest.mark.parametrize(
    "function,value",
    [
        (instant, "bad"),
        (day, "bad"),
        (identifier, "bad:key"),
        (integer, "01"),
        (integer, "9" * 100),
    ],
)
def test_safe_scalar_errors(function, value):
    with pytest.raises(Invalid):
        function(value)


@pytest.mark.parametrize(
    "value,places,expected",
    [
        ("0", 2, 0),
        ("-0.01", 2, -1),
        ("-92233720368547758.08", 2, -(2**63)),
        ("92233720368547758.07", 2, 2**63 - 1),
        ("0.001", 3, 1),
    ],
)
def test_scaled_exact_boundaries(value, places, expected):
    assert scaled(value, places) == expected


@pytest.mark.parametrize(
    "value,code",
    [
        ("1e2", "DECIMAL"),
        ("Infinity", "DECIMAL"),
        ("9" * 25, "DECIMAL_RANGE"),
        ("92233720368547758.08", "DECIMAL_RANGE"),
        ("0.001", "PRECISION"),
    ],
)
def test_scaled_rejects_inexact_nonfinite_overflow(value, code):
    with pytest.raises(Invalid, match=code):
        scaled(value, 2)


@pytest.mark.parametrize(
    "name,value",
    [("run.json", {}), ("run.json", []), ("policies.json", {}), ("policies.json", [])],
)
def test_invalid_control_is_fatal_safe(name, value):
    files = generate()
    files[name] = json.dumps(value).encode()
    with pytest.raises(Invalid):
        ingest(files.__getitem__)


@pytest.mark.parametrize("day_value", [date(2026, 3, 8), date(2026, 11, 1)])
def test_import_dst_days(day_value):
    db = ingest(generate(business_date=day_value).__getitem__)
    assert db.execute("SELECT status FROM run").fetchone()[0] == "complete"


def test_namespace_collisions_cannot_merge_independent_entities():
    files = generate()
    change(files, "qbo.json", lambda q: q["Invoice"][0].update(Id="1"))
    change(files, "deliveries.csv", lambda rs: rs[0].update(ticket_id="1"))
    change(files, "pos.csv", lambda rs: rs[0].update(transaction_id="1"))
    db = ingest(files.__getitem__)
    keys = {row[0] for row in db.execute("SELECT record_key FROM records")}
    assert {
        "qbo:Invoice:1",
        "qbo:Invoice:1:1",
        "cargas:delivery:1",
        "pos:POS:1:1",
    } <= keys
    change(files, "pos.csv", lambda rs: rs[0].update(transaction_id="1:1"))
    failed(files, "pos.csv", "IDENTIFIER")


@pytest.mark.parametrize(
    "name,mutate",
    [
        ("identity.json", lambda v: v["pos_events"][0].update(qbo_entity="invalid")),
        (
            "identity.json",
            lambda v: v["pos_events"][0].update(inventory_counted="true"),
        ),
        ("identity.json", lambda v: v["sku_fill_gallons"].update(CYLINDER="0.000")),
        ("identity.json", lambda v: v["allocations"][0].update(net_amount="1.001")),
        ("identity.json", lambda v: v.update(assets={})),
        ("opening_ar.json", lambda v: v["balances"][0].update(amount=0.0)),
        ("opening_ar.json", lambda v: v.update(as_of="bad")),
        ("updates.json", lambda v: v.update(records={})),
        ("updates.json", lambda v: v.update(source="other")),
        ("qbo.json", lambda v: v.update(Customer={})),
    ],
)
def test_support_and_wrapper_schema_boundaries(name, mutate):
    files = generate()
    change(files, name, mutate)
    failed(files, name)


def test_late_failure_rolls_back_normalized_rows_already_inserted():
    files = generate()
    # Chronology is checked while writing, after earlier source records were inserted.
    change(
        files,
        "deliveries.csv",
        lambda rs: rs[-1].update(delivered_at="2030-01-01T00:00:00+00:00"),
    )
    db, m = failed(files, "deliveries.csv", "WINDOW")
    assert m["pointer"] == ":row:12"
    assert (
        db.execute(
            "SELECT count(*) FROM occurrences WHERE file_id='deliveries.csv'"
        ).fetchone()[0]
        == 0
    )
    assert (
        db.execute(
            "SELECT count(*) FROM versions WHERE record_key LIKE 'cargas:delivery:%'"
        ).fetchone()[0]
        == 0
    )
    assert (
        db.execute("SELECT count(*) FROM records WHERE source='qbo'").fetchone()[0] > 0
    )


def test_manifest_future_tolerance_exact_boundary():
    files = generate()
    change(
        files,
        "manifests.json",
        lambda ms: ms[3].update(extracted_at="2026-11-04T07:05:00+00:00"),
    )
    db = ingest(files.__getitem__)
    assert db.execute("SELECT status FROM run").fetchone()[0] == "complete"


def test_multiple_errors_in_qbo_group_emit_only_one_alert():
    files = generate()
    del files["qbo.json"]
    del files["updates.json"]
    db = ingest(files.__getitem__)
    assert (
        db.execute("SELECT count(*) FROM alerts WHERE source='qbo'").fetchone()[0] == 1
    )
    assert (
        db.execute(
            "SELECT count(*) FROM manifests WHERE source='qbo' AND status='failed'"
        ).fetchone()[0]
        == 2
    )


def test_every_normalized_record_has_resolving_raw_provenance():
    files = generate()
    db = ingest(files.__getitem__)
    for occurrence in db.execute("SELECT * FROM occurrences"):
        name, pointer = occurrence["file_id"], occurrence["pointer"]
        if name in CSV_FIELDS:
            value = list(csv.DictReader(io.StringIO(files[name].decode())))[
                int(pointer.split(":")[-1]) - 2
            ]
        else:
            value = json.loads(files[name])
            for part in pointer[1:].strip("/").split("/") if pointer != "#" else []:
                value = value[int(part)] if isinstance(value, list) else value[part]
        assert json.loads(occurrence["raw"]) == value
    for row in db.execute("SELECT occurrence_ref FROM records"):
        assert db.execute("SELECT 1 FROM occurrences WHERE ref=?", (row[0],)).fetchone()


def test_unknown_sku_fill_is_preserved_without_invented_gallons():
    files = generate()
    change(files, "identity.json", lambda v: v["sku_fill_gallons"].clear())
    db = ingest(files.__getitem__)
    assert db.execute("SELECT status FROM run").fetchone()[0] == "complete"
    assert not db.execute(
        "SELECT 1 FROM records WHERE record_key='identity:fill:CYLINDER'"
    ).fetchone()
    row = db.execute(
        "SELECT payload FROM records WHERE record_key='pos:POS:T-CYLINDER:1'"
    ).fetchone()
    assert json.loads(row[0])["quantity"] == 1000
    assert "gallons" not in json.loads(row[0])


@pytest.mark.parametrize(
    "entity,mutate",
    [
        ("CreditMemo", lambda r: r.pop("AppliedAmount")),
        ("RefundReceipt", lambda r: r.update(RevenueEvent="bad:id")),
        ("Invoice", lambda r: r.update(TxnTaxDetail={})),
        ("Invoice", lambda r: r.update(TxnDate="2026-11-04")),
        ("Invoice", lambda r: r.update(TxnDate="2026-10-01")),
    ],
)
def test_adjustment_tax_and_posting_boundaries(entity, mutate):
    files = generate()
    change(files, "qbo.json", lambda q: mutate(q[entity][0]))
    failed(files, "qbo.json")


def test_malformed_identity_reference_rejected():
    files = generate()
    change(files, "identity.json", lambda v: v["customers"][0].update(qbo="bad:id"))
    failed(files, "identity.json", "IDENTIFIER")


def test_sqlite_financial_values_are_typed_scaled_integers():
    db = ingest(generate().__getitem__)
    row = db.execute(
        "SELECT value,scale,typeof(value) FROM scaled_values "
        "WHERE record_key='cargas:delivery:D-FRACTION' "
        "AND pointer='/gallons'"
    ).fetchone()
    assert tuple(row) == (5, 3, "integer")
    row = db.execute(
        "SELECT value,scale FROM scaled_values "
        "WHERE record_key='qbo:Invoice:I-PRICE' "
        "AND pointer='/Line/0/Amount'"
    ).fetchone()
    assert tuple(row) == (20000, 2)
    assert (
        db.execute(
            "SELECT count(*) FROM scaled_values WHERE typeof(value) != 'integer'"
        ).fetchone()[0]
        == 0
    )
    files = generate()
    change(files, "updates.json", lambda v: v["records"][1].update(SyncToken="0"))
    failed_db, _ = failed(files, "updates.json", "VERSION_CONFLICT")
    assert (
        failed_db.execute(
            "SELECT count(*) FROM scaled_values WHERE record_key LIKE 'qbo:%'"
        ).fetchone()[0]
        == 0
    )


def test_failure_only_oracle_exact_scopes():
    from pathlib import Path

    oracle = json.loads(Path("tests/fixtures/expected_findings.json").read_text())
    assert set(unavailable(ingest(generate("P11").__getitem__))) == set(
        oracle["scenarios"]["P11"]["not_evaluated"]
    )


@pytest.mark.parametrize("entity", ["Customer", "Item"])
def test_nontransaction_line_shape_isolated(entity):
    files = generate()
    change(files, "qbo.json", lambda q: q[entity][0].update(Line=["x"]))
    assert_source_isolated(files, "qbo.json", "SCHEMA")


def assert_source_isolated(files, name, code):
    db, m = failed(files, name, code)
    assert db.execute("SELECT count(*) FROM alerts").fetchone()[0] == 1
    healthy = "qbo" if m["source"] != "qbo" else "pos"
    assert (
        db.execute(
            "SELECT count(*) FROM records WHERE source=?", (healthy,)
        ).fetchone()[0]
        > 0
    )
    for table in ["versions", "occurrences", "scaled_values", "references_needed"]:
        assert (
            db.execute(
                f"SELECT count(*) FROM {table} WHERE record_key LIKE ?",
                ("pos:POS:%" if m["source"] == "pos" else m["source"] + ":%",),
            ).fetchone()[0]
            == 0
        )
    return db, m


@pytest.mark.parametrize(
    "name", ["qbo.json", "identity.json", "opening_ar.json", "updates.json"]
)
def test_deep_json_source_isolation(name):
    files = generate()
    files[name] = b"[" * 20000 + b"0" + b"]" * 20000
    assert_source_isolated(files, name, "JSON_SCHEMA")


def test_deep_manifest_fails_closed_with_raw_evidence():
    files = generate()
    files["manifests.json"] = b"[" * 20000 + b"0" + b"]" * 20000
    db = ingest(files.__getitem__)
    assert db.execute("SELECT count(*) FROM alerts").fetchone()[0] == 10
    assert db.execute("SELECT count(*) FROM records").fetchone()[0] == 0
    assert (
        db.execute("SELECT raw FROM files WHERE file_id='manifests.json'").fetchone()[0]
        == files["manifests.json"]
    )


@pytest.mark.parametrize(
    "collection",
    [
        "customers",
        "items",
        "assets",
        "allocations",
        "pos_events",
        "approvals",
        "posting_map",
    ],
)
@pytest.mark.parametrize("extra", [{"extra": "x"}, {"Line": ["x"]}])
def test_identity_exact_row_keys(collection, extra):
    files = generate()
    change(files, "identity.json", lambda v: v[collection][0].update(extra))
    assert_source_isolated(files, "identity.json", "SCHEMA")


@pytest.mark.parametrize("location", ["root", "row", "balances_type", "row_type"])
def test_opening_ar_exact_shapes(location):
    files = generate()

    def mutate(v):
        if location == "root":
            v["junk"] = "x"
        elif location == "row":
            v["balances"][0]["junk"] = "x"
        elif location == "balances_type":
            v["balances"] = "x"
        else:
            v["balances"][0] = "x"

    change(files, "opening_ar.json", mutate, count=True)
    assert_source_isolated(files, "opening_ar.json", "SCHEMA")


def test_identity_normalization_error_keeps_pointer():
    files = generate()
    change(
        files, "identity.json", lambda v: v["allocations"][0].update(net_amount="1.001")
    )
    db, m = assert_source_isolated(files, "identity.json", "PRECISION")
    assert m["pointer"] == "#/allocations/0"
    assert json.loads(db.execute("SELECT related_refs FROM alerts").fetchone()[0]) == [
        "file:identity.json#/allocations/0"
    ]


@pytest.mark.parametrize("name", list(CSV_FIELDS))
def test_exact_csv_repeat_is_immutable_duplicate_evidence(name):
    files = generate()
    baseline = ingest(files.__getitem__)
    first = files[name].splitlines(keepends=True)[1]
    files[name] += first
    change(
        files,
        "manifests.json",
        lambda ms: next(m for m in ms if m["file_id"] == name).update(
            row_count=str(
                int(next(m for m in ms if m["file_id"] == name)["row_count"]) + 1
            )
        ),
    )
    db = ingest(files.__getitem__)
    assert db.execute("SELECT status FROM run").fetchone()[0] == "complete"
    assert db.execute("SELECT count(*) FROM alerts").fetchone()[0] == 0
    for table in ["records", "versions", "scaled_values"]:
        assert (
            db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            == baseline.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        )
    evidence = db.execute(
        "SELECT record_key,version,count(*) FROM occurrences WHERE file_id=? "
        "GROUP BY record_key,version HAVING count(*)>1",
        (name,),
    ).fetchall()
    assert len(evidence) == 1 and evidence[0][2] == 2
    raws = db.execute(
        "SELECT raw FROM occurrences WHERE record_key=?", (evidence[0][0],)
    ).fetchall()
    assert raws[0][0] == raws[1][0]
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.execute("DELETE FROM occurrences WHERE record_key=?", (evidence[0][0],))


def test_csv_physical_end_line_from_original_bytes():
    files = generate()
    # A quoted optional field spans two physical lines; a blank line separates records.
    lines = files["deliveries.csv"].splitlines(keepends=True)
    fields = lines[1].decode().rstrip("\n").split(",")
    index = CSV_FIELDS["deliveries.csv"].index("meter_ticket_id")
    fields[index] = '"\n"'
    files["deliveries.csv"] = (
        lines[0] + ",".join(fields).encode() + b"\n\n" + b"".join(lines[2:])
    )
    # The multiline optional identifier is invalid: error belongs to its END line (3).
    db, m = failed(files, "deliveries.csv")
    assert m["pointer"] == ":row:3"
    assert files["deliveries.csv"].splitlines()[2].startswith(b'"')
    # A valid quoted field with an embedded newline is not available in this strict
    # identifier schema; blank-line provenance still resolves directly to raw bytes.
    files = generate()
    lines = files["deliveries.csv"].splitlines(keepends=True)
    files["deliveries.csv"] = lines[0] + lines[1] + b"\n" + b"".join(lines[2:])
    db = ingest(files.__getitem__)
    for o in db.execute(
        "SELECT pointer,raw FROM occurrences WHERE file_id='deliveries.csv'"
    ):
        physical = files["deliveries.csv"].splitlines()[
            int(o["pointer"].split(":")[-1]) - 1
        ]
        assert physical.split(b",")[0].decode() == json.loads(o["raw"])["ticket_id"]


def test_missing_manifest_namespace_does_not_collide():
    files = generate()

    def mutate(ms):
        ms[:] = [m for m in ms if m["file_id"] != "pos.csv"]
        next(m for m in ms if m["file_id"] == "prices.csv")["manifest_id"] = (
            "MISSING-pos.csv"
        )

    change(files, "manifests.json", mutate)
    db, m = assert_source_isolated(files, "pos.csv", "SCHEMA")
    assert m["manifest_id"] == "missing:pos.csv"
    assert (
        db.execute(
            "SELECT status FROM manifests WHERE manifest_id='MISSING-pos.csv'"
        ).fetchone()[0]
        == "success"
    )


def test_removed_payment_line_references_and_old_replay():
    files = generate()
    payment = next(p for p in json.loads(files["qbo.json"])["Payment"] if p["Line"])
    newer = copy.deepcopy(payment)
    newer.update(SyncToken="1", Line=[])
    change(
        files,
        "updates.json",
        lambda v: v.update(entity="Payment", records=[newer, payment]),
        count=True,
    )
    db = ingest(files.__getitem__)
    assert db.execute("SELECT status FROM run").fetchone()[0] == "complete"
    key = "qbo:Payment:" + payment["Id"]
    assert (
        db.execute("SELECT version FROM records WHERE record_key=?", (key,)).fetchone()[
            0
        ]
        == 1
    )
    assert not db.execute(
        "SELECT 1 FROM records WHERE record_key=?",
        (key + ":" + payment["Line"][0]["Id"],),
    ).fetchone()
    assert not db.execute(
        "SELECT 1 FROM references_needed WHERE record_key=?",
        (key + ":" + payment["Line"][0]["Id"],),
    ).fetchone()


@pytest.mark.parametrize(
    "error",
    [Invalid("STORAGE_BOUNDARY"), sqlite3.OperationalError("synthetic failure")],
)
def test_fatal_import_boundary_closes_connection(monkeypatch, error):
    import propane_demo.ingestion as module

    db = sqlite3.connect(":memory:")
    monkeypatch.setattr(module.sqlite3, "connect", lambda _: db)

    def fail(*args):
        raise error

    monkeypatch.setattr(module, "import_run", fail)
    with pytest.raises(type(error)):
        module.ingest(generate().__getitem__)
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        db.execute("SELECT 1")


@pytest.mark.parametrize(
    "field,value",
    [
        ("CustomerRef", "x"),
        ("LinkedTxn", ["x"]),
        ("Line", ["x"]),
        ("SalesItemLineDetail", "x"),
    ],
)
def test_optional_line_reference_shapes_do_not_crash(field, value):
    files = generate()
    change(
        files, "qbo.json", lambda q: q["Payment"][0]["Line"][0].update({field: value})
    )
    assert_source_isolated(files, "qbo.json", "SCHEMA")


def test_identity_float_error_keeps_pointer():
    files = generate()
    change(files, "identity.json", lambda v: v["customers"][0].update(qbo=1.2))
    _, m = assert_source_isolated(files, "identity.json", "SCHEMA")
    assert m["pointer"] == "#/customers/0"


def test_recursive_normalization_is_safe_source_failure():
    files = generate()
    # Legal JSON below the decoder limit can still exceed recursive normalization.
    # Keep the raw construction independent of Python json.dumps recursion.
    base = files["qbo.json"]
    customer = json.loads(base)["Customer"][0]
    # Inject a nested extension immediately after the first Customer Id.
    marker = json.dumps(customer["Id"]).encode()
    offset = base.index(marker, base.index(b'"Customer"')) + len(marker)
    files["qbo.json"] = (
        base[:offset]
        + b', "extension": '
        + b"[" * 2900
        + b'"x"'
        + b"]" * 2900
        + base[offset:]
    )
    assert isinstance(json.loads(files["qbo.json"]), dict)
    assert_source_isolated(files, "qbo.json", "JSON_SCHEMA")
