#!/usr/bin/env python3
"""
RAITO — Phase 1 Migration: ID-Based Entity Resolution

Creates:
  1. brands table (NEW)
  2. products.brand_id FK column (ALTER)
  3. customer_alias_lookup materialized view
  4. product_alias_lookup materialized view

Idempotent: safe to re-run. Uses IF NOT EXISTS / ON CONFLICT DO NOTHING.

Usage (Cloud Shell):
  DATABASE_URL="postgresql://raito_app:raito_app@127.0.0.1:5432/raito" python3 migrate_phase1_ids.py
"""

import os
import sys
import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://raito_app:raito_app@127.0.0.1:5432/raito")

# ═════════════════════════════════════════════════════════════════════════════
# Step 1: Create brands table
# ═════════════════════════════════════════════════════════════════════════════

SQL_CREATE_BRANDS = """
CREATE TABLE IF NOT EXISTS brands (
    id          SERIAL       PRIMARY KEY,
    key         VARCHAR(30)  NOT NULL UNIQUE,
    name_en     VARCHAR(100) NOT NULL,
    name_he     VARCHAR(100),
    owner       VARCHAR(100),
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE brands IS 'Brand dimension. key is a slug (turbo, danis). name_en is the dashboard display name.';
"""

# ═════════════════════════════════════════════════════════════════════════════
# Step 2: Seed brand data
# ═════════════════════════════════════════════════════════════════════════════

BRANDS_SEED = [
    # (key, name_en, name_he, owner, is_active)
    ("turbo",  "Turbo",              "טורבו",           "דני אבדיה",   True),
    ("danis",  "Dani's Dream Cake",  "דרים קייק של דני", "דניאל עמית",  True),
]

SQL_SEED_BRAND = """
INSERT INTO brands (key, name_en, name_he, owner, is_active)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (key) DO NOTHING;
"""

# ═════════════════════════════════════════════════════════════════════════════
# Step 3: Add brand_id FK to products (keep brand_key for backward compat)
# ═════════════════════════════════════════════════════════════════════════════

SQL_ADD_BRAND_ID = """
DO $$
BEGIN
    -- Add brand_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'products' AND column_name = 'brand_id'
    ) THEN
        ALTER TABLE products ADD COLUMN brand_id INT REFERENCES brands(id);
        RAISE NOTICE 'Added products.brand_id column';
    ELSE
        RAISE NOTICE 'products.brand_id already exists — skipping';
    END IF;
END $$;
"""

SQL_BACKFILL_BRAND_ID = """
UPDATE products p
SET brand_id = b.id
FROM brands b
WHERE p.brand_key = b.key
  AND p.brand_id IS NULL;
"""

# ═════════════════════════════════════════════════════════════════════════════
# Step 4: Customer alias lookup (materialized view)
# ═════════════════════════════════════════════════════════════════════════════

SQL_CUSTOMER_ALIAS_LOOKUP = """
DROP MATERIALIZED VIEW IF EXISTS customer_alias_lookup;

CREATE MATERIALIZED VIEW customer_alias_lookup AS
SELECT DISTINCT ON (alias)
       customer_id, name_en, alias
FROM (
    -- Primary Hebrew name
    SELECT c.id        AS customer_id,
           c.name_en   AS name_en,
           c.name_he   AS alias
    FROM   customers c
    WHERE  c.name_he IS NOT NULL

    UNION ALL

    -- All Hebrew aliases
    SELECT c.id        AS customer_id,
           c.name_en   AS name_en,
           unnest(c.name_he_aliases) AS alias
    FROM   customers c
    WHERE  c.name_he_aliases IS NOT NULL

    UNION ALL

    -- English name as alias too (for cases where distributor uses English)
    SELECT c.id        AS customer_id,
           c.name_en   AS name_en,
           c.name_en   AS alias
    FROM   customers c
) sub
WHERE alias IS NOT NULL AND alias != ''
ORDER BY alias, customer_id;

CREATE UNIQUE INDEX idx_cust_alias_lookup ON customer_alias_lookup (alias);
"""

# ═════════════════════════════════════════════════════════════════════════════
# Step 5: Product alias lookup (materialized view)
# ═════════════════════════════════════════════════════════════════════════════

