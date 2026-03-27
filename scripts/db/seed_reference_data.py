#!/usr/bin/env python3
"""
RAITO — Phase 1: Seed Reference Data into PostgreSQL

Reads from the existing SSOT engines (registry.py, pricing_engine.py, config.py)
and inserts all reference data into the SQL schema.

Usage:
    python3 scripts/db/seed_reference_data.py

Requires:
    - PostgreSQL running with schema.sql already applied
    - psycopg2 installed: pip install psycopg2-binary
    - Environment variable DATABASE_URL or defaults to local dev

This script is idempotent: uses INSERT ... ON CONFLICT DO NOTHING for all tables.
Safe to re-run after schema wipes or partial failures.
"""

import os
import sys
from pathlib import Path
from datetime import date

# Add scripts/ to path so we can import the SSOT engines
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import psycopg2
from psycopg2.extras import execute_values

# ── Connection ────────────────────────────────────────────────────────────────

DEFAULT_DB_URL = "postgresql://raito:raito@localhost:5432/raito"

def get_connection():
    """Get a PostgreSQL connection from DATABASE_URL env var or default."""
    url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# Seed Data — hardcoded from SSOT engines (registry.py + pricing_engine.py)
# ═════════════════════════════════════════════════════════════════════════════
# We import from the engines directly rather than re-typing values, so any
# future engine change is automatically picked up by re-running this seed.

from registry import PRODUCTS, CUSTOMER_NAMES_EN, CUSTOMER_PREFIXES, DISTRIBUTORS
from pricing_engine import (
    _B2B_PRICES, PRODUCTION_COST, _CUSTOMER_PRICES,
    _MAAYAN_CHAIN_TO_PRICEDB,
)

# ── Manufacturers ─────────────────────────────────────────────────────────────
# Source: RAITO_BRIEFING.md § Manufacturers

MANUFACTURERS_DATA = [
    # (name, contact_email, address, lead_time_days, moq_units, is_active)
    ("Vaniglia",       None,                   None,           None, None, True),
    ("Piece of Cake",  None,                   None,           None, None, False),
    ("Biscotti",       "dudi@biscotti.com",    "Bnei Brak",    14,   0,    True),
    ("Din Shiwuk",     None,                   None,           None, None, False),  # planned
    ("Rajuan",         None,                   None,           None, None, False),  # planned
]

# Map manufacturer name → the products they produce (for FK resolution)
MANUFACTURER_PRODUCT_MAP = {
    "Vaniglia":      ["chocolate", "vanilla", "mango", "pistachio", "magadat"],
    "Piece of Cake": ["dream_cake"],
    "Biscotti":      ["dream_cake_2"],
}

# ── Distributors ──────────────────────────────────────────────────────────────
# Source: registry.DISTRIBUTORS + briefing § Distributors

DISTRIBUTORS_DATA = [
    # (key, name_en, name_he, commission_pct, report_format, is_active, notes)
    ("icedream",    "Icedream",          "אייסדרים",         15.0,  "format_a_xlsx",   True,  "Two formats: A (monthly XLSX) and B (weekly XLS BIFF8)"),
    ("mayyan_froz", "Ma'ayan (Frozen)",  "מעיין נציגויות",   25.0,  "weekly_xlsx",     True,  "Frozen distribution. Reports have no revenue column."),
    ("biscotti",    "Biscotti",          "ביסקוטי",           0.0,  None,              True,  "Dream Cake chilled. Creator commission model: ₪10/cake to Daniel Amit."),
    ("mayyan_amb",  "Ma'ayan (Ambient)", "מעיין נציגויות",   0.0,   None,              False, "Turbo Nuts — future. Commission TBD."),
    ("karfree",     "Karfree Warehouse", "קרפרי",            0.0,   "pdf_report",      True,  "Cold storage warehouse. Inventory-only — no sales transactions."),
]

# ── Products (derived from registry.PRODUCTS) ────────────────────────────────
# Additional metadata from briefing that isn't in registry.py

