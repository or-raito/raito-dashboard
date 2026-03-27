#!/usr/bin/env python3
"""
RAITO — Phase 3: SQL Read Layer (database_manager.py)

Provides get_consolidated_data() that returns the EXACT same dict structure
as parsers.consolidate_data(), but reads from PostgreSQL instead of Excel files.

Usage:
    from db.database_manager import get_consolidated_data
    data = get_consolidated_data()
    # data has same shape as parsers.consolidate_data() output

The returned dict has:
    {
        'months':       ['December 2025', 'January 2026', ...],
        'products':     ['chocolate', 'vanilla', ...],
        'monthly_data': {
            'December 2025': {
                'icedreams':               {sku: {units, value, cartons}},
                'mayyan':                  {sku: {units, value, transactions}},
                'biscotti':                {sku: {units, value}},
                'combined':                {sku: {units, icedreams_units, mayyan_units, ...}},
                'icedreams_customers':     {cust_en: {sku: {units, value}}},
                'mayyan_chains':           {chain_he: {sku: units}},
                'mayyan_chains_revenue':   {chain_he: {sku: {units, value}}},
                'mayyan_accounts':         {(chain_he, acct_he): {sku: {units, value}}},
                'mayyan_accounts_revenue': {(chain_he, acct_he): {sku: {units, value}}},
                'mayyan_branches':         set(),
                'mayyan_types':            {},
                'biscotti_customers':      {branch_he: {sku: {units, value}}},
            },
            ...
        },
        'production': {},
        'warehouse':  {},
        'dist_inv':   {},
    }
"""

import os
import sys
from pathlib import Path
from collections import defaultdict

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import psycopg2
import psycopg2.extras

from pricing_engine import get_b2b_price_safe, get_production_cost
from config import MONTH_ORDER

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
# Reference Data Loaders (cached)
# ═════════════════════════════════════════════════════════════════════════════

_ref_cache = {}


def _load_ref(cur):
    """Load reference lookups into _ref_cache. Called once per session."""
    if _ref_cache:
        return

    # products: id → sku_key
    cur.execute("SELECT id, sku_key FROM products")
    _ref_cache['product_id_to_sku'] = {row[0]: row[1] for row in cur.fetchall()}
    _ref_cache['sku_to_product_id'] = {v: k for k, v in _ref_cache['product_id_to_sku'].items()}

    # customers: id → name_en, name_he
    cur.execute("SELECT id, name_en, name_he, name_he_aliases FROM customers")
    _ref_cache['customer_id_to_en'] = {}
    _ref_cache['customer_id_to_he'] = {}
    for cid, name_en, name_he, aliases in cur.fetchall():
        _ref_cache['customer_id_to_en'][cid] = name_en
        _ref_cache['customer_id_to_he'][cid] = name_he or name_en

    # distributors: id → key
    cur.execute("SELECT id, key, name_en, commission_pct FROM distributors")
    _ref_cache['dist_id_to_key'] = {}
    _ref_cache['dist_key_to_id'] = {}
    for did, key, name_en, comm in cur.fetchall():
        _ref_cache['dist_id_to_key'][did] = key
        _ref_cache['dist_key_to_id'][key] = did

    # sale_points: id → (customer_id, distributor_id, branch_name_he)
    cur.execute("SELECT id, customer_id, distributor_id, branch_name_he FROM sale_points")
    _ref_cache['sp_id_to_info'] = {}
    for spid, cust_id, dist_id, branch_he in cur.fetchall():
        _ref_cache['sp_id_to_info'][spid] = (cust_id, dist_id, branch_he)


def _month_str(year, month):
    """Convert year+month integers to the parsers.py month string format."""
    import calendar
    month_name = calendar.month_name[month]
    return f"{month_name} {year}"


