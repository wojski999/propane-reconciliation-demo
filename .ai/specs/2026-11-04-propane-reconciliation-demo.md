# Propane reconciliation demo — specification

Date: 2026-11-04. Status: **Proposed; owner approval required before implementation.**

This PR contains documentation only. Stack is decided; example policies below are demo defaults requiring confirmation before real use. System evidence and limitations: [source-system research](research/2026-11-04-source-systems.md).

## 1. Business case: four questions

**What, and for whom?** A small public demonstration for the owner and accounting/operations team of a propane distributor evaluating daily checks across QuickBooks Online (QBO), Cargas Energy and a POS system. It demonstrates a morning exception report using fictional records, not an integration or a claim of access to the prospect's systems.

**Why does it help?** Staff can start with missing billing, duplicates, unexplained differences and failed imports, and inspect the evidence rather than manually compare every row. Calculations use tested rules and code; Claude helps interpret the already computed results. It is decision support, not a certified audit or automatic accounting correction.

**What do we know / not know?** We know the requested source systems, audit goals, inventory equation and client-control requirement. We do not know the POS vendor, actual Cargas access/export contract, cross-system identifiers, posting policy, tax treatment, settlement timing, inventory measurement quality or appropriate materiality. See research unknowns. Demo mappings and tolerances are explicit assumptions, not verified client policies.

**What is demonstrated / deferred?** Now: deterministic local sample inputs, imports, reconciliations, evidence-linked HTML, alerts and optional Claude narrative. Later: client-approved mappings, read-only access, scheduling, operational monitoring and validation on private data in client-owned infrastructure.

## 2. Scope

### Now

- Local, offline-first synthetic sample files for QBO-shaped objects, Cargas-style tickets/readings, POS activity, prices, movement ledger and import manifests.
- One documented command to generate a scenario, load SQLite, run checks and write an HTML report plus machine-readable computed results and alert records.
- Clean and planted-issue scenarios; committed sample HTML and summary so reviewers need no API key.
- Accounting reconciliation includes journal/deposit evidence as well as invoices and payments.

### Later

Real QBO OAuth/CDC, Cargas exports/API only after access confirmation, vendor-specific POS adapter, read-only production operation, scheduling, private storage, deployment, notifications and approved thresholds. A real bank settlement feed may be needed to establish cash receipt rather than merely accounting agreement.

### Won't

No client data, unrelated company names or research, live credentials, production connections, write-back, invoice creation, automated refunds, autonomous financial decisions, tax advice, full ERP, forecasting, multi-tenant service or web framework. No fabricated claim that the Cargas sample is its documented export schema.

## 3. Decided stack and execution contract

Python 3.12; standard-library CSV/JSON, Decimal, datetime/zoneinfo, sqlite3 and HTML escaping; pytest with coverage.py/pytest-cov; Ruff; GitHub Actions on every PR. Minimal dependency for the Anthropic API only if needed. No server required: report is a self-contained HTML file with local evidence anchors.

Proposed future command: `python -m propane_demo --scenario issues --output output`. Default seed `20261104`, fixed business date `2026-11-03`, business timezone `America/Denver` (El Paso), explicit `--as-of` for reproducible runs. Clean scenario uses the same command with `--scenario clean`. This is a future interface, not an available command in this spec-only PR.

Money: Decimal, USD, explicit cent rounding HALF_UP at line/tax boundaries; serialize decimals as strings, store scaled integers in SQLite. Volume: decimal US gallons, precision 0.001 gallon; no binary floats. Comparisons use unrounded internal scaled values. UTC timestamps carry offsets and are displayed in the business timezone; day intervals are half-open local midnight boundaries converted to UTC, including DST. No currency conversion or guessed timezone.

CI later: `ruff check .`, `ruff format --check .`, `pytest --cov=propane_demo --cov-branch --cov-report=term-missing --cov-report=json --cov-fail-under=100`. Independently assert measured line coverage and branch coverage are each 100%; include generator, CLI, import, rules, rendering and summary/fallback code. Do not implement CI in this PR.

## 4. Sample data and ingestion

Generator is a pure deterministic function of seed, scenario and business date; fixed IDs/order/timestamps, no wall-clock or network dependence. Generate clean data first, then apply named independent mutations. `expected_findings.json` is a separate test oracle, never read by production checks. Each issue also runs independently; combined expectations explicitly list any legitimate cascading findings. Tests compare exact finding sets, not just minimum counts.

