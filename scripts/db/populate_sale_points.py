#!/usr/bin/env python3
"""
RAITO — Phase 3: Populate sale_points & Back-link Transactions
==============================================================

Runs the existing parsers (consolidate_data) to discover every unique
branch/POS and INSERTs them into the sale_points table.  Then back-fills
sales_transactions.sale_point_id based on the source_row_ref column
that Phase 2 (migrate_transactions.py) already stored.

Usage:
    cd scripts && python3 db/populate_sale_points.py

    # Just populate sale_points (skip transaction linking)
    cd scripts && python3 db/populate_sale_points.py --sale-points-only

    # Just back-link transactions (sale_points already populated)
    cd scripts && python3 db/populate_sale_points.py --link-only

    # Dry-run: show what would be inserted without writing
    cd scripts && python3 db/populate_sale_points.py --dry-run

Requires:
    - PostgreSQL with schema.sql applied, Phase 1 + Phase 2 complete
    - psycopg2: pip install psycopg2-binary
    - Environment variable DATABASE_URL or defaults to local dev

Idempotency:
    Uses INSERT ... ON CONFLICT (distributor_id, branch_name_he) DO UPDATE
    to update first/last order dates on re-run.
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import date
from collections import defaultdict

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import psycopg2
from psycopg2.extras import execute_batch

from parsers import consolidate_data
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
# Lookup caches
# ═════════════════════════════════════════════════════════════════════════════

_customer_cache = {}     # name_en → id
_distributor_cache = {}  # key → id


def load_caches(cur):
    global _customer_cache, _distributor_cache
    cur.execute("SELECT id, name_en FROM customers")
    _customer_cache = {name: cid for cid, name in cur.fetchall()}
    cur.execute("SELECT id, key FROM distributors")
    _distributor_cache = {key: did for did, key in cur.fetchall()}


def resolve_customer(name_raw, source_chain=None):
    """Resolve a raw branch/chain name to (customer_id, customer_name_en)."""
    name_en = extract_customer_name(name_raw, source_customer=source_chain)
    if not name_en:
        return None, name_en
    cid = _customer_cache.get(name_en)
    return cid, name_en


# ═════════════════════════════════════════════════════════════════════════════
# Month helpers
# ═════════════════════════════════════════════════════════════════════════════

MONTH_TO_DATE = {
    'November 2025': date(2025, 11, 1),
    'December 2025': date(2025, 12, 1),
    'January 2026':  date(2026, 1, 1),
    'February 2026': date(2026, 2, 1),
    'March 2026':    date(2026, 3, 1),
    'April 2026':    date(2026, 4, 1),
}


# ═════════════════════════════════════════════════════════════════════════════
# Phase 3a: Discover and insert sale points
# ═════════════════════════════════════════════════════════════════════════════

def discover_sale_points(data):
    """Walk consolidated parser data and collect every unique branch.

    Returns a list of dicts:
        [{distributor_key, branch_name_he, customer_name_en, customer_id,
          first_month, last_month}]
    """
    months_ordered = ['November 2025', 'December 2025', 'January 2026', 'February 2026', 'March 2026', 'April 2026']

    # key = (distributor_key, branch_name_he) → metadata
    sale_points = {}

    for month_str in months_ordered:
        md = data['monthly_data'].get(month_str, {})
        tx_date = MONTH_TO_DATE.get(month_str)

        # ── Ma'ayan accounts ──
        for (chain_raw, acct_name), pdata in md.get('mayyan_accounts', {}).items():
            total_units = sum(
                (v.get('units', 0) if isinstance(v, dict) else (v or 0))
                for v in pdata.values()
            )
            if total_units == 0:
                continue

            cust_id, cust_en = resolve_customer(acct_name, source_chain=chain_raw)
            key = ('mayyan_froz', acct_name)

            if key not in sale_points:
                sale_points[key] = {
                    'distributor_key': 'mayyan_froz',
                    'branch_name_he': acct_name,
                    'customer_id': cust_id,
                    'customer_name_en': cust_en,
                    'first_month': month_str,
                    'last_month': month_str,
                    'chain_raw': chain_raw,
                }
            else:
                sale_points[key]['last_month'] = month_str
                # Update customer_id if it was None before but resolved now
                if sale_points[key]['customer_id'] is None and cust_id is not None:
                    sale_points[key]['customer_id'] = cust_id
                    sale_points[key]['customer_name_en'] = cust_en

        # ── Icedream customers ──
        for cust_he, pdata in md.get('icedreams_customers', {}).items():
            total_units = sum(
                (v.get('units', 0) if isinstance(v, dict) else (v or 0))
                for v in pdata.values()
            )
            if total_units == 0:
                continue

            cust_id, cust_en = resolve_customer(cust_he)
            key = ('icedream', cust_he)

            if key not in sale_points:
                sale_points[key] = {
                    'distributor_key': 'icedream',
                    'branch_name_he': cust_he,
                    'customer_id': cust_id,
                    'customer_name_en': cust_en,
                    'first_month': month_str,
                    'last_month': month_str,
                    'chain_raw': None,
                }
            else:
                sale_points[key]['last_month'] = month_str
                if sale_points[key]['customer_id'] is None and cust_id is not None:
                    sale_points[key]['customer_id'] = cust_id
                    sale_points[key]['customer_name_en'] = cust_en

        # ── Biscotti customers ──
        for branch_he, pdata in md.get('biscotti_customers', {}).items():
            total_units = sum(
                (v.get('units', 0) if isinstance(v, dict) else (v or 0))
                for v in pdata.values()
            )
            if total_units == 0:
                continue

            cust_id, cust_en = resolve_customer(branch_he)
            # Biscotti branches all map to "Biscotti Chain" customer
            if cust_id is None:
                cust_id = _customer_cache.get('Biscotti Chain')
                cust_en = 'Biscotti Chain'

            key = ('biscotti', branch_he)

            if key not in sale_points:
                sale_points[key] = {
                    'distributor_key': 'biscotti',
                    'branch_name_he': branch_he,
                    'customer_id': cust_id,
                    'customer_name_en': cust_en,
                    'first_month': month_str,
                    'last_month': month_str,
                    'chain_raw': None,
                }
            else:
                sale_points[key]['last_month'] = month_str

    return list(sale_points.values())


INSERT_SP_SQL = """
    INSERT INTO sale_points
        (customer_id, distributor_id, branch_name_he, is_active,
         first_order_date, last_order_date)
    VALUES
        (%(customer_id)s, %(distributor_id)s, %(branch_name_he)s, %(is_active)s,
         %(first_order_date)s, %(last_order_date)s)
    ON CONFLICT (distributor_id, branch_name_he) DO UPDATE SET
        last_order_date = GREATEST(sale_points.last_order_date, EXCLUDED.last_order_date),
        first_order_date = LEAST(sale_points.first_order_date, EXCLUDED.first_order_date),
        is_active = EXCLUDED.is_active