def _parse_mayyan_source_ref(ref):
    """Parse Ma'ayan source_row_ref 'chain:<he>|acct:<he>' → (chain_he, acct_he).

    Returns (None, None) if format doesn't match.
    """
    if not ref or '|' not in ref:
        return None, None
    try:
        parts = ref.split('|', 1)
        chain_he = parts[0].split(':', 1)[1] if parts[0].startswith('chain:') else ''
        acct_he = parts[1].split(':', 1)[1] if parts[1].startswith('acct:') else ''
        return chain_he, acct_he
    except (IndexError, ValueError):
        return None, None


def _parse_biscotti_source_ref(ref):
    """Parse Biscotti source_row_ref 'branch:<he>' → branch_he string.

    Returns 'Unknown' if format doesn't match.
    """
    if ref and ref.startswith('branch:'):
        return ref.split(':', 1)[1]
    return 'Unknown'


def _parse_icedream_source_ref(ref):
    """Parse Icedream source_row_ref to extract the raw Hebrew customer name.

    Supports two formats:
      - New (Phase 2 v2): 'customer_he:<he>|customer_en:<en>'
      - Legacy (Phase 2 v1): 'customer:<name>'

    Returns the Hebrew name for branch-level granularity matching the Excel parser.
    """
    if not ref:
        return None
    if ref.startswith('customer_he:'):
        # New format: customer_he:<he>|customer_en:<en>
        parts = ref.split('|', 1)
        return parts[0].split(':', 1)[1]
    elif ref.startswith('customer:'):
        # Legacy format: customer:<name> — may be English or Hebrew
        return ref.split(':', 1)[1]
    return None


# ═════════════════════════════════════════════════════════════════════════════
# SQL Queries — Distributor-Level Totals
# ═════════════════════════════════════════════════════════════════════════════

SQL_DIST_PRODUCT_TOTALS = """
    SELECT
        st.year, st.month,
        d.key AS dist_key,
        p.sku_key,
        SUM(st.units_sold)   AS total_units,
        SUM(st.revenue_ils)  AS total_revenue
    FROM sales_transactions st
    JOIN products p     ON p.id = st.product_id
    JOIN distributors d ON d.id = st.distributor_id
    GROUP BY st.year, st.month, d.key, p.sku_key
    ORDER BY st.year, st.month, d.key, p.sku_key
"""

# ═════════════════════════════════════════════════════════════════════════════
# SQL Queries — Customer-Level Breakdown (Icedream)
# ═════════════════════════════════════════════════════════════════════════════

# Icedream: per-row data with source_row_ref for branch-level Hebrew name.
# We parse source_row_ref in Python to preserve branch granularity matching Excel.
# Falls back to c.name_he when source_row_ref doesn't contain Hebrew names.
SQL_ICEDREAM_CUSTOMERS = """
    SELECT
        st.year, st.month,
        st.source_row_ref,
        c.name_he AS customer_he,
        p.sku_key,
        st.units_sold  AS units,
        st.revenue_ils AS value
    FROM sales_transactions st
    JOIN products p     ON p.id = st.product_id
    JOIN distributors d ON d.id = st.distributor_id
    LEFT JOIN customers c ON c.id = st.customer_id
    WHERE d.key IN ('icedream')
      AND st.is_attributed = TRUE
"""

# ═════════════════════════════════════════════════════════════════════════════
# SQL Queries — Ma'ayan Account-Level Breakdown
# ═════════════════════════════════════════════════════════════════════════════

# NOTE: Phase 2 stores sale_point_id = NULL. Ma'ayan account-level data
# is preserved in source_row_ref as 'chain:<he>|acct:<he>'.
# We parse source_row_ref in Python (see _parse_mayyan_accounts below).
SQL_MAYYAN_ATTRIBUTED = """
    SELECT
        st.year, st.month,
        st.source_row_ref,
        p.sku_key,
        st.units_sold  AS units,
        st.revenue_ils AS value
    FROM sales_transactions st
    JOIN products p     ON p.id = st.product_id
    JOIN distributors d ON d.id = st.distributor_id
    WHERE d.key IN ('mayyan_froz', 'mayyan_amb')
      AND st.is_attributed = TRUE
      AND st.source_row_ref LIKE 'chain:%%|acct:%%'
"""