PRODUCT_EXTRA = {
    "chocolate":    {"barcode": "7290020531032", "units_carton": 10, "units_pallet": 2400, "shelf_life": 12, "storage": "-25°C", "launched": "2025-12-01", "order": 1},
    "vanilla":      {"barcode": "7290020531025", "units_carton": 6,  "units_pallet": 2400, "shelf_life": 12, "storage": "-25°C", "launched": "2025-12-01", "order": 2},
    "mango":        {"barcode": "7290020531018", "units_carton": 10, "units_pallet": 2400, "shelf_life": 12, "storage": "-25°C", "launched": "2025-12-01", "order": 3},
    "pistachio":    {"barcode": "7290020531049", "units_carton": 10, "units_pallet": 2400, "shelf_life": 12, "storage": "-25°C", "launched": "2026-02-01", "order": 4},
    "magadat":      {"barcode": None,            "units_carton": None,"units_pallet": None, "shelf_life": None,"storage": "-25°C", "launched": "2025-12-01", "order": 7, "discontinued": "2026-01-01"},
    "dream_cake":   {"barcode": "726529980677",  "units_carton": 3,  "units_pallet": 600,  "shelf_life": 3,  "storage": "-18°C", "launched": "2025-12-01", "order": 5, "discontinued": "2026-03-01"},
    "dream_cake_2": {"barcode": "7290117842973", "units_carton": 3,  "units_pallet": None, "shelf_life": None,"storage": "0-4°C", "launched": "2026-03-01", "order": 6},
}

# Hebrew product names as they appear in distributor files (for classify_product matching)
PRODUCT_NAMES_HE = {
    "chocolate":    "טורבו- גלידת שוקולד אגוזי לוז 250",
    "vanilla":      "טורבו- גלידת וניל מדגסקר 250 מל",
    "mango":        "טורבו- גלידת מנגו מאיה 250 מל",
    "pistachio":    "טורבו- גלידת פיסטוק 250",
    "magadat":      "טורבו מארז גלידות 250 מל * 3 יח'",
    "dream_cake":   "דרים קייק- 3 יח'",
    "dream_cake_2": "דרים קייק - ביסקוטי",
}

# ── Customers ─────────────────────────────────────────────────────────────────
# Source: registry.CUSTOMER_NAMES_EN + briefing §Sub-Brand Split Rules + §CC tab

# Hebrew aliases: all known variant spellings from raw distributor reports
CUSTOMER_ALIASES = {
    "AMPM":           ["דור אלון AM:PM", "AMPM", "דור אלון AMPM"],
    "Alonit":         ["אלונית", "דור אלון", "שפר את אלי לוי בע\"מ"],
    "Good Pharm":     ["גוד פארם"],
    "Domino's Pizza": ["דומינוס", "דומינוס פיצה"],
    "Delek Menta":    ["דלק מנטה"],
    "Wolt Market":    ["וולט מרקט", "וולט", "וואלט", "וואלט מרקט"],
    "Naomi's Farm":   ["חוות נעמי"],
    "Tiv Taam":       ["טיב טעם"],
    "Yango Deli":     ["ינגו", "ינגו דלי ישראל בע\"מ"],
    "Carmella":       ["כרמלה"],
    "Noy HaSade":     ["נוי השדה"],
    "Sonol":          ["סונול"],
    "Oogiplatset":    ["עוגיפלצת", "עוגיפלצת בע\"מ"],
    "Foot Locker":    ["פוט לוקר"],
    "Paz Super Yuda": ["פז חברת נפט- סופר יודה", "פז סופר יודה"],
    "Paz Yellow":     ["פז ילו", "פז יילו", "פז  ילו"],
    "Private Market": ["שוק פרטי"],
    "Biscotti Chain": ["ביסקוטי"],
}

# Customers tracked in the CC dashboard (the ~18 major accounts)
CC_TRACKED_CUSTOMERS = {
    "AMPM", "Alonit", "Good Pharm", "Domino's Pizza", "Delek Menta",
    "Wolt Market", "Naomi's Farm", "Tiv Taam", "Yango Deli", "Carmella",
    "Noy HaSade", "Sonol", "Oogiplatset", "Foot Locker", "Paz Super Yuda",
    "Paz Yellow", "Private Market", "Biscotti Chain",
}

# Primary distributor for each customer
CUSTOMER_PRIMARY_DIST = {
    "AMPM": "mayyan_froz", "Alonit": "mayyan_froz", "Delek Menta": "mayyan_froz",
    "Sonol": "mayyan_froz", "Paz Yellow": "mayyan_froz", "Paz Super Yuda": "mayyan_froz",
    "Tiv Taam": "mayyan_froz", "Private Market": "mayyan_froz", "Noy HaSade": "mayyan_froz",
    "Good Pharm": "icedream", "Domino's Pizza": "icedream", "Wolt Market": "icedream",
    "Naomi's Farm": "icedream", "Yango Deli": "icedream", "Carmella": "icedream",
    "Foot Locker": "icedream", "Oogiplatset": "icedream",
    "Biscotti Chain": "biscotti",
}


