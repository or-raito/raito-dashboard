#!/usr/bin/env python3
"""
RAITO — Link Biscotti branches to correct sale_point records

Creates sale_point records for all Wolt Market and Naomi's Farm branches
that come via the Biscotti distributor, then updates existing
sales_transactions rows to set the correct sale_point_id.

Each (distributor_id, branch_name_he) gets its own SP record, all pointing
to the correct customer_id (Wolt Market=6 or Naomi's Farm=7).

Usage (Cloud Shell):
  DATABASE_URL="postgresql://raito_app:raito_app@127.0.0.1:5432/raito" python3 link_biscotti_salepoints.py
"""

import os
import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://raito_app:raito_app@127.0.0.1:5432/raito")

# ── Explicit branch → (customer_id, city, clean_name) mapping ────────────────
# customer_id: Wolt Market=6, Naomi's Farm=7
# (confirmed manually)

WOLT_CUSTOMER_ID  = 6
NAOMI_CUSTOMER_ID = 7

WOLT_BRANCHES = [
    # (branch_name_he,                                    city,           branch_name_clean)
    ('וולט מרקט ר"ג',                                   'רמת גן',        'Wolt Market Ramat Gan'),
    ('וולט מרקט-אור יהודה(חנות מס\' 30)',               'אור יהודה',     'Wolt Market Or Yehuda'),
    ('וולט מרקט-אשדוד',                                  'אשדוד',         'Wolt Market Ashdod'),
    ('וולט מרקט-אשקלון(חנות מס\' 29)',                  'אשקלון',        'Wolt Market Ashkelon'),
    ('וולט מרקט-באר שבע',                                'באר שבע',       'Wolt Market Beer Sheva'),
    ('וולט מרקט-בן יהודה תל אביב',                      'תל אביב',       'Wolt Market Ben Yehuda TLV'),
    ('וולט מרקט-הרובע -ראשון לציון',                    'ראשון לציון',   'Wolt Market HaRova Rishon'),
    ('וולט מרקט-הרצליה פיתוח',                           'הרצליה',        'Wolt Market Herzliya'),
    ('וולט מרקט-וולפסון-תל אביב',                       'תל אביב',       'Wolt Market Wolfson TLV'),
    ('וולט מרקט-חיפה נמל',                               'חיפה',          'Wolt Market Haifa Port'),
    ('וולט מרקט-יד אליהו-תל אביב',                      'תל אביב',       'Wolt Market Yad Eliyahu TLV'),
    ('וולט מרקט-כפר סבא',                                'כפר סבא',       'Wolt Market Kfar Saba'),
    ('וולט מרקט-לב הארץ-כפר קאסם',                      'כפר קאסם',      'Wolt Market Lev HaAretz Kafr Qasim'),
    ('וולט מרקט-מודיעין',                                 'מודיעין',       'Wolt Market Modi\'in'),
    ('וולט מרקט-נס ציונה',                               'נס ציונה',      'Wolt Market Nes Ziona'),
    ('וולט מרקט-נתניה סנטר',                             'נתניה',         'Wolt Market Netanya Center'),
    ('וולט מרקט-נתניה פולג',                             'נתניה',         'Wolt Market Netanya Poleg'),
    ('וולט מרקט-סינמה סיטי-ירושלים',                    'ירושלים',       'Wolt Market Cinema City Jerusalem'),
    ('וולט מרקט-פלורנטין-תל אביב',                      'תל אביב',       'Wolt Market Florentin TLV'),
    ('וולט מרקט-פתח תקווה',                              'פתח תקווה',     'Wolt Market Petah Tikva'),       # new
    ('וולט מרקט-קריון',                                  'קריות',         'Wolt Market HaKiryon'),
    ('וולט מרקט-קריית אונו',                             'קריית אונו',    'Wolt Market Kiryat Ono'),
    ('וולט מרקט-ראשון מערב',                             'ראשון לציון',   'Wolt Market Rishon West'),
    ('וולט מרקט-רחובות',                                  'רחובות',        'Wolt Market Rehovot'),
    ('וולט מרקט-רמת השרון',                              'רמת השרון',     'Wolt Market Ramat HaSharon'),
    ('וולט מרקט-רעננה',                                  'רעננה',          'Wolt Market Ra\'anana'),
    ('וולט מרקט-תלפיות-ירושלים',                        'ירושלים',       'Wolt Market Talpiot Jerusalem'),
    ('וולט מרקט -נאות שמיר-רמלה',                       'רמלה',          'Wolt Market Naot Shamir Ramla'),  # new
]

