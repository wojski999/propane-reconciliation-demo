# Synthetic fixture contracts, version 1

Issue #4, approved business spec section 11 step 1. All identifiers, accounts,
prices and policies are fictional. This is a demo contract, **not** a Cargas or
POS vendor schema. No real adapter, validator, reconciliation engine or business
CLI is implemented by this step. Findings in the oracle are future acceptance
expectations, never evidence that a check ran.

## Generation and files

`propane_demo.generator.generate(scenario="clean", seed=20261104,
business_date=date(2026, 11, 3))` returns an ordered filename-to-UTF-8-bytes mapping.
The caller owns any writes. No clock, network, random state or filesystem output.
Use `Path(output, name).write_bytes(content)` to export each returned entry.
The installed `propane-smoke` command and foundation artifact remain unchanged.

The seed is an unsigned 32-bit integer and namespaces the run ID; financial values
stay fixed so hand calculations stay inspectable. The business date is a `date`,
not a string/datetime. Timestamps are offset-aware UTC ISO strings shifted relative
to the half-open America/Denver business day; DST yields 23/25-hour days. Inputs
include history from local-day start minus 192 elapsed hours for settlement grace and AR replay. QBO TxnDate
is a posting date, EventAt is explicit synthetic event chronology. The opening AR
snapshot is at local-day start minus 192 hours; business reporting window remains local day.
Generation supports [2020-01-01, 2035-01-01) and rejects other dates with
ValueError. Prices begin in 2019 to cover prior-day/history records even at the
first supported business date; they end exclusively at 2035-01-01.

JSON keys sort lexically, arrays retain explicit source order, CSV follows the
ordered columns declared in `CSV_FIELDS`, newline is LF and files end in LF.
Money/volume are decimal strings; money has two fractional places, gallons three.
Decimal HALF_UP rounds line/tax amounts at cents; scaled SQLite integers belong
to the later import step. No financial float, currency conversion or inferred basis.
Boundary answer vectors are test-only; generated application inputs contain no boundary verdicts or configured expected operational net.

## Source entities

QBO JSON has separate Invoice, SalesReceipt, Payment, CreditMemo, RefundReceipt,
JournalEntry, Customer, Item and Deposit arrays. All retain Id, SyncToken and
MetaData.LastUpdatedTime. Transaction entities retain TxnDate, TotalAmt, Line and LinkedTxn. DocNumber and
CustomerRef are retained where applicable; Payment uses PaymentRefNum, and
JournalEntry/Deposit have no invented top-level CustomerRef; Customer/Item do not pretend to have transaction
amounts. CustomerClass and Item.Classification are synthetic contract extensions.
Invoice alone carries Balance. Payment carries UnappliedAmt and allocation lines
with Amount and LinkedTxn. Sale/adjustment lines carry Id, Amount, DetailType and
SalesItemLineDetail with ItemRef, Qty, UnitPrice and TaxCodeRef; explicit discounts
and approvals are additional fields. TxnTaxDetail carries TotalTax and tax lines.
Credit/Refund links preserve original entity/type; AppliedAmount distinguishes
credit application from cash refund. RevenueEvent prevents repeated adjustment
recognition. Journal lines carry PostingType and AccountRef; DepositLineDetail
carries account and linked native transaction IDs. Deposit is never revenue.
Synthetic EventAt supplies deterministic AR ordering, then stable ID.

CSV delivery/reading, POS, settlements, movements and prices retain every column
from business spec section 4; `CSV_FIELDS` is the executable ordered header
contract. POS additionally retains external_reference and approval_id for business
duplicates and discount approval. Empty optional values are empty strings, never
invented source IDs. POS negative rows marked refunded retain their original sale.
Pending/void POS and cancelled deliveries are excluded by future consumers.

