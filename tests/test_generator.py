"""Fixture arithmetic/contract tests; business check engines do not exist yet."""

import csv
import io
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from propane_demo.contracts import CSV_FIELDS, QBO_ENTITIES, SCENARIOS
from propane_demo.generator import business_window, generate

ORACLE = json.loads(
    (Path(__file__).parent / "fixtures/expected_findings.json").read_text()
)


def dataset(scenario="clean", **kw):
    return {
        name: list(csv.DictReader(io.StringIO(raw.decode())))
        if name in CSV_FIELDS
        else json.loads(raw)
        for name, raw in generate(scenario, **kw).items()
    }


def dec(value):
    return Decimal(value)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_reproducible_ordered_files_and_oracle_inventory(scenario):
    output = generate(scenario)
    assert output == generate(scenario)
    assert list(output) == sorted(output)
    assert scenario in ORACLE["scenarios"]
    assert all(type(value) is bytes for value in output.values())
    assert not any("expected" in name for name in output)


def test_seed_is_run_namespace_date_is_explicit_and_no_wall_clock(tmp_path):
    first = dataset(seed=1, business_date=date(2024, 2, 29))
    second = dataset(seed=2, business_date=date(2024, 2, 29))
    assert first["run.json"]["business_date"] == "2024-02-29"
    assert first["run.json"]["run_id"] != second["run.json"]["run_id"]
    assert first["qbo.json"] == second["qbo.json"]
    assert first["qbo.json"]["Invoice"][0]["TxnDate"] == "2024-02-28"
    script = (
        "from propane_demo.generator import generate; import hashlib; "
        'print(hashlib.sha256(b"".join(generate().values())).hexdigest())'
    )
    results = [
        subprocess.run(
            [sys.executable, "-c", script],
            cwd=tmp_path,
            env={**os.environ, "TZ": tz, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        ).stdout
        for tz, seed in [("UTC", "1"), ("Asia/Tokyo", "7")]
    ]
    assert results[0] == results[1]


@pytest.mark.parametrize(
    ("day", "hours"),
    [(date(2026, 3, 8), 23), (date(2026, 11, 1), 25), (date(2026, 11, 3), 24)],
)
def test_dst_half_open_day(day, hours):
    start, end = business_window(day)
    assert end - start == timedelta(hours=hours)
    assert start.utcoffset() == end.utcoffset() == timedelta(0)
    assert dataset(business_date=day)["run.json"]["window_start"] == start.isoformat()


@pytest.mark.parametrize(
    ("kw", "message"),
    [
        ({"scenario": "bad"}, "scenario"),
        ({"seed": -1}, "Seed"),
        ({"seed": 2**32}, "Seed"),
        ({"seed": True}, "Seed"),
        ({"seed": 1.1}, "Seed"),
        ({"business_date": "2026-11-03"}, "date"),
    ],
)
def test_invalid_generator_arguments(kw, message):
    with pytest.raises(ValueError, match=message):
        generate(**kw)


def test_contracts_are_entity_specific_and_manifests_count_physical_rows():
    data = dataset()
    qbo = data["qbo.json"]
    assert tuple(qbo) == tuple(sorted(QBO_ENTITIES))
    assert "Balance" in qbo["Invoice"][0]
    assert "UnappliedAmt" in qbo["Payment"][0]
    assert "SalesItemLineDetail" in qbo["Invoice"][0]["Line"][0]
    assert "JournalEntryLineDetail" in qbo["JournalEntry"][0]["Line"][0]
    assert "DepositLineDetail" in qbo["Deposit"][0]["Line"][0]
    assert "TotalAmt" not in qbo["Customer"][0]
    assert "CustomerRef" not in qbo["Item"][0]
    for name, fields in CSV_FIELDS.items():
        assert list(data[name][0]) == fields
    for manifest in data["manifests.json"]:
        content = data[manifest["file_id"]]
        count = (
            sum(map(len, content.values()))
            if manifest["source"] == "qbo"
            else len(content)
        )
        assert int(manifest["row_count"]) == count
        assert manifest["status"] == "success"
    assert data["empty.json"] == []
    assert (
        data["updates.json"]["records"][0]["Id"]
        == data["updates.json"]["records"][1]["Id"]
    )
    assert [x["SyncToken"] for x in data["updates.json"]["records"]] == ["0", "1"]


def test_clean_split_combined_payments_adjustments_and_inventory():
    d = dataset()
    allocations = d["identity.json"]["allocations"]
    assert sum(
        dec(a["gallons"]) for a in allocations if a["delivery_id"] == "D-SPLIT"
    ) == dec("50")
    assert sum(
        dec(a["net_amount"]) for a in allocations if a["invoice_id"] == "I-COMBINED"
    ) == dec("100")
    q = d["qbo.json"]
    assert q["Invoice"][10]["Balance"] == "0.00"
    assert q["Payment"][0]["Line"][0]["Amount"] == "100.00"
    assert (
        q["CreditMemo"][0]["TotalAmt"] == q["RefundReceipt"][0]["TotalAmt"] == "100.00"
    )
    assert q["Payment"][1]["UnappliedAmt"] == "0.01"
    assert d["identity.json"]["sku_fill_gallons"] == {"CYLINDER": "5.000"}
    assert q["SalesReceipt"][3]["Line"][0]["DiscountAmount"] == "10.00"
    readings = {x["reading_id"]: dec(x["gallons"]) for x in d["readings.csv"]}
    assert readings["R-CLOSE"] == dec("1000") + dec("200") - dec("100") - dec("50")
    assert readings["R-ISOLATED-CLOSE"] == dec("1000") - sum(
        dec(x["gallons"]) for x in d["deliveries.csv"] if x["tank_id"] == "ISOLATED"
    ) - dec("5")
    transfers = [x for x in d["movements.csv"] if x["transfer_id"] == "X-1"]
    assert len(transfers) == 2
    assert (
        sum(
            dec(x["quantity"]) * (-1 if x["movement_type"] == "transfer_out" else 1)
            for x in transfers
        )
        == 0
    )
    assert ORACLE["scenarios"]["clean"] == {
        "findings": [],
        "alerts": [],
        "not_evaluated": [],
        "legitimate_cascades": [],
    }


def test_exact_money_gallon_boundaries_are_real_source_records():
    d = dataset()
    assert d["policies.json"]["money_rounding"] == "ROUND_HALF_UP"
    fraction = next(x for x in d["deliveries.csv"] if x["ticket_id"] == "D-FRACTION")
    assert dec(fraction["gallons"]) == dec("0.005")
    assert (dec(fraction["gallons"]) * dec("2.00")).quantize(
        dec(".01"), rounding=ROUND_HALF_UP
    ) == dec(fraction["net_amount"])
    boundary = next(
        x for x in d["qbo.json"]["SalesReceipt"] if x["Id"] == "SR-PRICE-BOUNDARY"
    )
    assert dec(boundary["TotalAmt"]) - dec("20.00") == dec("0.01")
    r = {x["reading_id"]: x for x in d["readings.csv"]}
    assert dec(r["R-BOUNDARY-CLOSE"]["gallons"]) - dec(
        r["R-BOUNDARY-OPEN"]["gallons"]
    ) == dec("5")
    assert dec(r["R-BOUNDARY-CLOSE"]["uncertainty_gallons"]) + dec(
        r["R-BOUNDARY-OPEN"]["uncertainty_gallons"]
    ) == dec("5")
    assert (
        next(x for x in d["deliveries.csv"] if x["ticket_id"] == "D-CANCELLED")[
            "status"
        ]
        == "cancelled"
    )
    assert {x["status"] for x in d["pos.csv"]} >= {
        "pending",
        "void",
        "refunded",
        "captured",
    }
    for file, fields in [
        ("deliveries.csv", ["gallons"]),
        ("readings.csv", ["gallons", "uncertainty_gallons"]),
        ("movements.csv", ["quantity"]),
    ]:
        for row in d[file]:
            for field in fields:
                assert dec(row[field]).as_tuple().exponent == -3


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("P01", ["C01"]),
        ("P02", ["C02"]),
        ("P03", ["C03"]),
        ("P04", ["C04"]),
        ("P05", ["C05", "C05"]),
        ("P06", ["C06", "C06"]),
        ("P07", ["C07"]),
        ("P08", ["C08"]),
        ("P09", ["C08"]),
        ("P10", ["C09"]),
        ("P11", ["C10"]),
        ("P12", ["C11", "C11"]),
        ("P13", ["C12"]),
        ("P14", ["C05"]),
        ("raw-repeat", ["C03"]),
        ("wrong-clearing", ["C12"]),
    ],
)
def test_independent_mutation_contract_and_exact_oracle_shape(name, expected):
    output = generate(name)
    assert output != generate("clean")
    findings = ORACLE["scenarios"][name]["findings"]
    assert [f["check_id"] for f in findings] == expected
    required = {
        "finding_id",
        "check_id",
        "severity",
        "status",
        "business_date",
        "rule_version",
        "actual",
        "expected",
        "delta",
        "threshold",
        "source_refs",
        "related_refs",
        "missing_reference",
        "explanation",
    }
    for f in findings:
        assert set(f) == required
        assert f["finding_id"] == f["check_id"] + "|" + "|".join(
            sorted(f["source_refs"])
        )
        assert f["source_refs"] and f["explanation"]
    # The fixture contains no other planted scenario's sentinel.
    if name == "P11":
        assert output["pos.csv"] == b"transaction_id,line_id\nT-MALFORMED\n"
    else:
        assert dataset(name)["manifests.json"][3]["status"] == "success"


