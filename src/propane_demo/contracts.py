"""Versioned fictional file contracts; validation/import belongs to step 2."""

CSV_FIELDS = {
    "deliveries.csv": (
        "ticket_id customer_id tank_id truck_id delivered_at item_id gallons "
        "gallon_basis unit_price net_amount status external_invoice_id meter_ticket_id"
    ).split(),
    "readings.csv": (
        "reading_id asset_id observed_at gallons gallon_basis temperature_f quality "
        "uncertainty_gallons capacity_gallons"
    ).split(),
    "pos.csv": (
        "transaction_id line_id occurred_at customer_id item_id quantity unit "
        "unit_price net_amount discount_amount tax_amount gross_amount tender "
        "status original_transaction_id settlement_batch_id inventory_asset_id "
        "external_reference approval_id"
    ).split(),
    "settlements.csv": (
        "batch_id settled_at gross refunds fees net qbo_deposit_id"
    ).split(),
    "movements.csv": (
        "movement_id occurred_at asset_id counterparty_asset_id movement_type "
        "quantity gallon_basis source_system source_id transfer_id"
    ).split(),
    "prices.csv": (
        "price_id item_id customer_class effective_from effective_to unit "
        "gallon_basis unit_price approved_discount_pct"
    ).split(),
}
QBO_ENTITIES = (
    "Invoice",
    "SalesReceipt",
    "Payment",
    "CreditMemo",
    "RefundReceipt",
    "JournalEntry",
    "Customer",
    "Item",
    "Deposit",
)
SCENARIOS = (
    "clean",
    "showcase",
    *(f"P{i:02}" for i in range(1, 15)),
    "raw-repeat",
    "wrong-clearing",
    "issues",
)
