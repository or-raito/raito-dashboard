# RAITO — SQL Schema Design & Migration Plan
*Senior System Architect Review Document*
*Prepared: 26 March 2026*

---

## Executive Summary

This document defines the PostgreSQL schema, migration strategy, and architectural
impact plan for RAITO's transition from a local Excel-based system to a cloud-native
Google Cloud SQL (PostgreSQL) environment. Every design decision is grounded in the
current SSOT engine logic, existing parser conventions, and the four functional module
requirements (BO, CC, SP, Sales Agents).

---

## Part 1 — SQL DDL: Schema Design

The schema is composed of **eight tables** across three logical layers:

```
Reference Layer:   manufacturers → distributors → products → customers → sale_points
Pricing Layer:     price_history
Transaction Layer: ingestion_batches → sales_transactions
```

The requested five tables (`products`, `customers`, `price_history`,
`sales_transactions`, `distributors`) are all defined below. Three supporting tables
(`manufacturers`, `sale_points`, `ingestion_batches`) are added because without them
the five core tables would contain orphaned foreign keys or unenforceable constraints.
They are lightweight and essential.

---

### Table 1 — `distributors`

Replaces the `DISTRIBUTORS` dict in `registry.py` and the commission constants
scattered across `config.py` and `cc_dashboard.py`.

```sql
CREATE TABLE distributors (
    id                  SERIAL          PRIMARY KEY,
    key                 VARCHAR(30)     NOT NULL UNIQUE,  -- 'icedreams', 'mayyan_froz', 'mayyan_amb', 'biscotti'
    name_en             VARCHAR(100)    NOT NULL,
    name_he             VARCHAR(100),
    commission_pct      NUMERIC(5,2)    NOT NULL DEFAULT 0.00,  -- e.g. 15.00 for Icedream
    report_format       VARCHAR(30),    -- 'monthly_xlsx', 'weekly_xlsx', 'weekly_xls_biff8', 'none'
    contact_name        VARCHAR(100),
    contact_email       VARCHAR(150),
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    notes               TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
```

**Design notes:**

- `commission_pct` lives here (not in `sales_transactions`) because it is a property
  of the distributor relationship, not of individual transactions. If Icedream's rate
  changes from 15% to 12%, a new row is not needed — this is a point-in-time
  renegotiation, not a per-transaction attribute. Future work: add a
  `commission_history` table if rate versioning is required.
- `report_format` is informational metadata for the ingestion pipeline — the parser
  selects the correct parsing strategy based on this value when pulling from the DB
  rather than hardcoding distributor keys in `parsers.py`.

---

### Table 2 — `manufacturers`

Lightweight supporting table required as a foreign key target for `products`.

```sql
CREATE TABLE manufacturers (
    id                  SERIAL          PRIMARY KEY,
    name                VARCHAR(100)    NOT NULL UNIQUE,  -- 'Vaniglia', 'Biscotti', 'Din Shiwuk'
    contact_email       VARCHAR(150),
    address             TEXT,
    lead_time_days      INT,
    moq_units           INT,            -- Minimum Order Quantity
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
```

---

### Table 3 — `products`

Replaces `registry.py`'s `PRODUCTS` dict, `PRODUCT_NAMES`, `PRODUCT_SHORT`,
`PRODUCT_STATUS`, `PRODUCTION_COST`, `SELLING_PRICE_B2B`, and the pack-size
constants used throughout `config.py` and `parsers.py`.