def test_hand_calculations_match_mutated_records_not_a_check_engine():
    p4 = dataset("P04")
    f4 = ORACLE["scenarios"]["P04"]["findings"][0]
    actual = dec(p4["qbo.json"]["Invoice"][0]["Line"][0]["Amount"])
    expected = dec(p4["deliveries.csv"][0]["gallons"]) * dec(
        p4["prices.csv"][0]["unit_price"]
    )
    assert (actual, expected, actual - expected) == tuple(
        map(dec, [f4["actual"], f4["expected"], f4["delta"]])
    )
    p5 = dataset("P05")
    assert p5["qbo.json"]["CreditMemo"][0]["TotalAmt"] == "150.00"
    assert dec(p5["pos.csv"][3]["discount_amount"]) / dec("100") * 100 == 15
    p6 = dataset("P06")
    assert (
        dec(p6["qbo.json"]["Payment"][-1]["Line"][0]["Amount"])
        - dec(p6["qbo.json"]["Invoice"][2]["TotalAmt"])
        == 10
    )
    p7 = dataset("P07")
    batch = p7["settlements.csv"][0]
    assert dec(batch["gross"]) - dec(batch["refunds"]) - dec(batch["fees"]) == 470
    assert dec(p7["qbo.json"]["Deposit"][0]["TotalAmt"]) - 470 == -10
    p8 = dataset("P08")
    assert dec(p8["readings.csv"][1]["gallons"]) - 1050 == -30
    assert max(dec("2.000"), dec(".005") * (dec("1000") + dec("200"))) == 6
    p13 = dataset("P13")["qbo.json"]["JournalEntry"][0]["Line"]
    assert dec(p13[0]["Amount"]) - dec(p13[1]["Amount"]) == 10
    wrong = dataset("wrong-clearing")["qbo.json"]["JournalEntry"][0]["Line"]
    assert wrong[0]["Amount"] == wrong[1]["Amount"] == "90.00"
    assert dec(wrong[0]["Amount"]) - 100 == -10


