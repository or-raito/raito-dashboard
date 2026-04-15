#!/usr/bin/env python3
"""
RAITO — Fix master_data field name corruption

Renames any 'distributor_key' → 'distributor' and 'customer_key' → 'customer'
fields that were saved incorrectly due to the fkFields mapping bug.

Usage (Cloud Shell):
  DATABASE_URL="postgresql://raito_app:raito_app@127.0.0.1:5432/raito" python3 fix_master_data_fields.py
"""

import os
import json
import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://raito_app:raito_app@127.0.0.1:5432/raito")


def fix_entity(records, field_renames):
    """Rename fields in a list of dicts. Returns (fixed_records, fix_count)."""
    fixed = 0
    for rec in records:
        for old_key, new_key in field_renames.items():
            if old_key in rec:
                rec[new_key] = rec.pop(old_key)
                fixed += 1
    return records, fixed


def main():
    print("=" * 60)
    print("RAITO — Fix master_data field names")
    print("=" * 60)

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # ── customers: distributor_key → distributor ──
        cur.execute("SELECT data FROM master_data WHERE entity = 'customers'")
        row = cur.fetchone()
        if row:
            customers = row[0]
            customers, n = fix_entity(customers, {'distributor_key': 'distributor'})
            cur.execute(
                "UPDATE master_data SET data = %s, updated_at = NOW() WHERE entity = 'customers'",
                (json.dumps(customers),)
            )
            print(f"  customers: fixed {n} field(s)")
        else:
            print("  customers: not found in master_data")

        # ── pricing: customer_key → customer, distributor_key → distributor ──
        cur.execute("SELECT data FROM master_data WHERE entity = 'pricing'")
        row = cur.fetchone()
        if row:
            pricing = row[0]
            pricing, n = fix_entity(pricing, {'customer_key': 'customer', 'distributor_key': 'distributor'})
            cur.execute(
                "UPDATE master_data SET data = %s, updated_at = NOW() WHERE entity = 'pricing'",
                (json.dumps(pricing),)
            )
            print(f"  pricing:   fixed {n} field(s)")
        else:
            print("  pricing: not found in master_data")

        conn.commit()
        print("\n  ✓ Done. Reload the dashboard to see the fix.")

    except Exception as e:
        conn.rollback()
        print(f"\n  ✗ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