### Source contracts

- QBO JSON: collections of Invoice, SalesReceipt, Payment, CreditMemo, RefundReceipt, JournalEntry, Customer, Item and **Deposit**. Preserve `Id`, `SyncToken`, `MetaData.LastUpdatedTime`, `TxnDate`, `DocNumber` where applicable, `CustomerRef`, `TotalAmt`, line IDs/details and `LinkedTxn`. Invoice `Balance`, Payment `UnappliedAmt`/line allocations, item quantity/unit price, discount/tax details and journal debit/credit account references retain their entity-specific structure. Do not pretend every entity shares every field. Refunds/credits are distinct from sales; deposits are not revenue.
- Cargas-style CSV (a demo contract, not a vendor schema): delivery `ticket_id, customer_id, tank_id, truck_id, delivered_at, item_id, gallons, gallon_basis, unit_price, net_amount, status, external_invoice_id, meter_ticket_id`; reading `reading_id, asset_id, observed_at, gallons, gallon_basis, temperature_f, quality, uncertainty_gallons, capacity_gallons`.
- POS CSV: `transaction_id, line_id, occurred_at, customer_id, item_id, quantity, unit, unit_price, net_amount, discount_amount, tax_amount, gross_amount, tender, status, original_transaction_id, settlement_batch_id, inventory_asset_id`. Separate settlement CSV carries `batch_id, settled_at, gross, refunds, fees, net, qbo_deposit_id`. Cylinder count is not automatically gallons: explicit synthetic SKU fill-volume mapping required, with unknown fill excluded and flagged.
- Inventory CSV: `movement_id, occurred_at, asset_id, counterparty_asset_id, movement_type, quantity, gallon_basis, source_system, source_id, transfer_id`. Purchases, internal transfers and customer outflows have distinct types.
- Price list CSV: `price_id, item_id, customer_class, effective_from, effective_to, unit, gallon_basis, unit_price, approved_discount_pct`. Intervals must not overlap for the same key.
- Explicit fictional identity mapping links customer/item/asset IDs and delivery-to-invoice-line relationships; no fuzzy matching by name or amount. Mapping cardinalities allow split invoices and combined delivery billing, with allocations in gallons and money. POS sales are marked as already represented in QBO and in inventory so they are counted once.
- Manifest per source: `run_id, source, file_id, expected_window_start/end, extracted_at, covered_through, status, row_count, error_code`. Include source rows/evidence for failed or empty feeds; empty successful data is distinct from a missing file. Synthetic AR includes an opening balance snapshot, invoices, allocated payments and credits through cutoff; QBO Invoice.Balance is a validation reference, not another additive movement.

Validate required fields, unique source keys, Decimal values, references, statuses, time windows and units before comparisons. Retain input file ID, row number or JSON pointer and immutable raw record for every normalized record. Namespace keys as `source:entity:id[:line]`; identical numeric IDs across systems never collide. Updates use source ID/version; reimport is idempotent. An exact repeated row is an ingestion duplicate and remains evidence even when normalization prevents double counting.

Load into a fresh SQLite database for each scenario/run; atomic per-source import and run status. Failed input is rolled back, its failure manifest persists separately, dependent checks become **not evaluated**, and no stale cached feed may masquerade as today's success. Run/report can still complete with a visible incomplete status and exit code 2. Exit 0 means a complete run (even with business exceptions); 1 means fatal execution failure. Invalid CLI configuration is fatal and explained without a traceback containing secrets.

## 5. Checks catalogue

All findings include `finding_id, check_id, severity, status, business_date, rule_version, actual, expected, delta, threshold, source_refs, related_refs, missing_reference, explanation`. IDs derive from check and sorted evidence keys. Source refs resolve to HTML evidence anchors with raw sample records and file/row/JSON pointer. A missing counterpart has no invented source ID: report the existing record, expected system/type and lookup key. Thresholds below are fictional defaults, versioned with the run.

### C01 — Delivery without billing