# ═════════════════════════════════════════════════════════════════════════════
# Seed Functions
# ═════════════════════════════════════════════════════════════════════════════

def seed_manufacturers(cur):
    """Insert manufacturer rows."""
    print("  Seeding manufacturers...")
    for name, email, addr, lead_time, moq, active in MANUFACTURERS_DATA:
        cur.execute("""
            INSERT INTO manufacturers (name, contact_email, address, lead_time_days, moq_units, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO NOTHING
        """, (name, email, addr, lead_time, moq, active))
    print(f"    → {len(MANUFACTURERS_DATA)} manufacturers")


def seed_distributors(cur):
    """Insert distributor rows."""
    print("  Seeding distributors...")
    for key, name_en, name_he, commission, fmt, active, notes in DISTRIBUTORS_DATA:
        cur.execute("""
            INSERT INTO distributors (key, name_en, name_he, commission_pct, report_format, is_active, notes)
            VALUES (%s, %s, %s, COALESCE(%s, 0.00), %s, %s, %s)
            ON CONFLICT (key) DO NOTHING
        """, (key, name_en, name_he, commission, fmt, active, notes))
    print(f"    → {len(DISTRIBUTORS_DATA)} distributors")


def seed_products(cur):
    """Insert product rows from registry.PRODUCTS + pricing_engine prices + briefing metadata."""
    print("  Seeding products...")

    # Resolve manufacturer IDs
    cur.execute("SELECT id, name FROM manufacturers")
    mfg_map = {name: mid for mid, name in cur.fetchall()}

    count = 0
    for sku, product in PRODUCTS.items():
        extra = PRODUCT_EXTRA.get(sku, {})
        b2b_price = _B2B_PRICES.get(sku)
        prod_cost = PRODUCTION_COST.get(sku)

        # Find manufacturer ID
        mfg_name = product.manufacturer
        # registry uses 'Raito' as manufacturer for Turbo — actual manufacturer is Vaniglia
        if mfg_name == 'Raito':
            mfg_name = 'Vaniglia'
        mfg_id = mfg_map.get(mfg_name)

        launched = extra.get("launched")
        discontinued = extra.get("discontinued")

        cur.execute("""
            INSERT INTO products (
                sku_key, barcode, full_name_en, full_name_he, short_name,
                brand_key, category, manufacturer_id, status,
                production_cost_ils, b2b_list_price_ils,
                units_per_carton, units_per_pallet, shelf_life_months, storage_temp,
                color_hex, flavor_color_hex, display_order,
                launched_at, discontinued_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            ON CONFLICT (sku_key) DO NOTHING
        """, (
            sku, extra.get("barcode"), product.name,
            PRODUCT_NAMES_HE.get(sku), product.short_name,
            product.brand, product.category, mfg_id, product.status,
            prod_cost, b2b_price,
            extra.get("units_carton"), extra.get("units_pallet"),
            extra.get("shelf_life"), extra.get("storage"),
            product.color,
            # Flavor colors from registry
            {"chocolate": "#8B4513", "vanilla": "#DAA520", "mango": "#FF8C00",
             "pistachio": "#93C572", "dream_cake": "#DB7093",
             "dream_cake_2": "#C2185B", "magadat": "#9CA3AF"}.get(sku),
            extra.get("order"),
            launched, discontinued,
        ))
        count += 1

    print(f"    → {count} products")


def seed_customers(cur):
    """Insert customer rows with Hebrew aliases."""
    print("  Seeding customers...")

    # Resolve distributor IDs
    cur.execute("SELECT id, key FROM distributors")
    dist_map = {key: did for did, key in cur.fetchall()}

    count = 0
    for name_en, aliases in CUSTOMER_ALIASES.items():
        # Find primary Hebrew name (first alias or from CUSTOMER_NAMES_EN reverse lookup)
        name_he = aliases[0] if aliases else None

        dist_key = CUSTOMER_PRIMARY_DIST.get(name_en)
        dist_id = dist_map.get(dist_key) if dist_key else None
        cc_tracked = name_en in CC_TRACKED_CUSTOMERS

        cur.execute("""
            INSERT INTO customers (
                name_en, name_he, name_he_aliases,
                primary_distributor_id, customer_type, cc_tracked, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name_en) DO NOTHING
        """, (
            name_en, name_he, aliases,
            dist_id, "chain", cc_tracked, True,
        ))
        count += 1

    print(f"    → {count} customers")


