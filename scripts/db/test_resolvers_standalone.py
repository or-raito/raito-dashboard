#!/usr/bin/env python3
"""
RAITO — Resolver Test (Standalone for Cloud Shell)
No local imports needed — all test data is embedded.
"""

import os
import sys
import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://raito_app:raito_app@127.0.0.1:5432/raito")

# ═════════════════════════════════════════════════════════════════════════════
# Embedded test data (from config.py + parsers.py)
# ═════════════════════════════════════════════════════════════════════════════

CUSTOMER_NAMES_EN = {
    'AMPM': 'AMPM',
    'אלונית': 'Alonit',
    'גוד פארם': 'Good Pharm',
    'דומינוס': "Domino's Pizza",
    'דור אלון': 'Alonit',
    'דלק מנטה': 'Delek Menta',
    'וולט מרקט': 'Wolt Market',
    'חוות נעמי': "Naomi's Farm",
    'טיב טעם': 'Tiv Taam',
    'ינגו': 'Yango Deli',
    'כרמלה': 'Carmella',
    'נוי השדה': 'Noy HaSade',
    'סונול': 'Sonol',
    'עוגיפלצת': 'Oogiplatset',
    'פוט לוקר': 'Foot Locker',
    'פז חברת נפט- סופר יודה': 'Paz Super Yuda',
    'פז סופר יודה': 'Paz Super Yuda',
    'פז ילו': 'Paz Yellow',
    'שוק פרטי': 'Private Market',
}

MAAYAN_CHAIN_NAMES = [
    'דור אלון',
    'שוק פרטי',
    'דלק מנטה',
    'סונול',
    'פז ילו',
    'פז יילו',
    'פז חברת נפט- סופר יודה',
    'שפר את אלי לוי בע"מ',
]

PRODUCT_TEST_NAMES = [
    # Icedream format
    ("טורבו- גלידת שוקולד אגוזי לוז 250", "chocolate"),
    ("טורבו- גלידת וניל מדגסקר 250 מל", "vanilla"),
    ("טורבו- גלידת מנגו מאיה 250 מל", "mango"),
    ("טורבו- גלידת פיסטוק 250", "pistachio"),
    ("טורבו מארז גלידות 250 מל * 3 יח'", "magadat"),
    ("דרים קייק- 3 יח'", "dream_cake"),
    ("דרים קייק - ביסקוטי", "dream_cake_2"),
    # Ma'ayan format (keyword match)
    ("גלידת חלבון שוקולד אגוזי לוז", "chocolate"),
    ("גלידת חלבון וניל", "vanilla"),
    ("גלידת חלבון מנגו", "mango"),
    ("גלידת חלבון פיסטוק", "pistachio"),
    # SKU keys
    ("chocolate", "chocolate"),
    ("vanilla", "vanilla"),
    ("mango", "mango"),
    ("pistachio", "pistachio"),
    ("dream_cake", "dream_cake"),
    ("dream_cake_2", "dream_cake_2"),
    ("magadat", "magadat"),
]


# ═════════════════════════════════════════════════════════════════════════════
# Inline resolver (no imports needed)
# ═════════════════════════════════════════════════════════════════════════════