```sql
CREATE TABLE products (
    id                      SERIAL          PRIMARY KEY,
    sku_key                 VARCHAR(30)     NOT NULL UNIQUE,  -- 'chocolate', 'vanilla', 'dream_cake_2', etc.
    barcode                 VARCHAR(30)     UNIQUE,           -- GTIN, e.g. '7290020531032'
    full_name_en            VARCHAR(150)    NOT NULL,         -- 'Turbo Chocolate'
    full_name_he            VARCHAR(150),                     -- Hebrew SKU name as it appears in distributor files
    short_name              VARCHAR(50),                      -- 'Chocolate', 'Dream Cake'
    brand_key               VARCHAR(30)     NOT NULL,         -- 'turbo', 'danis', 'turbo_nuts', 'ahlan', 'w'
    manufacturer_id         INT             REFERENCES manufacturers(id),
    status                  VARCHAR(20)     NOT NULL DEFAULT 'active',  -- 'active', 'discontinued', 'planned'
    production_cost_ils     NUMERIC(10,2),                    -- ₪6.50 for Turbo ice cream
    b2b_list_price_ils      NUMERIC(10,2),                    -- Flat B2B price (replaces get_b2b_price())
    units_per_carton        INT,                              -- 10 for Turbo, 3 for Dream Cake, 6 for Vanilla
    units_per_pallet        INT,
    shelf_life_months       INT,
    storage_temp_celsius    VARCHAR(20),                      -- '-25°C', '0-4°C', '24°C'
    launched_at             DATE,
    discontinued_at         DATE,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_product_status CHECK (status IN ('active', 'discontinued', 'planned')),
    CONSTRAINT chk_b2b_price_positive CHECK (b2b_list_price_ils IS NULL OR b2b_list_price_ils >= 0)
);
```

**Design notes:**

- `sku_key` is the durable string identifier used throughout the application layer
  (e.g., `'chocolate'`, `'dream_cake_2'`). This is NOT the barcode — it is the
  internal semantic key that `classify_product()` resolves to. Both must be stored.
- `full_name_he` is the exact Hebrew string as it appears in distributor Excel files
  (e.g., `טורבו- גלידת שוקולד אגוזי לוז 250 * 10 יח'`). This field is what
  `classify_product()` uses for matching, so it must be kept in sync with the actual
  distributor file vocabulary.
- `units_per_carton` replaces `extract_units_per_carton()` for known SKUs. The
  function still runs as a fallback for unrecognized strings, but registered products
  should always resolve from this field.
- `b2b_list_price_ils` replaces `get_b2b_price()` for the flat-rate SP/BO path.
  Per-customer negotiated prices live in `price_history`.

---

### Table 4 — `customers`

Replaces `CUSTOMER_NAMES_EN`, `CUSTOMER_PREFIXES`, and `_CC_CUSTOMER_META` in
`registry.py` and `cc_dashboard.py`. This is the **chain/network level** entity
(AMPM, Alonit, Wolt Market) — not the branch level.

```sql
CREATE TABLE customers (
    id                  SERIAL          PRIMARY KEY,
    name_en             VARCHAR(100)    NOT NULL UNIQUE,   -- 'AMPM', 'Wolt Market', 'Dominos Pizza'
    name_he             VARCHAR(100),                      -- 'דור אלון AM:PM', 'וולט מרקט'
    name_he_aliases     TEXT[],                            -- Array of alternate Hebrew spellings from raw reports
    primary_distributor_id  INT         REFERENCES distributors(id),
    customer_type       VARCHAR(30)     NOT NULL DEFAULT 'chain',  -- 'chain', 'independent', 'wholesale'
    cc_tracked          BOOLEAN         NOT NULL DEFAULT FALSE,    -- TRUE for the ~18 CC customers
    dist_commission_override NUMERIC(5,2),  -- NULL = use distributor default
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    first_order_date    DATE,
    notes               TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_customer_type CHECK (customer_type IN ('chain', 'independent', 'wholesale'))
);
```

**Design notes:**

- `name_he_aliases` (a PostgreSQL text array) solves the long-standing spelling
  normalization problem. All variants of `פז יילו` / `פז ילו` / `פז  ילו` are stored
  here, and the ingestion pipeline matches on this array rather than requiring a
  hardcoded `_MAAYAN_CHAIN_NORM` dict. This replaces `_ICE_CHAIN_PREFIXES`,
  `_MAAYAN_CHAIN_NORM`, and the chain-split logic in `extract_chain_name()`.
- `cc_tracked` is a simple boolean gate for the CC dashboard's ~18-customer scope.
  This replaces the hardcoded customer list in `_CC_CUSTOMER_META`.
