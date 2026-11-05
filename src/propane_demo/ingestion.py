"""Disposable SQLite run, atomic source imports and inspectable failure evidence.

Call ingest(generated_files.__getitem__) or ingest(lambda name: Path(...).read_bytes()).
The caller closes the returned SQLite connection. No persistent cache or migrations.
"""

import csv
import hashlib
import io
import json
import sqlite3
from datetime import timedelta
from zoneinfo import ZoneInfo

from propane_demo.contracts import CSV_FIELDS, QBO_ENTITIES
from propane_demo.generator import business_window
from propane_demo.validation import (
    CSV_KEYS,
    MONEY,
    QUANTITY,
    Invalid,
    csv_row,
    day,
    fields,
    identifier,
    instant,
    integer,
    links,
    normalize,
    qbo,
    ref,
    require,
    scaled,
    text,
    timestamps,
)

# File/atomic group/manifest source. Update replay MUST roll back with base QBO.
SOURCES = {
    "qbo.json": ("qbo", "qbo"),
    "updates.json": ("qbo", "qbo_updates"),
    "deliveries.csv": ("cargas", "cargas"),
    "readings.csv": ("readings", "readings"),
    "pos.csv": ("pos", "pos"),
    "settlements.csv": ("settlements", "settlements"),
    "movements.csv": ("inventory", "inventory"),
    "prices.csv": ("prices", "prices"),
    "identity.json": ("identity", "identity"),
    "opening_ar.json": ("ar", "ar"),
    "empty.json": ("optional_empty", "optional_empty"),
}
# Availability only; no verdicts or financial computations. C03 may still inspect
# raw occurrences from healthy sources. C11 diagnoses missing support separately.
DEPENDENCIES = {
    "C01": {"cargas", "qbo", "identity"},
    "C02": {"cargas", "qbo", "identity"},
    "C03:qbo": {"qbo"},
    "C03:pos": {"pos"},
    "C04:qbo": {"cargas", "qbo", "prices", "identity"},
    "C04:pos": {"pos", "prices", "identity"},
    "C05:qbo": {"qbo", "identity"},
    "C05:pos": {"pos", "prices", "identity"},
    "C06": {"qbo", "ar"},
    "C07": {"qbo", "pos", "settlements", "identity"},
    "C12": {"qbo", "identity"},
    "KPI:delivered": {"cargas", "identity"},
    "KPI:retail": {"pos", "identity"},
    "KPI:revenue": {"qbo", "pos", "identity"},
    "KPI:AR": {"qbo", "ar", "identity"},
}
SCHEMA = """
CREATE TABLE run (run_id TEXT PRIMARY KEY, business_date TEXT, rule_version TEXT,
 status TEXT NOT NULL, metadata TEXT NOT NULL);
CREATE TABLE files (file_id TEXT PRIMARY KEY, raw BLOB NOT NULL, sha256 TEXT NOT NULL);
CREATE TABLE manifests (file_id TEXT PRIMARY KEY, manifest_id TEXT UNIQUE NOT NULL,
 source TEXT NOT NULL, status TEXT NOT NULL, error_code TEXT NOT NULL,
 pointer TEXT NOT NULL, raw TEXT NOT NULL);
CREATE TABLE occurrences (ref TEXT PRIMARY KEY, file_id TEXT NOT NULL,
 pointer TEXT NOT NULL, record_key TEXT NOT NULL, version INTEGER NOT NULL,
 raw TEXT NOT NULL, FOREIGN KEY(file_id) REFERENCES files(file_id));
CREATE TABLE versions (record_key TEXT NOT NULL, version INTEGER NOT NULL,
 payload TEXT NOT NULL, occurrence_ref TEXT NOT NULL,
 PRIMARY KEY(record_key, version));
CREATE TABLE scaled_values (record_key TEXT NOT NULL, version INTEGER NOT NULL,
 pointer TEXT NOT NULL, value INTEGER NOT NULL, scale INTEGER NOT NULL,
 PRIMARY KEY(record_key, version, pointer),
 CHECK(typeof(value)='integer'), CHECK(scale IN (2,3)));
CREATE TABLE records (record_key TEXT PRIMARY KEY, source TEXT NOT NULL,
 version INTEGER NOT NULL, payload TEXT NOT NULL, occurrence_ref TEXT NOT NULL);
CREATE TABLE references_needed (record_key TEXT NOT NULL, target_key TEXT NOT NULL,
 PRIMARY KEY(record_key, target_key));
CREATE TABLE alerts (alert_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
 source TEXT NOT NULL, check_id TEXT NOT NULL, severity TEXT NOT NULL,
 reason_code TEXT NOT NULL, source_refs TEXT NOT NULL, related_refs TEXT NOT NULL,
 observed_at TEXT NOT NULL, status TEXT NOT NULL, UNIQUE(run_id, source, reason_code));
CREATE TRIGGER immutable_files_update BEFORE UPDATE ON files
 BEGIN SELECT RAISE(ABORT, 'immutable raw file'); END;
CREATE TRIGGER immutable_files_delete BEFORE DELETE ON files
 BEGIN SELECT RAISE(ABORT, 'immutable raw file'); END;
CREATE TRIGGER immutable_occurrence_update BEFORE UPDATE ON occurrences
 BEGIN SELECT RAISE(ABORT, 'immutable occurrence'); END;
CREATE TRIGGER immutable_occurrence_delete BEFORE DELETE ON occurrences
 BEGIN SELECT RAISE(ABORT, 'immutable occurrence'); END;
"""


