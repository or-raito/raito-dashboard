-- ═════════════════════════════════════════════════════════════════════════════
-- RAITO — Master Data Model Migration
-- ═════════════════════════════════════════════════════════════════════════════
-- Formalizes the canonical entity hierarchy:
--   Creator → Brand → SKU → Manufacturer → Distributor(assortment) → Customer → SalePoint
--
-- Adds:
--   1. creators                 — new table (Deni Avdija, Daniel Amit, ...)
--   2. distributor_assortment   — new table (which distributors carry which SKUs)
--   3. price_history.dist_pct   — commission at (customer × distributor × SKU) grain
--   4. brands.creator_id        — FK to creators
--   5. sale_points attribution  — status + suggested_customer_id + confidence
--
-- Idempotent: safe to run multiple times (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
-- Ownership: must be run as `raito` user (owner of all tables).
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. creators  (real persons with Raito commercial agreements)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS creators (
    id                  SERIAL          PRIMARY KEY,
    key                 VARCHAR(40)     NOT NULL UNIQUE,
    name_en             VARCHAR(120)    NOT NULL,
    name_he             VARCHAR(120),
    persona             VARCHAR(60),            -- "NBA player", "Pastry chef", etc.
    commercial_terms    JSONB           NOT NULL DEFAULT '{}'::jsonb,
                        -- e.g. {"royalty_per_unit_ils": 10, "sku_scope": ["dream_cake_*"]}
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    notes               TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE creators IS
    'Real persons with commercial agreements with Raito. A creator may own multiple brands (Deni: Turbo + Turbo Nuts).';
COMMENT ON COLUMN creators.commercial_terms IS
    'JSON bag of royalty / commission terms. Future-use: creator earnings reporting.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. brands.creator_id  (attach brand to its creator)
-- ─────────────────────────────────────────────────────────────────────────────
-- brands table already exists via migrate_phase1_ids.py

ALTER TABLE brands
    ADD COLUMN IF NOT EXISTS creator_id INT REFERENCES creators(id);

CREATE INDEX IF NOT EXISTS idx_brands_creator
    ON brands (creator_id) WHERE creator_id IS NOT NULL;


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. distributor_assortment  (which SKUs each distributor carries)
-- ─────────────────────────────────────────────────────────────────────────────
-- Enforces the assortment rule: a customer can only order a SKU from a
-- distributor that carries it. Date-aware so we can retire / introduce SKUs
-- per distributor without losing history.

CREATE TABLE IF NOT EXISTS distributor_assortment (
    id                  SERIAL          PRIMARY KEY,
    distributor_id      INT             NOT NULL REFERENCES distributors(id),
    product_id          INT             NOT NULL REFERENCES products(id),
    effective_from      DATE            NOT NULL DEFAULT CURRENT_DATE,
    effective_to        DATE,
    notes               TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_da_date_range
        CHECK (effective_to IS NULL OR effective_to > effective_from)
);

-- A distributor can only have one OPEN (effective_to IS NULL) row per product
CREATE UNIQUE INDEX IF NOT EXISTS idx_da_current
    ON distributor_assortment (distributor_id, product_id)
    WHERE effective_to IS NULL;

CREATE INDEX IF NOT EXISTS idx_da_product
    ON distributor_assortment (product_id);

COMMENT ON TABLE distributor_assortment IS
    'Distributor × Product catalogue. Enforces the assortment rule: a (customer, product) transaction must come from a distributor that carries that product.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. price_history.dist_pct  (commission at the pricing grain)
-- ─────────────────────────────────────────────────────────────────────────────
-- Existing price_history already has (product_id, customer_id, distributor_id) —
-- this is exactly the pricing grain we need. Add dist_pct here so commission
-- can vary per (customer × distributor × SKU) triple.

ALTER TABLE price_history
    ADD COLUMN IF NOT EXISTS dist_pct NUMERIC(5,2);

ALTER TABLE price_history
    DROP CONSTRAINT IF EXISTS chk_dist_pct_range;
ALTER TABLE price_history
    ADD  CONSTRAINT chk_dist_pct_range
         CHECK (dist_pct IS NULL OR (dist_pct >= 0 AND dist_pct <= 100));

COMMENT ON COLUMN price_history.dist_pct IS
    'Distributor commission % at the (customer, distributor, product) grain. NULL = fall back to distributors.commission_pct.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. sale_points — attribution status + suggestion fields
-- ─────────────────────────────────────────────────────────────────────────────
-- Status progresses: unassigned → suggested (pre-filled by matcher) → confirmed
-- (user clicks confirm in MD tab inbox).

ALTER TABLE sale_points
    ADD COLUMN IF NOT EXISTS attribution_status     VARCHAR(20) NOT NULL DEFAULT 'confirmed';

ALTER TABLE sale_points
    ADD COLUMN IF NOT EXISTS suggested_customer_id  INT REFERENCES customers(id);

ALTER TABLE sale_points
    ADD COLUMN IF NOT EXISTS suggestion_confidence  NUMERIC(4,3);

ALTER TABLE sale_points
    ADD COLUMN IF NOT EXISTS suggestion_reason      VARCHAR(60);

ALTER TABLE sale_points
    DROP CONSTRAINT IF EXISTS chk_sp_attr_status;
ALTER TABLE sale_points
    ADD  CONSTRAINT chk_sp_attr_status
         CHECK (attribution_status IN ('unassigned', 'suggested', 'confirmed'));

CREATE INDEX IF NOT EXISTS idx_sp_inbox
    ON sale_points (attribution_status)
    WHERE attribution_status IN ('unassigned', 'suggested');

COMMENT ON COLUMN sale_points.attribution_status IS
    'unassigned = no guess yet; suggested = matcher proposed a customer (confidence set); confirmed = user approved or legacy row. MD tab inbox shows status IN (unassigned, suggested).';


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Relax sale_points.customer_id NOT NULL
-- ─────────────────────────────────────────────────────────────────────────────
-- An 'unassigned' SP has no customer_id until the user confirms one in the
-- MD tab inbox. The FK stays — just the NOT NULL is dropped.

ALTER TABLE sale_points
    ALTER COLUMN customer_id DROP NOT NULL;


-- ─────────────────────────────────────────────────────────────────────────────
-- 7. Backfill: all existing sale_points are confirmed (they predate this flow)
-- ─────────────────────────────────────────────────────────────────────────────

UPDATE sale_points
   SET attribution_status = 'confirmed'
 WHERE attribution_status IS NULL
    OR attribution_status = '';

COMMIT;
