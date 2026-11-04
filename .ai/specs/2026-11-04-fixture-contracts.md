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
row_count is physical CSV rows / JSON array records; QBO sums entity arrays;
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