Inventory movement quantities are positive magnitudes; movement_type supplies
sign: purchase/transfer_in positive, transfer_out/customer_delivery/retail_sale
negative. Crosswalked POS deliveries are already represented in customer outflows.
Paired transfer X-1 has opposite assets, equal quantities and identical basis;
consolidation eliminates both sides. `identity.assets` defines measured assets;
`policies.unmeasured_assets` explicitly excludes UNMEASURED from sensor verdicts.
Adding an asset mapping without a closing reading (P12) requires unavailable
inventory, not zero. No basis or fill volume is inferred. Cylinder SKU is explicitly
5.000 gallons; unknown fill must be unavailable when introduced by import tests.

Identity JSON contains explicit customer/item/asset maps, many-to-many delivery
allocations (mapping_id, delivery_id, invoice_id, line_id, gallons, net_amount),
POS event crosswalks with inventory_counted, SKU fill volumes, approvals, and a
posting_map tying a configured journal clearing account to an operational invoice.
No fuzzy matches. Allocations A-SPLIT-A/B cover one delivery; A-COMB-A/B cover
one invoice. T-EQUAL-A/B are separate legitimate equal-value events.

Opening AR has snapshot_id, as_of and per-customer opening amount; invoice gross,
applied credits and allocated payments are replayed after that snapshot. Invoice
Balance is only a reference. Unapplied money and cash refunds do not reduce AR.

Each manifest retains manifest_id in addition to the section-4 required fields.
row_count is logical CSV data records (including exact repeats, excluding blank
lines) / JSON array records; QBO sums entity arrays;
identity and opening-AR JSON count top-level members (not normalized rows).
Updates are distinct source versions; the UPDATES-OK manifest counts records, not wrapper members. Raw-repeat preserves both physical pointers.
P11 deliberately emits a short malformed POS row and a failed CSV_SCHEMA manifest;
its declared count is one physical row. Successful empty optional JSON is [].
Manifest failure is authoritative, even if other files remain parseable.

## Evidence and oracle

The separate test-only `tests/fixtures/expected_findings.json` freezes exact
finding IDs, status, severity, values, thresholds, missing lookup keys and sorted
source/related references for all 18 scenarios. Application package data contains
only the source template and named patches; it never imports or reads the oracle.
Future consumers must independently compute and compare exact finding sets.

Evidence keys are `source:entity:id[:line]`; qbo entities preserve capitalization,
while source names are qbo/cargas/pos/prices/inventory/identity/ar. Manifest keys
are `manifest:<id>`; policy keys `policy:POLICY-1`; raw pointers
`file:qbo.json#/Invoice/<zero-based-index>` preserve distinct occurrences.
QBO object/line refs resolve to JSON pointers, CSV refs to immutable file/row.
Derived keys: meter_ticket refers to its delivery field, fee uses batch ID + fees,
account comes from journal/deposit account references, version from Id/SyncToken,
and external_reference comes from the POS field. Missing references describe the
lookup without manufacturing a counterpart record. Finding ID is check ID joined
with sorted primary evidence keys using `|`; related refs do not change identity.
C04 coalesces the price/allocation mismatch for the same invoice line into one
finding. C05 coalesces a crosswalked POS/QBO discount event into one finding. P05
explicitly approves 15% on its effective price/approval record while the separate
unusual-discount review threshold stays 10%; therefore no extra C04 mismatch.

## Inventory and calculations

- BULK-A: 1000 + 200 purchase - 100 D-OUT - 50 T-RETAIL = 1050 gallons;
  tolerance max(2, .005 × 1200) = 6. P08 changes closing to 1020: delta -30.
- ISOLATED: 1000 - (100 + 100 + 50 + 50 + 20 + 30 + 50) - 5 = 595.
- DEPOT: 500 - 50 = 450; TRUCK-A: 100 + 50 = 150; net transfer effect zero.
- BOUNDARY: 1000 expected, 1005 observed, tolerance 5; uncertainty 2.5 + 2.5 = 5;
  endpoints exactly 60 minutes from boundaries. Equality passes.