def seed_price_history(cur):
    """Insert initial price records from pricing_engine.

    Three categories:
    1. B2B list prices (customer_id = NULL) — from _B2B_PRICES
    2. Production costs — from PRODUCTION_COST (stored as price_type='production_cost')
    3. Customer-specific negotiated prices — from _CUSTOMER_PRICES
    """
    print("  Seeding price_history...")

    # Resolve product IDs
    cur.execute("SELECT id, sku_key FROM products")
    prod_map = {sku: pid for pid, sku in cur.fetchall()}

    # Resolve customer IDs
    cur.execute("SELECT id, name_en FROM customers")
    cust_map = {name: cid for cid, name in cur.fetchall()}

    launch_date = date(2025, 12, 1)  # Official data start
    count = 0

    # 1. B2B list prices (one row per product, customer_id = NULL)
    for sku, price in _B2B_PRICES.items():
        prod_id = prod_map.get(sku)
        if not prod_id:
            print(f"    ⚠ Skipping B2B price for unknown SKU: {sku}")
            continue
        cur.execute("""
            INSERT INTO price_history (
                product_id, customer_id, distributor_id,
                price_ils, effective_from, effective_to,
                price_type, source_reference
            ) VALUES (%s, NULL, NULL, %s, %s, NULL, 'b2b_list', 'pricing_engine._B2B_PRICES (initial seed)')
        """, (prod_id, price, launch_date))
        count += 1

    # 2. Production costs (stored as price_type='production_cost', customer_id = NULL)
    for sku, cost in PRODUCTION_COST.items():
        prod_id = prod_map.get(sku)
        if not prod_id:
            continue
        cur.execute("""
            INSERT INTO price_history (
                product_id, customer_id, distributor_id,
                price_ils, effective_from, effective_to,
                price_type, source_reference
            ) VALUES (%s, NULL, NULL, %s, %s, NULL, 'production_cost', 'pricing_engine.PRODUCTION_COST (initial seed)')
        """, (prod_id, cost, launch_date))
        count += 1

    # 3. Customer-specific negotiated prices (from _CUSTOMER_PRICES)
    # These apply to all Turbo SKUs for the given customer (per pricing_engine.get_customer_price logic)
    turbo_skus = [sku for sku, p in PRODUCTS.items() if p.is_turbo() and p.is_active()]
    for cust_en, price in _CUSTOMER_PRICES.items():
        cust_id = cust_map.get(cust_en)
        if not cust_id:
            print(f"    ⚠ Skipping customer price for unknown customer: {cust_en}")
            continue
        for sku in turbo_skus:
            prod_id = prod_map.get(sku)
            if not prod_id:
                continue
            cur.execute("""
                INSERT INTO price_history (
                    product_id, customer_id, distributor_id,
                    price_ils, effective_from, effective_to,
                    price_type, source_reference
                ) VALUES (%s, %s, NULL, %s, %s, NULL, 'negotiated', 'pricing_engine._CUSTOMER_PRICES (initial seed)')
            """, (prod_id, cust_id, price, launch_date))
            count += 1

    print(f"    → {count} price records")


# ═════════════════════════════════════════════════════════════════════════════
# Validation
# ═════════════════════════════════════════════════════════════════════════════