- `dist_commission_override` allows a per-customer commission rate (e.g., if Biscotti
  negotiates a different rate for one customer) without modifying the distributor row.

---

### Table 5 — `sale_points`

The micro-tier entity (1,200+ branches). This is new as a first-class SQL citizen —
currently derived dynamically in `salepoint_dashboard.py` from raw branch strings.

```sql
CREATE TABLE sale_points (
    id                  SERIAL          PRIMARY KEY,
    customer_id         INT             NOT NULL REFERENCES customers(id),
    distributor_id      INT             NOT NULL REFERENCES distributors(id),
    branch_name_he      VARCHAR(200)    NOT NULL,           -- Raw Hebrew branch name from distributor report
    branch_name_clean   VARCHAR(200),                       -- Normalized version, human-readable
    city                VARCHAR(100),
    region              VARCHAR(50),
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    first_order_date    DATE,
    last_order_date     DATE,           -- Updated by ingestion pipeline on each new transaction
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    UNIQUE (distributor_id, branch_name_he)  -- prevents duplicate sale points from the same distributor
);
```

**Design notes:**

- The `UNIQUE (distributor_id, branch_name_he)` constraint is the critical
  deduplication guard. The ingestion pipeline can safely `INSERT ... ON CONFLICT DO
  NOTHING` to auto-register new branches without risk of creating duplicates.
- `last_order_date` is maintained by the pipeline and drives the SP status taxonomy
  (Active / Reactivated / Mar gap / Churned) in `business_logic.py`.

---

### Table 6 — `price_history`

The Date-Aware Pricing table. This is the most architecturally significant new table —
it replaces the flat lookup in `pricing_engine.py` and is the foundation of the
"Price Versioning" roadmap item.

```sql
CREATE TABLE price_history (
    id                      SERIAL          PRIMARY KEY,
    product_id              INT             NOT NULL REFERENCES products(id),
    customer_id             INT             REFERENCES customers(id),    -- NULL = applies to all customers (B2B list price)
    distributor_id          INT             REFERENCES distributors(id), -- NULL = applies regardless of distributor
    price_ils               NUMERIC(10,2)   NOT NULL,
    effective_from          DATE            NOT NULL,
    effective_to            DATE,           -- NULL = currently active (open-ended)
    price_type              VARCHAR(20)     NOT NULL DEFAULT 'b2b_list', -- 'b2b_list', 'negotiated', 'fallback'
    source_reference        VARCHAR(200),   -- e.g. 'price db - 24.2.xlsx', 'contract_amendment_mar2026'
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Only one active price per product+customer+distributor combination at any point in time
    CONSTRAINT chk_date_range CHECK (effective_to IS NULL OR effective_to > effective_from),
    CONSTRAINT chk_price_positive CHECK (price_ils > 0),
    CONSTRAINT chk_price_type CHECK (price_type IN ('b2b_list', 'negotiated', 'fallback'))
);

-- Index for the hot query path: "what is the price for product X for customer Y on date D?"
CREATE INDEX idx_price_history_lookup
    ON price_history (product_id, customer_id, distributor_id, effective_from, effective_to);
```

**Design notes on the pricing lookup pattern:**

The application layer queries this table as:

```sql
SELECT price_ils FROM price_history
WHERE product_id = $1
  AND (customer_id = $2 OR customer_id IS NULL)
  AND (distributor_id = $3 OR distributor_id IS NULL)
  AND effective_from <= $4          -- $4 = transaction_date
  AND (effective_to IS NULL OR effective_to > $4)
ORDER BY
  (customer_id IS NOT NULL) DESC,   -- customer-specific price wins over NULL (generic)
  (distributor_id IS NOT NULL) DESC -- distributor-specific wins over NULL
LIMIT 1;
```

This is the SQL equivalent of `pricing_engine.get_customer_price()` cascading to
`get_b2b_price()` — the most specific non-null match wins.

**Retroactive integrity guarantee:** Because price records are immutable once
`effective_to` is set, re-parsing January 2026 data after a March 2026 price change
will still resolve to the January price. This is the core promise of Date-Aware
Pricing and the primary reason this table design was chosen over a simple price column
on the `products` table.

