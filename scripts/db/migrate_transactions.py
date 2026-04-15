#!/usr/bin/env python3
"""
RAITO — Phase 2: Historical Transaction Migration

Runs the existing parsers (parse_all_icedreams, parse_all_mayyan, parse_all_biscotti)
and writes the parsed data into the sales_transactions table.

Usage:
    cd scripts && python3 db/migrate_transactions.py

Requires:
    - PostgreSQL with schema.sql applied and Phase 1 seed data loaded
    - psycopg2: pip install psycopg2-binary
    - Environment variable DATABASE_URL or defaults to local dev

Idempotency:
    Uses ingestion_batches(source_file_name, distributor_id) unique index
    (WHERE status='complete') to skip already-ingested files.

Reconciliation:
    Prints a comparison table at the end showing SQL totals vs. the known
    benchmarks from RAITO_BRIEFING.md.
"""

import os
import sys
from pathlib import Path
from datetime import date, datetime

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import psycopg2
from psycopg2.extras import execute_batch

from parsers import (
    parse_all_icedreams, parse_all_mayyan, parse_all_biscotti, consolidate_data,
    parse_karfree_inventory, get_distributor_inventory,
)
from pricing_engine import (
    get_b2b_price_safe, get_production_cost, get_customer_price,
    PRODUCTION_COST,
)
from config import extract_customer_name, MONTH_ORDER

# ═════════════════════════════════════════════════════════════════════════════
# Connection
# ═════════════════════════════════════════════════════════════════════════════

DEFAULT_DB_URL = "postgresql://raito:raito@localhost:5432/raito"


def get_connection():
    url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# Lookup caches (loaded once from DB)
# ═════════════════════════════════════════════════════════════════════════════

_product_cache = {}      # sku_key → id
_customer_cache = {}     # name_en → id
_distributor_cache = {}  # key → (id, commission_pct)


def load_caches(cur):
    """Load reference table IDs into memory for FK resolution."""
    global _product_cache, _customer_cache, _distributor_cache

    cur.execute("SELECT id, sku_key FROM products")
    _product_cache = {sku: pid for pid, sku in cur.fetchall()}

    cur.execute("SELECT id, name_en FROM customers")
    _customer_cache = {name: cid for cid, name in cur.fetchall()}

    cur.execute("SELECT id, key, commission_pct FROM distributors")
    _distributor_cache = {key: (did, float(pct)) for did, key, pct in cur.fetchall()}


def resolve_product(sku):
    """Resolve SKU string to product ID. Returns None for unknown."""
    return _product_cache.get(sku)


def resolve_customer(name_raw, source_chain=None):
    """Resolve a raw branch/chain name to customer ID.

    Uses extract_customer_name() (same logic as the dashboard) to normalize,
    then looks up in the customer cache.
    """
    name_en = extract_customer_name(name_raw, source_customer=source_chain)
    if not name_en:
        return None, name_en
    cid = _customer_cache.get(name_en)
    return cid, name_en


def resolve_distributor(key):
    """Resolve distributor key to (id, commission_pct)."""
    return _distributor_cache.get(key, (None, 0.0))


# ═════════════════════════════════════════════════════════════════════════════
# Month → date helpers
# ═════════════════════════════════════════════════════════════════════════════

MONTH_TO_DATE = {
    'November 2025': date(2025, 11, 1),
    'December 2025': date(2025, 12, 1),
    'January 2026':  date(2026, 1, 1),
    'February 2026': date(2026, 2, 1),
    'March 2026':    date(2026, 3, 1),
    'April 2026':    date(2026, 4, 1),
}

MONTH_TO_NUM = {
    'November 2025': (2025, 11),
    'December 2025': (2025, 12),
    'January 2026':  (2026, 1),
    'February 2026': (2026, 2),
    'March 2026':    (2026, 3),
    'April 2026':    (2026, 4),
}