Rule: a completed delivery older than the 24-hour billing grace window must have mapped, nonvoid invoice line allocations covering its gallons. Inputs: deliveries, mappings, invoices, manifest completeness. Threshold: unallocated volume >0.001 gal after grace. Severity: high. Evidence: exact delivery ticket ID, meter ticket ID if present, mapping and partial invoice/line IDs; missing invoice lookup key. Exclude cancelled tickets; incomplete invoice feed means not evaluated.

### C02 — Invoice without delivery

Rule: nonvoid propane delivery invoice lines older than 24 hours need corresponding completed delivery allocation. Inputs: invoice item classification, delivery mappings/tickets. Threshold >0.001 unallocated gal. Severity high. Evidence: invoice and line, item, mapping IDs plus missing delivery lookup key. Service fees, deposits and POS/cylinder sales are explicitly classified and excluded.

### C03 — Duplicate transaction

Rule: repeated `(source, entity, Id, version)` is a duplicate import; different IDs sharing the same configured external ticket/payment/POS reference and matching customer, type and amount are a suspected business duplicate. Inputs: raw import and normalized reference index. Threshold: count >1. Severity high; business duplicates are review requests, never auto-deleted. Evidence: all duplicate raw occurrence IDs and transaction IDs. No similarity-only amount/date matching.

### C04 — Price or amount mismatch

Rule: eligible net sale line equals quantity × applicable effective price less approved explicit discounts, rounded to cents; line arithmetic and tax/gross bridge checked separately. Compare delivery billable allocations to matching invoice net lines, allowing split billing. Threshold: absolute difference >$0.01 (exactly $0.01 passes). Inputs: sale lines, delivery allocations, effective prices and tax fields. Severity high. Evidence: delivery/POS/invoice line IDs and price/discount/tax evidence IDs. Missing/ambiguous price or unknown units yields C11, not an invented price.

### C05 — Unusual credit, refund or discount

Rule: flag absolute credit/refund >$100.00, discount >10.00% of prediscount eligible net, or missing original-sale/approval reference for any nonzero credit/refund. Inputs: CreditMemo, RefundReceipt, discounts, approvals, original transactions. Threshold strictly exceeds the amounts above; missing required reference always flags. Severity medium; high for missing original sale. Evidence: exact adjustment/line, original sale where present, approval and policy IDs. These thresholds detect review candidates, not fraud. Credits allocated to AR and cash refunds have separate ledger treatment to prevent double reduction.

### C06 — Unapplied or excess payment

Rule: nonvoid payments older than 24 hours with `UnappliedAmt > $0.01`, or allocations exceeding the invoice's balance immediately before that payment by >$0.01, require review. Replay invoice/credit/payment events in timestamp then stable ID order against an opening snapshot; do not compare historical payment to today's residual balance. Inputs: Payment.Line.LinkedTxn, invoices, credits and opening AR. Severity medium for unapplied, high for excess allocation. Evidence: payment and allocation line, linked invoice/credit IDs, opening snapshot ID. No invoice linkage is interpreted as unapplied, not as a fabricated invoice.

### C07 — POS settlement versus QBO deposit

Rule: for settled batches past the two-business-day posting grace period, expected deposit = captured gross − refunds − processor fees; compare mapped QBO Deposit amounts and their payment/SalesReceipt links. Demo business days are Mon–Fri, no holiday calendar claim. Pending tenders excluded. Threshold absolute difference >$0.01, or missing deposit after grace. Inputs: POS lines, batch, fees/refunds, Deposit/linked payments. Severity high. Evidence: batch, all contributing POS transaction/line IDs, fee/refund IDs, Deposit IDs and links; explicit missing key if absent. No same-day revenue-versus-bank shortcut or cross-batch netting.

### C08 — Inventory balance

Rule per asset and consistent gallon basis: expected closing = opening + purchases + inbound transfers − outbound transfers − customer deliveries − other retail sales. POS transactions representing a delivery are excluded from other retail sales. A bulk-to-truck load is an internal transfer, not a customer delivery. Whole-business consolidation eliminates both sides of transfers; readings and transaction totals are never summed together as outflows.

Inputs: opening/closing readings, movement ledger, delivery/POS allocation and paired transfers. Tolerance: max(2.000 gal, 0.5% of opening + external purchases + inbound transfers); absolute observed-minus-expected beyond tolerance is high severity. Evidence: opening/closing reading IDs, every included movement/ticket/POS line ID, transfer pairs and policy ID; show signed contributions.