---

### Table 7 — `ingestion_batches`

Audit and deduplication control table. Every file upload creates one row here before
any transaction rows are written.

```sql
CREATE TABLE ingestion_batches (
    id                  SERIAL          PRIMARY KEY,
    source_file_name    VARCHAR(300)    NOT NULL,
    distributor_id      INT             NOT NULL REFERENCES distributors(id),
    file_format         VARCHAR(30),    -- 'format_a_xlsx', 'format_b_xls_biff8', 'weekly_xlsx'
    reporting_period    VARCHAR(20),    -- 'W12', 'FEB26', 'MAR26_W10_W11'
    record_count        INT,            -- Number of transaction rows loaded
    status              VARCHAR(20)     NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'complete', 'failed'
    uploaded_by         VARCHAR(100),   -- User or process that triggered ingestion
    upload_timestamp    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    error_message       TEXT,           -- Populated on failure

    CONSTRAINT chk_batch_status CHECK (status IN ('pending', 'processing', 'complete', 'failed'))
);
```

---

### Table 8 — `sales_transactions`

The unified landing table for all parsed distributor data. This is the heart of the
schema — all BO, CC, and SP queries ultimately run against this table.

```sql
CREATE TABLE sales_transactions (
    id                      BIGSERIAL       PRIMARY KEY,
    -- Time dimensions
    transaction_date        DATE            NOT NULL,  -- Exact date when known; week start date otherwise
    week_number             SMALLINT,                  -- ISO week number, e.g. 12
    year                    SMALLINT        NOT NULL,
    month                   SMALLINT        NOT NULL,  -- 1-12
    -- Product & distribution
    product_id              INT             NOT NULL REFERENCES products(id),
    distributor_id          INT             NOT NULL REFERENCES distributors(id),
    customer_id             INT             REFERENCES customers(id),    -- NULL if customer not yet mapped
    sale_point_id           INT             REFERENCES sale_points(id),  -- NULL for aggregated rows
    -- Quantities & financials
    units_sold              INT             NOT NULL,       -- Negative = return/credit note
    revenue_ils             NUMERIC(12,2)   NOT NULL,       -- Actual invoice value (Icedream) or calculated (Ma'ayan)
    unit_price_ils          NUMERIC(10,2),                  -- Derived: revenue_ils / units_sold (NULL if units=0)
    cost_ils                NUMERIC(12,2),                  -- production_cost × units (computed at ingest time)
    gross_margin_ils        NUMERIC(12,2),                  -- revenue - cost (computed at ingest time)
    distributor_commission_ils NUMERIC(12,2),               -- revenue × commission_pct (computed at ingest time)
    -- Flags
    is_return               BOOLEAN         NOT NULL DEFAULT FALSE,
    is_attributed           BOOLEAN         NOT NULL DEFAULT TRUE,  -- FALSE if customer could not be mapped
    revenue_method          VARCHAR(20)     NOT NULL DEFAULT 'actual',  -- 'actual', 'calculated', 'estimated'
    -- Audit
    ingestion_batch_id      INT             NOT NULL REFERENCES ingestion_batches(id),
    source_row_ref          VARCHAR(100),   -- Row identifier in source file for traceability
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Primary query indexes
CREATE INDEX idx_st_date      ON sales_transactions (transaction_date, year, month);
CREATE INDEX idx_st_product   ON sales_transactions (product_id);
CREATE INDEX idx_st_customer  ON sales_transactions (customer_id);
CREATE INDEX idx_st_salepoint ON sales_transactions (sale_point_id);
CREATE INDEX idx_st_dist      ON sales_transactions (distributor_id);
CREATE INDEX idx_st_batch     ON sales_transactions (ingestion_batch_id);
-- Composite index for the most common BO query (date + distributor filter)
CREATE INDEX idx_st_bo_main   ON sales_transactions (year, month, distributor_id, product_id);
```

**Design notes:**