- P04: 100 × 2 = 200 expected, 210 invoice, +10. P05: credit 150 exceeds 100
  by 50; discount 15/100 = 15%, five percentage points over 10%.
- P06: prepayment invoice 100, allocation 110, +10; other payment has 25 unapplied.
- P07: 500 gross - 20 refunds - 10 fees = 470, deposit 460, -10.
- P13: debit 100 - credit 90 = +10; wrong-clearing: debit/credit 90 balance,
  but clearing expected 100 gives -10. No manual journal required for other sales.

Clean includes exact one-cent price/unapplied boundaries, $100 credit/refund,
10% approved discount, exact 24-hour delivery/invoice/payment grace, real fractional
gallons, void/cancelled/zero/negative refund, tax bridge and paired transfers.
Additional test-only boundary vectors describe freshness, fee/grace and cent HALF_UP cases
for later rule tests; they do not ship in generated inputs.

## Scenario inventory and cascades

clean; P01 missing bill; P02 orphan invoice; P03 business duplicate; P04 price;
P05 credit and discount; P06 unapplied and excess; P07 short deposit; P08 inventory;
P09 uncertain reading; P10 stale QBO; P11 malformed POS; P12 mapping and reading;
P13 unbalanced journal; P14 refund without original; raw-repeat; wrong-clearing;
issues (P01–P14 in numeric order). Raw-repeat/wrong-clearing are independent,
not applied on top of P13. Manifest counts update after mutations; each call
loads a fresh template so mutating one scenario cannot contaminate another.

In combined issues, stale QBO suppresses QBO-dependent billing, money, posting
and adjustment verdicts; failed POS suppresses POS duplicate/price/settlement and
BULK-A and ISOLATED shortages. P09 uncertainty and P12 missing reading/mapping remain visible.
There are exactly five findings (C08 uncertainty, C09, C10, two C11), two alerts;
no false missing-counterpart conclusions or shortage from a failed feed. Oracle
lists not-evaluated scopes and legitimate cascades explicitly. Future rule tests
may refine this contract only with explicit fixture/oracle review together.

## Chronology and input isolation (review remediation)

`@start_hour:N` and `@end_hour:N` are elapsed UTC-hour offsets from the two
local-midnight boundaries. `@hour:N` is explicitly an elapsed offset from cutoff;
`@day:N` is a posting-date offset from the requested business date. Current
inventory movements, their delivery/POS sources, and most sale/revenue records
occur at start + 2 hours on every supported day. Opening/closing readings bracket
these movements; BOUNDARY readings sit exactly start - 1 hour and end - 1 hour.
The reading manifest ends at cutoff; no observation follows extraction or as-of.
All other history manifests start at start - 192 hours and finish at cutoff.

Intentional elapsed-time vectors: D-GRACE, I-GRACE and PAY-GRACE are exactly
24 hours old. On a 23-hour day they precede local midnight; on a 25-hour day they
are one hour after it. P10's watermark is exactly 25 hours old and therefore
coincides with midnight on a 25-hour day. Their local-day membership intentionally
changes; age and non-due/stale meaning do not. Historical D-MISSING and I-ORPHAN
are 30 hours old and remain before the business day. These distinct unmeasured
billing examples never add a current inventory movement.

I-CREDIT, I-PAY and I-PAID are advance invoices at cutoff - 36 hours for their
current-day mapped deliveries. CM-BOUNDARY/CM-UNUSUAL and PAY-APPLIED precede
cutoff by 29 hours; PAY-EXCESS by 28 hours. Each is strictly after its invoice.
This is explicit synthetic advance billing, not a policy inferred from real data.
Other current-day sale lines supply nonempty daily revenue and volume inputs.

