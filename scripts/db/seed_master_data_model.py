#!/usr/bin/env python3
"""
RAITO — Seed Master Data Model (creators + distributor_assortment + dist_pct)

Run AFTER migrate_master_data_model.sql has been applied.

Populates:
  1. creators         — Deni Avdija, Daniel Amit (+ planned: Ma Kashur, The Cohen)
  2. brands.creator_id — wires existing brands to their creators
  3. distributor_assortment — current active SKU × distributor catalogue
  4. price_history.dist_pct — backfills commission at the pricing grain from the
     currently-hardcoded per-distributor defaults (15/25/0)

Idempotent: uses INSERT ... ON CONFLICT DO NOTHING and UPDATE ... WHERE NULL.

Usage:
    export DATABASE_URL="postgresql://raito:raito@localhost:5433/raito"
    python3 scripts/db/seed_master_data_model.py
"""

import os
import sys
from pathlib import Path
from datetime import date

import psycopg2

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

DEFAULT_DB_URL = "postgresql://raito:raito@localhost:5432/raito"


def get_conn():
    url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# 1. Creators
# ─────────────────────────────────────────────────────────────────────────────
# (key, name_en, name_he, persona, commercial_terms_json, notes)

CREATORS = [
    (
        'deni_avdija', 'Deni Avdija', 'דני אבדיה',
        'NBA player (Portland Trail Blazers), nicknamed "Turbo"',
        '{}',            # royalty terms — fill in later (future-scope)
        'Brand face for Turbo ice cream + upcoming Turbo Nuts.',
    ),
    (
        'daniel_amit',  'Daniel Amit',  'דניאל עמית',
        'Creator / pastry brand owner',
        '{"royalty_per_unit_ils": 10, "sku_scope": ["dream_cake_2"], "paid_by": "biscotti"}',
        'Brand face for Dani\'s Dream Cake. Biscotti pays ₪10 per cake sold as royalty.',
    ),
    (
        'ma_kashur',    'Ma Kashur',    None,
        'Creator (Ahlan coffee — planned Jul 2026)',
        '{}',
        'Planned — not yet active.',
    ),
    (
        'the_cohen',    'The Cohen',    None,
        'Creator (W capsules — planned Aug 2026)',
        '{}',
        'Planned — not yet active.',
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Brand → Creator wiring  (Creator:Brand is 1:1)
# ─────────────────────────────────────────────────────────────────────────────
# A brand spans multiple CATEGORIES (products.category), not multiple brands.
#   Deni:   brand "turbo"  → categories: ice_cream, protein_snacks, ...
#   Daniel: brand "danis"  → categories: frozen_cakes, ... (extensible)
#
# (brand_key, creator_key, name_en_override)  — name override lets us rename
# brands that have outgrown their original category (e.g. "Dani's Dream Cake"
# → "Dani's" so Daniel can extend beyond cakes).

BRAND_CREATORS = [
    ('turbo', 'deni_avdija', 'Turbo by Deni Avdjia'),
    ('danis', 'daniel_amit', "Dani's"),
    ('ahlan', 'ma_kashur',   'Ahlan'),
    ('w',     'the_cohen',   'W'),
]

# Brands to deactivate — obsolete entries we're collapsing into a parent brand.
# (brand_key, reason)
BRANDS_TO_RETIRE = [
    ('turbo_nuts',
     'Collapsed into brand=turbo with category=protein_snacks (creator-level brand, 1 brand per creator).'),
]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Distributor assortment
# ─────────────────────────────────────────────────────────────────────────────
# (distributor_key, sku_key)
#
# THE ASSORTMENT RULE, made explicit:
#   - Turbo ice cream SKUs (Vaniglia) → Icedream + Ma'ayan Frozen
#   - Dream Cake SKUs (Biscotti)      → Biscotti only
#   - Turbo Nuts SKUs (Din Shiwuk)    → Ma'ayan Ambient (planned, ~June 2026)

ASSORTMENT = [
    # Icedream — Vaniglia ice cream
    ('icedreams',   'chocolate'),
    ('icedreams',   'vanilla'),
    ('icedreams',   'mango'),
    ('icedreams',   'pistachio'),
    ('icedreams',   'dream_cake'),     # historical (discontinued, kept for history)

    # Ma'ayan Frozen — same Vaniglia ice cream line
    ('mayyan_froz', 'chocolate'),
    ('mayyan_froz', 'vanilla'),
    ('mayyan_froz', 'mango'),
    ('mayyan_froz', 'pistachio'),

    # Biscotti — its own Dream Cake line (manufacturer = distributor)
    ('biscotti',    'dream_cake_2'),

    # Ma'ayan Ambient — planned Turbo Nuts (activate when SKUs go live)
    # ('mayyan_amb',  'nuts_sku1'),
    # ('mayyan_amb',  'nuts_sku2'),
]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Default dist_pct per distributor (used for price_history backfill)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_DIST_PCT = {
    'icedreams':   15.0,
    'mayyan_froz': 25.0,
    'biscotti':     0.0,
    'mayyan_amb':  25.0,  # placeholder — negotiate before nuts go live
}


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def seed_creators(cur):
    print("── 1. Seeding creators ...")
    for key, name_en, name_he, persona, terms, notes in CREATORS:
        cur.execute(
            """
            INSERT INTO creators (key, name_en, name_he, persona, commercial_terms, notes)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (key) DO NOTHING
            """,
            (key, name_en, name_he, persona, terms, notes),
        )
    cur.execute("SELECT COUNT(*) FROM creators")
    print(f"   creators in DB: {cur.fetchone()[0]}")


def wire_brands_to_creators(cur):
    print("── 2. Wiring brands → creators + renaming (1 brand per creator) ...")
    updated = 0
    for brand_key, creator_key, name_en in BRAND_CREATORS:
        cur.execute(
            """
            UPDATE brands
               SET creator_id = (SELECT id FROM creators WHERE key = %s),
                   name_en    = %s
             WHERE key = %s
            """,
            (creator_key, name_en, brand_key),
        )
        updated += cur.rowcount

    # Retire collapsed brands (e.g. turbo_nuts → folded into turbo/protein_snacks)
    retired = 0
    for brand_key, reason in BRANDS_TO_RETIRE:
        cur.execute(
            """
            UPDATE brands
               SET is_active = FALSE,
                   name_en   = name_en || ' [retired]'
             WHERE key = %s
               AND is_active = TRUE
            """,
            (brand_key,),
        )
        retired += cur.rowcount
        if cur.rowcount:
            print(f"   retired brand '{brand_key}': {reason}")

    print(f"   brands wired + renamed: {updated}, retired: {retired}")


def seed_assortment(cur):
    print("── 3. Seeding distributor_assortment ...")
    inserted = 0
    for dist_key, sku_key in ASSORTMENT:
        cur.execute(
            """
            INSERT INTO distributor_assortment (distributor_id, product_id, effective_from, notes)
            SELECT d.id, p.id, %s, 'seeded from master_data_model seed script'
              FROM distributors d
              JOIN products     p ON p.sku_key = %s
             WHERE d.key = %s
            ON CONFLICT DO NOTHING
            """,
            (date(2025, 12, 1), sku_key, dist_key),
        )
        inserted += cur.rowcount
    cur.execute(
        "SELECT COUNT(*) FROM distributor_assortment WHERE effective_to IS NULL"
    )
    print(f"   assortment rows inserted this run: {inserted}")
    print(f"   active assortment rows total:     {cur.fetchone()[0]}")


def backfill_price_history_dist_pct(cur):
    print("── 4. Back-filling price_history.dist_pct ...")
    total = 0
    for dist_key, default_pct in DEFAULT_DIST_PCT.items():
        cur.execute(
            """
            UPDATE price_history ph
               SET dist_pct = %s
              FROM distributors d
             WHERE ph.distributor_id = d.id
               AND d.key = %s
               AND ph.dist_pct IS NULL
            """,
            (default_pct, dist_key),
        )
        total += cur.rowcount
    print(f"   price_history rows back-filled: {total}")


def main():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            seed_creators(cur)
            wire_brands_to_creators(cur)
            seed_assortment(cur)
            backfill_price_history_dist_pct(cur)
        conn.commit()
        print("\n✅ Master data model seed complete.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