- `revenue_method` ('actual', 'calculated', 'estimated') preserves the current
  distinction between Icedream invoice values and Ma'ayan calculated values. This is
  critical for data quality reporting — the BO dashboard can flag when a month's
  revenue is fully actual vs. partially estimated.
- Pre-computed margin columns (`cost_ils`, `gross_margin_ils`,
  `distributor_commission_ils`) are stored at ingest time rather than derived at query
  time. For a table that will grow to millions of rows across 1,200+ sale points and
  weekly data, materializing these avoids repeated joins to `products` and
  `distributors` on every dashboard load.
- `is_attributed` (FALSE when `customer_id` is NULL) makes the historical data
  integrity problem explicit. In the current Excel system, unattributed March
  transactions silently inflated BO totals without appearing in CC. This column makes
  the discrepancy queryable: `WHERE is_attributed = FALSE` immediately surfaces the
  problem for investigation.
- `BIGSERIAL` for the primary key anticipates a large row count: at the current rate
  (~1,200 sale points × 5 products × 52 weeks × multiple distributors), the table
  will reach 300K–500K rows per year. BIGINT is the correct choice for long-term
  stability.

---

## Part 2 — Migration Strategy

The migration is structured as four sequential phases, each independently verifiable
before the next begins.

---

### Phase 0 — Environment Setup (1–2 days)

Provision a Google Cloud SQL PostgreSQL instance. Create the schema using the DDL
above. Establish a read-only connection from the local Python environment
(`scripts/`) so that the existing dashboard pipeline can be tested against the DB
alongside the current Excel flow before any cutover.

No data is moved in this phase. The goal is a running, empty database and a confirmed
connection from the local scripts.

---

### Phase 1 — Reference Data Migration (1 day)

Migrate the stable lookup tables first, in dependency order:

1. **`manufacturers`** — 3 rows (Vaniglia, Biscotti, Biscotti-archived Piece of Cake).
   Source: `RAITO_BRIEFING.md` manufacturers table + `Raito_Master_Data.xlsx`.

2. **`distributors`** — 4 rows (Icedream, Ma'ayan Frozen, Ma'ayan Ambient, Biscotti).
   Source: `DISTRIBUTORS` dict in `registry.py`.

3. **`products`** — 7 rows (all current + discontinued SKUs).
   Source: `PRODUCTS` dict in `registry.py` + `config.py` constants.

4. **`customers`** — ~20 rows (all CC customers + top SP chains).
   Source: `CUSTOMER_NAMES_EN` in `registry.py` + `Raito_Master_Data_export.xlsx`
   Customers sheet. Populate `name_he_aliases` from the union of all known variant
   spellings found in `_ICE_CHAIN_PREFIXES`, `_MAAYAN_CHAIN_NORM`, and the Ma'ayan
   sub-brand split rules.

5. **`price_history`** — Initial rows from `price db - 24.2.xlsx`.
   Use `effective_from = 2025-12-01` (launch date) and `effective_to = NULL` for all
   current prices. This establishes the pricing baseline. Future price changes will
   `UPDATE effective_to = change_date` on the old row and `INSERT` a new row — the
   old price is never deleted.

**Validation gate for Phase 1:** Run a simple query to confirm all 7 product SKU keys
and all 20 customer English names are present and match the current Python registry.
No dashboard changes yet.

---

### Phase 2 — Historical Transaction Migration (3–5 days)

Run the existing parsers in a special "migration mode" that writes to the database
instead of returning Python dicts. Process files in chronological order:

```
December 2025:   ICEDREAM- DECEMBER.xlsx  +  Mayyan_Turbo.xlsx (Dec rows)
January 2026:    icedream - January.xlsx  +  Mayyan_Turbo.xlsx (Jan rows)
February 2026:   ice_feb_full.xlsx        +  maay_feb_full.xlsx
March 2026 W10:  sales_week_12.xls (cols 2-3)  +  maayan_sales_week_10_11.xlsx (W10)
March 2026 W11:  sales_week_12.xls (cols 4-5)  +  maayan_sales_week_10_11.xlsx (W11)
March 2026 W12:  sales_week_12.xls (cols 6-7)  +  icedream_mar_w12.xlsx
```

