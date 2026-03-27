-- =============================================================================
-- RAITO — Inventory Snapshots Schema Migration
-- Run once against existing database to add the inventory_snapshots table.
-- Safe to re-run (DROP IF EXISTS).
--
-- Usage:
--   psql "postgresql://raito:raito@localhost:5432/raito" -f scripts/db/migrate_inventory_schema.sql
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS inventory_snapshots CASCADE;

CREATE TABLE inventory_snapshots (
    id                  SERIAL          PRIMARY KEY,
    distributor_id      INT             NOT NULL REFERENCES distributors(id),
    product_id          INT             NOT NULL REFERENCES products(id),
    units               INT             NOT NULL DEFAULT 0,
    pallets             NUMERIC(8,1),
    cartons             NUMERIC(10,1),
    snapshot_date       DATE            NOT NULL,
    source_type         VARCHAR(30)     NOT NULL DEFAULT 'distributor',
    ingestion_batch_id  INT             NOT NULL REFERENCES ingestion_batches(id),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_units_non_negative
        CHECK (units >= 0),
    CONSTRAINT chk_source_type
        CHECK (source_type IN ('warehouse', 'distributor')),
    CONSTRAINT uq_inv_snapshot
        UNIQUE (distributor_id, product_id, snapshot_date)
);

-- Latest snapshot lookup: most recent date per distributor/product
CREATE INDEX idx_inv_latest
    ON inventory_snapshots (distributor_id, product_id, snapshot_date DESC);

-- Batch-level rollback support
CREATE INDEX idx_inv_batch
    ON inventory_snapshots (ingestion_batch_id);

COMMENT ON TABLE inventory_snapshots IS
    'Point-in-time inventory levels. One row per (distributor, product, date). '
    'Karfree warehouse uses source_type=warehouse; Icedream/Ma''ayan use source_type=distributor. '
    'Latest snapshot per distributor is the current stock level.';

-- Ensure Karfree warehouse distributor exists (inventory-only, no sales)
INSERT INTO distributors (key, name_en, name_he, commission_pct, report_format, is_active, notes)
VALUES ('karfree', 'Karfree Warehouse', 'קרפרי', 0.00, 'pdf_report', TRUE,
        'Cold storage warehouse. Inventory-only — no sales transactions.')
ON CONFLICT (key) DO NOTHING;

COMMIT;

-- Verify
SELECT 'inventory_snapshots table created' AS status,
       count(*) AS column_count
FROM information_schema.columns
WHERE table_name = 'inventory_snapshots';