# Ma'ayan chain-level aggregation (by customer Hebrew name)
SQL_MAYYAN_CHAINS = """
    SELECT
        st.year, st.month,
        COALESCE(c.name_he, 'Unknown') AS chain_he,
        p.sku_key,
        SUM(st.units_sold) AS units
    FROM sales_transactions st
    JOIN products p     ON p.id = st.product_id
    JOIN distributors d ON d.id = st.distributor_id
    LEFT JOIN customers c ON c.id = st.customer_id
    WHERE d.key IN ('mayyan_froz', 'mayyan_amb')
      AND st.is_attributed = TRUE
    GROUP BY st.year, st.month, c.name_he, p.sku_key
"""

# ═════════════════════════════════════════════════════════════════════════════
# SQL Queries — Biscotti Customer-Level
# ═════════════════════════════════════════════════════════════════════════════

# Biscotti: branch_he stored in source_row_ref as 'branch:<he>'
SQL_BISCOTTI_ATTRIBUTED = """
    SELECT
        st.year, st.month,
        st.source_row_ref,
        p.sku_key,
        st.units_sold  AS units,
        st.revenue_ils AS value
    FROM sales_transactions st
    JOIN products p     ON p.id = st.product_id
    JOIN distributors d ON d.id = st.distributor_id
    WHERE d.key = 'biscotti'
      AND st.is_attributed = TRUE
      AND st.source_row_ref LIKE 'branch:%%'
"""

# ═════════════════════════════════════════════════════════════════════════════
# SQL Queries — Inventory Snapshots (Latest per Distributor × Product)
# ═════════════════════════════════════════════════════════════════════════════

# Karfree warehouse: latest snapshot per product (source_type = 'warehouse')
SQL_WAREHOUSE_INVENTORY = """
    SELECT p.sku_key, inv.units, inv.pallets, inv.snapshot_date
    FROM inventory_snapshots inv
    JOIN products p ON p.id = inv.product_id
    JOIN distributors d ON d.id = inv.distributor_id
    WHERE d.key = 'karfree'
      AND inv.source_type = 'warehouse'
      AND inv.snapshot_date = (
          SELECT MAX(inv2.snapshot_date)
          FROM inventory_snapshots inv2
          WHERE inv2.distributor_id = inv.distributor_id
            AND inv2.source_type = 'warehouse'
      )
"""

# Distributor inventory: latest snapshot per product per distributor
SQL_DISTRIBUTOR_INVENTORY = """
    SELECT d.key AS dist_key, p.sku_key, inv.units, inv.cartons, inv.snapshot_date
    FROM inventory_snapshots inv
    JOIN products p ON p.id = inv.product_id
    JOIN distributors d ON d.id = inv.distributor_id
    WHERE inv.source_type = 'distributor'
      AND inv.snapshot_date = (
          SELECT MAX(inv2.snapshot_date)
          FROM inventory_snapshots inv2
          WHERE inv2.distributor_id = inv.distributor_id
            AND inv2.source_type = 'distributor'
      )
"""