B-SETTLED sales at start - 150 hours and refund at -149 hours precede settlement
at -144 hours. The deposit at -120 hours follows settlement. Six elapsed days
before day start leaves more than two Mon-Fri business days before cutoff on
every tested weekday, including DST transition/adjacent days. SR-BATCH and
RR-BATCH mirror these historical POS events and do not create current revenue.
DEP-SHORT lines bridge 500 gross, -20 refund and -10 processor fee; P07 adds a
separate -10 settlement variance line, yielding 460. The comparison uses the
whole mapped deposit, while line 1 remains its stable primary evidence anchor.

T-DELIVERY is a captured representation of I-OUT, not a second sale. Its identity
crosswalk names PAY-DELIVERY, which allocates the same 200 to I-OUT at start + 3
hours, leaving Invoice.Balance zero. Consumers recognize invoice revenue once,
payment as AR/cash movement only, and D-OUT as the single inventory outflow.
I-VOID retains the synthetic status marker but its total, balance, line amount and
quantity are zero; excluding it or summing reported balances cannot inflate AR.

`updates.json` is a required QBO replay stream in the same atomic source import
as qbo.json, covered by UPDATES-OK. Its wrapper identifies entity Customer;
row_count counts `records`. Import qbo.json's base version, then replay records
by Id and numeric SyncToken; the repeated version 0 is byte-equivalent, hence
idempotent, and version 1 replaces it rather than adding another customer. Retain
both raw pointers as provenance. Missing/invalid stream or manifest fails that
source, never silently drops the update. This defines ingestion for issue #5;
no importer is implemented here.

posting_map carries linkage/account IDs only: derive operational net from the
linked invoice lines. Boundary answer vectors live only in tests. Architecture
and package-data tests prohibit application access to the oracle and restrict
shipped data to the source template. Numeric oracle assertions independently
calculate actual, expected, delta and thresholds from source/policy records;
consistent-but-wrong P07 and P13 oracle mutations must be rejected.


Posting-date policy: TxnDate is an explicit accounting posting date, not derived
from the local calendar date of EventAt. DEP-SHORT retains its start-relative
posting date when its elapsed-hour event crosses DST. I-GRACE/PAY-GRACE likewise
retain their explicit posting dates. I-CREDIT/I-PAY/I-PAID post on the previous
day for current-day deliveries: future daily KPI tests must separate their prior-day
revenue from current-day delivered gallons, rather than force event parity.

Every source timestamp is within its declared window, no later than extraction
and as-of plus future_max_minutes. Coverage lies within the declared window and
no later than extraction. Only P10's QBO covered_through is deliberately stale;
its newer records still obey window, extraction and future-time constraints.


## Step-2 ingestion representation

The importer now enforces the version-1 fictional boundaries. Its disposable
SQLite schema is recreated in memory for each invocation; there is no persistent
database format or migration. The smoke CLI/artifact contract remains unchanged.
Raw bytes are stored as immutable BLOBs with SHA-256; occurrences retain source
file and physical row / zero-based JSON pointer. Normalized JSON uses integer
cents and thousandths of gallons (temperature/discount percent: thousandths).
The `scaled_values` table additionally stores each numeric field as a typed SQLite
INTEGER with its scale, record/version and nested field pointer. No rounding or
binary float is accepted at import. Effective price intervals for
the same item/class/unit/basis must not overlap. Unknown units/statuses and
malformed reference syntax are source failures; absent supporting matches remain
missing lookup evidence for later C11 rather than guessed matches.

QBO source atomicity includes both base collections and the required update stream.
Exact same-version rows retain distinct occurrences, while the same physical file
replay is idempotent. Conflicting content at a source ID/version fails the source.
The highest numeric version owns current records/lines; previous versions and
raw occurrences remain available without double counting. Each other manifest
source is atomic independently. A failure rolls back normalized records, versions
and occurrences, preserving original file bytes, a failed manifest and one C10
critical alert. Successful empty feeds are different from missing/unreadable,
malformed, failed or wrong-row-count feeds.

