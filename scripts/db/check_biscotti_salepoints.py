#!/usr/bin/env python3
"""
RAITO — Check Biscotti branch coverage in sale_points table

For each Wolt Market and Naomi's Farm branch from Biscotti data,
shows whether a matching sale_point already exists (by name/address match)
or needs to be created.

Usage (Cloud Shell):
  DATABASE_URL="postgresql://raito:raito@127.0.0.1:5432/raito" python3 check_biscotti_salepoints.py
"""

import os
import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://raito:raito@127.0.0.1:5432/raito")

# All Biscotti branch names that need customer attribution
BISCOTTI_BRANCHES = {
    'wolt': [
        'וולט מרקט -נאות שמיר-רמלה',
        'וולט מרקט ר"ג',
        'וולט מרקט-אור יהודה(חנות מס\' 30)',
        'וולט מרקט-אשדוד',
        'וולט מרקט-אשקלון(חנות מס\' 29)',
        'וולט מרקט-באר שבע',
        'וולט מרקט-בן יהודה תל אביב',
        'וולט מרקט-הרובע -ראשון לציון',
        'וולט מרקט-הרצליה פיתוח',
        'וולט מרקט-וולפסון-תל אביב',
        'וולט מרקט-חיפה נמל',
        'וולט מרקט-יד אליהו-תל אביב',
        'וולט מרקט-כפר סבא',
        'וולט מרקט-לב הארץ-כפר קאסם',
        'וולט מרקט-מודיעין',
        'וולט מרקט-נס ציונה',
        'וולט מרקט-נתניה סנטר',
        'וולט מרקט-נתניה פולג',
        'וולט מרקט-סינמה סיטי-ירושלים',
        'וולט מרקט-פלורנטין-תל אביב',
        'וולט מרקט-פתח תקווה',
        'וולט מרקט-קריון',
        'וולט מרקט-קריית אונו',
        'וולט מרקט-ראשון מערב',
        'וולט מרקט-רחובות',
        'וולט מרקט-רמת השרון',
        'וולט מרקט-רעננה',
        'וולט מרקט-תלפיות-ירושלים',
    ],
    'naomis_farm': [
        'חוות נעמי - ניהול מעדניות בע"מ - סניף ק.אונו',
        'חוות נעמי בורוכוב בע"מ',
        'חוות נעמי ניהול מעדניות בע"מ - סניף חשמונאים',
        'חוות נעמי ניהול מעדניות בע"מ - סניף כורזין',
        'חוות נעמי ניהול מעדניות בע"מ - סניף מודיעין',
    ],
}


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # ── Get Wolt Market and Naomi's Farm customer IDs ──
    cur.execute("""
        SELECT id, name_en FROM customers
        WHERE name_en IN ('Wolt Market', 'Naomi''s Farm')
        ORDER BY name_en
    """)
    customer_ids = {row[0]: row[1] for row in cur.fetchall()}
    cid_by_name = {v: k for k, v in customer_ids.items()}

    wolt_id   = cid_by_name.get('Wolt Market')
    naomi_id  = cid_by_name.get("Naomi's Farm")
    print(f"Wolt Market   customer_id = {wolt_id}")
    print(f"Naomi's Farm  customer_id = {naomi_id}")

    # ── Load all sale_points for these customers ──
    for cust_name, cust_id, branches in [
        ('Wolt Market',   wolt_id,  BISCOTTI_BRANCHES['wolt']),
        ("Naomi's Farm",  naomi_id, BISCOTTI_BRANCHES['naomis_farm']),
    ]:
        print(f"\n{'='*60}")
        print(f"{cust_name} (customer_id={cust_id})")
        print(f"{'='*60}")

        if not cust_id:
            print("  ✗ Customer not found in DB")
            continue

        # Load existing sale_points for this customer
        cur.execute("""
            SELECT id, branch_name_he, branch_name_clean, city
            FROM sale_points
            WHERE customer_id = %s
            ORDER BY branch_name_he
        """, (cust_id,))
        existing_sps = cur.fetchall()
        print(f"  Existing sale_points in DB: {len(existing_sps)}")
        if existing_sps:
            print("  Existing entries:")
            for sp in existing_sps:
                print(f"    SP#{sp[0]:5d}  {sp[1] or '':<40s}  {sp[2] or ''}")

        # Check each Biscotti branch
        print(f"\n  Biscotti branches ({len(branches)} total):")
        matched = 0
        unmatched = []
        for branch in branches:
            # Try to find a match by name_he
            found = None
            for sp in existing_sps:
                sp_name = (sp[1] or '').strip()  # branch_name_he
                if sp_name and (sp_name == branch or branch.startswith(sp_name) or sp_name.startswith(branch[:10])):
                    found = sp
                    break
            if found:
                matched += 1
                print(f"    ✓  '{branch}' → SP#{found[0]} ({found[1]})")
            else:
                unmatched.append(branch)
                print(f"    ✗  '{branch}' → NO MATCH")

        print(f"\n  Summary: {matched} matched, {len(unmatched)} need new SP records")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
