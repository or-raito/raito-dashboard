#!/usr/bin/env python3
"""
RAITO — raito_loader.py
Weekly data ingestion CLI for Cloud SQL.

Loads a single distributor file (Icedream / Ma'ayan / Biscotti / Karfree stock)
into Cloud SQL, reusing the battle-tested parsers from parsers.py.

Usage:
    # Sales file — auto-detect distributor from filename
    python3 db/raito_loader.py --file data/icedreams/week13.xlsx

    # Explicit distributor
    python3 db/raito_loader.py --distributor mayyan --file data/mayyan/maayan_w13.xlsx

    # Dry run — parse and preview without writing
    python3 db/raito_loader.py --dry-run --file data/icedreams/week13.xlsx

    # Force re-ingest (overwrites existing batch for same period)
    python3 db/raito_loader.py --force --file data/icedreams/week13.xlsx

    # Target local Postgres (default: Cloud SQL)
    python3 db/raito_loader.py --target local --file data/icedreams/week13.xlsx

Authentication (Cloud SQL):
    Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
    Or use gcloud ADC: gcloud auth application-default login

Connection:
    --target cloud  (default): uses google-cloud-sql-connector (no IP whitelisting needed)
    --target local:             uses DATABASE_URL env var or localhost:5432
"""

import argparse
import os
import sys
import shutil
import tempfile
from pathlib import Path
from datetime import date, datetime

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

INSTANCE_CONNECTION_NAME = "raito-house-of-brands:me-west1:raito-db"
DB_USER = "raito"
DB_PASS = "raito"
DB_NAME = "raito"
LOCAL_DB_URL = os.environ.get("DATABASE_URL", "postgresql://raito:raito@localhost:5432/raito")

DISTRIBUTOR_PATTERNS = {
    'icedream': ['icedream', 'ice_dream', 'אייסדרים'],
    'mayyan':   ['maayan', 'mayyan', 'מעיין'],
    'biscotti': ['biscotti', 'daniel', 'ביסקוטי'],
    'karfree':  ['karfree', 'קרפרי'],
}

STOCK_PATTERNS = ['stock', 'מלאי', 'inventory']


# ─────────────────────────────────────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────────────────────────────────────

def get_cloud_connection():
    """Connect to Cloud SQL via the Cloud SQL Python Connector (no proxy needed).

    Requires either:
      - GOOGLE_APPLICATION_CREDENTIALS env var pointing to a service account JSON key
      - Or gcloud ADC: `gcloud auth application-default login`
    """
    try:
        from google.cloud.sql.connector import Connector
    except ImportError:
        print("✗ google-cloud-sql-connector not installed.")
        print("  Run: pip install 'google-cloud-sql-connector[psycopg2]'")
        sys.exit(1)

    connector = Connector()
    conn = connector.connect(
        INSTANCE_CONNECTION_NAME,
        "psycopg2",
        user=DB_USER,
        password=DB_PASS,
        db=DB_NAME,
    )
    conn.autocommit = False
    return conn, connector


def get_local_connection():
    """Connect to local Postgres via DATABASE_URL."""
    import psycopg2
    conn = psycopg2.connect(LOCAL_DB_URL)
    conn.autocommit = False
    return conn, None


def get_connection(target):
    if target == 'cloud':
        return get_cloud_connection()
    else:
        return get_local_connection()


# ─────────────────────────────────────────────────────────────────────────────
# Auto-detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_distributor(filepath):
    """Infer distributor and file type from the file path."""
    name = filepath.name.lower()
    parts = [p.lower() for p in filepath.parts]

    for dist_key, patterns in DISTRIBUTOR_PATTERNS.items():
        if any(p in name for p in patterns) or any(p in ' '.join(parts) for p in patterns):
            is_stock = any(p in name for p in STOCK_PATTERNS)
            return dist_key, is_stock

    # Check parent folder
    parent = filepath.parent.name.lower()
    if 'icedream' in parent:
        is_stock = any(p in name for p in STOCK_PATTERNS)
        return 'icedream', is_stock
    if 'maayan' in parent or 'mayyan' in parent:
        is_stock = any(p in name for p in STOCK_PATTERNS)
        return 'mayyan', is_stock
    if 'biscotti' in parent:
        return 'biscotti', False
    if 'karfree' in parent:
        return 'karfree', True

    return None, False


