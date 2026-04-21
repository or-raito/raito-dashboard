-- Phase 6.1 — Add canonical_sp_id to sale_points for alias grouping
-- Run on both raito_dev and raito (prod) databases.
--
-- Semantics:
--   canonical_sp_id IS NULL  → this SP is a canonical record (the "real" physical location)
--   canonical_sp_id = X      → this SP is an alias of canonical SP X (same store, different name/distributor)
--
-- Usage: psql $DATABASE_URL -f migrate_sp_canonical.sql

BEGIN;

-- 1. Add the self-referencing FK column
ALTER TABLE sale_points ADD COLUMN IF NOT EXISTS canonical_sp_id INT REFERENCES sale_points(id);

-- 2. Partial index — only rows that ARE aliases (non-null canonical_sp_id)
CREATE INDEX IF NOT EXISTS idx_sp_canonical ON sale_points (canonical_sp_id) WHERE canonical_sp_id IS NOT NULL;

-- 3. Ensure raito_app has full CRUD on sale_points
GRANT SELECT, INSERT, UPDATE, DELETE ON sale_points TO raito_app;

COMMIT;