def test_raw_repeat_exact_occurrence_pointers_and_no_business_duplicate():
    qbo = dataset("raw-repeat")["qbo.json"]
    assert qbo["Invoice"][0] == qbo["Invoice"][-1]
    assert ORACLE["scenarios"]["raw-repeat"]["findings"][0]["source_refs"] == [
        "file:qbo.json#/Invoice/0",
        f"file:qbo.json#/Invoice/{len(qbo['Invoice']) - 1}",
    ]


def test_combined_inputs_suppression_and_legitimate_cascades():
    output = generate("issues")
    assert output["pos.csv"] == generate("P11")["pos.csv"]
    q = json.loads(output["qbo.json"])
    assert q["Invoice"][0]["TotalAmt"] == "210.00"
    assert q["CreditMemo"][0]["TotalAmt"] == "150.00"
    assert any(x["Id"] == "RR-NO-ORIGINAL" for x in q["RefundReceipt"])
    oracle = ORACLE["scenarios"]["issues"]
    assert [f["check_id"] for f in oracle["findings"]] == [
        "C08",
        "C09",
        "C10",
        "C11",
        "C11",
    ]
    assert len(oracle["alerts"]) == 2
    assert len(oracle["legitimate_cascades"]) == 3
    assert "C01" in oracle["not_evaluated"]
    assert not any(f["status"] == "exception" for f in oracle["findings"])