# ─────────────────────────────────────────────────────────────────────────────
# Reference cache (same pattern as migrate_transactions.py)
# ─────────────────────────────────────────────────────────────────────────────

_product_cache = {}
_customer_cache = {}
_distributor_cache = {}


def load_caches(cur):
    global _product_cache, _customer_cache, _distributor_cache
    cur.execute("SELECT id, sku_key FROM products")
    _product_cache = {sku: pid for pid, sku in cur.fetchall()}
    cur.execute("SELECT id, name_en FROM customers")
    _customer_cache = {name: cid for cid, name in cur.fetchall()}
    cur.execute("SELECT id, key, commission_pct FROM distributors")
    _distributor_cache = {key: (did, float(pct)) for did, key, pct in cur.fetchall()}

    # Also populate migrate_transactions module's own cache, since build_transaction_row
    # uses its own module-level _product_cache (separate from ours above).
    from migrate_transactions import load_caches as _mt_load_caches
    _mt_load_caches(cur)


# ─────────────────────────────────────────────────────────────────────────────
# Batch helpers (shared with migrate_transactions.py)
# ─────────────────────────────────────────────────────────────────────────────

def create_batch(cur, source_file, distributor_id, file_format=None, period=None, force=False):
    """Create ingestion batch. Returns (batch_id, already_existed).

    If force=True, deletes any existing complete batch for this file+distributor
    before creating a new one (enables re-ingestion).
    """
    if force:
        # Must delete child rows first (FK constraint from sales_transactions and inventory_snapshots)
        cur.execute("""
            DELETE FROM sales_transactions
            WHERE ingestion_batch_id IN (
                SELECT id FROM ingestion_batches
                WHERE source_file_name = %s AND distributor_id = %s AND status = 'complete'
            )
        """, (source_file, distributor_id))
        cur.execute("""
            DELETE FROM inventory_snapshots
            WHERE ingestion_batch_id IN (
                SELECT id FROM ingestion_batches
                WHERE source_file_name = %s AND distributor_id = %s AND status = 'complete'
            )
        """, (source_file, distributor_id))
        cur.execute("""
            DELETE FROM ingestion_batches
            WHERE source_file_name = %s AND distributor_id = %s AND status = 'complete'
        """, (source_file, distributor_id))

    cur.execute("""
        SELECT id FROM ingestion_batches
        WHERE source_file_name = %s AND distributor_id = %s AND status = 'complete'
    """, (source_file, distributor_id))
    existing = cur.fetchone()
    if existing:
        return None, True  # already ingested

    cur.execute("""
        INSERT INTO ingestion_batches (source_file_name, distributor_id, file_format, reporting_period, status)
        VALUES (%s, %s, %s, %s, 'processing')
        RETURNING id
    """, (source_file, distributor_id, file_format, period))
    return cur.fetchone()[0], False


def complete_batch(cur, batch_id, record_count):
    cur.execute("""
        UPDATE ingestion_batches
        SET status = 'complete', record_count = %s, completed_at = NOW()
        WHERE id = %s
    """, (record_count, batch_id))


def fail_batch(cur, batch_id, error_msg):
    cur.execute("""
        UPDATE ingestion_batches
        SET status = 'failed', error_message = %s, completed_at = NOW()
        WHERE id = %s
    """, (str(error_msg)[:1000], batch_id))


# ─────────────────────────────────────────────────────────────────────────────
# Per-distributor loaders
# ─────────────────────────────────────────────────────────────────────────────

def _copy_to_data_folder(filepath, subfolder):
    """Copy the input file into the project data folder so parsers can find it."""
    from config import DATA_DIR
    dest_dir = DATA_DIR / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filepath.name
    if dest.resolve() != filepath.resolve():
        shutil.copy2(filepath, dest)
    return dest_dir


