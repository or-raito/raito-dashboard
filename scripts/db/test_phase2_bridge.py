#!/usr/bin/env python3
"""
RAITO — Phase 2 Validation: CC↔DB ID Bridge Test

Validates that all CC dashboard customer IDs can be mapped to DB customer IDs
via the entity resolver. This proves end-to-end ID resolution works.

Usage (Cloud Shell):
  DATABASE_URL="postgresql://raito_app:raito_app@127.0.0.1:5432/raito" python3 test_phase2_bridge.py
"""

import os
import sys
import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://raito_app:raito_app@127.0.0.1:5432/raito")

# ═════════════════════════════════════════════════════════════════════════════
# CC Dashboard's hardcoded mapping (from cc_dashboard.py)
# English name → CC internal ID
# ═════════════════════════════════════════════════════════════════════════════

CC_CUSTOMER_EN_TO_CC_ID = {
    'AMPM':            1,
    'Alonit':          2,
    'Good Pharm':      3,
    'Delek Menta':     4,
    'Wolt Market':     5,
    'Tiv Taam':        6,
    'Yango Deli':      7,
    "Domino's Pizza":  16,
    'Carmella':        8,
    'Noy HaSade':      9,
    'Private Market':  11,
    'Paz Yellow':      13,
    'Paz Super Yuda':  14,
    'Sonol':           15,
    "Naomi's Farm":    17,
    'Foot Locker':     19,
}

# CC customer metadata display names (may differ from EN names above)
CC_CUSTOMER_META = {
    1:  "AMPM",
    2:  "Alonit",
    3:  "Good Pharm",
    4:  "Delek",
    5:  "Wolt Market",
    6:  "Tiv Taam",
    7:  "Yingo Deli",
    8:  "Carmela",
    9:  "Noy Hasade",
    10: "Carrefour",
    11: "Private Market",
    12: "Ugipletzet",
    13: "Paz Yellow",
    14: "Paz Super Yuda",
    15: "Sonol",
    16: "Domino's",
    17: "Naomi's Farm",
    18: "Hama",
    19: "Foot Locker",
    20: "Biscotti Chain",
}

# Known product SKUs
PRODUCT_SKUS = ['chocolate', 'vanilla', 'mango', 'pistachio', 'magadat', 'dream_cake', 'dream_cake_2']

# Distributor keys
DISTRIBUTOR_KEYS = ['icedream', 'mayyan_froz', 'biscotti']

# Brand keys
BRAND_KEYS = ['turbo', 'danis']


