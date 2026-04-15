#!/usr/bin/env python3
"""
RAITO — Phase 3: Ingest Parsed Data → sales_transactions

Reads Excel files via parsers.consolidate_data(), resolves all entities
to DB IDs via EntityResolver, and writes rows to sales_transactions.

Each distributor file becomes an ingestion_batch for dedup/rollback.
Uses UPSERT logic: if a batch already exists (same file + distributor),
it's skipped unless --force is passed.

Usage (local with Cloud SQL proxy running):
  cd scripts
  DATABASE_URL="postgresql://raito_app:raito_app@127.0.0.1:5432/raito" python3 db/ingest_to_db.py

  With --force to re-ingest (deletes old batch, re-inserts):
  DATABASE_URL="..." python3 db/ingest_to_db.py --force

  Dry-run (shows what would be inserted, no DB writes):
  DATABASE_URL="..." python3 db/ingest_to_db.py --dry-run
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import date, datetime
from collections import defaultdict

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import psycopg2
import psycopg2.extras

DB_URL = os.environ.get("DATABASE_URL", "postgresql://raito_app:raito_app@127.0.0.1:5432/raito")

# ═════════════════════════════════════════════════════════════════════════════
# Month → date helpers
# ═════════════════════════════════════════════════════════════════════════════

_MONTH_TO_DATE = {
    'November 2025':  date(2025, 11, 1),
    'December 2025':  date(2025, 12, 1),
    'January 2026':   date(2026, 1, 1),
    'February 2026':  date(2026, 2, 1),
    'March 2026':     date(2026, 3, 1),
    'April 2026':     date(2026, 4, 1),
    'May 2026':       date(2026, 5, 1),
}


def _month_str_to_parts(month_str):
    """Convert 'March 2026' → (date(2026,3,1), year=2026, month=3)."""
    d = _MONTH_TO_DATE.get(month_str)
    if d:
        return d, d.year, d.month
    # Fallback: try parsing
    try:
        d = datetime.strptime(month_str, '%B %Y').date().replace(day=1)
        return d, d.year, d.month
    except ValueError:
        return None, None, None


# ═════════════════════════════════════════════════════════════════════════════
# Batch management
# ═════════════════════════════════════════════════════════════════════════════

def _create_batch(cur, source_name, distributor_id, period, file_format='excel'):
    """Create an ingestion_batches row. Returns batch_id."""
    cur.execute("""
        INSERT INTO ingestion_batches
            (source_file_name, distributor_id, file_format, reporting_period, status)
        VALUES (%s, %s, %s, %s, 'processing')
        RETURNING id
    """, (source_name, distributor_id, file_format, period))
    return cur.fetchone()[0]


def _complete_batch(cur, batch_id, record_count):
    """Mark batch as complete."""
    cur.execute("""
        UPDATE ingestion_batches
        SET status = 'complete', record_count = %s, completed_at = NOW()
        WHERE id = %s
    """, (record_count, batch_id))


def _batch_exists(cur, source_name, distributor_id):
    """Check if a completed batch already exists for this file+distributor."""
    cur.execute("""
        SELECT id FROM ingestion_batches
        WHERE source_file_name = %s AND distributor_id = %s AND status = 'complete'
    """, (source_name, distributor_id))
    row = cur.fetchone()
    return row[0] if row else None


def _rollback_batch(cur, batch_id):
    """Delete all transactions for a batch, then delete the batch itself."""
    cur.execute("DELETE FROM sales_transactions WHERE ingestion_batch_id = %s", (batch_id,))
    deleted = cur.rowcount
    cur.execute("DELETE FROM ingestion_batches WHERE id = %s", (batch_id,))
    return deleted


# ═════════════════════════════════════════════════════════════════════════════
# Sale point upsert
# ═════════════════════════════════════════════════════════════════════════════

def _upsert_sale_point(cur, customer_id, distributor_id, branch_name_he):
    """Upsert a sale_points record.

    Returns the sale_point_id.

    Attribution behaviour:
    - If caller passes a confident customer_id (from EntityResolver), the row
      is created/kept as 'confirmed'.
    - If customer_id is None, we run the smart-suggest matcher
      (scripts/sp_attribution.suggest_customer_for_branch) to propose a
      Customer Root. The resulting row lands in the MD tab "Unassigned Sale
      Points" inbox with status 'suggested' (or 'unassigned' if no match).
    - Existing rows are never demoted: a confirmed SP stays confirmed even if
      the same branch shows up again on a later ingest.
    """
    # Lazy import — avoids circular deps at module load
    import sys, os
    _SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _SCRIPTS not in sys.path:
        sys.path.insert(0, _SCRIPTS)
    from sp_attribution import suggest_customer_for_branch

    if customer_id is not None:
        # Confident attribution from the caller — status = confirmed
        cur.execute("""
            INSERT INTO sale_points
                (customer_id, distributor_id, branch_name_he,
                 attribution_status, is_active)
            VALUES (%s, %s, %s, 'confirmed', TRUE)
            ON CONFLICT (distributor_id, branch_name_he) DO UPDATE
                SET customer_id        = COALESCE(sale_points.customer_id,
                                                  EXCLUDED.customer_id),
                    attribution_status = CASE
                        WHEN sale_points.attribution_status = 'confirmed'
                            THEN sale_points.attribution_status
                        ELSE 'confirmed'
                    END
            RETURNING id
        """, (customer_id, distributor_id, branch_name_he))
        return cur.fetchone()[0]

    # No caller-provided attribution → run the matcher
    s = suggest_customer_for_branch(cur, distributor_id, branch_name_he)
    cur.execute("""
        INSERT INTO sale_points
            (customer_id, distributor_id, branch_name_he,
             attribution_status, suggested_customer_id,
             suggestion_confidence, suggestion_reason, is_active)
        VALUES (NULL, %s, %s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (distributor_id, branch_name_he) DO UPDATE
            SET suggested_customer_id = COALESCE(
                    sale_points.suggested_customer_id,
                    EXCLUDED.suggested_customer_id
                ),
                suggestion_confidence = COALESCE(
                    sale_points.suggestion_confidence,
                    EXCLUDED.suggestion_confidence
                ),
                suggestion_reason     = COALESCE(
                    sale_points.suggestion_reason,
                    EXCLUDED.suggestion_reason
                ),
                attribution_status    = CASE
                    WHEN sale_points.attribution_status = 'confirmed'
                        THEN sale_points.attribution_status
                    ELSE EXCLUDED.attribution_status
                END
        RETURNING id
    """, (
        distributor_id,
        branch_name_he,
        s['status'],
        s['customer_id'],
        s['confidence'],
        s['reason'],
    ))
    return cur.fetchone()[0]


# ═════════════════════════════════════════════════════════════════════════════
# Insert transactions
# ═════════════════════════════════════════════════════════════════════════════

SQL_INSERT_TXN = """
    INSERT INTO sales_transactions (
        transaction_date, week_number, year, month,
        product_id, distributor_id, customer_id, sale_point_id,
        units_sold, revenue_ils, unit_price_ils, cost_ils, gross_margin_ils,
        distributor_commission_ils,
        is_return, is_attributed, revenue_method,
        ingestion_batch_id, source_row_ref
    ) VALUES (
        %(transaction_date)s, %(week_number)s, %(year)s, %(month)s,
        %(product_id)s, %(distributor_id)s, %(customer_id)s, %(sale_point_id)s,
        %(units_sold)s, %(revenue_ils)s, %(unit_price_ils)s, %(cost_ils)s, %(gross_margin_ils)s,
        %(distributor_commission_ils)s,
        %(is_return)s, %(is_attributed)s, %(revenue_method)s,
        %(ingestion_batch_id)s, %(source_row_ref)s
    )
"""


def _build_txn_row(txn_date, year, month, product_id, distributor_id,
                   customer_id, units, revenue, unit_price, cost_per_unit,
                   dist_pct, revenue_method, batch_id, source_ref,
                   week_number=None, sale_point_id=None):
    """Build a dict suitable for SQL_INSERT_TXN."""
    is_return = units < 0
    gross_margin = round(revenue - abs(units) * cost_per_unit, 2) if cost_per_unit else None
    dist_commission = round(revenue * dist_pct / 100, 2) if dist_pct and revenue else None

    return {
        'transaction_date': txn_date,
        'week_number': week_number,
        'year': year,
        'month': month,
        'product_id': product_id,
        'distributor_id': distributor_id,
        'customer_id': customer_id,
        'sale_point_id': sale_point_id,
        'units_sold': units,
        'revenue_ils': round(revenue, 2),
        'unit_price_ils': round(unit_price, 2) if unit_price else None,
        'cost_ils': round(abs(units) * cost_per_unit, 2) if cost_per_unit else None,
        'gross_margin_ils': gross_margin,
        'distributor_commission_ils': dist_commission,
        'is_return': is_return,
        'is_attributed': customer_id is not None,
        'revenue_method': revenue_method,
        'ingestion_batch_id': batch_id,
        'source_row_ref': source_ref,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Main ingestion logic
# ═════════════════════════════════════════════════════════════════════════════

def ingest_all(conn, force=False, dry_run=False):
    """Parse all distributor files and ingest into sales_transactions.

    Returns (total_rows_inserted, total_batches_created).
    """
    from parsers import consolidate_data
    from db.resolvers import EntityResolver
    from pricing_engine import get_production_cost

    print("=" * 60)
    print("RAITO Phase 3: Ingest → sales_transactions")
    print("=" * 60)

    # ── Step 1: Parse all Excel files ──
    print("\n[1/4] Parsing distributor Excel files...")
    data = consolidate_data()

    # ── Step 2: Initialize resolver ──
    print("\n[2/4] Initializing entity resolver...")
    resolver = EntityResolver(conn=conn)

    # Resolve product SKUs → IDs
    product_ids = {}
    for sku in data.get('products', []):
        result = resolver.resolve_product_by_sku(sku)
        if result:
            product_ids[sku] = result[0]
        else:
            print(f"  ⚠ Product '{sku}' not found in DB — transactions will be skipped")

    # Resolve distributor keys → IDs
    dist_ids = {}
    for key in ('icedream', 'mayyan_froz', 'biscotti'):
        did = resolver.resolve_distributor(key)
        if did:
            dist_ids[key] = did
        else:
            print(f"  ⚠ Distributor '{key}' not found in DB")

    print(f"  Products: {len(product_ids)}/{len(data.get('products', []))}")
    print(f"  Distributors: {len(dist_ids)}/3")

    # ── Step 3: Build transaction rows ──
    print("\n[3/4] Building transaction rows...")
    cur = conn.cursor()
    total_rows = 0
    total_batches = 0
    stats = defaultdict(lambda: {'rows': 0, 'units': 0, 'revenue': 0.0})

    for month_str, mdata in data.get('monthly_data', {}).items():
        txn_date, year, month = _month_str_to_parts(month_str)
        if not txn_date:
            print(f"  ⚠ Skipping unknown month: {month_str}")
            continue

        # ── Icedream transactions ──
        ice_dist_id = dist_ids.get('icedream')
        if ice_dist_id:
            batch_name = f"icedream_{month_str.replace(' ', '_').lower()}"
            existing = _batch_exists(cur, batch_name, ice_dist_id)
            if existing and not force:
                print(f"  ⏭ Icedream {month_str}: already ingested (batch #{existing})")
            else:
                if existing and force:
                    deleted = _rollback_batch(cur, existing)
                    print(f"  ↻ Rolled back Icedream {month_str}: {deleted} old rows removed")

                if not dry_run:
                    batch_id = _create_batch(cur, batch_name, ice_dist_id, month_str)
                else:
                    batch_id = -1

                rows = []
                for cust_name, prods in mdata.get('icedreams_customers', {}).items():
                    cust_result = resolver.resolve_customer(cust_name)
                    cust_id = cust_result[0] if cust_result else None

                    for sku, pdata in prods.items():
                        pid = product_ids.get(sku)
                        if not pid:
                            continue
                        units = pdata.get('units', 0)
                        revenue = pdata.get('value', 0.0)
                        unit_price = round(revenue / units, 2) if units else 0
                        cost = get_production_cost(sku)

                        rows.append(_build_txn_row(
                            txn_date=txn_date, year=year, month=month,
                            product_id=pid, distributor_id=ice_dist_id,
                            customer_id=cust_id,
                            units=units, revenue=revenue,
                            unit_price=unit_price, cost_per_unit=cost,
                            dist_pct=15, revenue_method='actual',
                            batch_id=batch_id,
                            source_ref=f"customer:{cust_name}",
                        ))

                if rows and not dry_run:
                    psycopg2.extras.execute_batch(cur, SQL_INSERT_TXN, rows)
                    _complete_batch(cur, batch_id, len(rows))
                    conn.commit()

                total_rows += len(rows)
                total_batches += 1
                stats[f'icedream_{month_str}'] = {
                    'rows': len(rows),
                    'units': sum(r['units_sold'] for r in rows),
                    'revenue': sum(r['revenue_ils'] for r in rows),
                }
                print(f"  ✓ Icedream {month_str}: {len(rows)} rows"
                      f" ({sum(r['units_sold'] for r in rows):,} units,"
                      f" ₪{sum(r['revenue_ils'] for r in rows):,.0f})"
                      f"{' [DRY RUN]' if dry_run else ''}")

        # ── Ma'ayan transactions ──
        may_dist_id = dist_ids.get('mayyan_froz')
        if may_dist_id:
            batch_name = f"mayyan_{month_str.replace(' ', '_').lower()}"
            existing = _batch_exists(cur, batch_name, may_dist_id)
            if existing and not force:
                print(f"  ⏭ Ma'ayan {month_str}: already ingested (batch #{existing})")
            else:
                if existing and force:
                    deleted = _rollback_batch(cur, existing)
                    print(f"  ↻ Rolled back Ma'ayan {month_str}: {deleted} old rows removed")

                if not dry_run:
                    batch_id = _create_batch(cur, batch_name, may_dist_id, month_str)
                else:
                    batch_id = -1

                rows = []
                # Ma'ayan accounts: keyed by (chain_raw, account_name)
                for (chain_raw, acct), prods in mdata.get('mayyan_accounts', {}).items():
                    # Resolve using the chain name (Hebrew)
                    from config import extract_customer_name
                    cust_en = extract_customer_name(acct, source_customer=chain_raw)
                    cust_result = resolver.resolve_customer(cust_en)
                    cust_id = cust_result[0] if cust_result else None

                    for sku, pdata in prods.items():
                        pid = product_ids.get(sku)
                        if not pid:
                            continue
                        if not isinstance(pdata, dict):
                            continue
                        units = pdata.get('units', 0)
                        revenue = pdata.get('value', 0.0)
                        unit_price = round(revenue / units, 2) if units else 0
                        cost = get_production_cost(sku)

                        rows.append(_build_txn_row(
                            txn_date=txn_date, year=year, month=month,
                            product_id=pid, distributor_id=may_dist_id,
                            customer_id=cust_id,
                            units=units, revenue=revenue,
                            unit_price=unit_price, cost_per_unit=cost,
                            dist_pct=25, revenue_method='calculated',
                            batch_id=batch_id,
                            source_ref=f"chain:{chain_raw}|acct:{acct}",
                        ))

                if rows and not dry_run:
                    psycopg2.extras.execute_batch(cur, SQL_INSERT_TXN, rows)
                    _complete_batch(cur, batch_id, len(rows))
                    conn.commit()

                total_rows += len(rows)
                total_batches += 1
                stats[f'mayyan_{month_str}'] = {
                    'rows': len(rows),
                    'units': sum(r['units_sold'] for r in rows),
                    'revenue': sum(r['revenue_ils'] for r in rows),
                }
                print(f"  ✓ Ma'ayan {month_str}: {len(rows)} rows"
                      f" ({sum(r['units_sold'] for r in rows):,} units,"
                      f" ₪{sum(r['revenue_ils'] for r in rows):,.0f})"
                      f"{' [DRY RUN]' if dry_run else ''}")

        # ── Biscotti transactions ──
        bisc_dist_id = dist_ids.get('biscotti')
        if bisc_dist_id:
            batch_name = f"biscotti_{month_str.replace(' ', '_').lower()}"
            existing = _batch_exists(cur, batch_name, bisc_dist_id)
            if existing and not force:
                print(f"  ⏭ Biscotti {month_str}: already ingested (batch #{existing})")
            else:
                if existing and force:
                    deleted = _rollback_batch(cur, existing)
                    print(f"  ↻ Rolled back Biscotti {month_str}: {deleted} old rows removed")

                if not dry_run:
                    batch_id = _create_batch(cur, batch_name, bisc_dist_id, month_str)
                else:
                    batch_id = -1

                rows = []
                for branch, prods in mdata.get('biscotti_customers', {}).items():
                    # Resolve branch → customer
                    cust_result = resolver.resolve_customer(branch)
                    cust_id = cust_result[0] if cust_result else None

                    # Upsert sale_point record (creates if new, returns existing ID if known)
                    sp_id = None
                    if not dry_run:
                        sp_id = _upsert_sale_point(cur, cust_id, bisc_dist_id, branch)

                    for sku, pdata in prods.items():
                        pid = product_ids.get(sku)
                        if not pid:
                            continue
                        units = pdata.get('units', 0)
                        revenue = pdata.get('value', 0.0)
                        unit_price = round(revenue / units, 2) if units else 0
                        cost = get_production_cost(sku)

                        rows.append(_build_txn_row(
                            txn_date=txn_date, year=year, month=month,
                            product_id=pid, distributor_id=bisc_dist_id,
                            customer_id=cust_id,
                            units=units, revenue=revenue,
                            unit_price=unit_price, cost_per_unit=cost,
                            dist_pct=0, revenue_method='calculated',
                            batch_id=batch_id,
                            source_ref=f"branch:{branch}",
                            sale_point_id=sp_id,
                        ))

                if rows and not dry_run:
                    psycopg2.extras.execute_batch(cur, SQL_INSERT_TXN, rows)
                    _complete_batch(cur, batch_id, len(rows))
                    conn.commit()

                total_rows += len(rows)
                total_batches += 1
                stats[f'biscotti_{month_str}'] = {
                    'rows': len(rows),
                    'units': sum(r['units_sold'] for r in rows),
                    'revenue': sum(r['revenue_ils'] for r in rows),
                }
                print(f"  ✓ Biscotti {month_str}: {len(rows)} rows"
                      f" ({sum(r['units_sold'] for r in rows):,} units,"
                      f" ₪{sum(r['revenue_ils'] for r in rows):,.0f})"
                      f"{' [DRY RUN]' if dry_run else ''}")

    cur.close()

    # ── Step 4: Summary ──
    print("\n[4/4] Ingestion summary")
    print("=" * 60)
    print(f"  Total batches:  {total_batches}")
    print(f"  Total rows:     {total_rows:,}")
    total_units = sum(s['units'] for s in stats.values())
    total_rev = sum(s['revenue'] for s in stats.values())
    print(f"  Total units:    {total_units:,}")
    print(f"  Total revenue:  ₪{total_rev:,.0f}")

    if dry_run:
        print("\n  ℹ DRY RUN — no data was written to the database.")
    else:
        # Report unresolved entities
        resolver.print_unresolved()

        # Verify totals match
        print("\n  Verification: querying sales_transactions...")
        verify_cur = conn.cursor()
        verify_cur.execute("""
            SELECT count(*), COALESCE(sum(units_sold), 0), COALESCE(sum(revenue_ils), 0)
            FROM sales_transactions
        """)
        db_count, db_units, db_rev = verify_cur.fetchone()
        print(f"  DB total rows:    {db_count:,}")
        print(f"  DB total units:   {int(db_units):,}")
        print(f"  DB total revenue: ₪{float(db_rev):,.0f}")

        # Per-distributor breakdown
        verify_cur.execute("""
            SELECT d.name_en, count(*), sum(st.units_sold), sum(st.revenue_ils)
            FROM sales_transactions st
            JOIN distributors d ON st.distributor_id = d.id
            GROUP BY d.name_en
            ORDER BY d.name_en
        """)
        print("\n  Per-distributor:")
        for name, cnt, units, rev in verify_cur.fetchall():
            print(f"    {name:20s}: {cnt:5d} rows, {int(units):8,} units, ₪{float(rev):10,.0f}")

        # Attribution rate
        verify_cur.execute("""
            SELECT
                count(*) FILTER (WHERE is_attributed) AS attributed,
                count(*) AS total
            FROM sales_transactions
        """)
        attr, total = verify_cur.fetchone()
        pct = (attr / total * 100) if total > 0 else 0
        print(f"\n  Attribution rate: {attr}/{total} ({pct:.1f}%)")
        verify_cur.close()

    return total_rows, total_batches


def main():
    parser = argparse.ArgumentParser(description='RAITO Phase 3: Ingest parsed data to sales_transactions')
    parser.add_argument('--force', action='store_true', help='Re-ingest even if batch already exists (rolls back old data)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be inserted without writing to DB')
    args = parser.parse_args()

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False

    try:
        rows, batches = ingest_all(conn, force=args.force, dry_run=args.dry_run)
        if rows == 0 and batches == 0:
            print("\n  ℹ Nothing to ingest (all batches already exist). Use --force to re-ingest.")
    except Exception as e:
        conn.rollback()
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