def load_icedream_sales(cur, filepath, dry_run, force, verbose):
    """Load an Icedream monthly sales file."""
    from parsers import parse_all_icedreams
    from migrate_transactions import (
        migrate_icedream, build_transaction_row,
        MONTH_TO_DATE, MONTH_TO_NUM,
    )
    from psycopg2.extras import execute_batch
    from config import MONTH_ORDER

    print(f"  Parsing Icedream file: {filepath.name}")
    _copy_to_data_folder(filepath, 'icedreams')
    data = parse_all_icedreams()

    dist_id, commission_pct = _distributor_cache.get('icedream', (None, 0))
    if not dist_id:
        print("  ✗ Distributor 'icedream' not found in DB")
        return 0, 0, 0

    INSERT_SQL = _get_insert_sql()
    total_new = total_conflicts = total_rows = 0

    for month_str, mdata in sorted(data.items(), key=lambda x: MONTH_ORDER.get(x[0], 99)):
        if month_str not in MONTH_TO_DATE:
            if verbose:
                print(f"    Skipping unknown month: {month_str}")
            continue

        batch_id, existed = create_batch(
            cur, f"icedream_{month_str}", dist_id,
            file_format='format_a_xlsx', period=month_str, force=force,
        )
        if existed:
            if verbose:
                print(f"    {month_str}: already ingested (use --force to re-import)")
            total_conflicts += 1
            continue

        rows = _build_icedream_rows(mdata, month_str, dist_id, commission_pct, batch_id)
        total_rows += len(rows)

        if dry_run:
            print(f"    [DRY RUN] {month_str}: would insert {len(rows)} rows")
            fail_batch(cur, batch_id, 'dry_run')
        else:
            _insert_with_progress(cur, INSERT_SQL, rows, label=month_str, verbose=verbose)
            complete_batch(cur, batch_id, len(rows))
            total_new += 1
            if verbose:
                print(f"    {month_str}: {len(rows)} rows inserted ✓")

    return total_rows, total_new, total_conflicts


def _build_icedream_rows(mdata, month_str, dist_id, commission_pct, batch_id):
    from migrate_transactions import build_transaction_row, MONTH_TO_DATE, MONTH_TO_NUM
    from config import extract_customer_name

    rows = []
    by_customer = mdata.get('by_customer', {})
    customer_product_units = {}

    for cust_raw, products in by_customer.items():
        cust_en = extract_customer_name(cust_raw)
        cust_id = _customer_cache.get(cust_en) if cust_en else None
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
            customer_product_units.setdefault(sku, {'units': 0, 'value': 0.0})
            customer_product_units[sku]['units'] += units
            customer_product_units[sku]['value'] += value

    for sku, total_vals in mdata.get('totals', {}).items():
        remainder_units = total_vals.get('units', 0) - customer_product_units.get(sku, {}).get('units', 0)
        remainder_value = total_vals.get('value', 0) - customer_product_units.get(sku, {}).get('value', 0.0)
        if abs(remainder_units) >= 1 or abs(remainder_value) >= 1:
            row = build_transaction_row(
                month_str, sku, remainder_units, remainder_value,
                dist_id, commission_pct, None, batch_id,
                revenue_method='actual', source_row_ref='unattributed_remainder',
            )
            if row:
                rows.append(row)

    return rows


def load_mayyan_sales(cur, filepath, dry_run, force, verbose):
    """Load a Ma'ayan weekly/monthly sales file."""
    from parsers import parse_all_mayyan
    from migrate_transactions import build_transaction_row, MONTH_TO_DATE, MONTH_TO_NUM
    from psycopg2.extras import execute_batch
    from config import MONTH_ORDER, extract_customer_name

    print(f"  Parsing Ma'ayan file: {filepath.name}")
    _copy_to_data_folder(filepath, 'mayyan')
    data = parse_all_mayyan()

    dist_id, commission_pct = _distributor_cache.get('mayyan_froz', (None, 0))
    if not dist_id:
        print("  ✗ Distributor 'mayyan_froz' not found in DB")
        return 0, 0, 0

    INSERT_SQL = _get_insert_sql()
    total_rows = total_new = total_conflicts = 0

    for month_str, mdata in sorted(data.items(), key=lambda x: MONTH_ORDER.get(x[0], 99)):
        if month_str not in MONTH_TO_DATE:
            if verbose:
                print(f"    Skipping unknown month: {month_str}")
            continue

        batch_id, existed = create_batch(
            cur, f"mayyan_{month_str}", dist_id,
            file_format='weekly_xlsx', period=month_str, force=force,
        )
        if existed:
            if verbose:
                print(f"    {month_str}: already ingested (use --force to re-import)")
            total_conflicts += 1
            continue

        rows = _build_mayyan_rows(mdata, month_str, dist_id, commission_pct, batch_id)
        total_rows += len(rows)

        if dry_run:
            print(f"    [DRY RUN] {month_str}: would insert {len(rows)} rows")
            fail_batch(cur, batch_id, 'dry_run')
        else:
            _insert_with_progress(cur, INSERT_SQL, rows, label=month_str, verbose=verbose)
            complete_batch(cur, batch_id, len(rows))
            total_new += 1
            if verbose:
                print(f"    {month_str}: {len(rows)} rows inserted ✓")

    return total_rows, total_new, total_conflicts