Import status is complete/incomplete; it is not a freshness/business verdict.
The later C09 engine consumes actual manifest watermarks. Failure availability
is derived from declared source dependencies and real asset movement links,
never test-oracle suppression lists. This API does not implement findings, C11
matching, business reconciliation, KPI arithmetic or reporting.

Synthetic demo severity clarification: an unavailable asset inventory quantity is
a core inventory KPI under the existing C11 policy, hence P12 missing boundary
readings have high severity. This documents the already approved fixture/oracle
interpretation; it creates no new client policy or inventory calculation.


## Step-2 review corrections (PR #11)

CSV occurrence pointers use the physical **ending line** of each data record,
from `csv.DictReader.line_num`; blank lines consume physical line numbers but do
not add records. A quoted multiline record points to its closing line. Invalid
multiline identifier fields fail at that same ending line. Raw file bytes remain
the authoritative evidence. Exact repeated CSV records retain separate immutable
occurrences under one version/current record; repeated price rows do not create
an overlapping interval. Differing content at the same CSV key is a source failure.
The occurrences grouped by record_key/version expose duplicate evidence for future
C03; this importer does not evaluate C03.

Identity collections reject unknown row keys. Required keys remain as documented
above; only pos_events.delivery_id/payment_id and approvals.approved_discount_pct
are optional. Opening AR accepts exactly snapshot_id/as_of/balances, with exactly
customer_id/amount in each balance. Customer/Item cannot carry transaction Line.
Source parsing recursion failures are safe JSON_SCHEMA failures; unusable manifest
indexes fail closed for all groups while raw bytes and failure manifests survive.
Invalid control metadata remains fatal. A fatal expected import/storage boundary
closes the allocated connection before propagating the error.

Synthetic absent-manifest IDs use `missing:<file>`, a namespace impossible for
validated real manifest identifiers. A higher QBO parent version clears current
child records **and their reference requirements**; older replay preserves raw
history without restoring deleted current records/references.

P11 suppresses only the asset-specific inventory checks in the reviewed oracle;
it does not suppress the whole inventory KPI. Whole-scope identity/inventory/
readings failures retain whole inventory unavailability. Oracle contents remain
unchanged and test-only.

## Step-3 pure rule boundary

`rule_inputs.from_database(db, blocked=None)` detaches validated current scaled
records and immutable occurrence references from the disposable import. The pure
`rules.reconcile(inputs)` API returns step-3 findings and `not_evaluated` reasons;
it does not write to SQLite, render, invoke a CLI, read fixtures or use a network.
The importer remains the validation boundary; direct callers must use that same
validated representation (integer cents, thousandths of quantities/percentages).

Implemented scope is C01–C07/C12 plus required supporting C11 for those checks.
C08/C09, inventory C11, alerts/report aggregation and all KPI computation remain
later steps. `freshness_evaluated` is always false here. The optional `blocked`
scope mapping accepts future freshness results with their evidence; no staleness
is inferred or claimed by this step. Import-failure scopes are supplied by the
adapter, including unavailable source groups, so root C10 failures do not cascade
into guessed missing-reference verdicts. Per-record C11 reasons mark only the
calculation that lacks support; other independent comparisons still run.

The oracle tests compare every section-5 field except explanation wording for all
applicable independent scenarios. P10 and combined `issues` tests explicitly inject
P10's future blocked scopes; they do not implement/test C09's detection algorithm.
P12's delivery mapping C11 is applicable; its missing inventory reading is deferred.
Additional tests directly exercise combined failures without injected freshness.

Money is computed with Decimal HALF_UP at line boundaries, with enough local
precision for products of validated signed 64-bit scaled values. Comparisons use
unrounded differences. Percent strings retain small nonzero threshold excesses.
Taxes are bridged from explicit TotalTax/TaxLine and POS net/tax/gross fields;
no absent tax rate is invented. Allocation money is checked both against invoice
net and the proportional delivery billable net, including split/combined billing.