# ═════════════════════════════════════════════════════════════════════════════
# Inventory Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _check_inventory_table(cur):
    """Check if inventory_snapshots table exists. Returns False if not."""
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'inventory_snapshots'
        )
    """)
    return cur.fetchone()[0]


def _get_warehouse_inventory(cur):
    """Fetch latest Karfree warehouse snapshot from SQL.

    Returns dict matching parse_karfree_inventory() output format:
    {
        'report_date': 'DD/MM/YYYY',
        'products': {sku: {'units': int, 'pallets': int, 'batches': []}},
        'total_units': int,
        'total_pallets': int,
    }
    """
    if not _check_inventory_table(cur):
        return {}

    cur.execute(SQL_WAREHOUSE_INVENTORY)
    rows = cur.fetchall()
    if not rows:
        return {}

    products = {}
    total_units = 0
    total_pallets = 0
    report_date = None

    for sku, units, pallets, snapshot_date in rows:
        units = int(units)
        pallets_val = int(pallets) if pallets is not None else 0
        products[sku] = {
            'units': units,
            'pallets': pallets_val,
            'batches': [],  # Batch-level detail not stored in SQL
        }
        total_units += units
        total_pallets += pallets_val
        if report_date is None:
            report_date = snapshot_date.strftime('%d/%m/%Y')

    return {
        'report_date': report_date,
        'products': products,
        'total_units': total_units,
        'total_pallets': total_pallets,
    }


def _get_distributor_inventory(cur):
    """Fetch latest Icedream/Ma'ayan stock snapshots from SQL.

    Returns dict matching get_distributor_inventory() output format:
    {
        'icedream': {
            'report_date': 'DD/MM/YYYY',
            'products': {sku: {'units': int, 'cartons': float, 'factor': int}},
            'total_units': int,
        },
        'mayyan': { ... },
    }
    """
    if not _check_inventory_table(cur):
        return {}

    cur.execute(SQL_DISTRIBUTOR_INVENTORY)
    rows = cur.fetchall()
    if not rows:
        return {}

    # dist_key mapping: SQL uses 'icedream' and 'mayyan_froz'
    # Dashboard expects 'icedream' and 'mayyan'
    DIST_KEY_MAP = {
        'icedream': 'icedream',
        'mayyan_froz': 'mayyan',
    }

    result = {}
    for dist_key, sku, units, cartons, snapshot_date in rows:
        display_key = DIST_KEY_MAP.get(dist_key)
        if not display_key:
            continue

        if display_key not in result:
            result[display_key] = {
                'report_date': snapshot_date.strftime('%d/%m/%Y'),
                'products': {},
                'total_units': 0,
            }

        units = int(units)
        cartons_val = float(cartons) if cartons is not None else 0
        factor = max(1, round(units / cartons_val)) if cartons_val > 0 else 1

        result[display_key]['products'][sku] = {
            'units': units,
            'cartons': cartons_val,
            'factor': factor,
        }
        result[display_key]['total_units'] += units

    return result


# ═════════════════════════════════════════════════════════════════════════════
# Main Public API
# ═════════════════════════════════════════════════════════════════════════════

def get_consolidated_data():
    """
    Query PostgreSQL and return a dict matching parsers.consolidate_data() output.

    This is the Phase 3 drop-in replacement. Dashboard generators
    (dashboard.py, cc_dashboard.py, salepoint_dashboard.py) consume this
    identically to the Excel-based consolidate_data().
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        _load_ref(cur)
        products = ['chocolate', 'vanilla', 'mango', 'magadat',
                     'dream_cake', 'dream_cake_2', 'pistachio']

        # ── 1. Distributor × Product totals ──────────────────────────────────
        cur.execute(SQL_DIST_PRODUCT_TOTALS)
        dist_totals = cur.fetchall()

        # Discover all months present in the data
        all_months_set = set()
        for year, month, dist_key, sku, units, revenue in dist_totals:
            ms = _month_str(year, month)
            if ms in MONTH_ORDER:
                all_months_set.add(ms)

        all_months = sorted(
            [m for m in all_months_set],
            key=lambda x: MONTH_ORDER.get(x, 99)
        )

        # Initialize monthly_data skeleton
        monthly_data = {}
        for m in all_months:
            monthly_data[m] = {
                'icedreams': {},
                'mayyan': {},
                'biscotti': {},
                'combined': {},
                'icedreams_customers': {},
                'mayyan_chains': {},
                'mayyan_chains_revenue': {},
                'mayyan_accounts': {},
                'mayyan_accounts_revenue': {},
                'mayyan_branches': set(),
                'mayyan_types': {},
                'biscotti_customers': {},
            }

        # Populate distributor-level totals
        for year, month, dist_key, sku, units, revenue in dist_totals:
            ms = _month_str(year, month)
            if ms not in monthly_data:
                continue

            units = int(units)
            revenue = float(revenue)

            if dist_key == 'icedream':
                monthly_data[ms]['icedreams'][sku] = {
                    'units': units,
                    'value': round(revenue, 2),
                    'cartons': 0,  # Not tracked in SQL (informational only)
                }
            elif dist_key in ('mayyan_froz', 'mayyan_amb'):
                existing = monthly_data[ms]['mayyan'].get(sku, {'units': 0, 'value': 0, 'transactions': 0})
                monthly_data[ms]['mayyan'][sku] = {
                    'units': existing['units'] + units,
                    'value': round(existing['value'] + revenue, 2),
                    'transactions': 0,
                }
            elif dist_key == 'biscotti':
                monthly_data[ms]['biscotti'][sku] = {
                    'units': units,
                    'value': round(revenue, 2),
                }

        # ── 2. Build combined totals ─────────────────────────────────────────
        for m in all_months:
            md = monthly_data[m]
            for p in products:
                ice_units = md['icedreams'].get(p, {}).get('units', 0)
                may_units = md['mayyan'].get(p, {}).get('units', 0)
                bisc_units = md['biscotti'].get(p, {}).get('units', 0)
                ice_value = md['icedreams'].get(p, {}).get('value', 0)
                _may_actual = md['mayyan'].get(p, {}).get('value', 0)
                may_value = _may_actual if _may_actual > 0 else round(may_units * get_b2b_price_safe(p), 2)
                bisc_value = md['biscotti'].get(p, {}).get('value', 0)
                total_value = round(ice_value + may_value + bisc_value, 2)
                prod_cost_per_unit = get_production_cost(p)
                total_units = ice_units + may_units + bisc_units
                total_prod_cost = round(total_units * prod_cost_per_unit, 2)
                gross_margin = round(total_value - total_prod_cost, 2) if p != 'magadat' else 0

                md['combined'][p] = {
                    'units': total_units,
                    'icedreams_units': ice_units,
                    'mayyan_units': may_units,
                    'biscotti_units': bisc_units,
                    'icedreams_value': ice_value,
                    'mayyan_value': may_value,
                    'biscotti_value': bisc_value,
                    'total_value': total_value,
                    'production_cost': total_prod_cost,
                    'gross_margin': gross_margin,
                }

        # ── 3. Icedream customers ────────────────────────────────────────────
        # Keys must be raw Hebrew names (branch-level) — downstream CC calls
        # extract_customer_name(cust_heb) and SP uses the raw key as branch name.
        # source_row_ref stores the raw Hebrew: 'customer_he:<he>|customer_en:<en>'
        cur.execute(SQL_ICEDREAM_CUSTOMERS)
        for year, month, source_ref, cust_he_fallback, sku, units, value in cur.fetchall():
            ms = _month_str(year, month)
            if ms not in monthly_data:
                continue

            # Extract raw Hebrew branch name from source_row_ref, fall back to c.name_he
            cust_key = _parse_icedream_source_ref(source_ref) or cust_he_fallback or 'Unknown'

            custs = monthly_data[ms]['icedreams_customers']
            if cust_key not in custs:
                custs[cust_key] = {}
            existing = custs[cust_key].get(sku, {'units': 0, 'value': 0.0})
            custs[cust_key][sku] = {
                'units': existing['units'] + int(units),
                'value': round(existing['value'] + float(value), 2),
            }

        # Filter out zero-unit customers (same as consolidate_data)
        for m in all_months:
            filtered = {}
            for cust, pdata in monthly_data[m]['icedreams_customers'].items():
                total_u = sum(v.get('units', 0) for v in pdata.values())
                if total_u != 0:
                    for p, vals in pdata.items():
                        vals['value'] = round(vals.get('value', 0), 2)
                    filtered[cust] = pdata
            monthly_data[m]['icedreams_customers'] = filtered

        # ── 4. Ma'ayan accounts ──────────────────────────────────────────────
        # Phase 2 stores (chain_he, acct_he) in source_row_ref as
        # 'chain:<chain_he>|acct:<acct_he>'. Parse these back into tuple keys.
        cur.execute(SQL_MAYYAN_ATTRIBUTED)
        for year, month, source_ref, sku, units, value in cur.fetchall():
            ms = _month_str(year, month)
            if ms not in monthly_data:
                continue

            chain_he, acct_he = _parse_mayyan_source_ref(source_ref)
            if chain_he is None:
                continue

            key = (chain_he, acct_he)
            accts = monthly_data[ms]['mayyan_accounts']
            if key not in accts:
                accts[key] = {}
            existing = accts[key].get(sku, {'units': 0, 'value': 0.0})
            accts[key][sku] = {
                'units': existing['units'] + int(units),
                'value': round(existing['value'] + float(value), 2),
            }

        # mayyan_accounts_revenue is a passthrough (pricing applied at ingest)
        for m in all_months:
            monthly_data[m]['mayyan_accounts_revenue'] = monthly_data[m]['mayyan_accounts']

        # Ma'ayan branches: all unique acct_he values from the accounts
        for m in all_months:
            for (chain_he, acct_he) in monthly_data[m]['mayyan_accounts']:
                monthly_data[m]['mayyan_branches'].add(acct_he)

        # ── 5. Ma'ayan chains (customer-level aggregation) ───────────────────
        cur.execute(SQL_MAYYAN_CHAINS)
        for year, month, chain_he, sku, units in cur.fetchall():
            ms = _month_str(year, month)
            if ms not in monthly_data:
                continue
            chains = monthly_data[ms]['mayyan_chains']
            if chain_he not in chains:
                chains[chain_he] = {}
            chains[chain_he][sku] = int(units)

        # Build mayyan_chains_revenue (units × B2B price, same as consolidate_data)
        for m in all_months:
            chains_rev = {}
            for chain, pdata in monthly_data[m]['mayyan_chains'].items():
                chains_rev[chain] = {}
                for p, units in pdata.items():
                    chains_rev[chain][p] = {
                        'units': units,
                        'value': round(units * get_b2b_price_safe(p), 2),
                    }
            monthly_data[m]['mayyan_chains_revenue'] = chains_rev

        # ── 7. Biscotti customers ────────────────────────────────────────────
        # Phase 2 stores branch_he in source_row_ref as 'branch:<he>'
        cur.execute(SQL_BISCOTTI_ATTRIBUTED)
        for year, month, source_ref, sku, units, value in cur.fetchall():
            ms = _month_str(year, month)
            if ms not in monthly_data:
                continue
            branch_key = _parse_biscotti_source_ref(source_ref)
            biscs = monthly_data[ms]['biscotti_customers']
            if branch_key not in biscs:
                biscs[branch_key] = {}
            existing = biscs[branch_key].get(sku, {'units': 0, 'value': 0.0})
            biscs[branch_key][sku] = {
                'units': existing['units'] + int(units),
                'value': round(existing['value'] + float(value), 2),
            }

        # ── 8. Inventory Snapshots ──────────────────────────────────────────
        warehouse_data = _get_warehouse_inventory(cur)
        dist_inv_data = _get_distributor_inventory(cur)

        # ── Assemble final output ────────────────────────────────────────────
        consolidated = {
            'months': all_months,
            'products': products,
            'monthly_data': monthly_data,
            'production': {},
            'warehouse': warehouse_data,
            'dist_inv': dist_inv_data,
        }

        return consolidated

    finally:
        cur.close()
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# Validation Helper
# ═════════════════════════════════════════════════════════════════════════════