Each file creates one `ingestion_batches` row before any transactions are written.
If the batch fails mid-way, all its rows can be deleted by `ingestion_batch_id` and
the file re-processed cleanly.

**Validation gate for Phase 2:** Run SQL aggregations and compare against the
confirmed dashboard totals from `RAITO_BRIEFING.md` §"Current Data State":

| Month     | Expected Units | Expected Revenue (₪) |
|-----------|---------------|----------------------|
| Dec '25   | 83,753        | 1,559,374            |
| Jan '26   | 51,131        | 1,092,105            |
| Feb '26   | 58,331        | 1,084,381            |
| Mar '26   | 19,610        | 379,155              |

Any discrepancy above ₪10 (the current known rounding residual) is a parsing bug
that must be resolved before Phase 3 begins. This is the single most important
validation checkpoint in the entire migration.

---

### Phase 3 — Dual-Run Period (2–3 weeks)

Run both pipelines in parallel: the existing Excel-based system continues as the
production source, while a shadow SQL pipeline ingests the same data. Each week's
new data (W13, W14, etc.) is processed through both paths, and the outputs are
compared.

During this phase:
- The dashboard is still generated from the Python dicts (existing flow).
- A new `db_dashboard.py` shadow script generates the same KPIs from SQL queries.
- Any gap between the two outputs triggers investigation and a parser fix before
  Phase 4.

This phase ends only when two consecutive weeks show zero discrepancy between the
Excel and SQL pipelines.

---

### Phase 4 — SQL Cutover (1 day)

Modify `parsers.py` and `unified_dashboard.py` to read from the SQL database as the
primary source. The Excel files become an archive/backup source only (they are never
deleted — they remain in `data/` as the audit trail and fallback).

Specifically:
- `consolidate_data()` is replaced by `consolidate_data_from_db()` which runs SQL
  aggregation queries and returns an identically shaped Python dict. The rest of the
  dashboard pipeline (`dashboard.py`, `cc_dashboard.py`, `salepoint_dashboard.py`)
  requires zero changes — they still receive and process the same data structure.
- `parsers.py` retains its parsing functions but its primary role shifts to ETL: parse
  → validate → write to `sales_transactions` → return confirmation.

---

## Part 3 — Architectural Impact

### `parsers.py` — Evolution into an ETL Pipeline

Current role: parse Excel files → return Python dicts held in memory for the duration
of one `unified_dashboard.py` run.

New role (post-Phase 4): a persistent ETL pipeline.

**What changes:**
- Each parser function (`parse_icedreams_file`, `parse_mayyan_file`, etc.) gains a
  `db_conn` parameter. When provided, parsed rows are written to `sales_transactions`
  instead of being returned as dicts.
- `consolidate_data()` is split into two functions: `ingest_file(filepath, db_conn)`
  (ETL path) and `consolidate_data_from_db(db_conn, filters)` (read path for
  dashboards).
- The `ingestion_batches` table provides built-in idempotency: before processing a
  file, the pipeline checks if a batch with the same `source_file_name` and
  `status='complete'` already exists. If so, it skips the file. This is the SQL
  equivalent of the current manual "archive" convention for old partial files.
- The `_MAAYAN_CHAIN_TO_PRICEDB`, `_ICE_CHAIN_PREFIXES`, and `_MAAYAN_CHAIN_NORM`
  hardcoded dicts in `parsers.py` are replaced by a query against `customers` on
  `name_he_aliases`. This is a significant simplification — adding a new chain name
  variant no longer requires a code change, only a DB record update.

**What does not change:**
- All parsing logic for Format A (`.xlsx`) and Format B (`.xls` BIFF8) Icedream files.
- The `sign * -1` returns handling.
- The `classify_product()` matching logic (though it begins querying `products.sku_key`
  from the DB rather than from `config.py`).
- The Ma'ayan per-row pricing via `_mayyan_chain_price()`.

---

### `pricing_engine.py` — SQL-Backed Two-Tier API