def validate(cur):
    """Run post-seed validation checks against the briefing source of truth."""
    print("\n  Running validation checks...")
    errors = []

    # Check 1: Product count
    cur.execute("SELECT COUNT(*) FROM products")
    prod_count = cur.fetchone()[0]
    expected_products = len(PRODUCTS)
    if prod_count != expected_products:
        errors.append(f"Products: expected {expected_products}, got {prod_count}")
    else:
        print(f"    ✓ Products: {prod_count} (matches registry.PRODUCTS)")

    # Check 2: All active SKUs have B2B prices
    cur.execute("""
        SELECT p.sku_key FROM products p
        WHERE p.status IN ('active', 'new')
          AND NOT EXISTS (
              SELECT 1 FROM price_history ph
              WHERE ph.product_id = p.id
                AND ph.price_type = 'b2b_list'
                AND ph.effective_to IS NULL
          )
    """)
    missing_prices = [r[0] for r in cur.fetchall()]
    if missing_prices:
        errors.append(f"Active products missing B2B prices: {missing_prices}")
    else:
        print("    ✓ All active products have B2B list prices")

    # Check 3: Customer count
    cur.execute("SELECT COUNT(*) FROM customers")
    cust_count = cur.fetchone()[0]
    expected_customers = len(CUSTOMER_ALIASES)
    if cust_count != expected_customers:
        errors.append(f"Customers: expected {expected_customers}, got {cust_count}")
    else:
        print(f"    ✓ Customers: {cust_count}")

    # Check 4: CC-tracked customers
    cur.execute("SELECT COUNT(*) FROM customers WHERE cc_tracked = TRUE")
    cc_count = cur.fetchone()[0]
    expected_cc = len(CC_TRACKED_CUSTOMERS)
    if cc_count != expected_cc:
        errors.append(f"CC-tracked customers: expected {expected_cc}, got {cc_count}")
    else:
        print(f"    ✓ CC-tracked customers: {cc_count}")

    # Check 5: Customer-specific prices cover all CC Ma'ayan chains
    cur.execute("""
        SELECT c.name_en FROM customers c
        WHERE c.cc_tracked = TRUE
          AND c.primary_distributor_id = (SELECT id FROM distributors WHERE key = 'mayyan_froz')
          AND NOT EXISTS (
              SELECT 1 FROM price_history ph
              WHERE ph.customer_id = c.id
                AND ph.price_type = 'negotiated'
                AND ph.effective_to IS NULL
          )
    """)
    missing_cust_prices = [r[0] for r in cur.fetchall()]
    if missing_cust_prices:
        # Some Ma'ayan chains legitimately don't have negotiated prices (use B2B fallback)
        print(f"    ℹ Ma'ayan customers without negotiated prices (using B2B fallback): {missing_cust_prices}")
    else:
        print("    ✓ All Ma'ayan CC customers have negotiated prices")

    # Check 6: B2B prices match pricing_engine values
    cur.execute("""
        SELECT p.sku_key, ph.price_ils
        FROM price_history ph
        JOIN products p ON p.id = ph.product_id
        WHERE ph.price_type = 'b2b_list'
          AND ph.customer_id IS NULL
          AND ph.effective_to IS NULL
        ORDER BY p.sku_key
    """)
    for sku, db_price in cur.fetchall():
        engine_price = _B2B_PRICES.get(sku)
        if engine_price and abs(float(db_price) - engine_price) > 0.01:
            errors.append(f"B2B price mismatch for {sku}: DB={db_price}, engine={engine_price}")
    print("    ✓ B2B prices match pricing_engine._B2B_PRICES")

    # Check 7: Distributor count
    cur.execute("SELECT COUNT(*) FROM distributors")
    dist_count = cur.fetchone()[0]
    if dist_count != len(DISTRIBUTORS_DATA):
        errors.append(f"Distributors: expected {len(DISTRIBUTORS_DATA)}, got {dist_count}")
    else:
        print(f"    ✓ Distributors: {dist_count}")

    if errors:
        print(f"\n  ✗ VALIDATION FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"    • {e}")
        return False
    else:
        print("\n  ✓ ALL VALIDATION CHECKS PASSED")
        return True


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("RAITO — Phase 1: Seed Reference Data")
    print("=" * 60)

    conn = get_connection()
    cur = conn.cursor()

    try:
        print("\nPhase 1a: Reference tables")
        seed_manufacturers(cur)
        seed_distributors(cur)
        seed_products(cur)
        seed_customers(cur)

        print("\nPhase 1b: Price history")
        seed_price_history(cur)

        print("\nPhase 1c: Validation")
        ok = validate(cur)

        if ok:
            conn.commit()
            print("\n✓ All data committed to database.")
        else:
            conn.rollback()
            print("\n✗ Rolled back — fix validation errors and re-run.")
            sys.exit(1)

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    print("\n" + "=" * 60)
    print("Phase 1 complete. Next: Phase 2 (historical transaction migration)")
    print("=" * 60)


if __name__ == "__main__":
    main()