"""


def insert_sale_points(cur, sp_list, dry_run=False):
    """Insert discovered sale points into the DB.

    Returns: (inserted_count, skipped_count, unresolved_customers)
    """
    rows = []
    skipped = 0
    unresolved = []  # branches where customer_id could not be resolved

    for sp in sp_list:
        dist_id = _distributor_cache.get(sp['distributor_key'])
        if dist_id is None:
            print(f"  WARNING: Unknown distributor key '{sp['distributor_key']}' — skipping")
            skipped += 1
            continue

        cust_id = sp['customer_id']
        if cust_id is None:
            # Try one more time — sometimes branches don't resolve cleanly
            unresolved.append(sp)
            skipped += 1
            continue

        first_date = MONTH_TO_DATE.get(sp['first_month'])
        last_date = MONTH_TO_DATE.get(sp['last_month'])
        # Active if they ordered in the most recent month
        is_active = sp['last_month'] in ('March 2026', 'February 2026')

        rows.append({
            'customer_id': cust_id,
            'distributor_id': dist_id,
            'branch_name_he': sp['branch_name_he'],
            'is_active': is_active,
            'first_order_date': first_date,
            'last_order_date': last_date,
        })

    if dry_run:
        print(f"\n  [DRY RUN] Would insert {len(rows)} sale points, skip {skipped}")
        for r in rows[:20]:
            print(f"    dist={r['distributor_id']} | {r['branch_name_he'][:40]:<40} | cust={r['customer_id']}")
        if len(rows) > 20:
            print(f"    ... and {len(rows) - 20} more")
    else:
        execute_batch(cur, INSERT_SP_SQL, rows, page_size=200)
        print(f"  Upserted {len(rows)} sale points ({skipped} skipped)")

    if unresolved:
        print(f"\n  ⚠ {len(unresolved)} branches with unresolved customer_id:")
        for sp in unresolved[:30]:
            print(f"    [{sp['distributor_key']}] {sp['branch_name_he'][:50]} → customer_en='{sp['customer_name_en']}'")
        if len(unresolved) > 30:
            print(f"    ... and {len(unresolved) - 30} more")

    return len(rows), skipped, unresolved


# ═════════════════════════════════════════════════════════════════════════════
# Phase 3b: Back-link sales_transactions.sale_point_id
# ═════════════════════════════════════════════════════════════════════════════

def backfill_transaction_links(cur, dry_run=False):
    """Match existing sales_transactions to sale_points using source_row_ref.

    migrate_transactions.py stores references like:
      - Icedream:  "customer_he:שם הלקוח|customer_en:Customer Name"
      - Ma'ayan:   "chain:שרשרת|acct:שם חשבון"
      - Biscotti:  "branch:שם הסניף"

    We parse these, look up the sale_point by (distributor_id, branch_name_he),
    and SET sale_point_id.
    """

    # Load all sale_points into a lookup: (distributor_id, branch_name_he) → sp_id
    cur.execute("SELECT id, distributor_id, branch_name_he FROM sale_points")
    sp_lookup = {}
    for sp_id, dist_id, branch in cur.fetchall():
        sp_lookup[(dist_id, branch)] = sp_id

    if not sp_lookup:
        print("  No sale_points in DB — nothing to link")
        return 0

    print(f"  Loaded {len(sp_lookup)} sale_points for matching")

    # Load distributor key→id map
    cur.execute("SELECT id, key FROM distributors")
    dist_key_to_id = {key: did for did, key in cur.fetchall()}

    # Fetch unlinked transactions
    cur.execute("""
        SELECT t.id, t.distributor_id, t.source_row_ref
        FROM sales_transactions t
        WHERE t.sale_point_id IS NULL
          AND t.source_row_ref IS NOT NULL
          AND t.source_row_ref != 'unattributed_remainder'
    """)
    transactions = cur.fetchall()
    print(f"  Found {len(transactions)} unlinked transactions with source_row_ref")

    # Parse source_row_ref and resolve
    updates = []  # (sale_point_id, transaction_id)
    unmatched = 0
    matched_by_type = defaultdict(int)

    icedream_dist_id = dist_key_to_id.get('icedream')
    mayyan_dist_id = dist_key_to_id.get('mayyan_froz')
    biscotti_dist_id = dist_key_to_id.get('biscotti')

    for tx_id, tx_dist_id, ref in transactions:
        sp_id = None

        if ref.startswith('chain:') and '|acct:' in ref:
            # Ma'ayan: "chain:שרשרת|acct:שם חשבון"
            parts = dict(p.split(':', 1) for p in ref.split('|') if ':' in p)
            acct = parts.get('acct', '').strip()
            if acct:
                sp_id = sp_lookup.get((tx_dist_id, acct))
                if sp_id:
                    matched_by_type['mayyan'] += 1

        elif ref.startswith('customer_he:'):
            # Icedream: "customer_he:שם|customer_en:Name"
            parts = dict(p.split(':', 1) for p in ref.split('|') if ':' in p)
            cust_he = parts.get('customer_he', '').strip()
            if cust_he:
                sp_id = sp_lookup.get((tx_dist_id, cust_he))
                if sp_id:
                    matched_by_type['icedream'] += 1

        elif ref.startswith('branch:'):
            # Biscotti: "branch:שם הסניף"
            branch = ref.split(':', 1)[1].strip()
            if branch:
                sp_id = sp_lookup.get((tx_dist_id, branch))
                if sp_id:
                    matched_by_type['biscotti'] += 1

        if sp_id:
            updates.append((sp_id, tx_id))
        else:
            unmatched += 1

    print(f"  Matched: {len(updates)} transactions → sale_points")
    for dist, count in sorted(matched_by_type.items()):
        print(f"    {dist}: {count}")
    print(f"  Unmatched: {unmatched}")

    if dry_run:
        print(f"\n  [DRY RUN] Would update {len(updates)} transactions")
    else:
        if updates:
            execute_batch(
                cur,
                "UPDATE sales_transactions SET sale_point_id = %s WHERE id = %s",
                updates,
                page_size=500,
            )
            print(f"  Updated {len(updates)} transactions with sale_point_id")

    return len(updates)


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Phase 3: Populate sale_points & back-link transactions",
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without writing to DB')
    parser.add_argument('--sale-points-only', action='store_true',
                        help='Only populate sale_points, skip transaction linking')
    parser.add_argument('--link-only', action='store_true',
                        help='Only back-link transactions (sale_points already populated)')
    args = parser.parse_args()

    print("=" * 60)
    print("RAITO Phase 3: Populate sale_points & back-link transactions")
    print("=" * 60)

    conn = get_connection()
    cur = conn.cursor()

    try:
        load_caches(cur)
        print(f"  Loaded {len(_customer_cache)} customers, {len(_distributor_cache)} distributors")

        if not args.link_only:
            # Phase 3a: Discover and insert sale points
            print("\n── Phase 3a: Discovering sale points from Excel data ──")
            data = consolidate_data()
            sp_list = discover_sale_points(data)
            print(f"  Discovered {len(sp_list)} unique sale points")

            by_dist = defaultdict(int)
            for sp in sp_list:
                by_dist[sp['distributor_key']] += 1
            for dk, count in sorted(by_dist.items()):
                print(f"    {dk}: {count}")

            inserted, skipped, unresolved = insert_sale_points(cur, sp_list, dry_run=args.dry_run)

            if not args.dry_run:
                conn.commit()
                print("  ✓ sale_points committed")

        if not args.sale_points_only:
            # Phase 3b: Back-link transactions
            print("\n── Phase 3b: Back-linking sales_transactions → sale_points ──")
            linked = backfill_transaction_links(cur, dry_run=args.dry_run)

            if not args.dry_run:
                conn.commit()
                print("  ✓ transaction links committed")

        # Summary
        if not args.dry_run:
            print("\n── Summary ──")
            cur.execute("SELECT COUNT(*) FROM sale_points")
            sp_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sales_transactions WHERE sale_point_id IS NOT NULL")
            linked_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sales_transactions")
            total_tx = cur.fetchone()[0]
            print(f"  sale_points:           {sp_count} rows")
            print(f"  transactions linked:   {linked_count} / {total_tx}")

    except Exception as e:
        conn.rollback()
        print(f"\n  ✗ ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