Reading endpoints must be within 60 minutes of boundary, basis must match (`observed` or `net_60F`), quality valid, and combined stated endpoint uncertainty no greater than tolerance. Otherwise **sensor uncertain, no verdict**, medium severity, listing readings and reason; no shortage/excess conclusion. Missing readings use C11 and no verdict. Do not calculate temperature correction from an invented factor or assume a fixed percentage-to-gallons tank conversion. Transport/bobtail meter tickets preserve measurement basis.

### C09 — Stale source

Rule: required source `covered_through` is >24 hours behind report cutoff, or reading violates C08 endpoint freshness. Future extraction >5 minutes beyond as-of is invalid metadata. Inputs: manifests/readings and as-of. Severity high for stale required feed, medium for reading uncertainty. Evidence: manifest or reading IDs; report gap duration and impacted checks. Creates an alert. A fresh extraction time with an old coverage watermark remains stale.

### C10 — Import failure

Rule: source missing, unreadable, parse/schema failure, failed extraction status or row-count mismatch creates one source/run alert and prevents dependent verdicts. Threshold: any failure. Severity critical. Evidence: failure manifest ID, file ID and safe error code/row pointer; never raw exception secrets. Produces a prominent top-of-report alert even if all business checks cannot run.

### C11 — Missing/incomplete supporting data

Rule: absent required reference, mapping, price, measurement basis, boundary reading or opening AR prevents that calculation. Inputs: validated records and dependencies. Threshold any required omission. Severity medium, high if it prevents a core KPI. Evidence: exact existing records and missing lookup keys; use synthetic run/manifest reference when no row exists. Report affected KPI/check as unavailable/partial, never zero or pass. Invalid source schema uses C10 instead; avoid duplicate alerts for the same root failure.

### C12 — Accounting posting consistency

Rule: journal debits equal credits within $0.01 per entry; configured clearing-account postings tied to invoice/payment/POS external references agree with the corresponding operational net amounts within $0.01. Do not require a manual JournalEntry for every QBO invoice: native QBO transactions can post directly. Inputs: JournalEntry lines, synthetic account mapping and transaction links. Severity high. Evidence: journal/line/account IDs, related invoice/payment/batch IDs and mapping policy. Missing required configured posting becomes missing evidence, never an assumed debit.

## 6. Planted issue register and clean oracle

Each scenario mutation has a stable ID, isolated evidence and a test with the expected check, severity, delta and source refs. These are planned synthetic IDs, not real records.

- P01 / C01: completed `delivery:D-MISSING` lacks billing after grace; evidence D-MISSING.
- P02 / C02: `Invoice:I-ORPHAN:1` has no delivery; evidence invoice/line and item LPG-DELIVERY.
- P03 / C03: `POS:T-DUP-A:1` and `POS:T-DUP-B:1` share external reference EXT-DUP; both IDs appear. Separate raw-repeat fixture repeats one QBO object with distinct import occurrence pointers.
- P04 / C04: `Invoice:I-PRICE:1`, `delivery:D-PRICE`, `price:PRICE-BASE` show 100 gal × $2.00 versus $210.00 net; delta +$10.00.
- P05 / C05: `CreditMemo:CM-UNUSUAL` credits $150.00 against `Invoice:I-CREDIT`; `POS:T-DISCOUNT:1` has 15% discount. Both review findings expected, with original sale/price evidence.
- P06 / C06: `Payment:PAY-UNAPPLIED` has $25.00 unapplied; `Payment:PAY-EXCESS:1` allocates $110.00 to `Invoice:I-PAY` with $100.00 prepayment balance; excess $10.00.
- P07 / C07: `batch:B-SETTLED` has $500.00 captured, $20.00 refunds, $10.00 fees; `Deposit:DEP-SHORT` has $460.00 versus expected $470.00; delta −$10.00. Include underlying POS/refund/fee IDs in oracle.
- P08 / C08: asset BULK-A `reading:R-OPEN` 1000 gal + `movement:M-PURCHASE` 200 − `delivery:D-OUT` 100 − `POS:T-RETAIL:1` 50 = 1050 expected; `reading:R-CLOSE` 1020 gives −30 gal, tolerance 6 gal. Direct bulk dispensing in this fixture; truck scenario separately verifies transfers cancel.
- P09 / C08: `reading:R-UNCERTAIN` quality uncertain produces sensor-uncertain/no-verdict, no shortage finding.
- P10 / C09: `manifest:QBO-STALE` watermark 25 hours old produces alert and suppresses false missing-invoice conclusions.
- P11 / C10: `manifest:POS-FAILED` represents malformed POS import; alert and dependent POS KPIs/checks unavailable.
- P12 / C11: `delivery:D-NO-MAPPING` has absent customer/item mapping; `asset:TRUCK-NO-READING` lacks closing reading. Both list precise missing keys and no guessed matches.
- P13 / C12: `JournalEntry:JE-UNBALANCED` debits $100.00 and credits $90.00; delta $10.00, both line IDs listed. Separate balanced-but-wrong-clearing fixture tests posting amount mismatch.
- P14 / C05: `RefundReceipt:RR-NO-ORIGINAL` lacks original sale reference; high severity with missing lookup key.