Current role: in-memory price lookup from static Python dicts, loaded from
`price db - 24.2.xlsx` at module import time.

New role: a thin API layer over the `price_history` table.

**What changes:**
- `get_b2b_price(sku)` becomes a query:
  `SELECT price_ils FROM price_history WHERE product_id = ? AND customer_id IS NULL
   AND effective_from <= NOW() AND (effective_to IS NULL OR effective_to > NOW())`
- `get_customer_price(sku, customer_en)` queries with a `customer_id` join, falling
  back to `customer_id IS NULL` if no negotiated price exists. This is the exact
  cascade the current function implements, now enforced by SQL priority ordering.
- `load_mayyan_price_table()` is retired. Its data lives in `price_history` with
  `distributor_id = [Ma'ayan id]` rows.
- `get_mayyan_chain_price(price_table, chain_raw, sku)` is replaced by the standard
  `get_customer_price()` path — because Ma'ayan chains are now first-class `customers`
  records, the special-case function is no longer needed.
- `js_brand_rev_function()` (the JS code-gen helper for SP brand filter prices) is
  updated to query current prices from the DB at dashboard build time rather than
  reading from hardcoded Python dicts. The generated JS output is identical.

**What does not change:**
- The two-tier API surface (`get_b2b_price`, `get_customer_price`) — all callers
  in `salepoint_dashboard.py`, `salepoint_excel.py`, and `cc_dashboard.py` remain
  unchanged.
- The fallback-to-B2B cascade behavior.
- The `KeyError` on unknown SKU semantics (now a `NOT FOUND` exception from the query
  layer).

---

### `registry.py` — Thin Compatibility Shim

Current role: the in-memory product catalog and customer name mapping (SSOT for
`PRODUCTS`, `CUSTOMER_NAMES_EN`, etc.).

New role (post-Phase 4): a compatibility shim that loads its constants from the DB at
startup rather than defining them statically. The public API (`PRODUCTS`, `BRANDS`,
`CUSTOMER_NAMES_EN`, `validate_sku()`, `get_brand_skus()`) remains identical.

This means zero changes are required in any caller of `registry.py`. The migration
is transparent to `dashboard.py`, `cc_dashboard.py`, `salepoint_dashboard.py`, and
`salepoint_excel.py`.

---

### Dashboard Generators — Zero Changes Required

`dashboard.py`, `cc_dashboard.py`, `salepoint_dashboard.py`, and `unified_dashboard.py`
all receive a Python dict from `consolidate_data()`. As long as
`consolidate_data_from_db()` returns an identically shaped dict, none of these files
require modification during the SQL cutover. This is the key architectural benefit of
the current SSOT design — the data layer and the presentation layer are already
cleanly separated.

---

## Appendix: Key Design Decisions & Rationale

| Decision | Rationale |
|---|---|
| Store pre-computed margin columns in `sales_transactions` | Avoids repeated joins at query time across a large table. Trade-off: slightly more storage, significantly faster dashboard loads. |
| `name_he_aliases` as a PostgreSQL text array | Eliminates hardcoded normalization dicts. New spelling variants are a DB update, not a code change. |
| `is_attributed` boolean on transactions | Makes the current BO/CC attribution gap queryable and auditable rather than silently hidden. |
| `effective_to = NULL` for open-ended prices | Standard SCD Type 2 pattern. Avoids date-range overlap bugs from using `effective_to = '9999-12-31'`. |
| `ingestion_batches` as a separate table | Provides clean rollback semantics — a failed batch is a single `DELETE WHERE batch_id = ?` away from being re-runnable. |
| `revenue_method` enum on transactions | Preserves the Icedream (actual) vs. Ma'ayan (calculated) revenue distinction for data quality reporting. |
| `sale_points.UNIQUE(distributor_id, branch_name_he)` | Enables idempotent `INSERT ... ON CONFLICT DO NOTHING` for auto-registration of new branches during ingestion. |

---

*End of Document*
*For questions or review, reference `RAITO_BRIEFING.md` decisions #93–97 (Phase 1–4 SSOT refactor)*