SQL_PRODUCT_ALIAS_LOOKUP = """
DROP MATERIALIZED VIEW IF EXISTS product_alias_lookup;

CREATE MATERIALIZED VIEW product_alias_lookup AS
-- Full Hebrew name
SELECT p.id       AS product_id,
       p.sku_key  AS sku_key,
       p.full_name_en AS name_en,
       p.full_name_he AS alias
FROM   products p
WHERE  p.full_name_he IS NOT NULL

UNION ALL

-- SKU key as alias (for code-level lookups)
SELECT p.id       AS product_id,
       p.sku_key  AS sku_key,
       p.full_name_en AS name_en,
       p.sku_key  AS alias
FROM   products p

UNION ALL

-- English name as alias
SELECT p.id       AS product_id,
       p.sku_key  AS sku_key,
       p.full_name_en AS name_en,
       p.full_name_en AS alias
FROM   products p
WHERE  p.full_name_en IS NOT NULL;

CREATE INDEX idx_prod_alias_lookup ON product_alias_lookup (alias);
"""

# ═════════════════════════════════════════════════════════════════════════════
# Execute
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("RAITO Phase 1 Migration: ID-Based Entity Resolution")
    print("=" * 60)

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Step 1: Create brands table
        print("\n[1/5] Creating brands table...")
        cur.execute(SQL_CREATE_BRANDS)
        conn.commit()
        print("  ✓ brands table ready")

        # Step 2: Seed brand data
        print("\n[2/5] Seeding brand data...")
        for brand in BRANDS_SEED:
            cur.execute(SQL_SEED_BRAND, brand)
        conn.commit()
        cur.execute("SELECT id, key, name_en FROM brands ORDER BY id")
        rows = cur.fetchall()
        for r in rows:
            print(f"  brand_id={r[0]}  key={r[1]}  name_en={r[2]}")
        print(f"  ✓ {len(rows)} brands in table")

        # Step 3: Add brand_id FK to products
        print("\n[3/5] Adding products.brand_id FK...")
        cur.execute(SQL_ADD_BRAND_ID)
        conn.commit()
        cur.execute(SQL_BACKFILL_BRAND_ID)
        updated = cur.rowcount
        conn.commit()
        print(f"  ✓ Backfilled {updated} products with brand_id")

        # Verify
        cur.execute("""
            SELECT p.sku_key, p.brand_key, p.brand_id, b.name_en
            FROM products p
            LEFT JOIN brands b ON p.brand_id = b.id
            ORDER BY p.display_order
        """)
        for r in cur.fetchall():
            status = "✓" if r[2] else "✗ MISSING"
            print(f"  {status}  {r[0]}: brand_key={r[1]} → brand_id={r[2]} ({r[3]})")

        # Step 4: Customer alias lookup
        print("\n[4/5] Creating customer_alias_lookup materialized view...")
        cur.execute(SQL_CUSTOMER_ALIAS_LOOKUP)
        conn.commit()
        cur.execute("SELECT count(*) FROM customer_alias_lookup")
        alias_count = cur.fetchone()[0]
        print(f"  ✓ {alias_count} alias entries")

        # Show sample
        cur.execute("""
            SELECT alias, customer_id, name_en
            FROM customer_alias_lookup
            ORDER BY customer_id, alias
            LIMIT 15
        """)
        for r in cur.fetchall():
            print(f"  '{r[0]}' → customer_id={r[1]} ({r[2]})")
        print("  ...")

        # Step 5: Product alias lookup
        print("\n[5/5] Creating product_alias_lookup materialized view...")
        cur.execute(SQL_PRODUCT_ALIAS_LOOKUP)
        conn.commit()
        cur.execute("SELECT count(*) FROM product_alias_lookup")
        prod_count = cur.fetchone()[0]
        print(f"  ✓ {prod_count} product alias entries")

        cur.execute("""
            SELECT alias, product_id, sku_key
            FROM product_alias_lookup
            ORDER BY product_id, alias
            LIMIT 15
        """)
        for r in cur.fetchall():
            print(f"  '{r[0]}' → product_id={r[1]} ({r[2]})")

        print("\n" + "=" * 60)
        print("Phase 1 migration complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Run the dry-run resolver test: python3 test_resolvers.py")
        print("  2. Review any unmatched names and add aliases")
        print("  3. Update parsers.py to use resolve_customer() / resolve_product()")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