Generator must finalize exact line-level oracle IDs for all contributing records before rule tests are written; no runtime oracle access. The clean fixture contains valid split/combined billing, services without delivery, legitimate equal-value sales, applied payments, approved adjustments, gross/tax/fee bridges, balanced journals, paired truck transfers, valid empty sources and boundary tolerances. Expect **zero findings and zero alerts**, all core checks evaluated. Uncertain/missing feeds are explicit issue fixtures, never hidden inside the clean fixture.

## 7. Morning report and Claude

Top: business date, run ID, complete/incomplete status and import/staleness alerts. KPIs: delivered gallons (completed customer deliveries); other retail gallons; total gallons sold without double counting; net revenue excluding taxes and refunded sales under the explicit scenario policy; AR as of cutoff from opening snapshot plus invoices minus applied credits/payments. Cash sales do not create AR; deposits/payments are not additional revenue. Show source scope, gallon basis, calculation evidence and unavailable/partial labels. Provide reported QBO balance comparison rather than double-counting it.

Prioritize critical/high/medium exceptions, stable sort by check and evidence IDs. Every exception, KPI contribution and alert links to source evidence anchors; missing sources link to the manifest/missing-reference explanation. Include passed/not-evaluated counts and reasons, data freshness per source (window, watermark, extraction time, status), threshold/rule version and reconciliation worksheet. Escape all source and generated text; no remote assets or external record URLs claimed to work.

Claude is an optional final narrative step. It receives **only** the computed, minimal results: finding IDs, severities, preformatted KPI/delta/threshold strings, coverage and quality warnings. No raw customer records, identifiers from real systems or credentials. Instructions prohibit calculation, altered numbers, unsupported causes and invented remedies; request a short plain-English summary citing finding IDs. Treat the response as untrusted text and escape it. The deterministic report remains authoritative; label narrative AI-generated and never ingest it into rules or totals. A minimal response contract validates cited finding IDs; do not claim that validation proves every sentence is correct.

Use `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` from environment; no hard-coded model or committed secrets. Without either value, use a deterministic computed-results summary. API timeout (15 seconds), authentication/rate/network failure, empty/malformed response or unsupported finding reference also falls back, with a visible narrative-status note. No automatic retry loop in the demo. Inject a fake API client in tests; default runs/CI make no network calls. Commit one clearly labeled illustrative Claude summary and corresponding computed sample/report; display it only for its matching scenario digest, never reuse stale narrative for another run. Live Claude use is optional and incurs provider usage in the account supplying the key.

## 8. Alerts

Persist alert records with stable `alert_id, run_id, source, check_id, severity, reason_code, source_refs, observed_at, status`. Import failure and stale required source each produce an alert plus a top-of-report line. Deduplicate per run/source/reason; retain prior-run records only if explicitly exported, not as an implicit live incident service. Sensor uncertainty is visible as an exception. No email/SMS/webhook delivery in the demo. If report rendering fails, print a safe error and preserve computed results/alerts when possible; fatal exit 1 must not claim a successful report.

## 9. Security and ownership