class SimpleResolver:
    def __init__(self, conn):
        self.customer_alias = {}   # alias → (id, name_en)
        self.product_alias = {}    # alias → (id, sku_key)
        self.product_keywords = {
            'וניל': 'vanilla', 'מנגו': 'mango', 'שוקולד': 'chocolate',
            'מארז': 'magadat', 'דרים': 'dream_cake', 'פיסטוק': 'pistachio',
        }
        self.product_sku_to_id = {}

        cur = conn.cursor()

        # Load customer aliases
        cur.execute("SELECT alias, customer_id, name_en FROM customer_alias_lookup")
        for alias, cid, name_en in cur.fetchall():
            if alias:
                self.customer_alias[alias.strip()] = (cid, name_en)

        # Load product aliases
        cur.execute("SELECT alias, product_id, sku_key FROM product_alias_lookup")
        for alias, pid, sku in cur.fetchall():
            if alias:
                self.product_alias[alias.strip()] = (pid, sku)
                self.product_sku_to_id[sku] = pid

        cur.close()

    def resolve_customer(self, raw):
        if not raw:
            return None
        clean = raw.strip()
        r = self.customer_alias.get(clean)
        if r:
            return r
        # Prefix match
        for alias in sorted(self.customer_alias.keys(), key=len, reverse=True):
            if clean.startswith(alias) and len(alias) >= 3:
                return self.customer_alias[alias]
        return None

    def resolve_product(self, raw):
        if not raw:
            return None
        clean = raw.strip()
        r = self.product_alias.get(clean)
        if r:
            return r
        # Keyword match
        for kw, sku in self.product_keywords.items():
            if kw in clean:
                pid = self.product_sku_to_id.get(sku)
                if pid:
                    return (pid, sku)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Tests
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("RAITO Resolver Dry-Run Test (Standalone)")
    print("=" * 60)

    conn = psycopg2.connect(DB_URL)
    resolver = SimpleResolver(conn)

    # ── Customer test ──
    print("\nCUSTOMER RESOLUTION")
    print("-" * 60)
    cust_ok, cust_total = 0, 0
    unmatched_cust = []

    for heb, expected_en in CUSTOMER_NAMES_EN.items():
        cust_total += 1
        r = resolver.resolve_customer(heb)
        if r:
            cid, name_en = r
            match = "✓" if name_en == expected_en else f"⚠ got '{name_en}'"
            print(f"  {match}  '{heb}' → id={cid} ({name_en})")
            cust_ok += 1
        else:
            print(f"  ✗  '{heb}' → NOT FOUND (expected: {expected_en})")
            unmatched_cust.append((heb, expected_en))

    print(f"\n  Ma'ayan chain names:")
    for chain in MAAYAN_CHAIN_NAMES:
        cust_total += 1
        r = resolver.resolve_customer(chain)
        if r:
            cid, name_en = r
            print(f"  ✓  '{chain}' → id={cid} ({name_en})")
            cust_ok += 1
        else:
            print(f"  ✗  '{chain}' → NOT FOUND")
            unmatched_cust.append((chain, "?"))

    print(f"\n  Customer coverage: {cust_ok}/{cust_total} ({cust_ok/cust_total*100:.0f}%)")

    # ── Product test ──
    print("\nPRODUCT RESOLUTION")
    print("-" * 60)
    prod_ok, prod_total = 0, 0
    unmatched_prod = []

    for name, expected_sku in PRODUCT_TEST_NAMES:
        prod_total += 1
        r = resolver.resolve_product(name)
        if r:
            pid, sku = r
            match = "✓" if sku == expected_sku else f"⚠ got '{sku}'"
            print(f"  {match}  '{name}' → id={pid} ({sku})")
            prod_ok += 1
        else:
            print(f"  ✗  '{name}' → NOT FOUND (expected: {expected_sku})")
            unmatched_prod.append((name, expected_sku))

    print(f"\n  Product coverage: {prod_ok}/{prod_total} ({prod_ok/prod_total*100:.0f}%)")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Customers: {cust_ok}/{cust_total} ({cust_ok/cust_total*100:.0f}%)")
    print(f"  Products:  {prod_ok}/{prod_total} ({prod_ok/prod_total*100:.0f}%)")

    if unmatched_cust:
        print(f"\n  ⚠ {len(unmatched_cust)} customer names need aliases:")
        for heb, en in unmatched_cust:
            print(f"    '{heb}' → should map to '{en}'")

    if unmatched_prod:
        print(f"\n  ⚠ {len(unmatched_prod)} product names need aliases:")
        for name, sku in unmatched_prod:
            print(f"    '{name}' → should map to '{sku}'")

    if not unmatched_cust and not unmatched_prod:
        print("\n  ✓ 100% resolution! Ready for parser integration.")

    conn.close()


if __name__ == "__main__":
    main()
