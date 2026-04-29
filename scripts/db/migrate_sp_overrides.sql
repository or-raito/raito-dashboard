-- SP Customer Overrides — user-defined SP→Customer mappings
-- These overrides take priority over hardcoded rules in extract_customer_name().
-- Run on raito_dev first, then raito (prod) after validation.
--
-- Usage: psql $DATABASE_URL -f migrate_sp_overrides.sql

BEGIN;

CREATE TABLE IF NOT EXISTS sp_customer_overrides (
    id          SERIAL PRIMARY KEY,
    sp_name     TEXT NOT NULL,              -- raw Hebrew SP name (exact match key)
    customer_en TEXT NOT NULL,              -- English customer name (e.g. 'AMPM', 'Wolt Market')
    distributor TEXT,                       -- optional: limit to specific distributor
    match_type  TEXT NOT NULL DEFAULT 'exact',  -- 'exact', 'prefix', 'contains'
    notes       TEXT,                       -- optional: why this override exists
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (sp_name, distributor)           -- prevent duplicate overrides
);

-- Index for fast lookup during extract_customer_name()
CREATE INDEX IF NOT EXISTS idx_sp_overrides_name ON sp_customer_overrides (sp_name);
CREATE INDEX IF NOT EXISTS idx_sp_overrides_customer ON sp_customer_overrides (customer_en);

-- Grant access to both DB users
GRANT SELECT, INSERT, UPDATE, DELETE ON sp_customer_overrides TO raito_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON sp_customer_overrides TO raito;
GRANT USAGE, SELECT ON SEQUENCE sp_customer_overrides_id_seq TO raito_app;
GRANT USAGE, SELECT ON SEQUENCE sp_customer_overrides_id_seq TO raito;

COMMIT;
