#!/usr/bin/env python3
"""
RAITO — Fix 3 Unresolved Biscotti Branches

1. Add alias 'חן כרמלה למסחר בע"מ' → Carmella (existing customer)
2. Create new customer 'Matilda Yehud' (מתילדה יהוד) under Biscotti distributor
3. Create new customer 'Delicious Rishon LeZion' (דלישס ראשון לציון) under Biscotti distributor
4. Refresh materialized views

Usage (Cloud Shell):
  DATABASE_URL="postgresql://raito_app:raito_app@127.0.0.1:5432/raito" python3 fix_biscotti_aliases.py
"""

import os
import sys
import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://raito_app:raito_app@127.0.0.1:5432/raito")


def main():
    print("=" * 60)
    print("RAITO — Fix 3 Unresolved Biscotti Branches")
    print("=" * 60)

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # ── 1. Add alias for Carmella ──
        print("\n1. Adding alias for Carmella...")
        alias = 'חן כרמלה למסחר בע"מ'

        # Check current aliases
        cur.execute("SELECT id, name_he_aliases FROM customers WHERE name_en = 'Carmella'")
        row = cur.fetchone()
        if not row:
            print("  ✗ Customer 'Carmella' not found in DB!")
            sys.exit(1)

        carm_id, existing = row
        existing = existing or []

        if alias in existing:
            print(f"  ℹ Alias already exists for Carmella (id={carm_id})")
        else:
            cur.execute(
                "UPDATE customers SET name_he_aliases = array_append(name_he_aliases, %s) WHERE name_en = 'Carmella'",
                (alias,)
            )
            print(f"  ✓ Added '{alias}' → Carmella (id={carm_id})")

        # ── 2. Get Biscotti distributor ID ──
        cur.execute("SELECT id FROM distributors WHERE key = 'biscotti'")
        biscotti_row = cur.fetchone()
        if not biscotti_row:
            print("  ✗ Biscotti distributor not found!")
            sys.exit(1)
        biscotti_dist_id = biscotti_row[0]
        print(f"\n  Biscotti distributor_id = {biscotti_dist_id}")

        # ── 3. Create Matilda Yehud ──
        print("\n2. Creating 'Matilda Yehud'...")
        cur.execute("SELECT id FROM customers WHERE name_en = 'Matilda Yehud'")
        if cur.fetchone():
            print("  ℹ Already exists — skipping")
        else:
            cur.execute("""
                INSERT INTO customers (
                    name_en, name_he, name_he_aliases,
                    primary_distributor_id, customer_type, cc_tracked, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                'Matilda Yehud',
                'מתילדה יהוד',
                ['מתילדה יהוד (אונר שיווק מזון בע"מ)', 'מתילדה יהוד'],
                biscotti_dist_id,
                'independent',
                False,
                True,
            ))
            new_id = cur.fetchone()[0]
            print(f"  ✓ Created 'Matilda Yehud' → id={new_id}")

        # ── 4. Create Delicious Rishon LeZion ──
        print("\n3. Creating 'Delicious Rishon LeZion'...")
        cur.execute("SELECT id FROM customers WHERE name_en = 'Delicious Rishon LeZion'")
        if cur.fetchone():
            print("  ℹ Already exists — skipping")
        else:
            cur.execute("""
                INSERT INTO customers (
                    name_en, name_he, name_he_aliases,
                    primary_distributor_id, customer_type, cc_tracked, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                'Delicious Rishon LeZion',
                'דלישס ראשון לציון',
                ['דלישס ראשון לציון'],
                biscotti_dist_id,
                'independent',
                False,
                True,
            ))
            new_id = cur.fetchone()[0]
            print(f"  ✓ Created 'Delicious Rishon LeZion' → id={new_id}")

        # ── 5. Refresh materialized views ──
        print("\n4. Refreshing materialized views...")
        cur.execute("REFRESH MATERIALIZED VIEW customer_alias_lookup")
        print("  ✓ customer_alias_lookup refreshed")

        conn.commit()
        print("\n  ✓ All changes committed.")

        # ── 6. Verify ──
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)

        test_aliases = [
            'חן כרמלה למסחר בע"מ',
            'מתילדה יהוד (אונר שיווק מזון בע"מ)',
            'דלישס ראשון לציון',
        ]
        for alias in test_aliases:
            cur.execute(
                "SELECT customer_id, name_en FROM customer_alias_lookup WHERE alias = %s",
                (alias,)
            )
            row = cur.fetchone()
            if row:
                print(f"  ✓ '{alias}' → customer_id={row[0]} ({row[1]})")
            else:
                print(f"  ✗ '{alias}' → NOT FOUND")

    except Exception as e:
        conn.rollback()
        print(f"\n  ✗ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
