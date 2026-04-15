#!/usr/bin/env python3
"""
RAITO — Fix unattributed Biscotti transactions

Directly UPDATE sales_transactions rows that couldn't be attributed during
the original ingest because the 3 Biscotti branch names weren't in the alias
table. Now that the aliases exist, we can resolve them by matching source_row_ref.

Usage (Cloud Shell):
  DATABASE_URL="postgresql://raito_app:raito_app@127.0.0.1:5432/raito" python3 fix_unattributed_biscotti.py
"""

import os
import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://raito_app:raito_app@127.0.0.1:5432/raito")

# Maps source_row_ref branch name → customer_id (from fix_biscotti_aliases.py output)
BRANCH_TO_CUSTOMER = {
    'חן כרמלה למסחר בע"מ':                     10,  # Carmella
    'מתילדה יהוד (אונר שיווק מזון בע"מ)':       20,  # Matilda Yehud
    'דלישס ראשון לציון':                         21,  # Delicious Rishon LeZion
}


def main():
    print("=" * 60)
    print("RAITO — Fix Unattributed Biscotti Transactions")
    print("=" * 60)

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Show current state
        print("\nCurrent unattributed rows:")
        cur.execute("""
            SELECT source_row_ref, COUNT(*), SUM(units_sold), SUM(revenue_ils)
            FROM sales_transactions
            WHERE is_attributed = FALSE
            GROUP BY source_row_ref
            ORDER BY source_row_ref
        """)
        rows = cur.fetchall()
        if not rows:
            print("  ℹ No unattributed rows found — nothing to fix.")
            return

        for ref, cnt, units, rev in rows:
            print(f"  {ref}: {cnt} rows, {units} units, ₪{rev:.0f}")

        total_fixed = 0
        print()

        for branch_name, customer_id in BRANCH_TO_CUSTOMER.items():
            # source_row_ref format is "branch:<branch_name>"
            ref = f"branch:{branch_name}"

            cur.execute("""
                UPDATE sales_transactions
                SET customer_id = %s,
                    is_attributed = TRUE
                WHERE source_row_ref = %s
                  AND is_attributed = FALSE
                RETURNING id
            """, (customer_id, ref))

            updated = cur.rowcount
            total_fixed += updated
            if updated:
                print(f"  ✓ '{branch_name}' → customer_id={customer_id}: {updated} rows updated")
            else:
                print(f"  ℹ '{branch_name}': no unattributed rows found (may already be clean)")

        conn.commit()

        print(f"\n  ✓ {total_fixed} rows attributed. Committed.")

        # Verify
        print("\nVerification — remaining unattributed:")
        cur.execute("""
            SELECT COUNT(*) FROM sales_transactions WHERE is_attributed = FALSE
        """)
        remaining = cur.fetchone()[0]
        if remaining == 0:
            print("  ✓ 100% attribution — no unattributed rows remain!")
        else:
            print(f"  ⚠ {remaining} rows still unattributed")
            cur.execute("""
                SELECT source_row_ref, COUNT(*)
                FROM sales_transactions
                WHERE is_attributed = FALSE
                GROUP BY source_row_ref
            """)
            for ref, cnt in cur.fetchall():
                print(f"    {ref}: {cnt} rows")

    except Exception as e:
        conn.rollback()
        print(f"\n  ✗ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