# ═════════════════════════════════════════════════════════════════════════════
# Batch management
# ═════════════════════════════════════════════════════════════════════════════

def create_batch(cur, source_file, distributor_id, file_format=None, period=None):
    """Create an ingestion_batches row. Returns batch_id or None if already exists."""
    # Check if already ingested (idempotency guard)
    cur.execute("""
        SELECT id FROM ingestion_batches
        WHERE source_file_name = %s AND distributor_id = %s AND status = 'complete'
    """, (source_file, distributor_id))
    existing = cur.fetchone()
    if existing:
        return None  # already ingested

    cur.execute("""
        INSERT INTO ingestion_batches (source_file_name, distributor_id, file_format, reporting_period, status)
        VALUES (%s, %s, %s, %s, 'processing')
        RETURNING id
    """, (source_file, distributor_id, file_format, period))
    return cur.fetchone()[0]


def complete_batch(cur, batch_id, record_count):
    """Mark a batch as complete with its record count."""
    cur.execute("""
        UPDATE ingestion_batches
        SET status = 'complete', record_count = %s, completed_at = NOW()
        WHERE id = %s
    """, (record_count, batch_id))


def fail_batch(cur, batch_id, error_msg):
    """Mark a batch as failed."""
    cur.execute("""
        UPDATE ingestion_batches
        SET status = 'failed', error_message = %s, completed_at = NOW()
        WHERE id = %s
    """, (str(error_msg)[:1000], batch_id))


# ═════════════════════════════════════════════════════════════════════════════
# Transaction insertion
# ═════════════════════════════════════════════════════════════════════════════

INSERT_SQL = """
    INSERT INTO sales_transactions (
        transaction_date, week_number, year, month,
        product_id, distributor_id, customer_id, sale_point_id,
        units_sold, revenue_ils, unit_price_ils, cost_ils,
        gross_margin_ils, distributor_commission_ils,
        is_return, is_attributed, revenue_method,
        ingestion_batch_id, source_row_ref
    ) VALUES (
        %(transaction_date)s, %(week_number)s, %(year)s, %(month)s,
        %(product_id)s, %(distributor_id)s, %(customer_id)s, %(sale_point_id)s,
        %(units_sold)s, %(revenue_ils)s, %(unit_price_ils)s, %(cost_ils)s,
        %(gross_margin_ils)s, %(distributor_commission_ils)s,
        %(is_return)s, %(is_attributed)s, %(revenue_method)s,
        %(ingestion_batch_id)s, %(source_row_ref)s
    )
"""