AR replays events after opening snapshot through as-of in timestamp/stable-ID
order. Opening customer balances establish opening coverage, not invented
per-invoice residuals: an allocation to an invoice predating the opening snapshot
needs missing per-invoice support (C11). Reported Invoice.Balance is never used as
historical prepayment balance. AppliedAmount credits reduce AR once; a Payment
line cross-referencing that credit does not become additional cash. Ambiguous
multi-credit, mixed/over-capacity credit or invoice links get C11, without guessed
allocation. Unlinked cash yields one payment-level unapplied finding with its
allocation lines as related evidence. Cash refunds do not reduce AR.

Batch grace preserves the settlement's Denver local time while counting Mon–Fri
business dates; exactly two days passes, the first instant beyond is due. Each
batch derives expected deposit from its captured/refunded POS lines less explicit
fees. Deposit totals, line totals, expected transaction links and linked amounts
are checked separately; pending/void POS and void deposits are excluded.
Configured journal clearing amounts derive from linked operational records;
no expected operational amount or manual journal requirement is introduced.

## Step-3 review clarifications

C02 distinguishes absent/inactive deliveries from existing completed deliveries
whose identity mapping is unavailable. The latter reuse the delivery's C11 root
and mark each allocated invoice line not evaluated, including split billing.
An ambiguous item measurement basis likewise produces C11 rather than selecting
an arbitrary first mapping.

C04 limits the eligible discount to the lesser of explicit approval and price
policy. An existing approval that is exceeded still supplies a computable price:
compare actual net with quantity times effective price less the approved discount.
Missing approval remains C11. Tax and gross bridges are independent findings.
The tax primary ref is the current parent's immutable file/JSON pointer followed
by `/TxnTaxDetail/TotalTax`; tax-line pointers and the parent are related evidence.
Gross uses the existing parent record. These refs resolve inside retained raw JSON,
without invented source records or a new evidence registry. Tax lines need no Id.

C07 amount comparisons do not require successful transaction-link comparison.
Absent targets produce C11 for that link scope; existing unexpected/foreign or
omitted expected links produce high C07 with the existing batch, deposit and
immutable deposit `/Line` pointer as primary evidence. Linked record amounts,
deposit total/line sum, batch gross/refund/net and expected settlement amount
remain separate comparisons, never cross-batch netting. Existing derived
`pos:component:<batch>:gross|refunds|net` refs resolve to the corresponding fields
of `pos:batch:<batch>` and its immutable occurrence; fee refs resolve to its fees.
All related native transaction refs name existing records; absent IDs belong in
missing_reference, not fabricated anchors. A conflicting finding ID raises an
explicit deterministic ValueError; only identical full findings deduplicate.

C06 reports incremental excess against max(prior signed balance, zero); it keeps
the signed replay balance and event history, and a new allocation of at most one
cent cannot create another excess finding. Unapplied cash does not depend on an
opening customer balance; missing customer coverage still blocks AR replay.
C06 and C12 share cash computation: linked non-credit cash plus unapplied cash.
Unlinked lines and UnappliedAmt can describe the same unapplied amount, so use
the maximum (also TotalAmt when there are no links), never add those twice.
Credit cross-references remain noncash and cannot reduce AR a second time.

The synthetic configured clearing account is **debit-positive**: debit amounts
are positive and credit amounts negative. Operational amounts use the same sign.
This is an explicit demo posting assumption, not a configurable client policy.

## Shared evidence identity (PR 12 re-review)

Clearing C12 primary refs include the explicit `identity:posting:<mapping_id>`
and clearing journal line keys. Several posting mappings may share one journal
and account without merging their independent operational comparisons. This
refines the internal step-3 finding identity; the independent oracle file remains
unchanged, with the test explicitly adapting this primary/related ref promotion.
C07 linked-line comparisons include `pos:batch:<batch_id>` alongside deposit line
and linked transaction keys. A combined deposit is still checked independently
against each mapped batch; no cross-batch allocation or netting is inferred.
Absent native links mark only `C07:<batch-key>:links` not evaluated: amount checks
that have sufficient evidence still run. Conflicting full findings with identical
IDs remain an engine error, never an overwrite. C04 bridge eligibility uses the
configured `price_tolerance`, including when it differs from the demo cent default.