NAOMI_BRANCHES = [
    # (branch_name_he,                                                    city,           branch_name_clean)
    ('חוות נעמי - ניהול מעדניות בע"מ - סניף ק.אונו',                   'קריית אונו',   "Naomi's Farm Kiryat Ono"),
    ('חוות נעמי בורוכוב בע"מ',                                           'תל אביב',      "Naomi's Farm Borochov"),
    ('חוות נעמי ניהול מעדניות בע"מ - סניף חשמונאים',                   'תל אביב',      "Naomi's Farm Hashmonaim"),
    ('חוות נעמי ניהול מעדניות בע"מ - סניף כורזין',                     'כורזים',       "Naomi's Farm Korazim"),
    ('חוות נעמי ניהול מעדניות בע"מ - סניף מודיעין',                    'מודיעין',      "Naomi's Farm Modi'in"),
]


def main():
    print("=" * 60)
    print("RAITO — Link Biscotti branches to sale_points")
    print("=" * 60)

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # ── Get Biscotti distributor ID ──
        cur.execute("SELECT id FROM distributors WHERE key = 'biscotti'")
        bisc_dist_id = cur.fetchone()[0]
        print(f"\nBiscotti distributor_id = {bisc_dist_id}")

        # ── 1. Insert SP records ──
        print("\n1. Creating sale_point records...")
        sp_map = {}  # branch_name_he → sale_point_id

        all_branches = (
            [(b[0], b[1], b[2], WOLT_CUSTOMER_ID)  for b in WOLT_BRANCHES] +
            [(b[0], b[1], b[2], NAOMI_CUSTOMER_ID) for b in NAOMI_BRANCHES]
        )

        created = 0
        existing = 0
        for branch_he, city, clean, cust_id in all_branches:
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

            # Check if it was a new insert or update
            cur.execute("""
                SELECT created_at > NOW() - INTERVAL '5 seconds'
                FROM sale_points WHERE id = %s
            """, (sp_id,))
            is_new = cur.fetchone()[0]
            if is_new:
                created += 1
                print(f"  + SP#{sp_id:5d}  '{branch_he[:45]}' ({city})")
            else:
                existing += 1
                print(f"  = SP#{sp_id:5d}  '{branch_he[:45]}' (already existed)")

        print(f"\n  Created: {created}  |  Updated: {existing}")

        # ── 2. Update sales_transactions ──
        print("\n2. Linking sales_transactions to sale_point IDs...")
        updated_total = 0

        for branch_he, sp_id in sp_map.items():
            source_ref = f"branch:{branch_he}"
            cur.execute("""
                UPDATE sales_transactions
                SET sale_point_id = %s
                WHERE source_row_ref = %s
                  AND distributor_id = %s
            """, (sp_id, source_ref, bisc_dist_id))
            n = cur.rowcount
            updated_total += n
            if n:
                print(f"  ✓ SP#{sp_id} ← {n} txn(s)  '{branch_he[:45]}'")

        conn.commit()
        print(f"\n  ✓ {updated_total} transactions linked to sale_point IDs. Committed.")

        # ── 3. Verify ──
        print("\n3. Verification")
        print("-" * 40)
        cur.execute("""
            SELECT c.name_en, COUNT(*), SUM(st.units_sold), SUM(st.revenue_ils)
            FROM sales_transactions st
            JOIN sale_points sp ON st.sale_point_id = sp.id
            JOIN customers c ON sp.customer_id = c.id
            WHERE st.distributor_id = %s
            GROUP BY c.name_en
            ORDER BY SUM(st.units_sold) DESC
        """, (bisc_dist_id,))
        rows = cur.fetchall()
        print(f"  {'Customer':<25} {'Txns':>6} {'Units':>8} {'Revenue':>12}")
        print(f"  {'-'*24} {'-'*6} {'-'*8} {'-'*12}")
        for name, txns, units, rev in rows:
            print(f"  {name:<25} {txns:>6} {units:>8,} ₪{rev:>11,.0f}")

        # Unlinked
        cur.execute("""
            SELECT COUNT(*) FROM sales_transactions
            WHERE distributor_id = %s AND sale_point_id IS NULL
        """, (bisc_dist_id,))
        unlinked = cur.fetchone()[0]
        if unlinked:
            print(f"\n  ⚠ {unlinked} Biscotti transactions still have no sale_point_id")
        else:
            print(f"\n  ✓ All Biscotti transactions have a sale_point_id")

    except Exception as e:
        conn.rollback()
        print(f"\n  ✗ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