def test_every_oracle_evidence_key_resolves_to_real_or_derived_source():
    for name, expectation in ORACLE["scenarios"].items():
        # Failed CSV remains raw evidence; its valid pre-failure rows are not findings.
        data = dataset(name) if name not in {"P11", "issues"} else None
        if data is None:
            output = generate(name)
            data = {
                key: json.loads(raw)
                for key, raw in output.items()
                if key.endswith(".json")
            }
            data.update(
                {
                    key: list(csv.DictReader(io.StringIO(raw.decode())))
                    for key, raw in output.items()
                    if key in CSV_FIELDS
                }
            )
        keys = {"policy:POLICY-1", "ar:snapshot:AR-OPEN"}
        for entity, records in data["qbo.json"].items():
            for index, record in enumerate(records):
                root = f"qbo:{entity}:{record['Id']}"
                keys.add(root)
                keys.add(f"file:qbo.json#/{entity}/{index}")
                keys.add(f"qbo:version:{record['Id']}:{record['SyncToken']}")
                for line in record.get("Line", []):
                    keys.add(root + ":" + line["Id"])
                    detail = line.get("JournalEntryLineDetail", {})
                    if "AccountRef" in detail:
                        keys.add("qbo:account:" + detail["AccountRef"]["value"])
        for record in data["deliveries.csv"]:
            keys.add("cargas:delivery:" + record["ticket_id"])
            keys.add("cargas:meter_ticket:" + record["meter_ticket_id"])
        for record in data["readings.csv"]:
            keys.add("cargas:reading:" + record["reading_id"])
        for record in data["pos.csv"]:
            keys.add(f"pos:POS:{record['transaction_id']}:{record['line_id']}")
            if record.get("external_reference"):
                keys.add("pos:external_reference:" + record["external_reference"])
        for record in data["settlements.csv"]:
            keys.add("pos:batch:" + record["batch_id"])
            keys.add("pos:fee:" + record["batch_id"] + ":fees")
        for record in data["movements.csv"]:
            keys.add("inventory:movement:" + record["movement_id"])
        for record in data["prices.csv"]:
            keys.add("prices:price:" + record["price_id"])
        for collection, entity, id_field in [
            ("allocations", "allocation", "mapping_id"),
            ("assets", "asset", "mapping_id"),
            ("approvals", "approval", "approval_id"),
            ("posting_map", "posting", "mapping_id"),
        ]:
            for record in data["identity.json"][collection]:
                keys.add(f"identity:{entity}:{record[id_field]}")
        for manifest in data["manifests.json"]:
            keys.add("manifest:" + manifest["manifest_id"])
            keys.add("file:" + manifest["file_id"])
        if name in {"P11", "issues"}:
            keys.add("file:pos.csv:row:2")
        for finding in expectation["findings"]:
            assert set(finding["source_refs"] + finding["related_refs"]) <= keys, name


@pytest.mark.parametrize(
    "day", [date(2019, 12, 31), date(2035, 1, 1), date.min, date.max]
)
def test_outside_fictional_price_range_is_explicit(day):
    with pytest.raises(ValueError, match="price coverage"):
        generate(business_date=day)


@pytest.mark.parametrize("seed", [0, 2**32 - 1])
def test_seed_boundaries_and_returns_do_not_share_state(seed):
    output = generate(seed=seed)
    run = json.loads(output["run.json"])
    assert run["run_id"] == f"synthetic-{seed}-2026-11-03-clean"
    output["qbo.json"] = b"changed by caller"
    assert generate(seed=seed)["qbo.json"] != b"changed by caller"


