-- =============================================================================
-- RAITO Supply Chain — PostgreSQL Schema DDL
-- Phase 0: Database structure for SSOT migration
-- Generated: 26 March 2026
-- Target: Google Cloud SQL (PostgreSQL 15+)
-- =============================================================================

-- Run order: this file is self-contained and idempotent (DROP IF EXISTS).
-- Execute once to create all tables, indexes, and constraints.

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- LAYER 1: Reference Data
-- ─────────────────────────────────────────────────────────────────────────────

-- Table 1: manufacturers
-- Source: RAITO_BRIEFING.md § Manufacturers
DROP TABLE IF EXISTS inventory_snapshots CASCADE;
DROP TABLE IF EXISTS sales_transactions CASCADE;
DROP TABLE IF EXISTS ingestion_batches CASCADE;
DROP TABLE IF EXISTS price_history CASCADE;
DROP TABLE IF EXISTS sale_points CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS distributors CASCADE;
DROP TABLE IF EXISTS manufacturers CASCADE;

CREATE TABLE manufacturers (
    id              SERIAL          PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL UNIQUE,
    contact_email   VARCHAR(150),
    address         TEXT,
    lead_time_days  INT,
    moq_units       INT,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE manufacturers IS 'Production partners (Vaniglia, Biscotti, etc.). Source: registry.py + Master Data.';


-- Table 2: distributors
-- Source: registry.DISTRIBUTORS + RAITO_BRIEFING.md § Distributors

CREATE TABLE distributors (
    id              SERIAL          PRIMARY KEY,
    key             VARCHAR(30)     NOT NULL UNIQUE,
    name_en         VARCHAR(100)    NOT NULL,
    name_he         VARCHAR(100),
    commission_pct  NUMERIC(5,2)    NOT NULL DEFAULT 0.00,
    report_format   VARCHAR(30),
    contact_name    VARCHAR(100),
    contact_email   VARCHAR(150),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE distributors IS 'Distribution partners. commission_pct = their take on each sale. Source: registry.DISTRIBUTORS.';


-- Table 3: products
-- Source: registry.PRODUCTS + pricing_engine._B2B_PRICES + PRODUCTION_COST

CREATE TABLE products (
    id                      SERIAL          PRIMARY KEY,
    sku_key                 VARCHAR(30)     NOT NULL UNIQUE,
    barcode                 VARCHAR(30)     UNIQUE,
    full_name_en            VARCHAR(150)    NOT NULL,
    full_name_he            VARCHAR(150),
    short_name              VARCHAR(50),
    brand_key               VARCHAR(30)     NOT NULL,
    category                VARCHAR(30)     NOT NULL DEFAULT 'ice_cream',
    manufacturer_id         INT             REFERENCES manufacturers(id),
    status                  VARCHAR(20)     NOT NULL DEFAULT 'active',
    production_cost_ils     NUMERIC(10,2),
    b2b_list_price_ils      NUMERIC(10,2),
    units_per_carton        INT,
    units_per_pallet        INT,
    shelf_life_months       INT,
    storage_temp            VARCHAR(30),
    color_hex               VARCHAR(10),
    flavor_color_hex        VARCHAR(10),
    display_order           INT,
    launched_at             DATE,
    discontinued_at         DATE,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_product_status
        CHECK (status IN ('active', 'discontinued', 'planned', 'new')),
    CONSTRAINT chk_b2b_price
        CHECK (b2b_list_price_ils IS NULL OR b2b_list_price_ils >= 0),
    CONSTRAINT chk_prod_cost
        CHECK (production_cost_ils IS NULL OR production_cost_ils >= 0)
);

COMMENT ON TABLE products IS 'Product catalog. Replaces registry.PRODUCTS + pricing_engine._B2B_PRICES. sku_key is the canonical internal identifier.';
COMMENT ON COLUMN products.full_name_he IS 'Hebrew SKU name as it appears in distributor Excel files — used for classify_product() matching.';
COMMENT ON COLUMN products.units_per_carton IS 'Carton-to-unit multiplier (10 for Turbo, 6 for Vanilla, 3 for Dream Cake).';


-- Table 4: customers
-- Source: registry.CUSTOMER_NAMES_EN + _ICE_CHAIN_PREFIXES + _MAAYAN_CHAIN_NORM

CREATE TABLE customers (
    id                          SERIAL          PRIMARY KEY,
    name_en                     VARCHAR(100)    NOT NULL UNIQUE,
    name_he                     VARCHAR(100),
    name_he_aliases             TEXT[],
    primary_distributor_id      INT             REFERENCES distributors(id),
    customer_type               VARCHAR(30)     NOT NULL DEFAULT 'chain',
    cc_tracked                  BOOLEAN         NOT NULL DEFAULT FALSE,
    dist_commission_override    NUMERIC(5,2),
    is_active                   BOOLEAN         NOT NULL DEFAULT TRUE,
    first_order_date            DATE,
    notes                       TEXT,
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_customer_type
        CHECK (customer_type IN ('chain', 'independent', 'wholesale'))
);

COMMENT ON TABLE customers IS 'Top-level customer entities (AMPM, Wolt Market, etc.). name_he_aliases holds all known Hebrew spelling variants for parser matching.';
COMMENT ON COLUMN customers.cc_tracked IS 'TRUE for the ~18 customers tracked in the Customer Centric dashboard.';


-- Table 5: sale_points
-- Source: derived dynamically from distributor branch strings in salepoint_dashboard.py

CREATE TABLE sale_points (
    id                  SERIAL          PRIMARY KEY,
    customer_id         INT             NOT NULL REFERENCES customers(id),
    distributor_id      INT             NOT NULL REFERENCES distributors(id),
    branch_name_he      VARCHAR(250)    NOT NULL,
    branch_name_clean   VARCHAR(250),
    city                VARCHAR(100),
    region              VARCHAR(50),
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    first_order_date    DATE,
    last_order_date     DATE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    UNIQUE (distributor_id, branch_name_he)
);

COMMENT ON TABLE sale_points IS 'Individual branches / points of sale (~1,200+). Auto-registered by the ingestion pipeline via ON CONFLICT DO NOTHING.';


-- ─────────────────────────────────────────────────────────────────────────────
-- LAYER 2: Pricing (Date-Aware / SCD Type 2)
-- ─────────────────────────────────────────────────────────────────────────────

-- Table 6: price_history
-- Source: pricing_engine._B2B_PRICES + _CUSTOMER_PRICES + price db Excel

CREATE TABLE price_history (
    id                  SERIAL          PRIMARY KEY,
    product_id          INT             NOT NULL REFERENCES products(id),
    customer_id         INT             REFERENCES customers(id),
    distributor_id      INT             REFERENCES distributors(id),
    price_ils           NUMERIC(10,2)   NOT NULL,
    effective_from      DATE            NOT NULL,
    effective_to        DATE,
    price_type          VARCHAR(20)     NOT NULL DEFAULT 'b2b_list',
    source_reference    VARCHAR(200),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_date_range
        CHECK (effective_to IS NULL OR effective_to > effective_from),
    CONSTRAINT chk_price_positive
        CHECK (price_ils > 0),
    CONSTRAINT chk_price_type
        CHECK (price_type IN ('b2b_list', 'negotiated', 'production_cost'))
);

-- Hot path: "What is the price for product X for customer Y on date D?"
-- NOTE: Cannot use NOW() in partial index (not immutable). Instead, index all
-- rows and let the query's WHERE clause filter by date at runtime.
-- The composite (product_id, customer_id, effective_from DESC) ordering
-- makes the cascading price lookup fast even without a partial filter.
CREATE INDEX idx_price_lookup
    ON price_history (product_id, customer_id, effective_from DESC);

-- Secondary: all active prices for a customer (CC dashboard load)
CREATE INDEX idx_price_by_customer
    ON price_history (customer_id, product_id)
    WHERE effective_to IS NULL;

COMMENT ON TABLE price_history IS 'Date-effective pricing (SCD Type 2). NULL customer_id = B2B list price. NULL effective_to = currently active. Replaces pricing_engine two-tier API.';


-- ─────────────────────────────────────────────────────────────────────────────
-- LAYER 3: Transactions
-- ─────────────────────────────────────────────────────────────────────────────

-- Table 7: ingestion_batches
-- Audit and deduplication control

CREATE TABLE ingestion_batches (
    id                  SERIAL          PRIMARY KEY,
    source_file_name    VARCHAR(300)    NOT NULL,
    distributor_id      INT             NOT NULL REFERENCES distributors(id),
    file_format         VARCHAR(30),
    reporting_period    VARCHAR(30),
    record_count        INT,
    status              VARCHAR(20)     NOT NULL DEFAULT 'pending',
    uploaded_by         VARCHAR(100),
    upload_timestamp    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    error_message       TEXT,

    CONSTRAINT chk_batch_status
        CHECK (status IN ('pending', 'processing', 'complete', 'failed', 'rolled_back'))
);

-- Prevent double-ingestion of the same file for the same distributor
CREATE UNIQUE INDEX idx_batch_dedup
    ON ingestion_batches (source_file_name, distributor_id)
    WHERE status = 'complete';

COMMENT ON TABLE ingestion_batches IS 'One row per ingested file. Provides rollback semantics (DELETE WHERE batch_id=?) and dedup (unique on file+distributor when complete).';


-- Table 8: sales_transactions
-- The unified landing table — all BO, CC, SP queries run against this

CREATE TABLE sales_transactions (
    id                          BIGSERIAL       PRIMARY KEY,
    -- Time dimensions
    transaction_date            DATE            NOT NULL,
    week_number                 SMALLINT,
    year                        SMALLINT        NOT NULL,
    month                       SMALLINT        NOT NULL,
    -- Entities
    product_id                  INT             NOT NULL REFERENCES products(id),
    distributor_id              INT             NOT NULL REFERENCES distributors(id),
    customer_id                 INT             REFERENCES customers(id),
    sale_point_id               INT             REFERENCES sale_points(id),
    -- Financials
    units_sold                  INT             NOT NULL,
    revenue_ils                 NUMERIC(12,2)   NOT NULL,
    unit_price_ils              NUMERIC(10,2),
    cost_ils                    NUMERIC(12,2),
    gross_margin_ils            NUMERIC(12,2),
    distributor_commission_ils  NUMERIC(12,2),
    -- Metadata
    is_return                   BOOLEAN         NOT NULL DEFAULT FALSE,
    is_attributed               BOOLEAN         NOT NULL DEFAULT TRUE,
    revenue_method              VARCHAR(20)     NOT NULL DEFAULT 'actual',
    -- Audit
    ingestion_batch_id          INT             NOT NULL REFERENCES ingestion_batches(id),
    source_row_ref              VARCHAR(100),
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_revenue_method
        CHECK (revenue_method IN ('actual', 'calculated', 'estimated'))
);

-- Primary query indexes (covering the four dashboard views)
CREATE INDEX idx_st_date         ON sales_transactions (year, month, transaction_date);
CREATE INDEX idx_st_product      ON sales_transactions (product_id);
CREATE INDEX idx_st_customer     ON sales_transactions (customer_id);
CREATE INDEX idx_st_salepoint    ON sales_transactions (sale_point_id) WHERE sale_point_id IS NOT NULL;
CREATE INDEX idx_st_distributor  ON sales_transactions (distributor_id);
CREATE INDEX idx_st_batch        ON sales_transactions (ingestion_batch_id);

-- BO main query: monthly totals by distributor and product
CREATE INDEX idx_st_bo_main
    ON sales_transactions (year, month, distributor_id, product_id);

-- CC main query: customer-level monthly aggregation
CREATE INDEX idx_st_cc_main
    ON sales_transactions (customer_id, year, month, product_id)
    WHERE customer_id IS NOT NULL;

-- SP main query: sale-point-level behavior
CREATE INDEX idx_st_sp_main
    ON sales_transactions (sale_point_id, year, month)
    WHERE sale_point_id IS NOT NULL;

COMMENT ON TABLE sales_transactions IS 'Unified transaction table. All parsed distributor data lands here. Negative units_sold = returns. revenue_method tracks actual (Icedream invoice) vs calculated (Ma''ayan units*price).';
COMMENT ON COLUMN sales_transactions.is_attributed IS 'FALSE when customer could not be mapped from branch name. Surfaces BO/CC gaps for investigation.';


-- ─────────────────────────────────────────────────────────────────────────────
-- LAYER 4: Inventory Snapshots
-- ─────────────────────────────────────────────────────────────────────────────

-- Table 9: inventory_snapshots
-- Point-in-time stock levels per distributor/warehouse location per product.
-- Sources: Karfree warehouse PDF reports, Icedream stock XLSX, Ma'ayan stock XLSX.

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

COMMENT ON TABLE inventory_snapshots IS 'Point-in-time inventory levels. One row per (distributor, product, date). Karfree warehouse uses source_type=warehouse; Icedream/Ma''ayan use source_type=distributor. Latest snapshot per distributor is the current stock level.';
COMMENT ON COLUMN inventory_snapshots.pallets IS 'Pallet count from warehouse reports (Karfree). NULL for distributor stock files.';
COMMENT ON COLUMN inventory_snapshots.cartons IS 'Carton count from distributor stock files. NULL for warehouse reports.';
COMMENT ON COLUMN inventory_snapshots.source_type IS 'warehouse = Karfree cold storage; distributor = Icedream/Ma''ayan stock files.';

COMMIT;