def build_transaction_row(
    month_str, product_sku, units, revenue,
    dist_id, commission_pct, customer_id, batch_id,
    revenue_method='actual', source_row_ref=None,
):
    """Build a single transaction parameter dict for insertion.

    Args:
        dist_id: Integer distributor ID (already resolved from distributors table).
        commission_pct: Float commission percentage for the distributor.
    """
    product_id = resolve_product(product_sku)
    if product_id is None:
        return None

    year, month_num = MONTH_TO_NUM.get(month_str, (2026, 1))
    tx_date = MONTH_TO_DATE.get(month_str, date(2026, 1, 1))
    prod_cost = get_production_cost(product_sku)

    cost = round(abs(units) * prod_cost, 2) if units != 0 else 0
    gross_margin = round(revenue - cost, 2) if revenue > 0 else round(-abs(cost) + revenue, 2)
    commission = round(abs(revenue) * commission_pct / 100.0, 2)
    unit_price = round(revenue / units, 2) if units != 0 else None
    is_return = units < 0

    return {
        'transaction_date': tx_date,
        'week_number': None,
        'year': year,
        'month': month_num,
        'product_id': product_id,
        'distributor_id': dist_id,
        'customer_id': customer_id,
        'sale_point_id': None,  # Phase 2 doesn't populate sale_points yet
        'units_sold': units,
        'revenue_ils': round(revenue, 2),
        'unit_price_ils': unit_price,
        'cost_ils': cost,
        'gross_margin_ils': gross_margin,
        'distributor_commission_ils': commission,
        'is_return': is_return,
        'is_attributed': customer_id is not None,
        'revenue_method': revenue_method,
        'ingestion_batch_id': batch_id,
        'source_row_ref': source_row_ref,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Distributor-specific migration
# ═════════════════════════════════════════════════════════════════════════════

def migrate_icedream(cur, data):
    """Migrate Icedream parsed data.

    Icedream data shape (from parse_all_icedreams):
        {month_str: {
            'totals': {product: {'units': int, 'value': float, 'cartons': float}},
            'by_customer': {customer_name: {product: {'units': int, 'value': float, 'cartons': float}}}
        }}

    Strategy: insert per-customer rows (attributed). Then check for unattributed
    remainder (totals - sum(by_customer)) and insert as unattributed if any.
    """
    dist_id, commission_pct = resolve_distributor('icedream')
    total_rows = 0

    for month_str, mdata in sorted(data.items(), key=lambda x: MONTH_ORDER.get(x[0], 99)):
        if month_str not in MONTH_TO_DATE:
            print(f"    Skipping unknown month: {month_str}")
            continue

        batch_id = create_batch(
            cur, f"icedream_{month_str}", dist_id,
            file_format='format_a_xlsx', period=month_str,
        )
        if batch_id is None:
            print(f"    {month_str}: already ingested, skipping")
            continue

        rows = []
        by_customer = mdata.get('by_customer', {})

        # 1. Attributed rows (per-customer)
        customer_product_units = {}  # track for unattributed remainder
        for cust_raw, products in by_customer.items():
            cust_id, cust_en = resolve_customer(cust_raw)
            for sku, vals in products.items():
                units = vals.get('units', 0)
                value = vals.get('value', 0)
                if units == 0 and value == 0:
                    continue

                row = build_transaction_row(
                    month_str, sku, units, value,
                    dist_id, commission_pct, cust_id, batch_id,
                    revenue_method='actual',
                    source_row_ref=f"customer_he:{cust_raw}|customer_en:{cust_en or ''}",
                )
                if row:
                    rows.append(row)

                # Track attributed units per product
                if sku not in customer_product_units:
                    customer_product_units[sku] = {'units': 0, 'value': 0.0}
                customer_product_units[sku]['units'] += units
                customer_product_units[sku]['value'] += value

        # 2. Unattributed remainder (totals - customer-attributed)
        totals = mdata.get('totals', {})
        for sku, total_vals in totals.items():
            total_units = total_vals.get('units', 0)
            total_value = total_vals.get('value', 0)
            attr = customer_product_units.get(sku, {'units': 0, 'value': 0.0})
            remainder_units = total_units - attr['units']
            remainder_value = total_value - attr['value']

            if abs(remainder_units) >= 1 or abs(remainder_value) >= 1:
                row = build_transaction_row(
                    month_str, sku, remainder_units, remainder_value,
                    dist_id, commission_pct, None, batch_id,
                    revenue_method='actual',
                    source_row_ref='unattributed_remainder',
                )
                if row:
                    rows.append(row)

        if rows:
            execute_batch(cur, INSERT_SQL, rows)
        complete_batch(cur, batch_id, len(rows))
        total_rows += len(rows)
        print(f"    {month_str}: {len(rows)} rows")

    return total_rows


def migrate_mayyan(cur, data):
    """Migrate Ma'ayan parsed data.

    Ma'ayan data shape (from parse_all_mayyan):
        {month_str: {
            'totals':   {product: {'units': int, 'value': float, 'transactions': int}},
            'by_chain': {chain_he: {product: units_int}},
            'by_account': {(chain_he, acct_he): {product: {'units': int, 'value': float}}},
            'by_customer_type': {...},
            'branches': set(...),
        }}

    Strategy: use by_account for per-customer attributed rows (pre-priced at parse time).
    Revenue method = 'calculated' (units × per-chain contract price).
    """
    dist_id, commission_pct = resolve_distributor('mayyan_froz')
    total_rows = 0

    for month_str, mdata in sorted(data.items(), key=lambda x: MONTH_ORDER.get(x[0], 99)):
        if month_str not in MONTH_TO_DATE:
            print(f"    Skipping unknown month: {month_str}")
            continue

        batch_id = create_batch(
            cur, f"mayyan_{month_str}", dist_id,
            file_format='weekly_xlsx', period=month_str,
        )
        if batch_id is None:
            print(f"    {month_str}: already ingested, skipping")
            continue

        rows = []
        by_account = mdata.get('by_account', {})
        account_product_units = {}  # track for unattributed remainder

        for (chain_he, acct_he), products in by_account.items():
            # Resolve customer from the chain name (Ma'ayan uses source_chain fallback)
            cust_id, cust_en = resolve_customer(acct_he, source_chain=chain_he)

            for sku, vals in products.items():
                units = vals.get('units', 0)
                value = vals.get('value', 0.0)
                if units == 0 and value == 0:
                    continue

                row = build_transaction_row(
                    month_str, sku, units, value,
                    dist_id, commission_pct, cust_id, batch_id,
                    revenue_method='calculated',
                    source_row_ref=f"chain:{chain_he}|acct:{acct_he}",
                )
                if row:
                    rows.append(row)

                if sku not in account_product_units:
                    account_product_units[sku] = {'units': 0, 'value': 0.0}
                account_product_units[sku]['units'] += units
                account_product_units[sku]['value'] += value

        # Unattributed remainder (totals - by_account sums)
        totals = mdata.get('totals', {})
        for sku, total_vals in totals.items():
            total_units = total_vals.get('units', 0)
            total_value = total_vals.get('value', 0)
            attr = account_product_units.get(sku, {'units': 0, 'value': 0.0})
            remainder_units = total_units - attr['units']
            remainder_value = total_value - attr['value']

            if abs(remainder_units) >= 1 or abs(remainder_value) >= 1:
                row = build_transaction_row(
                    month_str, sku, remainder_units, remainder_value,
                    dist_id, commission_pct, None, batch_id,
                    revenue_method='calculated',
                    source_row_ref='unattributed_remainder',
                )
                if row:
                    rows.append(row)

        if rows:
            execute_batch(cur, INSERT_SQL, rows)
        complete_batch(cur, batch_id, len(rows))
        total_rows += len(rows)
        print(f"    {month_str}: {len(rows)} rows")

    return total_rows


def migrate_biscotti(cur, data):
    """Migrate Biscotti parsed data.

    Biscotti data shape (from parse_all_biscotti):
        {month_str: {
            'totals':      {product: {'units': int, 'value': float}},
            'by_customer': {branch_he: {product: {'units': int, 'value': float}}},
        }}

    Strategy: per-branch rows. All branches map to 'Biscotti Chain' customer.
    Revenue = units × ₪80.0 (BISCOTTI_PRICE_DREAM_CAKE), method = 'calculated'.
    """
    dist_id, commission_pct = resolve_distributor('biscotti')
    total_rows = 0

    for month_str, mdata in sorted(data.items(), key=lambda x: MONTH_ORDER.get(x[0], 99)):
        if month_str not in MONTH_TO_DATE:
            print(f"    Skipping unknown month: {month_str}")
            continue

        batch_id = create_batch(
            cur, f"biscotti_{month_str}", dist_id,
            file_format=None, period=month_str,
        )
        if batch_id is None:
            print(f"    {month_str}: already ingested, skipping")
            continue

        rows = []
        by_customer = mdata.get('by_customer', {})

        # All Biscotti branches → "Biscotti Chain" customer
        biscotti_cust_id = _customer_cache.get('Biscotti Chain')

        for branch_he, products in by_customer.items():
            for sku, vals in products.items():
                units = vals.get('units', 0)
                value = vals.get('value', 0.0)
                if units == 0:
                    continue

                row = build_transaction_row(
                    month_str, sku, units, value,
                    dist_id, commission_pct, biscotti_cust_id, batch_id,
                    revenue_method='calculated',
                    source_row_ref=f"branch:{branch_he}",
                )
                if row:
                    rows.append(row)

        if rows:
            execute_batch(cur, INSERT_SQL, rows)
        complete_batch(cur, batch_id, len(rows))
        total_rows += len(rows)
        print(f"    {month_str}: {len(rows)} rows")

    return total_rows


# ═════════════════════════════════════════════════════════════════════════════
# Inventory Snapshot Migration
# ═════════════════════════════════════════════════════════════════════════════

INSERT_INVENTORY_SQL = """
    INSERT INTO inventory_snapshots (
        distributor_id, product_id, units, pallets, cartons,
        snapshot_date, source_type, ingestion_batch_id
    ) VALUES (
        %(distributor_id)s, %(product_id)s, %(units)s, %(pallets)s, %(cartons)s,
        %(snapshot_date)s, %(source_type)s, %(ingestion_batch_id)s
    )
    ON CONFLICT (distributor_id, product_id, snapshot_date)
    DO UPDATE SET
        units   = EXCLUDED.units,
        pallets = EXCLUDED.pallets,
        cartons = EXCLUDED.cartons,
        ingestion_batch_id = EXCLUDED.ingestion_batch_id
"""


def _parse_date_str(date_str):
    """Parse DD/MM/YYYY date string to Python date. Returns None on failure."""
    if not date_str:
        return None
    try:
        parts = date_str.strip().split('/')
        return date(int(parts[2]), int(parts[1]), int(parts[0]))
    except (ValueError, IndexError):
        return None


def migrate_karfree_inventory(cur):
    """Migrate Karfree warehouse inventory from PDF reports.

    Uses parse_karfree_inventory() which reads the latest PDF from data/karfree/.
    Each product becomes one inventory_snapshots row with source_type='warehouse'.
    """
    karfree_data = parse_karfree_inventory()
    if not karfree_data or not karfree_data.get('products'):
        print("    No Karfree inventory data found")
        return 0

    # Resolve Karfree distributor ID
    karfree_id = _distributor_cache.get('karfree')
    if not karfree_id:
        # Try to insert on the fly if seed hasn't been updated yet
        cur.execute("""
            INSERT INTO distributors (key, name_en, name_he, commission_pct, is_active, notes)
            VALUES ('karfree', 'Karfree Warehouse', 'קרפרי', 0.00, TRUE,
                    'Cold storage warehouse. Inventory-only.')
            ON CONFLICT (key) DO UPDATE SET key = 'karfree'
            RETURNING id
        """)
        karfree_id = (cur.fetchone()[0], 0.0)
        _distributor_cache['karfree'] = karfree_id
    dist_id = karfree_id[0] if isinstance(karfree_id, tuple) else karfree_id

    report_date_str = karfree_data.get('report_date')
    snapshot_date = _parse_date_str(report_date_str) or date.today()

    source_file = f"karfree_stock_{snapshot_date.strftime('%Y_%m_%d')}"
    batch_id = create_batch(cur, source_file, dist_id, file_format='pdf_report',
                            period=snapshot_date.strftime('%Y-%m-%d'))
    if batch_id is None:
        print(f"    Karfree {snapshot_date}: already ingested, skipping")
        return 0

    rows = []
    for sku, pdata in karfree_data['products'].items():
        product_id = resolve_product(sku)
        if not product_id:
            continue
        rows.append({
            'distributor_id': dist_id,
            'product_id': product_id,
            'units': pdata.get('units', 0),
            'pallets': pdata.get('pallets'),
            'cartons': None,
            'snapshot_date': snapshot_date,
            'source_type': 'warehouse',
            'ingestion_batch_id': batch_id,
        })

    if rows:
        execute_batch(cur, INSERT_INVENTORY_SQL, rows)
    complete_batch(cur, batch_id, len(rows))
    print(f"    Karfree ({snapshot_date}): {len(rows)} product snapshots, "
          f"{karfree_data.get('total_units', 0):,} total units")
    return len(rows)


def migrate_distributor_inventory(cur):
    """Migrate Icedream and Ma'ayan stock files into inventory_snapshots.

    Uses get_distributor_inventory() which finds the latest *stock* Excel files
    in data/icedreams/ and data/mayyan/.
    """
    dist_inv = get_distributor_inventory()
    if not dist_inv:
        print("    No distributor inventory files found")
        return 0

    total_rows = 0

    for dist_label, dist_key in [('icedream', 'icedream'), ('mayyan', 'mayyan_froz')]:
        inv_data = dist_inv.get(dist_label)
        if not inv_data or not inv_data.get('products'):
            print(f"    {dist_label}: no stock data")
            continue

        dist_entry = _distributor_cache.get(dist_key)
        if not dist_entry:
            print(f"    {dist_label}: distributor key '{dist_key}' not found in DB")
            continue
        dist_id = dist_entry[0] if isinstance(dist_entry, tuple) else dist_entry

        report_date_str = inv_data.get('report_date')
        snapshot_date = _parse_date_str(report_date_str) or date.today()

        source_file = f"{dist_label}_stock_{snapshot_date.strftime('%Y_%m_%d')}"
        batch_id = create_batch(cur, source_file, dist_id, file_format='xlsx',
                                period=snapshot_date.strftime('%Y-%m-%d'))
        if batch_id is None:
            print(f"    {dist_label} ({snapshot_date}): already ingested, skipping")
            continue

        rows = []
        for sku, pdata in inv_data['products'].items():
            product_id = resolve_product(sku)
            if not product_id:
                continue
            rows.append({
                'distributor_id': dist_id,
                'product_id': product_id,
                'units': pdata.get('units', 0),
                'pallets': None,
                'cartons': pdata.get('cartons'),
                'snapshot_date': snapshot_date,
                'source_type': 'distributor',
                'ingestion_batch_id': batch_id,
            })

        if rows:
            execute_batch(cur, INSERT_INVENTORY_SQL, rows)
        complete_batch(cur, batch_id, len(rows))
        total_rows += len(rows)
        print(f"    {dist_label} ({snapshot_date}): {len(rows)} product snapshots, "
              f"{inv_data.get('total_units', 0):,} total units")

    return total_rows


def print_inventory_summary(cur):
    """Print a summary of inventory_snapshots data in the DB."""
    cur.execute("""
        SELECT d.name_en, inv.source_type, inv.snapshot_date,
               COUNT(*) AS products,
               SUM(inv.units) AS total_units
        FROM inventory_snapshots inv
        JOIN distributors d ON d.id = inv.distributor_id
        GROUP BY d.name_en, inv.source_type, inv.snapshot_date
        ORDER BY inv.snapshot_date DESC, d.name_en
    """)
    results = cur.fetchall()

    if not results:
        print("\n  No inventory snapshots in database.")
        return

    print(f"\n{'--- Inventory Snapshots ---':^80}")
    print(f"{'Source':<25} {'Type':<12} {'Date':<14} {'Products':>10} {'Total Units':>14}")
    print("-" * 78)
    for name, stype, sdate, products, units in results:
        print(f"{name:<25} {stype:<12} {str(sdate):<14} {products:>10} {int(units):>14,}")


# ═════════════════════════════════════════════════════════════════════════════
# Reconciliation report
# ═════════════════════════════════════════════════════════════════════════════

# Known benchmarks from RAITO_BRIEFING.md §Current Data State (25 Mar 2026)
BENCHMARKS = {
    'December 2025': {'units': 83753,  'revenue': 1559374},
    'January 2026':  {'units': 51131,  'revenue': 1092105},
    'February 2026': {'units': 58331,  'revenue': 1084381},
    'March 2026':    {'units': 19610,  'revenue': 379155},
}


def print_reconciliation(cur):
    """Query SQL totals and compare against briefing benchmarks."""
    print("\n" + "=" * 80)
    print("RECONCILIATION REPORT")
    print("=" * 80)

    # Per-month SQL totals
    cur.execute("""
        SELECT year, month,
               SUM(units_sold) AS total_units,
               ROUND(SUM(revenue_ils)::numeric, 2) AS total_revenue
        FROM sales_transactions
        GROUP BY year, month
        ORDER BY year, month
    """)
    sql_data = {}
    for year, month_num, units, revenue in cur.fetchall():
        sql_data[(year, month_num)] = {'units': int(units), 'revenue': float(revenue)}

    # Header
    print(f"\n{'Month':<18} {'SQL Units':>12} {'Expected':>12} {'Δ Units':>10} "
          f"{'SQL Rev ₪':>14} {'Expected ₪':>14} {'Δ Rev ₪':>12} {'Status':>8}")
    print("-" * 110)

    all_ok = True
    total_sql_u = total_exp_u = total_sql_r = total_exp_r = 0

    for month_str, bench in BENCHMARKS.items():
        year, month_num = MONTH_TO_NUM[month_str]
        sql = sql_data.get((year, month_num), {'units': 0, 'revenue': 0})

        du = sql['units'] - bench['units']
        dr = sql['revenue'] - bench['revenue']
        ok = abs(du) <= 5 and abs(dr) <= 50  # allow tiny rounding

        total_sql_u += sql['units']
        total_exp_u += bench['units']
        total_sql_r += sql['revenue']
        total_exp_r += bench['revenue']

        status = "✓" if ok else "✗ MISMATCH"
        if not ok:
            all_ok = False

        label = f"{month_str[:3]} '{str(year)[-2:]}"
        print(f"{label:<18} {sql['units']:>12,} {bench['units']:>12,} {du:>+10,} "
              f"{sql['revenue']:>14,.2f} {bench['revenue']:>14,.2f} {dr:>+12,.2f} {status:>8}")

    # Totals row
    total_du = total_sql_u - total_exp_u
    total_dr = total_sql_r - total_exp_r
    print("-" * 110)
    print(f"{'TOTAL':<18} {total_sql_u:>12,} {total_exp_u:>12,} {total_du:>+10,} "
          f"{total_sql_r:>14,.2f} {total_exp_r:>14,.2f} {total_dr:>+12,.2f}")

    # Per-distributor breakdown
    print(f"\n{'--- Per Distributor ---':^80}")
    cur.execute("""
        SELECT d.name_en, year, month,
               SUM(units_sold) AS units,
               ROUND(SUM(revenue_ils)::numeric, 2) AS revenue
        FROM sales_transactions st
        JOIN distributors d ON d.id = st.distributor_id
        GROUP BY d.name_en, year, month
        ORDER BY year, month, d.name_en
    """)
    print(f"\n{'Distributor':<22} {'Month':>10} {'Units':>10} {'Revenue ₪':>14}")
    print("-" * 60)
    for name, year, month_num, units, revenue in cur.fetchall():
        label = f"{month_num:02d}/{year}"
        print(f"{name:<22} {label:>10} {int(units):>10,} {float(revenue):>14,.2f}")

    # Attribution summary
    cur.execute("""
        SELECT
            COUNT(*) AS total_rows,
            SUM(CASE WHEN is_attributed THEN 1 ELSE 0 END) AS attributed,
            SUM(CASE WHEN NOT is_attributed THEN 1 ELSE 0 END) AS unattributed,
            SUM(CASE WHEN is_return THEN 1 ELSE 0 END) AS returns
        FROM sales_transactions
    """)
    total, attr, unattr, returns = cur.fetchone()
    print(f"\n{'--- Data Quality ---':^80}")
    print(f"  Total transaction rows:  {total:,}")
    print(f"  Attributed (customer):   {attr:,} ({attr/total*100:.1f}%)")
    print(f"  Unattributed:            {unattr:,} ({unattr/total*100:.1f}%)")
    print(f"  Return rows:             {returns:,}")

    # Batch summary
    cur.execute("""
        SELECT d.name_en, ib.reporting_period, ib.record_count, ib.status
        FROM ingestion_batches ib
        JOIN distributors d ON d.id = ib.distributor_id
        ORDER BY ib.id
    """)
    print(f"\n{'--- Ingestion Batches ---':^80}")
    print(f"{'Distributor':<22} {'Period':<20} {'Rows':>8} {'Status':>10}")
    print("-" * 64)
    for name, period, count, status in cur.fetchall():
        print(f"{name:<22} {period or '-':<20} {count or 0:>8} {status:>10}")

    if all_ok:
        print(f"\n{'✓ ALL MONTHS RECONCILE WITHIN TOLERANCE':^80}")
    else:
        print(f"\n{'✗ RECONCILIATION FAILURES — INVESTIGATE BEFORE PHASE 3':^80}")

    return all_ok


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 80)
    print("RAITO — Phase 2: Historical Transaction Migration")
    print("=" * 80)

    conn = get_connection()
    cur = conn.cursor()

    try:
        print("\nLoading reference caches...")
        load_caches(cur)
        print(f"  Products:     {len(_product_cache)}")
        print(f"  Customers:    {len(_customer_cache)}")
        print(f"  Distributors: {len(_distributor_cache)}")

        # ── Run parsers (same as consolidate_data but we keep the raw output) ──
        print("\nParsing Icedream files...")
        icedream_data = parse_all_icedreams()
        print(f"  Months found: {list(icedream_data.keys())}")

        print("\nParsing Ma'ayan files...")
        mayyan_data = parse_all_mayyan()
        print(f"  Months found: {list(mayyan_data.keys())}")

        print("\nParsing Biscotti files...")
        biscotti_data = parse_all_biscotti()
        print(f"  Months found: {list(biscotti_data.keys())}")

        # ── Migrate each distributor ──
        print("\n--- Migrating Icedream transactions ---")
        ice_rows = migrate_icedream(cur, icedream_data)

        print("\n--- Migrating Ma'ayan transactions ---")
        may_rows = migrate_mayyan(cur, mayyan_data)

        print("\n--- Migrating Biscotti transactions ---")
        bis_rows = migrate_biscotti(cur, biscotti_data)

        total = ice_rows + may_rows + bis_rows
        print(f"\n  Total rows inserted: {total:,} "
              f"(Icedream: {ice_rows}, Ma'ayan: {may_rows}, Biscotti: {bis_rows})")

        # ── Inventory Snapshots ──
        print("\n--- Migrating Inventory Snapshots ---")

        print("\n  Karfree Warehouse:")
        karfree_rows = migrate_karfree_inventory(cur)

        print("\n  Distributor Stock:")
        dist_inv_rows = migrate_distributor_inventory(cur)

        inv_total = karfree_rows + dist_inv_rows
        print(f"\n  Inventory snapshots inserted: {inv_total} "
              f"(Karfree: {karfree_rows}, Distributors: {dist_inv_rows})")

        print_inventory_summary(cur)

        # ── Reconciliation ──
        ok = print_reconciliation(cur)

        if ok:
            conn.commit()
            print("\n✓ All data committed.")
        else:
            print("\n⚠ Reconciliation mismatches detected.")
            print("  Data is committed (mismatches may be within acceptable range).")
            print("  Review the report above. To roll back: DELETE FROM sales_transactions;")
            conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

    print("\n" + "=" * 80)
    print("Phase 2 complete.")
    print("Next: Phase 3 (dual-run validation period)")
    print("=" * 80)


if __name__ == "__main__":
    main()