def test_qbo_entities_do_not_invent_shared_transaction_fields():
    q = dataset()["qbo.json"]
    assert "CustomerRef" not in q["JournalEntry"][0]
    assert "CustomerRef" not in q["Deposit"][0]
    assert "DocNumber" not in q["Deposit"][0]
    assert "PaymentRefNum" in q["Payment"][0]
    assert "DocNumber" not in q["Payment"][0]


def test_mutations_change_only_declared_files():
    clean = generate()
    expected = {
        "P01": {"deliveries.csv", "manifests.json"},
        "P02": {"qbo.json", "manifests.json"},
        "P03": {"qbo.json", "pos.csv", "identity.json", "manifests.json"},
        "P04": {"qbo.json", "identity.json"},
        "P05": {"qbo.json", "pos.csv", "prices.csv", "identity.json"},
        "P06": {"qbo.json", "manifests.json"},
        "P07": {"qbo.json"},
        "P08": {"readings.csv"},
        "P09": {"readings.csv"},
        "P10": {"manifests.json"},
        "P11": {"pos.csv", "manifests.json"},
        "P12": {"deliveries.csv", "identity.json", "readings.csv", "manifests.json"},
        "P13": {"qbo.json"},
        "P14": {"qbo.json", "manifests.json"},
        "raw-repeat": {"qbo.json", "manifests.json"},
        "wrong-clearing": {"qbo.json"},
    }
    for name, changed in expected.items():
        output = generate(name)
        # Run ID intentionally differs in run metadata and every manifest.
        actual = {file for file in output if output[file] != clean[file]}
        assert actual == changed | {"run.json", "manifests.json"}, name


def test_oracle_numerical_deltas_and_explicit_no_verdict():
    for scenario in ORACLE["scenarios"].values():
        ids = [f["finding_id"] for f in scenario["findings"]]
        assert ids == sorted(set(ids))
        for f in scenario["findings"]:
            if f["delta"] is not None:
                assert dec(f["actual"]) - dec(f["expected"]) == dec(f["delta"])
            if f["status"] in {"sensor_uncertain", "not_evaluated"}:
                assert f["actual"] is f["expected"] is f["delta"] is None


def test_independent_problem_records_are_exact():
    assert dataset("P01")["deliveries.csv"][-1]["ticket_id"] == "D-MISSING"
    assert dataset("P02")["qbo.json"]["Invoice"][-1]["Id"] == "I-ORPHAN"
    assert [r["external_reference"] for r in dataset("P03")["pos.csv"][-2:]] == [
        "EXT-DUP",
        "EXT-DUP",
    ]
    assert dataset("P09")["readings.csv"][3]["quality"] == "uncertain"
    assert (
        dataset("P10")["manifests.json"][0]["covered_through"]
        == "2026-11-03T06:00:00+00:00"
    )
    p12 = dataset("P12")
    assert (
        p12["deliveries.csv"][-1]["customer_id"]
        == p12["deliveries.csv"][-1]["item_id"]
        == "UNKNOWN"
    )
    assert not any(
        r["asset_id"] == "TRUCK-NO-READING"
        and r["observed_at"].endswith("2026-11-04T07:00:00+00:00")
        for r in p12["readings.csv"]
    )
    assert dataset("P14")["qbo.json"]["RefundReceipt"][-1]["LinkedTxn"] == []


def test_discount_override_is_approved_but_still_unusual():
    data = dataset("P05")
    assert data["prices.csv"][5]["approved_discount_pct"] == "15.00"
    assert data["identity.json"]["approvals"][2]["approved_discount_pct"] == "15.00"
    assert data["policies.json"]["discount_limit_pct"] == "10.00"
    assert {f["check_id"] for f in ORACLE["scenarios"]["P05"]["findings"]} == {"C05"}


def test_serialized_financial_values_never_use_binary_float():
    def reject_float(value):
        pytest.fail("JSON financial float: " + value)

    for raw in generate().values():
        if raw.startswith((b"{", b"[")):
            json.loads(raw, parse_float=reject_float)
