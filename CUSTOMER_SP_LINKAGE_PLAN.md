# Phase 6 — Customer ↔ Sale Point Linkage Plan

**Status:** Planned
**Last updated:** 2026-04-20
**Owner:** or@raito.ai
**Depends on:** Phases 0–5 (complete), prod deployed

---

## TL;DR — The Vision

A sale point management system that lets the user attach sale points to customers, merge duplicate sale points (same physical store appearing under different names across distributors), and export/import SP assignments via Excel. The SP dashboard integrates directly — clicking a customer's SP count opens the SP tab filtered to that customer.

**Key constraint:** The same physical location can appear under different names in different distributor reports (e.g., "הולמס פלייס ר"א" in Icedream vs "Holmes Place TA" in Biscotti). The system must support alias grouping.

---

## Current State (audited 2026-04-20)

### What exists

| Component | Details |
|---|---|
| `sale_points` table | 1,469 rows, all have `customer_id` populated, 19 unique customers |
| Largest customer | Private Market (842 SPs), Paz Yellow (149), Wolt Market (74), Alonit (74) |
| Columns | id, customer_id, distributor_id, branch_name_he, branch_name_clean, city, region, geo fields, is_active, dates |
| Unique constraint | `(distributor_id, branch_name_he)` — same branch name can exist under different distributors |
| FK references | `sales_transactions.sale_point_id → sale_points.id` |
| SP dashboard | `salepoint_dashboard.py` — builds from in-memory parsed data, not from DB `sale_points` table directly |
| SP dedup | Already exists in `_extract()` (line 533–565) — merges same branch name across distributors at build time |
| Customer resolution | `extract_customer_name()` in `config.py` + `CUSTOMER_NAMES_EN`/`CUSTOMER_PREFIXES` in `registry.py` |
| Biscotti SP routing | Hardcoded `_BISCOTTI_SP_CUSTOMER` list in `salepoint_dashboard.py` (line 501–508) |

### What's missing

| Gap | Impact |
|---|---|
| No `canonical_sp_id` column | Can't group alias SPs (same physical store, different names) |
| No UI to reassign SP↔Customer | Every new customer (e.g., Holmes Place) requires code change in registry.py |
| No Excel export of SP↔Customer mapping | User can't review/edit assignments in bulk |
| SP dashboard not filterable by customer from MD tab | No cross-tab navigation |
| New customers not auto-detected | Holmes Place shows up in reports but isn't linked to a customer entity |

---

## Data Model Changes

### 1. New column on `sale_points`

```sql
ALTER TABLE sale_points ADD COLUMN canonical_sp_id INT REFERENCES sale_points(id);
CREATE INDEX idx_sp_canonical ON sale_points (canonical_sp_id) WHERE canonical_sp_id IS NOT NULL;
```

**Semantics:**
- `canonical_sp_id IS NULL` → this SP is a **canonical** record (the "real" physical location)
- `canonical_sp_id = X` → this SP is an **alias** of canonical SP `X` (same physical store, different name/distributor)

**Example:**
| id | branch_name_he | distributor | customer | canonical_sp_id |
|---|---|---|---|---|
| 101 | הולמס פלייס ר"א | Icedream | Holmes Place | NULL |
| 450 | Holmes Place TA North | Biscotti | Holmes Place | 101 |

### 2. New `customers` relational table alignment

The relational `customers` table (id-based) is the FK target for `sale_points.customer_id`. The MD tab `customers` JSONB entity uses text keys. These are currently separate — the ingestion pipeline populates the relational table, and the MD tab manages the JSONB.

**Decision needed (at implementation time):** Should the SP assignment UI work against the relational `customers.id` or the JSONB `customers.key`? Recommendation: keep using `customers.id` (relational FK) since `sale_points` already uses it. The UI resolves display names from either source.

---

## Implementation Phases

### Phase 6.0 — Price History Tracking

**Problem:** When a price is edited in the MD tab, the old value is overwritten. The audit log captures raw before/after JSON, but there's no structured price history or UI to view it.

**Solution:** Wire the MD tab pricing CRUD to the existing `price_history` relational table (SCD Type 2). Every price change auto-inserts a history record.

**Backend changes (`db_dashboard.py`):**
- On pricing **create**: insert row into `price_history` with `effective_from = today`, `effective_to = NULL`
- On pricing **update** (if `sale_price` or `cost` changed): close the old history row (`effective_to = today`), insert new row (`effective_from = today`)
- On pricing **delete**: close the history row (`effective_to = today`)
- New route: `GET /api/pricing/history?sku_key=X&customer=Y&distributor=Z` — returns price timeline for a specific pricing entry

**Frontend changes (`unified_dashboard.py`):**
- Small 📊 history icon on each pricing row in the MD tab
- Clicking it opens a popover/modal showing the price timeline: date range → sale price → cost → who changed it
- Timeline sorted newest-first

**Resolving product_id / customer_id / distributor_id:**
The `price_history` table uses integer FKs (`product_id`, `customer_id`, `distributor_id`). The MD tab pricing uses text keys (`sku_key`, `customer`, `distributor`). The backend must resolve text keys → integer IDs when writing to `price_history`. A helper function queries the relational `products`, `customers`, `distributors` tables to resolve.

**Files:** `scripts/db/db_dashboard.py`(API + history write hooks), `scripts/unified_dashboard.py` (history icon + popover)

---

### Phase 6.1 — DB Migration + Backend API

**DB migration script** (`scripts/db/migrate_sp_canonical.sql`):
```sql
ALTER TABLE sale_points ADD COLUMN IF NOT EXISTS canonical_sp_id INT REFERENCES sale_points(id);
CREATE INDEX IF NOT EXISTS idx_sp_canonical ON sale_points (canonical_sp_id) WHERE canonical_sp_id IS NOT NULL;
GRANT SELECT, INSERT, UPDATE, DELETE ON sale_points TO raito_app;
```

**New API routes in `db_dashboard.py`:**

| Route | Method | Purpose |
|---|---|---|
| `/api/salepoints` | GET | List all SPs with customer name, distributor name, canonical info. Supports `?customer_id=X` filter |
| `/api/salepoints/search` | GET | Search SPs by name pattern (`?q=הולמס`). Returns matching SPs with current assignment |
| `/api/salepoints/assign` | POST | Bulk assign SPs to a customer: `{sp_ids: [1,2,3], customer_id: 5}` |
| `/api/salepoints/merge` | POST | Merge alias SPs: `{canonical_id: 101, alias_ids: [450, 451]}` |
| `/api/salepoints/unmerge` | POST | Unlink an alias: `{sp_id: 450}` (sets `canonical_sp_id = NULL`) |
| `/api/salepoints/export` | GET | Download Excel: Customer → Canonical SP → Aliases. Supports `?customer_id=X` |
| `/api/salepoints/upload` | POST | Upload edited Excel to update assignments (customer_id + canonical_sp_id) |
| `/api/salepoints/stats` | GET | Summary: per-customer SP counts, unlinked count, alias count |

### Phase 6.2 — MD Tab UI (Customer → SP Management)

**Changes to `unified_dashboard.py` (Customers section):**

1. **SP count badge on each customer row** — clickable number showing "74 SPs" that links to SP dashboard filtered by that customer
2. **"Manage Sale Points" button per customer** — opens a modal:
   - Lists all SPs assigned to this customer (canonical + aliases)
   - Each canonical SP expandable to show its aliases
   - Search box: type a pattern, see matching **unlinked** SPs, checkbox to assign
   - "Merge" button: select 2+ SPs → pick canonical → others become aliases
   - "Unlink" button: remove an alias link or reassign to different customer
3. **"Unlinked Sale Points" section** — shows SPs with no customer assignment (if any exist)
4. **Quick-assign from search** — type "הולמס", see all matching SPs across all distributors, assign to Holmes Place in one click

**SP count in customer table columns:**
```
| Name HE | Name EN | Type | Distributor | Sale Points | Status | Contact |
                                           ^^^^^^^^^^^
                                           clickable badge
```

### Phase 6.3 — SP Dashboard Integration

**Changes to `salepoint_dashboard.py`:**

1. **Accept `?customer=X` URL parameter** — pre-filter the SP tab to show only that customer's sale points
2. **Show customer name column** in the SP detail table
3. **Canonical grouping view** — option to group by canonical SP, showing aliases as sub-rows with combined metrics
4. **Link back to MD tab** — "Edit assignments" link that opens the customer's SP management modal

**Cross-tab navigation flow:**
```
MD Tab → Customer row → "74 SPs" badge → SP Tab filtered to that customer
SP Tab → "Edit assignments" → MD Tab → Customer SP management modal
```

### Phase 6.4 — Excel Export/Import

**Export format** (`/api/salepoints/export`):

Sheet: "Sale Point Assignments"
| Column | Description |
|---|---|
| SP ID | `sale_points.id` (read-only) |
| Branch Name (HE) | `branch_name_he` (read-only) |
| Branch Name (Clean) | `branch_name_clean` |
| City | `city` |
| Distributor | distributor name (read-only) |
| Customer | customer name (editable — user changes this to reassign) |
| Customer ID | `customer_id` (auto-resolved from customer name on upload) |
| Canonical SP ID | `canonical_sp_id` (editable — user sets this to group aliases) |
| Canonical Branch Name | name of the canonical SP (for reference) |
| Is Active | `is_active` |
| Last Order | `last_order_date` |
| Total Units (all time) | aggregated from `sales_transactions` |

**Upload logic:**
1. Parse Excel
2. For each row, resolve customer name → `customer_id`
3. Update `customer_id` and `canonical_sp_id` on matching `sale_points.id`
4. Diff preview before committing (same pattern as MD bulk import)

### Phase 6.5 — QA & Deploy

1. Test on dev environment first
2. Run DB migration on dev (`raito_dev`)
3. Test all flows: search, assign, merge, export, import, cross-tab navigation
4. Deploy to prod: run migration on `raito`, merge dev → main, deploy

---

## Files to Modify

| File | Changes |
|---|---|
| `scripts/db/migrate_sp_canonical.sql` | NEW — DDL for `canonical_sp_id` column + indexes + permissions |
| `scripts/db/db_dashboard.py` | New API routes (Phase 6.1) |
| `scripts/unified_dashboard.py` | MD tab Customers section — SP count badge, management modal (Phase 6.2) |
| `scripts/salepoint_dashboard.py` | Customer filter param, canonical grouping, cross-tab links (Phase 6.3) |
| `scripts/db/md_excel_roundtrip.py` | SP export/import functions (Phase 6.4) |

---

## Edge Cases & Decisions

### 1. Holmes Place (the trigger case)
Holmes Place branches appear in Icedream reports but have no customer entity yet. Flow:
1. User creates "Holmes Place" customer in MD tab (Customers → + Add Customer)
2. User goes to "Manage Sale Points" for Holmes Place
3. Searches "הולמס" → sees matching unlinked SPs
4. Assigns them → done

### 2. Multi-distributor sale points
Same physical store buying from both Icedream and Biscotti (e.g., Wolt Market):
- Two separate SP records (one per distributor, different `branch_name_he`)
- Both assigned to same customer
- Can optionally be merged as aliases of one canonical SP
- Metrics aggregated across aliases in canonical view

### 3. "Private Market" (842 SPs)
These are small independent stores, each a unique physical location. They should NOT be merged — each is a separate canonical SP under the "Private Market" customer.

### 4. Reassignment
If a SP is reassigned from Customer A to Customer B:
- `UPDATE sale_points SET customer_id = B WHERE id = X`
- Historical `sales_transactions` still reference the SP, so revenue attribution follows the SP
- The audit log tracks the change

### 5. New SPs appearing in future uploads
The ingestion pipeline (`ingest_to_db.py`) creates new SP records on `ON CONFLICT DO NOTHING`. New SPs get `customer_id` from the parser's `extract_customer_name()`. If the customer is unknown, the SP gets assigned to a default/catch-all. The user can then reassign via the UI.

---

## Resume Checklist

1. ☐ Read this plan
2. ☐ Implement Phase 6.0 (price history tracking)
3. ☐ Run DB migration on dev (canonical_sp_id)
4. ☐ Implement Phase 6.1 (SP backend API)
5. ☐ Implement Phase 6.2 (MD tab SP UI)
6. ☐ Implement Phase 6.3 (SP dashboard integration)
7. ☐ Implement Phase 6.4 (Excel export/import)
8. ☐ QA on dev
9. ☐ Deploy to prod

---

_End of plan._
