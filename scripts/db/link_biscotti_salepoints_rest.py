#!/usr/bin/env python3
"""
RAITO — Link remaining 3 Biscotti branches to sale_points

Handles the 3 non-Wolt/Naomi branches:
  - חן כרמלה למסחר בע"מ       → Carmella (customer_id=10)
  - מתילדה יהוד                → Matilda Yehud (customer_id=20)
  - דלישס ראשון לציון          → Delicious Rishon LeZion (customer_id=21)

Usage (Cloud Shell):
  DATABASE_URL="postgresql://raito_app:raito_app@127.0.0.1:5432/raito" python3 link_biscotti_salepoints_rest.py
"""

import os
import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://raito_app:raito_app@127.0.0.1:5432/raito")

BRANCHES = [
    # (branch_name_he,                        customer_name_en,          city,               clean_name)
    ('חן כרמלה למסחר בע"מ',                  'Carmella',                'כרמל',             'Carmella'),
    ('מתילדה יהוד (אונר שיווק מזון בע"מ)',   'Matilda Yehud',           'יהוד',             'Matilda Yehud'),
    ('דלישס ראשון לציון',                     'Delicious Rishon LeZion', 'ראשון לציון',      'Delicious Rishon LeZion'),
]


def main():
    print("=" * 60)
    print("RAITO — Link remaining Biscotti branches")
    print("=" * 60)

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Biscotti distributor ID
        cur.execute("SELECT id FROM distributors WHERE key = 'biscotti'")
        bisc_dist_id = cur.fetchone()[0]
        print(f"\nBiscotti distributor_id = {bisc_dist_id}")

        sp_map = {}

        for branch_he, cust_name, city, clean in BRANCHES:
            # Get customer_id
            cur.execute("SELECT id FROM customers WHERE name_en = %s", (cust_name,))
            row = cur.fetchone()
            if not row:
                print(f"  ✗ Customer '{cust_name}' not found — skipping")
                continue
            cust_id = row[0]

            # Upsert SP record
            cur.execute("""
                INSERT INTO sale_points
                    (customer_id, distributor_id, branch_name_he, branch_name_clean, city, is_active)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (distributor_id, branch_name_he) DO UPDATE
                    SET customer_id = EXCLUDED.customer_id,
                        branch_name_clean = EXCLUDED.branch_name_clean,
                        city = EXCLUDED.city
                RETURNING id
            """, (cust_id, bisc_dist_id, branch_he, clean, city))
            sp_id = cur.fetchone()[0]
            sp_map[branch_he] = sp_id
            print(f"  + SP#{sp_id}  '{branch_he}' → {cust_name}")

        # Link transactions
        print("\nLinking transactions...")
        total = 0
        for branch_he, sp_id in sp_map.items():
            cur.execute("""
                UPDATE sales_transactions
                SET sale_point_id = %s
                WHERE source_row_ref = %s AND distributor_id = %s
            """, (sp_id, f"branch:{branch_he}", bisc_dist_id))
            n = cur.rowcount
            total += n
            print(f"  ✓ SP#{sp_id} ← {n} txn(s)")

        conn.commit()
        print(f"\n  ✓ {total} transactions linked. Committed.")

        # Final check
        cur.execute("""
            SELECT COUNT(*) FROM sales_transactions
            WHERE distributor_id = %s AND sale_point_id IS NULL
        """, (bisc_dist_id,))
        remaining = cur.fetchone()[0]
        if remaining == 0:
            print("  ✓ All Biscotti transactions now have a sale_point_id!")
        else:
            print(f"  ⚠ {remaining} transactions still unlinked")

    except Exception as e:
        conn.rollback()
        print(f"\n  ✗ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