def _build_mayyan_rows(mdata, month_str, dist_id, commission_pct, batch_id):
    from migrate_transactions import build_transaction_row, MONTH_TO_DATE
    from config import extract_customer_name

    rows = []
    by_account = mdata.get('by_account', {})
    account_units = {}

    for (chain_he, acct_he), products in by_account.items():
        cust_en = extract_customer_name(acct_he, source_customer=chain_he)
        cust_id = _customer_cache.get(cust_en) if cust_en else None
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
            account_units.setdefault(sku, {'units': 0, 'value': 0.0})
            account_units[sku]['units'] += units
            account_units[sku]['value'] += value

    for sku, total_vals in mdata.get('totals', {}).items():
        rem_units = total_vals.get('units', 0) - account_units.get(sku, {}).get('units', 0)
        rem_value = total_vals.get('value', 0) - account_units.get(sku, {}).get('value', 0.0)
        if abs(rem_units) >= 1 or abs(rem_value) >= 1:
            row = build_transaction_row(
                month_str, sku, rem_units, rem_value,
                dist_id, commission_pct, None, batch_id,
                revenue_method='calculated', source_row_ref='unattributed_remainder',
            )
            if row:
                rows.append(row)

    return rows


def load_biscotti_sales(cur, filepath, dry_run, force, verbose):
    """Load a Biscotti weekly sales file."""
    from parsers import parse_all_biscotti
    from migrate_transactions import build_transaction_row, MONTH_TO_DATE
    from config import MONTH_ORDER

    print(f"  Parsing Biscotti file: {filepath.name}")
    _copy_to_data_folder(filepath, 'biscotti')
    data = parse_all_biscotti()

    dist_id, commission_pct = _distributor_cache.get('biscotti', (None, 0))
    if not dist_id:
        print("  ✗ Distributor 'biscotti' not found in DB")
        return 0, 0, 0

    biscotti_cust_id = _customer_cache.get('Biscotti Chain')
    INSERT_SQL = _get_insert_sql()
    total_rows = total_new = total_conflicts = 0

    for month_str, mdata in sorted(data.items(), key=lambda x: MONTH_ORDER.get(x[0], 99)):
        if month_str not in MONTH_TO_DATE:
            if verbose:
                print(f"    Skipping unknown month: {month_str}")
            continue

        batch_id, existed = create_batch(
            cur, f"biscotti_{month_str}", dist_id,
            file_format=None, period=month_str, force=force,
        )
        if existed:
            if verbose:
                print(f"    {month_str}: already ingested (use --force to re-import)")
            total_conflicts += 1
            continue

        rows = []
        for branch_he, products in mdata.get('by_customer', {}).items():
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

        total_rows += len(rows)

        if dry_run:
            print(f"    [DRY RUN] {month_str}: would insert {len(rows)} rows")
            fail_batch(cur, batch_id, 'dry_run')
        else:
            _insert_with_progress(cur, INSERT_SQL, rows, label=month_str, verbose=verbose)
            complete_batch(cur, batch_id, len(rows))
            total_new += 1
            if verbose:
                print(f"    {month_str}: {len(rows)} rows inserted ✓")

    return total_rows, total_new, total_conflicts


