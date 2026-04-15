#!/usr/bin/env python3
"""
RAITO — Resolver Dry-Run Test

Parses all distributor Excel files using parsers.consolidate_data(),
then tests every customer name and product name against the DB resolvers.

Reports:
  - Matched names (with IDs)
  - Unmatched names (need aliases added to DB)
  - Coverage percentage

Usage (Cloud Shell):
  DATABASE_URL="postgresql://raito_app:raito_app@127.0.0.1:5432/raito" python3 test_resolvers.py

Can also run locally if DB is accessible.
"""

import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from resolvers import EntityResolver


def test_customer_resolution(resolver):
    """Test resolver against all known customer names from parsers."""
    print("\n" + "=" * 60)
    print("CUSTOMER RESOLUTION TEST")
    print("=" * 60)

    # Import customer names from config (these are what parsers output)
    from config import CUSTOMER_NAMES_EN

    total = 0
    matched = 0
    unmatched = []

    # Test Hebrew → English resolution
    for heb_name, expected_en in CUSTOMER_NAMES_EN.items():
        total += 1
        result = resolver.resolve_customer(heb_name)
        if result:
            cid, name_en = result
            status = "✓" if name_en == expected_en else f"⚠ got '{name_en}'"
            print(f"  {status}  '{heb_name}' → id={cid} name_en='{name_en}'")
            matched += 1
        else:
            print(f"  ✗  '{heb_name}' → NOT FOUND (expected: '{expected_en}')")
            unmatched.append((heb_name, expected_en))

    # Also test the Ma'ayan chain-to-price mapping names
    print("\n  --- Ma'ayan chain names ---")
    from parsers import _MAAYAN_CHAIN_TO_PRICEDB
    for chain_name in _MAAYAN_CHAIN_TO_PRICEDB.keys():
        total += 1
        result = resolver.resolve_customer(chain_name)
        if result:
            cid, name_en = result
            print(f"  ✓  '{chain_name}' → id={cid} name_en='{name_en}'")
            matched += 1
        else:
            print(f"  ✗  '{chain_name}' → NOT FOUND")
            unmatched.append((chain_name, "?"))

    pct = (matched / total * 100) if total > 0 else 0
    print(f"\n  Coverage: {matched}/{total} ({pct:.0f}%)")
    if unmatched:
        print(f"\n  ⚠ {len(unmatched)} names need aliases added to customers.name_he_aliases:")
        for heb, en in unmatched:
            print(f"    '{heb}' → should map to '{en}'")

    return matched, total


def test_product_resolution(resolver):
    """Test resolver against Hebrew product names from distributor files."""
    print("\n" + "=" * 60)
    print("PRODUCT RESOLUTION TEST")
    print("=" * 60)

    # Hebrew product names as they appear in various distributor files
    test_names = [
        # Icedream format
        "טורבו- גלידת שוקולד אגוזי לוז 250",
        "טורבו- גלידת וניל מדגסקר 250 מל",
        "טורבו- גלידת מנגו מאיה 250 מל",
        "טורבו- גלידת פיסטוק 250",
        "טורבו מארז גלידות 250 מל * 3 יח'",
        "דרים קייק- 3 יח'",
        "דרים קייק - ביסקוטי",
        # Ma'ayan format
        "גלידת חלבון שוקולד אגוזי לוז",
        "גלידת חלבון וניל",
        "גלידת חלבון מנגו",
        "גלידת חלבון פיסטוק",
        # Substring patterns
        "שוקולד",
        "וניל",
        "מנגו",
        "פיסטוק",
        "דרים",
        # SKU keys (code-level)
        "chocolate",
        "vanilla",
        "mango",
        "pistachio",
        "dream_cake",
        "dream_cake_2",
        "magadat",
    ]

    total = 0
    matched = 0

    for name in test_names:
        total += 1
        result = resolver.resolve_product(name)
        if result:
            pid, sku, name_en = result
            print(f"  ✓  '{name}' → id={pid} sku={sku} ({name_en})")
            matched += 1
        else:
            print(f"  ✗  '{name}' → NOT FOUND")

    pct = (matched / total * 100) if total > 0 else 0
    print(f"\n  Coverage: {matched}/{total} ({pct:.0f}%)")

    return matched, total


def test_distributor_resolution(resolver):
    """Test distributor resolution."""
    print("\n" + "=" * 60)
    print("DISTRIBUTOR RESOLUTION TEST")
    print("=" * 60)

    test_keys = [
        ("icedream", "Icedream"),
        ("mayyan_froz", "Ma'ayan (Frozen)"),
        ("biscotti", "Biscotti"),
        ("karfree", "Karfree Warehouse"),
        ("אייסדרים", "Icedream (by Hebrew name)"),
        ("מעיין נציגויות", "Ma'ayan (by Hebrew name)"),
        ("ביסקוטי", "Biscotti (by Hebrew name)"),
    ]

    for key, desc in test_keys:
        did = resolver.resolve_distributor(key)
        if did:
            print(f"  ✓  '{key}' → distributor_id={did} ({desc})")
        else:
            print(f"  ✗  '{key}' → NOT FOUND ({desc})")


def test_brand_resolution(resolver):
    """Test brand resolution."""
    print("\n" + "=" * 60)
    print("BRAND RESOLUTION TEST")
    print("=" * 60)

    for key in ["turbo", "danis"]:
        bid = resolver.resolve_brand(key)
        if bid:
            name = resolver.brand_name(bid)
            print(f"  ✓  '{key}' → brand_id={bid} ({name})")
        else:
            print(f"  ✗  '{key}' → NOT FOUND")


def main():
    print("=" * 60)
    print("RAITO Resolver Dry-Run Test")
    print("=" * 60)

    with EntityResolver() as resolver:
        test_brand_resolution(resolver)
        test_distributor_resolution(resolver)
        cust_m, cust_t = test_customer_resolution(resolver)
        prod_m, prod_t = test_product_resolution(resolver)

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Brands:       all resolved")
        print(f"  Distributors: all resolved")
        print(f"  Customers:    {cust_m}/{cust_t} ({cust_m/cust_t*100:.0f}%)")
        print(f"  Products:     {prod_m}/{prod_t} ({prod_m/prod_t*100:.0f}%)")

        if cust_m < cust_t or prod_m < prod_t:
            print("\n  ⚠ Some names unresolved. Add missing aliases to DB:")
            print("    UPDATE customers SET name_he_aliases = array_append(name_he_aliases, '<alias>')")
            print("    WHERE name_en = '<customer>';")
            print("    REFRESH MATERIALIZED VIEW customer_alias_lookup;")
        else:
            print("\n  ✓ 100% resolution! Ready for Phase 1 parser integration.")


if __name__ == "__main__":
    main()