def main():
    print("=" * 60)
    print("RAITO Phase 2 Validation: CC↔DB ID Bridge")
    print("=" * 60)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # ── Load alias lookups ──
    cust_aliases = {}  # alias → (customer_id, name_en)
    cur.execute("SELECT alias, customer_id, name_en FROM customer_alias_lookup")
    for alias, cid, name_en in cur.fetchall():
        if alias:
            cust_aliases[alias.strip()] = (cid, name_en)

    prod_aliases = {}  # alias → (product_id, sku_key)
    cur.execute("SELECT alias, product_id, sku_key FROM product_alias_lookup")
    for alias, pid, sku in cur.fetchall():
        if alias:
            prod_aliases[alias.strip()] = (pid, sku)

    # ── 1. CC Customer Bridge ──
    print("\n1. CC↔DB CUSTOMER ID BRIDGE")
    print("-" * 60)
    bridge = {}  # cc_id → db_customer_id
    bridged = 0

    for en_name, cc_id in sorted(CC_CUSTOMER_EN_TO_CC_ID.items(), key=lambda x: x[1]):
        result = cust_aliases.get(en_name)
        if result:
            db_id, db_name = result
            bridge[cc_id] = db_id
            bridged += 1
            cc_display = CC_CUSTOMER_META.get(cc_id, en_name)
            print(f"  ✓  CC#{cc_id:2d} ({cc_display:16s}) → DB#{db_id:2d} ({db_name})")
        else:
            cc_display = CC_CUSTOMER_META.get(cc_id, en_name)
            print(f"  ✗  CC#{cc_id:2d} ({cc_display:16s}) → NOT FOUND in DB (en_name='{en_name}')")

    print(f"\n  Bridge coverage: {bridged}/{len(CC_CUSTOMER_EN_TO_CC_ID)} ({bridged/len(CC_CUSTOMER_EN_TO_CC_ID)*100:.0f}%)")

    # ── 2. Product ID Resolution ──
    print("\n2. PRODUCT ID RESOLUTION")
    print("-" * 60)
    prod_ok = 0
    for sku in PRODUCT_SKUS:
        result = prod_aliases.get(sku)
        if result:
            pid, sku_key = result
            print(f"  ✓  '{sku}' → product_id={pid}")
            prod_ok += 1
        else:
            print(f"  ✗  '{sku}' → NOT FOUND")
    print(f"\n  Coverage: {prod_ok}/{len(PRODUCT_SKUS)} ({prod_ok/len(PRODUCT_SKUS)*100:.0f}%)")

    # ── 3. Distributor Resolution ──
    print("\n3. DISTRIBUTOR RESOLUTION")
    print("-" * 60)
    cur.execute("SELECT id, key, name_en FROM distributors ORDER BY id")
    dist_rows = {row[1]: (row[0], row[2]) for row in cur.fetchall()}
    for dk in DISTRIBUTOR_KEYS:
        if dk in dist_rows:
            did, name = dist_rows[dk]
            print(f"  ✓  '{dk}' → distributor_id={did} ({name})")
        else:
            print(f"  ✗  '{dk}' → NOT FOUND")

    # ── 4. Brand Resolution ──
    print("\n4. BRAND RESOLUTION")
    print("-" * 60)
    cur.execute("SELECT id, key, name_en FROM brands ORDER BY id")
    brand_rows = {row[1]: (row[0], row[2]) for row in cur.fetchall()}
    for bk in BRAND_KEYS:
        if bk in brand_rows:
            bid, name = brand_rows[bk]
            print(f"  ✓  '{bk}' → brand_id={bid} ({name})")
        else:
            print(f"  ✗  '{bk}' → NOT FOUND")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("PHASE 2 SUMMARY")
    print("=" * 60)
    print(f"  CC↔DB bridge:   {bridged}/{len(CC_CUSTOMER_EN_TO_CC_ID)} customers")
    print(f"  Products:       {prod_ok}/{len(PRODUCT_SKUS)}")
    print(f"  Distributors:   {len([k for k in DISTRIBUTOR_KEYS if k in dist_rows])}/{len(DISTRIBUTOR_KEYS)}")
    print(f"  Brands:         {len([k for k in BRAND_KEYS if k in brand_rows])}/{len(BRAND_KEYS)}")

    all_ok = (
        bridged == len(CC_CUSTOMER_EN_TO_CC_ID) and
        prod_ok == len(PRODUCT_SKUS) and
        all(k in dist_rows for k in DISTRIBUTOR_KEYS) and
        all(k in brand_rows for k in BRAND_KEYS)
    )

    if all_ok:
        print("\n  ✓ 100% bridge coverage! Phase 2 validated.")
        print("  CC dashboard can now route data using DB IDs.")
    else:
        print("\n  ⚠ Some entities not bridged — review above.")

    # ── Bridge table (for reference) ──
    if bridge:
        print("\n  CC↔DB Bridge Table:")
        print("  CC_ID  DB_ID  Customer")
        print("  ─────  ─────  ────────")
        for cc_id in sorted(bridge.keys()):
            db_id = bridge[cc_id]
            name = CC_CUSTOMER_META.get(cc_id, '?')
            print(f"  {cc_id:5d}  {db_id:5d}  {name}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
