#!/usr/bin/env python3
"""
One-time full re-ingestion of all distributor sales into sales_transactions.
Run from Cloud Shell after cloning the repo:

    cd ~/raito-repo/scripts
    python3 db/full_reingest.py --force

Uses the same raito_loader functions that the upload endpoint now calls.
"""
import os, sys

# Ensure scripts/ and scripts/db/ are on the path
scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, scripts_dir)
sys.path.insert(0, os.path.join(scripts_dir, 'db'))

import psycopg2
from pathlib import Path
from raito_loader import (
    load_caches,
    load_icedream_sales,
    load_mayyan_sales,
    load_biscotti_sales,
)


def main():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        # Fall back to Cloud SQL proxy socket
        db_url = 'postgresql://raito_app:raito_app@/raito?host=/cloudsql/raito-house-of-brands:me-west1:raito-db'

    print(f"Connecting to DB...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    print("Loading caches (products, customers, distributors)...")
    load_caches(cur)

    # Use a dummy path — the loaders call parse_all_*() which read from data/ folder
    # The actual filepath param is only used for _copy_to_data_folder (already done)
    dummy = Path("dummy.xlsx")

    results = {}

    print("\n=== Icedream ===")
    try:
        rows, new, skipped = load_icedream_sales(cur, dummy, dry_run=False, force=True, verbose=True)
        results['icedream'] = {'rows': rows, 'new': new, 'skipped': skipped}
        print(f"  → {rows} rows, {new} batches new, {skipped} skipped")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        conn.rollback()
        results['icedream'] = {'error': str(e)}

    print("\n=== Ma'ayan ===")
    try:
        rows, new, skipped = load_mayyan_sales(cur, dummy, dry_run=False, force=True, verbose=True)
        results['mayyan'] = {'rows': rows, 'new': new, 'skipped': skipped}
        print(f"  → {rows} rows, {new} batches new, {skipped} skipped")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        conn.rollback()
        results['mayyan'] = {'error': str(e)}

    print("\n=== Biscotti ===")
    try:
        rows, new, skipped = load_biscotti_sales(cur, dummy, dry_run=False, force=True, verbose=True)
        results['biscotti'] = {'rows': rows, 'new': new, 'skipped': skipped}
        print(f"  → {rows} rows, {new} batches new, {skipped} skipped")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        conn.rollback()
        results['biscotti'] = {'error': str(e)}

    print("\nCommitting...")
    conn.commit()
    conn.close()

    print("\n=== Summary ===")
    for dist, r in results.items():
        if 'error' in r:
            print(f"  {dist}: FAILED — {r['error']}")
        else:
            print(f"  {dist}: {r['rows']} rows inserted, {r['new']} months")

    # Verify
    print("\nVerifying...")
    conn2 = psycopg2.connect(db_url)
    cur2 = conn2.cursor()
    cur2.execute("""
        SELECT year, month, SUM(units_sold) AS units,
               ROUND(SUM(revenue_ils)::numeric, 0) AS revenue,
               COUNT(*) AS txn_count
        FROM sales_transactions
        GROUP BY year, month
        ORDER BY year, month
    """)
    print(f"\n{'Year':>4} {'Mon':>3} {'Units':>10} {'Revenue':>12} {'Txns':>6}")
    print("-" * 40)
    for row in cur2.fetchall():
        print(f"{row[0]:>4} {row[1]:>3} {row[2]:>10,} {row[3]:>12,} {row[4]:>6,}")
    conn2.close()


if __name__ == '__main__':
    main()