def load_inventory_snapshot(cur, filepath, distributor_key, dry_run, force, verbose):
    """Load a stock/inventory file (Icedream stock, Ma'ayan stock, or Karfree PDF)."""
    from parsers import parse_distributor_stock, parse_karfree_inventory

    is_karfree = distributor_key == 'karfree'

    if is_karfree:
        print(f"  Parsing Karfree warehouse PDF: {filepath.name}")
        _copy_to_data_folder(filepath, 'karfree')
        inv_data = parse_karfree_inventory()
        dist_map_key = 'karfree'
        source_type = 'warehouse'
    else:
        print(f"  Parsing {distributor_key} stock file: {filepath.name}")
        subfolder = 'icedreams' if distributor_key == 'icedream' else 'mayyan'
        _copy_to_data_folder(filepath, subfolder)
        inv_data = parse_distributor_stock(filepath)
        dist_map_key = 'icedream' if distributor_key == 'icedream' else 'mayyan_froz'
        source_type = 'distributor'

    if not inv_data or not inv_data.get('products'):
        print(f"  ✗ No product data found in {filepath.name}")
        return 0, 0, 0

    dist_entry = _distributor_cache.get(dist_map_key)
    if not dist_entry:
        print(f"  ✗ Distributor '{dist_map_key}' not found in DB")
        return 0, 0, 0
    dist_id = dist_entry[0] if isinstance(dist_entry, tuple) else dist_entry

    report_date_str = inv_data.get('report_date')
    snapshot_date = _parse_date_str(report_date_str) or date.today()

    source_file = f"{distributor_key}_stock_{snapshot_date.strftime('%Y_%m_%d')}"
    batch_id, existed = create_batch(
        cur, source_file, dist_id, file_format='xlsx' if not is_karfree else 'pdf_report',
        period=snapshot_date.strftime('%Y-%m-%d'), force=force,
    )
    if existed:
        print(f"  Already ingested (use --force to re-import): {source_file}")
        return 0, 0, 1

    INSERT_INV_SQL = """
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

    rows = []
    for sku, pdata in inv_data['products'].items():
        product_id = _product_cache.get(sku)
        if not product_id:
            continue
        rows.append({
            'distributor_id': dist_id,
            'product_id': product_id,
            'units': pdata.get('units', 0),
            'pallets': pdata.get('pallets') if is_karfree else None,
            'cartons': pdata.get('cartons') if not is_karfree else None,
            'snapshot_date': snapshot_date,
            'source_type': source_type,
            'ingestion_batch_id': batch_id,
        })

    if dry_run:
        total_u = inv_data.get('total_units', 0)
        print(f"  [DRY RUN] Would insert {len(rows)} product snapshots "
              f"({total_u:,} total units) for {snapshot_date}")
        fail_batch(cur, batch_id, 'dry_run')
        return len(rows), 0, 0

    from psycopg2.extras import execute_batch
    execute_batch(cur, INSERT_INV_SQL, rows)
    complete_batch(cur, batch_id, len(rows))

    total_u = inv_data.get('total_units', 0)
    print(f"  ✓ {len(rows)} product snapshots inserted "
          f"({total_u:,} total units, date: {snapshot_date})")
    return len(rows), 1, 0


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_insert_sql():
    return """
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


def _parse_date_str(date_str):
    if not date_str:
        return None
    try:
        parts = date_str.strip().split('/')
        return date(int(parts[2]), int(parts[1]), int(parts[0]))
    except (ValueError, IndexError):
        return None