def dump(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def read(read_file, name):
    try:
        raw = read_file(name)
    except KeyError:
        raise Invalid("MISSING") from None
    except OSError:
        raise Invalid("UNREADABLE") from None
    require(isinstance(raw, bytes), "UNREADABLE")
    return raw


def parse(raw):
    try:
        # Duplicate object members are ambiguous; JSON numeric literals are not
        # accepted as financial strings by normalize/scaled.
        return json.loads(raw, object_pairs_hook=unique_members)
    except (ValueError, UnicodeError, RecursionError):
        raise Invalid("JSON_SCHEMA") from None


def unique_members(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON_SCHEMA")
        result[key] = value
    return result


def control(read_file):
    try:
        raw_controls = {
            name: read(read_file, name) for name in ("run.json", "policies.json")
        }
        run = parse(raw_controls["run.json"])
        policy = parse(raw_controls["policies.json"])
        fields(
            run,
            [
                "run_id",
                "business_date",
                "window_start",
                "window_end",
                "as_of",
                "contract_version",
            ],
        )
        labels = run.get("report_labels", {})
        require(isinstance(labels, dict))
        for key, label in labels.items():
            text(key)
            text(label)
        identifier(run["run_id"])
        require(run["contract_version"] == "1", "CONTRACT_VERSION")
        start, end = business_window(day(run["business_date"]))
        require(
            (instant(run["window_start"]), instant(run["window_end"])) == (start, end),
            "WINDOW",
        )
        require(instant(run["as_of"]) >= end, "WINDOW")
        require(policy["fictional"] is True and policy["synthetic"] is True)
        require(policy["currency"] == "USD" and policy["timezone"] == "America/Denver")
        require(policy["version"] == "1" and policy["future_max_minutes"] == 5)
        identifier(policy["policy_id"])
        return run, policy, raw_controls
    except (KeyError, TypeError):
        raise Invalid("CONTROL_SCHEMA") from None


def metadata(manifest, name, run):
    fields(
        manifest,
        [
            "manifest_id",
            "run_id",
            "source",
            "file_id",
            "expected_window_start",
            "expected_window_end",
            "extracted_at",
            "covered_through",
            "status",
            "row_count",
            "error_code",
        ],
    )
    identifier(manifest["manifest_id"])
    require(manifest["file_id"] == name and manifest["run_id"] == run["run_id"])
    require(manifest["source"] == SOURCES[name][1])
    require(manifest["status"] in {"success", "failed"}, "MANIFEST_STATUS")
    integer(manifest["row_count"])
    start, end, extracted, covered = [
        instant(manifest[key])
        for key in (
            "expected_window_start",
            "expected_window_end",
            "extracted_at",
            "covered_through",
        )
    ]
    require(
        start
        <= covered
        <= end
        <= extracted
        <= instant(run["as_of"]) + timedelta(minutes=5),
        "WINDOW",
    )
    require(
        start <= instant(run["window_start"]) and end >= instant(run["window_end"]),
        "WINDOW",
    )
    if manifest["status"] == "failed":
        require(
            bool(manifest["error_code"])
            and bool(safe_error_code(manifest["error_code"])),
            "ERROR_CODE",
        )
    else:
        require(manifest["error_code"] == "", "ERROR_CODE")


def safe_error_code(value):
    # Safe codes only, never exception messages supplied by a source adapter.
    return value in {"CSV_SCHEMA", "JSON_SCHEMA", "EXTRACTION_FAILED", "UNREADABLE"}


def rows(name, raw):
    if name in CSV_FIELDS:
        try:
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8")), strict=True)
            if reader.fieldnames != CSV_FIELDS[name]:
                raise Invalid("CSV_SCHEMA", ":row:2")
            return [(f":row:{reader.line_num}", row) for row in reader]
        except (UnicodeError, csv.Error):
            raise Invalid("CSV_SCHEMA") from None
    value = parse(raw)
    if name == "qbo.json":
        require(isinstance(value, dict) and set(value) == set(QBO_ENTITIES))
        result = []
        for entity, objects in value.items():
            require(isinstance(objects, list))
            result.extend(
                (f"#/{entity}/{i}", (entity, row)) for i, row in enumerate(objects)
            )
        return result
    if name == "updates.json":
        fields(value, ["source", "entity", "records"])
        require(value["source"] == "qbo" and value["entity"] in QBO_ENTITIES)
        require(isinstance(value["records"], list))
        return [
            (f"#/records/{i}", (value["entity"], row))
            for i, row in enumerate(value["records"])
        ]
    if name == "empty.json":
        require(value == [])
        return []
    # Structured supporting JSON counts top-level members; individual entries
    # still get their own pointers and validated normalized records below.
    require(isinstance(value, dict))
    return [("#/" + key, item) for key, item in value.items()]


def support(name, entries):
    value = {pointer[2:]: item for pointer, item in entries}
    result = []
    if name == "opening_ar.json":
        fields(value, ["snapshot_id", "as_of", "balances"])
        require(set(value) == {"snapshot_id", "as_of", "balances"})
        require(isinstance(value["balances"], list))
        identifier(value["snapshot_id"])
        instant(value["as_of"])
        seen = set()
        for row in value["balances"]:
            fields(row, ["customer_id", "amount"])
            require(set(row) == {"customer_id", "amount"})
            identifier(row["customer_id"])
            require(row["customer_id"] not in seen, "DUPLICATE_KEY")
            seen.add(row["customer_id"])
            scaled(row["amount"], 2)
        result.append(("#", "ar:snapshot:" + value["snapshot_id"], value))
    else:
        required = {
            "customers": "mapping_id cargas pos qbo",
            "items": "mapping_id cargas qbo unit gallon_basis",
            "assets": "mapping_id source_id asset_id",
            "allocations": (
                "mapping_id delivery_id invoice_id line_id gallons net_amount"
            ),
            "pos_events": "mapping_id pos_id qbo_entity qbo_id inventory_counted",
            "approvals": "approval_id policy_id",
            "posting_map": "mapping_id journal_id external_ref account_id",
        }
        require(set(value) == set(required) | {"sku_fill_gallons"})
        for collection, required_fields in required.items():
            require(isinstance(value[collection], list))
            for i, row in enumerate(value[collection]):
                try:
                    fields(row, required_fields.split())
                    optional = {
                        "pos_events": {"delivery_id", "payment_id"},
                        "approvals": {"approved_discount_pct"},
                    }.get(collection, set())
                    require(set(row) <= set(required_fields.split()) | optional)
                    for key in row:
                        if key == "inventory_counted":
                            require(type(row[key]) is bool)
                        else:
                            require(isinstance(row[key], str) and bool(row[key]))
                            if key not in {
                                "gallons",
                                "net_amount",
                                "approved_discount_pct",
                            }:
                                for component in (
                                    row[key].split(":")
                                    if key == "pos_id"
                                    else [row[key]]
                                ):
                                    identifier(component)
                    if collection == "pos_events":
                        require(row["qbo_entity"] in QBO_ENTITIES, "REFERENCE")
                    entity = {
                        "allocations": "allocation",
                        "approvals": "approval",
                        "posting_map": "posting",
                    }.get(collection, collection[:-1])
                    record_id = row.get("mapping_id", row.get("approval_id"))
                    identifier(record_id)
                    result.append(
                        (f"#/{collection}/{i}", f"identity:{entity}:{record_id}", row)
                    )
                except Invalid as error:
                    raise Invalid(error.code, f"#/{collection}/{i}") from None
        require(isinstance(value["sku_fill_gallons"], dict))
        for sku, volume in value["sku_fill_gallons"].items():
            identifier(sku)
            require(scaled(volume, 3) > 0, "NEGATIVE")
            result.append(
                (
                    "#/sku_fill_gallons/" + sku,
                    "identity:fill:" + sku,
                    {"gallons": volume},
                )
            )
    return result


def needed(key, row):
    """Syntactically valid missing support survives for C11, never guessed."""
    refs = []
    if "CustomerRef" in row:
        ref(row["CustomerRef"])
        refs.append("qbo:Customer:" + row["CustomerRef"]["value"])
    links(row.get("LinkedTxn", []))
    for link in row.get("LinkedTxn", []):
        refs.append(f"qbo:{link['TxnType']}:{link['TxnId']}")
    require(isinstance(row.get("Line", []), list))
    for line in row.get("Line", []):
        fields(line, ["Id"])
        require("Line" not in line)
        refs.extend(needed(key, line))
        if "SalesItemLineDetail" in line:
            fields(line["SalesItemLineDetail"], ["ItemRef"])
            ref(line["SalesItemLineDetail"]["ItemRef"])
            refs.append("qbo:Item:" + line["SalesItemLineDetail"]["ItemRef"]["value"])
    if key.startswith("identity:allocation:"):
        refs.extend(
            [
                "cargas:delivery:" + row["delivery_id"],
                f"qbo:Invoice:{row['invoice_id']}:{row['line_id']}",
            ]
        )
    return refs


def numeric_fields(value, pointer=""):
    """Typed SQLite cells alongside the validated structured payload."""
    if isinstance(value, dict):
        for key, child in value.items():
            path = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
            if key in MONEY | QUANTITY | {"approved_discount_pct", "temperature_f"}:
                yield path, child, 2 if key in MONEY else 3
            else:
                yield from numeric_fields(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from numeric_fields(child, pointer + "/" + str(index))


def put(db, name, pointer, key, version, row, normalized, source, current=True):
    payload = dump(normalized)
    old = db.execute(
        "SELECT o.raw FROM versions v JOIN occurrences o "
        "ON o.ref=v.occurrence_ref WHERE v.record_key=? AND v.version=?",
        (key, version),
    ).fetchone()
    raw_record = row["gallons"] if key.startswith("identity:fill:") else row
    require(old is None or old[0] == dump(raw_record), "VERSION_CONFLICT")
    occurrence = "file:" + name + pointer
    db.execute(
        "INSERT OR IGNORE INTO occurrences VALUES (?,?,?,?,?,?)",
        (occurrence, name, pointer, key, version, dump(raw_record)),
    )
    if old is None:
        db.execute(
            "INSERT INTO versions VALUES (?,?,?,?)", (key, version, payload, occurrence)
        )
    for path, value, scale in numeric_fields(normalized):
        db.execute(
            "INSERT OR IGNORE INTO scaled_values VALUES (?,?,?,?,?)",
            (key, version, path, value, scale),
        )
    if current:
        db.execute(
            """INSERT INTO records VALUES (?,?,?,?,?)
            ON CONFLICT(record_key) DO UPDATE SET version=excluded.version,
            payload=excluded.payload, occurrence_ref=excluded.occurrence_ref
            WHERE excluded.version > records.version""",
            (key, source, version, payload, occurrence),
        )
        for target in needed(key, row):
            db.execute(
                "INSERT OR IGNORE INTO references_needed VALUES (?,?)", (key, target)
            )


def import_file(db, name, raw, manifest):
    entries = rows(name, raw)
    require(len(entries) == integer(manifest["row_count"]), "ROW_COUNT")
    if name in {"identity.json", "opening_ar.json"}:
        records = []
        for pointer, key, row in support(name, entries):
            try:
                records.append((pointer, key, 0, row, normalize(row)))
            except Invalid as error:
                raise Invalid(error.code, pointer) from None
    else:
        records = []
        for pointer, row in entries:
            try:
                if name in {"qbo.json", "updates.json"}:
                    entity, row = row
                    normalized = qbo(entity, row)
                    key, version = (
                        f"qbo:{entity}:{row['Id']}",
                        integer(row["SyncToken"]),
                    )
                else:
                    normalized = csv_row(name, row)
                    source, entity, id_field = CSV_KEYS[name]
                    key = f"{source}:{entity}:{row[id_field]}"
                    if name == "pos.csv":
                        key += ":" + row["line_id"]
                    version = 0
                records.append((pointer, key, version, row, normalized))
            except (Invalid, KeyError, TypeError, RecursionError) as error:
                code = (
                    error.code
                    if isinstance(error, Invalid)
                    else "JSON_SCHEMA"
                    if isinstance(error, RecursionError)
                    else "SCHEMA"
                )
                raise Invalid(code, pointer) from None
    seen = {}
    intervals = {}
    for pointer, key, version, row, normalized in records:
        try:
            if name not in {"qbo.json", "updates.json"}:
                require(
                    key not in seen or (name in CSV_FIELDS and seen[key] == row),
                    "DUPLICATE_KEY",
                )
            repeated = key in seen
            seen[key] = row
            for stamp in timestamps(row):
                require(
                    instant(manifest["expected_window_start"])
                    <= stamp
                    <= instant(manifest["expected_window_end"])
                    and stamp <= instant(manifest["extracted_at"]),
                    "WINDOW",
                )
            if "TxnDate" in row:
                zone = ZoneInfo("America/Denver")
                first = (
                    instant(manifest["expected_window_start"]).astimezone(zone).date()
                )
                last = instant(manifest["expected_window_end"]).astimezone(zone).date()
                require(first <= day(row["TxnDate"]) < last, "POSTING_WINDOW")
            if name == "prices.csv" and not repeated:
                price_key = tuple(
                    row[k]
                    for k in ("item_id", "customer_class", "unit", "gallon_basis")
                )
                lo, hi = day(row["effective_from"]), day(row["effective_to"])
                for a, b in intervals.get(price_key, []):
                    require(hi <= a or lo >= b, "PRICE_OVERLAP")
                intervals.setdefault(price_key, []).append((lo, hi))
            current = db.execute(
                "SELECT version FROM records WHERE record_key=?", (key,)
            ).fetchone()
            if current is not None and version > current[0]:
                prefix = key + ":"
                db.execute(
                    "DELETE FROM records WHERE substr(record_key,1,?)=?",
                    (len(prefix), prefix),
                )
                db.execute(
                    "DELETE FROM references_needed WHERE record_key=? "
                    "OR substr(record_key,1,?)=?",
                    (key, len(prefix), prefix),
                )
            is_current = current is None or version >= current[0]
            put(
                db,
                name,
                pointer,
                key,
                version,
                row,
                normalized,
                SOURCES[name][0],
                is_current,
            )
            for line in row.get("Line", []):
                put(
                    db,
                    name,
                    pointer + "/Line/" + str(row["Line"].index(line)),
                    key + ":" + line["Id"],
                    version,
                    line,
                    normalize(line),
                    SOURCES[name][0],
                    is_current,
                )
        except Invalid as error:
            raise Invalid(error.code, pointer) from None


def ingest(read_file):
    """Return a NEW in-memory database. Invalid control metadata is fatal.

    A source failure yields incomplete status, one critical C10/group alert and
    zero normalized rows from that atomic group. Raw file bytes always survive.
    """
    run, policy, raw_controls = control(read_file)
    db = sqlite3.connect(":memory:")
    try:
        return import_run(db, read_file, run, policy, raw_controls)
    except (Invalid, sqlite3.Error):
        db.close()
        raise


def import_run(db, read_file, run, policy, raw_controls):
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    db.execute(
        "INSERT INTO run VALUES (?,?,?,?,?)",
        (run["run_id"], run["business_date"], policy["version"], "complete", dump(run)),
    )
    for name, raw in raw_controls.items():
        db.execute(
            "INSERT INTO files VALUES (?,?,?)",
            (name, raw, hashlib.sha256(raw).hexdigest()),
        )
    try:
        manifest_bytes = read(read_file, "manifests.json")
        db.execute(
            "INSERT INTO files VALUES (?,?,?)",
            (
                "manifests.json",
                manifest_bytes,
                hashlib.sha256(manifest_bytes).hexdigest(),
            ),
        )
        manifests = parse(manifest_bytes)
        require(isinstance(manifests, list))
        index = {}
        ids = set()
        for manifest in manifests:
            fields(manifest, ["file_id", "manifest_id"])
            identifier(manifest["manifest_id"])
            require(
                manifest["file_id"] not in index and manifest["manifest_id"] not in ids,
                "DUPLICATE_MANIFEST",
            )
            require(manifest["file_id"] in SOURCES)
            index[manifest["file_id"]] = manifest
            ids.add(manifest["manifest_id"])
    except (Invalid, KeyError, TypeError):
        index = {}
    failures = {}
    for group in dict.fromkeys(group for group, _ in SOURCES.values()):
        inputs = []
        errors = []
        for name, (owner, _) in SOURCES.items():
            if owner != group:
                continue
            manifest = index.get(name, {})
            try:
                raw = read(read_file, name)
                db.execute(
                    "INSERT INTO files VALUES (?,?,?)",
                    (name, raw, hashlib.sha256(raw).hexdigest()),
                )
                metadata(manifest, name, run)
                inputs.append((name, raw, manifest))
            except (Invalid, KeyError, TypeError) as error:
                errors.append(
                    (
                        name,
                        error if isinstance(error, Invalid) else Invalid("SCHEMA"),
                    )
                )
        db.execute("SAVEPOINT source_import")
        for name, raw, manifest in inputs:
            try:
                # Parse even failed sources to retain the exact row pointer when
                # possible, but never accept an authoritative failed manifest.
                import_file(db, name, raw, manifest)
                if manifest["status"] == "failed":
                    raise Invalid(manifest["error_code"])
            except (Invalid, KeyError, TypeError) as error:
                errors.append(
                    (
                        name,
                        error if isinstance(error, Invalid) else Invalid("SCHEMA"),
                    )
                )
        if errors:
            db.execute("ROLLBACK TO source_import")
            failures[group] = errors
        db.execute("RELEASE source_import")
        for name, (owner, _) in SOURCES.items():
            if owner == group:
                m = index.get(name, {})
                error = next((e for n, e in errors if n == name), None)
                code = error.code if error else "SOURCE_ROLLBACK" if errors else ""
                db.execute(
                    "INSERT INTO manifests VALUES (?,?,?,?,?,?,?)",
                    (
                        name,
                        m.get("manifest_id", "missing:" + name),
                        group,
                        "failed" if errors else "success",
                        code,
                        error.pointer if error else "",
                        dump(m),
                    ),
                )
        if errors:
            name, error = errors[0]
            m = index.get(name, {})
            manifest_id = m.get("manifest_id", "missing:" + name)
            refs = ["manifest:" + manifest_id]
            related = ["file:" + name + error.pointer]
            db.execute(
                "INSERT OR IGNORE INTO alerts VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    f"C10|manifest:{manifest_id}",
                    run["run_id"],
                    group,
                    "C10",
                    "critical",
                    error.code,
                    dump(refs),
                    dump(related),
                    run["as_of"],
                    "open",
                ),
            )
    if failures:
        db.execute("UPDATE run SET status='incomplete'")
    db.commit()
    return db


def dependencies(records):
    """Actual source requirements, including asset and posting relationships."""
    result = {scope: set(required) for scope, required in DEPENDENCIES.items()}
    assets = {
        v["asset_id"] for k, v in records.items() if k.startswith("identity:asset:")
    }
    movements = [v for k, v in records.items() if k.startswith("inventory:movement:")]
    for asset in assets:
        aliases = {asset} | {
            v["source_id"]
            for k, v in records.items()
            if k.startswith("identity:asset:") and v["asset_id"] == asset
        }
        required = {"identity", "readings", "inventory"}
        required.update(
            m["source_system"]
            for m in movements
            if m["asset_id"] in aliases and m["source_system"] in {"cargas", "pos"}
        )
        required.update(
            "pos"
            for k, v in records.items()
            if k.startswith("pos:POS:") and v["inventory_asset_id"] in aliases
        )
        required.update(
            "cargas"
            for k, v in records.items()
            if k.startswith("cargas:delivery:")
            and aliases & {v["tank_id"], v["truck_id"]}
        )
        result["C08:" + asset] = required
    result["C08"] = {"identity", "inventory", "readings"}
    result["KPI:inventory"] = {"identity", "inventory", "readings"}
    return result


def unavailable(db):
    """Import eligibility; use one persisted root alert per atomic source."""
    failed = {
        row[0]: json.loads(row[1])
        for row in db.execute(
            "SELECT source,source_refs FROM alerts WHERE check_id='C10'"
        )
    }
    records = {
        key: json.loads(payload)
        for key, payload in db.execute("SELECT record_key,payload FROM records")
    }
    return {
        scope: {
            "status": "not_evaluated" if scope.startswith("C") else "unavailable",
            "source_refs": sorted(
                ref for source in required & failed.keys() for ref in failed[source]
            ),
        }
        for scope, required in dependencies(records).items()
        if required & failed.keys()
    }