Real version: client owns repository, OAuth app, provider accounts, deployment, credentials, billing and revocation. Request least privilege; QBO's accounting OAuth scope is broad, so do not claim OAuth enforces read-only. Enforce read-only adapter operations, no transaction write endpoints, access controls and client review; confirm supported Cargas/POS privileges. Tokens require protected storage/rotation in a real deployment; env-only secrets suffice for this local demo. Exclude env files, generated databases and local credentials from version control when implemented. Never log secrets or send source exports to Claude. No API credentials or connection requests are needed to review the committed sample. The owner approves the spec and later deployment separately.

## 10. Tests and acceptance

- Unit tests for every rule, traceability, boundary exactly at/just over tolerance, rounding, zero/negative amounts, refunds, voids, late posting, duplicate imports versus updates and distinct legitimate equal-value sales.
- Integration tests generate/import clean and issues datasets into temporary SQLite, run checks, inspect exact oracle finding sets, alert persistence, idempotency and source rollback. Test every mutation alone and combined. Missing/stale feed must never produce a false clean pass or spurious missing-counterpart verdict.
- Inventory tests cover assets/transfers/consolidation, no double counted POS/delivery, different gallon bases, stale/missing readings, excessive uncertainty and exact tolerance.
- KPI tests independently hand-calculate revenue/AR/volume, opening balances, credit/payment ordering, fees/tax and partial data. Date tests cover El Paso day cutoff and DST; malformed metadata must be explicit.
- HTML tests ensure all referenced anchors exist, synthetic source IDs resolve, missing references say missing, hostile source/Claude text is escaped, and no remote assets/secrets leak.
- Optional Claude adapter tests cover success and every fallback using a stub; snapshots normalize no volatile fields and sample narrative matches its digest.
- Acceptance: all named problems caught with exact evidence; zero false positives on clean data; both line and branch coverage 100% for all application modules; Ruff and PR CI green; reproducible offline one-command report without API key; committed sample opens locally; incomplete feeds produce visible alert/no-verdict states and defined exit code. No application code until explicit owner approval.

## 11. Small implementation plan (after approval)

1. Agree fixture contracts, price/timing policies and hand-calculated oracle; implement deterministic generator and its tests.
2. Add validated atomic SQLite import, provenance, manifests and failure alerts with tests.
3. Add billing/payment/accounting/POS checks in small tested increments.
4. Add asset inventory worksheets, uncertainty handling, freshness and missing-data propagation.
5. Add KPI calculation, HTML evidence/report and offline summary; verify clean/issues end-to-end.
6. Add optional Claude adapter/fallback tests, commit matching illustrative output, add CI coverage gates and business README. Fresh review and successful CI before owner decides on merge/deployment.

No real-integration scaffolding, vendor SDKs or deployment infrastructure in these steps.

## 12. Business README outline

- “Start your morning with the transactions that need attention.” Explain missing bills, duplicates, settlement differences and unexplained inventory changes.
- “What the morning report shows.” Screenshot/sample report link, gallons/revenue/AR, prioritized evidence, data freshness and prominent failed-feed warning.
- “Try the sample.” Python 3.12 prerequisite, minimal setup and the single command from section 3; no key needed. Explain where the report appears and that issue findings are deliberately planted.
- “How to trust the numbers.” Tested calculation rules, source links, no verdict with uncertain data; Claude summarizes results.
- “What this demo does not connect to.” Synthetic records, real integrations only after confirming exports, permissions and policies.
- “Your accounts and data remain yours.” Optional key in environment, client-owned deployment; link technical spec/research for interested readers.

## Owner approval and open questions

Approve the scope, fictional thresholds and fixtures before implementation. Client-specific answers are not needed to demonstrate assumptions, but are mandatory before a real integration:

1. Which POS, Cargas version/modules, supported API/report/CSV exports and client permissions exist? What are example sanitized headers and stable cross-system reference IDs?
2. Which system owns invoice/payment/credit/GL posting, and what is the actual Cargas-to-QBO integration and batch granularity?
3. What are billing and settlement delays, price/discount approvals, taxes, deposit fees, AR opening source and posting-day rules?
4. Which assets/readings are available, their gallon basis, calibrated uncertainty, tank conversion tables and accepted inventory tolerances? Are retail fills/exchanges tracked by volume, weight or count?
5. May optional summaries send minimized computed findings to the client's Anthropic account, and which model/retention settings are approved?

Approval record: pending; no implementation authorization recorded.