def _insert_with_progress(cur, sql, rows, label='', verbose=False):
    """Insert rows with optional tqdm progress bar."""
    if not rows:
        return
    try:
        from tqdm import tqdm
        from psycopg2.extras import execute_batch
        CHUNK = 500
        chunks = [rows[i:i + CHUNK] for i in range(0, len(rows), CHUNK)]
        desc = f"    {label}"
        for chunk in tqdm(chunks, desc=desc, unit='batch', disable=not verbose or len(rows) < CHUNK):
            execute_batch(cur, sql, chunk)
    except ImportError:
        from psycopg2.extras import execute_batch
        execute_batch(cur, sql, rows)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='RAITO — Load a distributor data file into Cloud SQL.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 db/raito_loader.py --file data/icedreams/week13.xlsx
  python3 db/raito_loader.py --distributor mayyan --file data/mayyan/maayan_w13.xlsx
  python3 db/raito_loader.py --dry-run --file data/icedreams/week13.xlsx
  python3 db/raito_loader.py --force --file data/icedreams/week13.xlsx
  python3 db/raito_loader.py --target local --file data/icedreams/week13.xlsx
        """
    )
    parser.add_argument('--file', required=True, help='Path to the distributor data file')
    parser.add_argument('--distributor', choices=['icedream', 'mayyan', 'biscotti', 'karfree'],
                        help='Distributor (auto-detected from filename if omitted)')
    parser.add_argument('--target', choices=['cloud', 'local'], default='cloud',
                        help='Database target: cloud (default) or local')
    parser.add_argument('--dry-run', action='store_true',
                        help='Parse and preview without writing to the database')
    parser.add_argument('--force', action='store_true',
                        help='Delete existing batch for this period and re-import')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show per-month progress details')

    args = parser.parse_args()

    filepath = Path(args.file).resolve()
    if not filepath.exists():
        print(f"✗ File not found: {filepath}")
        sys.exit(1)

    # ── Detect distributor ────────────────────────────────────────────────────
    distributor = args.distributor
    is_stock = False
    if not distributor:
        distributor, is_stock = detect_distributor(filepath)
        if not distributor:
            print("✗ Could not auto-detect distributor from filename.")
            print("  Use --distributor {icedream,mayyan,biscotti,karfree}")
            sys.exit(1)
        stock_label = " [stock/inventory]" if is_stock else " [sales]"
        print(f"  Auto-detected: {distributor}{stock_label}")
    else:
        is_stock = any(p in filepath.name.lower() for p in STOCK_PATTERNS)

    # Karfree is always inventory
    if distributor == 'karfree':
        is_stock = True

    # ── Print header ──────────────────────────────────────────────────────────
    print("=" * 65)
    print("RAITO Loader")
    print("=" * 65)
    print(f"  File:        {filepath.name}")
    print(f"  Distributor: {distributor}")
    print(f"  Type:        {'inventory/stock' if is_stock else 'sales transactions'}")
    print(f"  Target:      {args.target.upper()}" + (" (Cloud SQL)" if args.target == 'cloud' else ""))
    print(f"  Mode:        {'DRY RUN — no data will be written' if args.dry_run else 'LIVE'}")
    if args.force:
        print(f"  Force:       YES — existing batches will be overwritten")
    print("=" * 65)

    # ── Connect ───────────────────────────────────────────────────────────────
    print(f"\nConnecting to {'Cloud SQL' if args.target == 'cloud' else 'local Postgres'}...")
    try:
        conn, connector = get_connection(args.target)
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)
    print("  ✓ Connected")

    cur = conn.cursor()
    started_at = datetime.now()

    try:
        print("\nLoading reference data...")
        load_caches(cur)
        print(f"  ✓ {len(_product_cache)} products, {len(_customer_cache)} customers, "
              f"{len(_distributor_cache)} distributors")

        # ── Run the appropriate loader ────────────────────────────────────────
        print(f"\nIngesting data...")
        if is_stock:
            rows_processed, batches_new, batches_skipped = load_inventory_snapshot(
                cur, filepath, distributor, args.dry_run, args.force, args.verbose,
            )
        elif distributor == 'icedream':
            rows_processed, batches_new, batches_skipped = load_icedream_sales(
                cur, filepath, args.dry_run, args.force, args.verbose,
            )
        elif distributor == 'mayyan':
            rows_processed, batches_new, batches_skipped = load_mayyan_sales(
                cur, filepath, args.dry_run, args.force, args.verbose,
            )
        elif distributor == 'biscotti':
            rows_processed, batches_new, batches_skipped = load_biscotti_sales(
                cur, filepath, args.dry_run, args.force, args.verbose,
            )
        else:
            print(f"✗ Unknown distributor: {distributor}")
            sys.exit(1)

        # ── Commit or rollback ────────────────────────────────────────────────
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()

        elapsed = (datetime.now() - started_at).total_seconds()

        # ── Summary ───────────────────────────────────────────────────────────
        print("\n" + "=" * 65)
        print("SUMMARY")
        print("=" * 65)
        print(f"  Rows processed:       {rows_processed:,}")
        print(f"  New batches added:    {batches_new}")
        print(f"  Batches skipped:      {batches_skipped}  (already ingested)")
        print(f"  Time elapsed:         {elapsed:.1f}s")
        if args.dry_run:
            print("\n  ⚠  DRY RUN — no data was written to the database.")
        else:
            print(f"\n  ✓ Done. Refresh dashboard: curl -s {_get_refresh_url(args.target)} > /dev/null")
        print("=" * 65)

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()
        if connector:
            connector.close()


def _get_refresh_url(target):
    if target == 'cloud':
        return "https://raito-dashboard-20004010285.me-west1.run.app/refresh"
    return "http://localhost:8080/refresh"


if __name__ == '__main__':
    main()