## Step-4 inventory and freshness boundary

`rules.reconcile(inputs)` now evaluates the actual source watermarks before all
implemented checks (C01–C12); `freshness_evaluated` is true. The detached input
contains validated manifests, persisted alerts and record-derived dependencies.
`rule_inputs.reconcile_database(db)` orchestrates that pure function and persists
its alerts idempotently in the existing disposable database. It does not render,
compute KPIs, perform IO outside SQLite, or call a network. C10 owns invalid
metadata, including extraction beyond as-of plus five minutes; no C09/C11 root
is added for the same failed source. C09 compares coverage with report as-of,
not extraction time, and retains one worst-watermark alert per atomic source/run.
Reading endpoint freshness is expressed as the C08 sensor-uncertain exception;
quality and uncertainty likewise cannot produce a shortage/excess verdict.

`inventory` contains one worksheet per explicitly measured asset, signed
`contributions`, immutable source keys, basis, expected/observed/delta/tolerance
and evaluated/not-evaluated/sensor-uncertain state. A blocked worksheet retains
known signed `ledger_inputs` without claiming an expected total. Source records
validate ledger outflows; a POS delivery representation contributes zero rather
than another outflow. Retail count conversion requires the explicit SKU fill
mapping and the ledger's stated basis. No temperature conversion exists.
`consolidation` removes paired transfer contributions and is unavailable if any
asset is unavailable/uncertain or bases cannot be combined. Per-asset exceptions
remain visible even if their deltas offset in consolidation. This is inventory
arithmetic only; revenue, AR and sales-volume KPI arithmetic remains step 5.

Blank CSV gallon_basis is a missing-support value retained for C11. An unknown
nonblank basis remains a C10 schema failure. Missing or ambiguous endpoints,
unknown SKU fill, incompatible ledger bases, incomplete transfer pairs and inconsistent
ledger/source evidence use exact existing refs and lookup keys, never guessed
volume. Transfers are validated before either endpoint asset is compared.

The full literal 18-scenario oracle is now compared without injecting future
freshness scopes. The reviewed C12 primary posting mapping is promoted in the
literal oracle and checked explicitly, with unchanged amounts/thresholds. P10's
eligibility contract additionally lists C04:pos (QBO customer price class) and
C05:pos:POS:T-REFUND:1 (QBO approval), dependencies already established by the
step-3 source-failure tests. In combined issues, the whole failed C05:pos scope
subsumes that per-refund scope. No business expected values or planted findings
change. Future KPI unavailable scopes are eligibility, not computed KPI results.


### PR 14 review corrections

A ledger outflow linked to a non-completed delivery or non-captured POS line is
conflicting support: C11 `movement_source_status` includes both existing movement
and source refs, and a source lookup with `expected_status:completed` or
`expected_status:captured`. The asset and inventory KPI remain unavailable; signed
known ledger inputs remain visible. No shortage/excess total is inferred.
Present endpoint bases that differ follow approved C08: medium sensor uncertainty,
with both readings, no conversion, no expected/observed/delta/tolerance claimed.
A missing endpoint basis remains high C11; a ledger basis conflict remains C11.

Step 5 handoff: blank basis on an unmeasured-asset delivery currently has no C11
from inventory. Delivered-volume KPI must mark that input partial rather than
silently including or excluding it. This step implements no KPI arithmetic.
C09 gap durations retain Decimal precision (80-digit working context), including
subsecond watermark differences. Future HTML must format durations for people
without changing exact threshold comparisons or source evidence. No new renderer
or formatting option is introduced here.