def validate_against_parsers():
    """
    Compare SQL-based consolidated data vs Excel-based consolidated data.
    Prints a reconciliation report showing deltas per month/distributor.
    """
    from parsers import consolidate_data as excel_consolidate

    print("=" * 70)
    print("PHASE 3 RECONCILIATION: SQL vs Excel Parser Output")
    print("=" * 70)

    print("\nLoading Excel-based data...")
    excel_data = excel_consolidate()

    print("Loading SQL-based data...")
    sql_data = get_consolidated_data()

    # Compare months
    excel_months = set(excel_data['months'])
    sql_months = set(sql_data['months'])
    print(f"\nMonths in Excel: {sorted(excel_months)}")
    print(f"Months in SQL:   {sorted(sql_months)}")
    if excel_months != sql_months:
        print(f"  ⚠ Month mismatch! Excel-only: {excel_months - sql_months}, SQL-only: {sql_months - excel_months}")

    common_months = sorted(excel_months & sql_months, key=lambda x: MONTH_ORDER.get(x, 99))

    # Per-month comparison
    print(f"\n{'Month':<20} {'Source':<8} {'Units':>10} {'Revenue':>14} {'Δ Units':>10} {'Δ Revenue':>14}")
    print("-" * 80)

    for m in common_months:
        e_md = excel_data['monthly_data'].get(m, {})
        s_md = sql_data['monthly_data'].get(m, {})

        for dist_label, e_key in [('Icedream', 'icedreams'), ('Ma\'ayan', 'mayyan'), ('Biscotti', 'biscotti')]:
            e_dist = e_md.get(e_key, {})
            s_dist = s_md.get(e_key, {})

            e_units = sum(v.get('units', 0) for v in e_dist.values() if isinstance(v, dict))
            e_rev = sum(v.get('value', 0) for v in e_dist.values() if isinstance(v, dict))
            s_units = sum(v.get('units', 0) for v in s_dist.values() if isinstance(v, dict))
            s_rev = sum(v.get('value', 0) for v in s_dist.values() if isinstance(v, dict))

            d_u = s_units - e_units
            d_r = s_rev - e_rev

            flag_u = " ✓" if d_u == 0 else f" ⚠"
            flag_r = " ✓" if abs(d_r) < 1 else f" ⚠"

            print(f"{m:<20} {dist_label:<8} {s_units:>10,} {s_rev:>14,.2f} {d_u:>+10,}{flag_u} {d_r:>+14,.2f}{flag_r}")

    # ── Icedream Customer-level comparison ──
    print(f"\n--- Icedream Customers (by key) ---")
    print(f"{'Month':<20} {'Key Count (E/S)':<20} {'E-Units':>10} {'S-Units':>10} {'Δ':>10}")
    print("-" * 75)
    ice_ok = True
    for m in common_months:
        e_custs = excel_data['monthly_data'].get(m, {}).get('icedreams_customers', {})
        s_custs = sql_data['monthly_data'].get(m, {}).get('icedreams_customers', {})
        e_total = sum(sum(v.get('units', 0) for v in pdata.values()) for pdata in e_custs.values())
        s_total = sum(sum(v.get('units', 0) for v in pdata.values()) for pdata in s_custs.values())
        d = s_total - e_total
        flag = " ✓" if d == 0 else " ⚠"
        if d != 0:
            ice_ok = False
        print(f"{m:<20} {len(e_custs):>5} / {len(s_custs):<5}       {e_total:>10,} {s_total:>10,} {d:>+10,}{flag}")

    # Show sample key comparison for first month
    if common_months:
        m0 = common_months[0]
        e_keys = set(excel_data['monthly_data'].get(m0, {}).get('icedreams_customers', {}).keys())
        s_keys = set(sql_data['monthly_data'].get(m0, {}).get('icedreams_customers', {}).keys())
        common_keys = e_keys & s_keys
        print(f"\n  Sample ({m0}): {len(common_keys)} matching keys, "
              f"{len(e_keys - s_keys)} Excel-only, {len(s_keys - e_keys)} SQL-only")
        if e_keys - s_keys:
            print(f"  Excel-only samples: {list(e_keys - s_keys)[:3]}")
        if s_keys - e_keys:
            print(f"  SQL-only samples:   {list(s_keys - e_keys)[:3]}")

    # ── Ma'ayan Accounts comparison ──
    print(f"\n--- Ma'ayan Accounts (tuple keys) ---")
    print(f"{'Month':<20} {'Key Count (E/S)':<20} {'E-Units':>10} {'S-Units':>10} {'Δ':>10}")
    print("-" * 75)
    may_ok = True
    for m in common_months:
        e_accts = excel_data['monthly_data'].get(m, {}).get('mayyan_accounts', {})
        s_accts = sql_data['monthly_data'].get(m, {}).get('mayyan_accounts', {})
        e_total = sum(
            sum(v.get('units', 0) for v in pdata.values() if isinstance(v, dict))
            for pdata in e_accts.values()
        )
        s_total = sum(
            sum(v.get('units', 0) for v in pdata.values() if isinstance(v, dict))
            for pdata in s_accts.values()
        )
        d = s_total - e_total
        flag = " ✓" if d == 0 else " ⚠"
        if d != 0:
            may_ok = False
        print(f"{m:<20} {len(e_accts):>5} / {len(s_accts):<5}       {e_total:>10,} {s_total:>10,} {d:>+10,}{flag}")

    # Show sample tuple keys
    if common_months:
        m0 = common_months[0]
        e_keys = set(excel_data['monthly_data'].get(m0, {}).get('mayyan_accounts', {}).keys())
        s_keys = set(sql_data['monthly_data'].get(m0, {}).get('mayyan_accounts', {}).keys())
        common_keys = e_keys & s_keys
        print(f"\n  Sample ({m0}): {len(common_keys)} matching keys, "
              f"{len(e_keys - s_keys)} Excel-only, {len(s_keys - e_keys)} SQL-only")
        if e_keys - s_keys:
            samples = list(e_keys - s_keys)[:3]
            print(f"  Excel-only samples: {samples}")
        if s_keys - e_keys:
            samples = list(s_keys - e_keys)[:3]
            print(f"  SQL-only samples:   {samples}")

    # ── Biscotti Customers comparison ──
    print(f"\n--- Biscotti Customers ---")
    for m in common_months:
        e_bisc = excel_data['monthly_data'].get(m, {}).get('biscotti_customers', {})
        s_bisc = sql_data['monthly_data'].get(m, {}).get('biscotti_customers', {})
        if e_bisc or s_bisc:
            e_total = sum(
                sum(v.get('units', 0) for v in pdata.values() if isinstance(v, dict))
                for pdata in e_bisc.values()
            )
            s_total = sum(
                sum(v.get('units', 0) for v in pdata.values() if isinstance(v, dict))
                for pdata in s_bisc.values()
            )
            d = s_total - e_total
            flag = " ✓" if d == 0 else " ⚠"
            print(f"  {m}: E={len(e_bisc)} keys/{e_total:,}u, S={len(s_bisc)} keys/{s_total:,}u  Δ={d:+,}{flag}")

    print("\n" + "=" * 70)
    print("Reconciliation complete.")
    if ice_ok and may_ok:
        print("✓ All customer-level data matches.")
    else:
        print("⚠ Some customer-level mismatches detected — see above.")
    print("=" * 70)


def reset_cache():
    """Clear reference data cache. Useful for testing."""
    global _ref_cache
    _ref_cache = {}


if __name__ == '__main__':
    validate_against_parsers()
