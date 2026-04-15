# Raito Project — Architecture & Code

> **When to load:** Dashboard changes, code work, build pipeline, DB schema, deploy commands.

---

## Data Structure

### Folder Layout (in project directory)

```
data/
  icedreams/       ← Icedream monthly/weekly sales reports (.xlsx)
  mayyan/          ← Ma'ayan monthly/weekly sales reports (.xlsx)
  biscotti/        ← Biscotti sales reports (future — stub parser ready)
  karfree/         ← Karfree warehouse inventory reports (.pdf, sorted by mtime)
  price data/      ← B2B price DB per customer (.xlsx)
  production/      ← Production data (future)
  Din Shiwuk/      ← Din Shiwuk item setup forms (future, not parsed yet)
  master data/     ← Raito_Master_Data.xlsx — master source (Portfolio + Config always from here)
                   Raito_Master_Data_export.xlsx — user-edited export (7 sheets; primary data source when present)

docs/              ← Dashboard outputs (dashboard.html, .xlsx reports, briefing)
dashboards/        ← Sales Dashboard (separate system)
scripts/           ← All code (config, parsers, dashboard, reports)
  insights_data.py   → Extracts all Raito data into JSON (monthly + weekly, WoW deltas, highlights)
  weekly_deck.js     → Node.js PptxGenJS script — reads JSON from stdin, writes .pptx
archive/           ← Old dashboards, reports, one-time analyses
docs/
  raito_weekly_insights.pptx  ← Weekly insights deck output (regenerated each week)
CLAUDE.md          ← Auto-loaded project context (short orientation + key rules, points here)
.claude/commands/  ← Custom slash commands:
  update-week.md     → /project:update-week [N]  — full weekly update checklist
  validate-week.md   → /project:validate-week [N] — parse & validate only, no edits
  insights.md        → /project:insights          — generate weekly insights .pptx deck
```

### Current Source Files

| Month | Icedream Sales | Ma'ayan Sales |
|---|---|---|
| December 2025 | `data/icedreams/ICEDREAM- DECEMBER.xlsx` | `data/mayyan/Mayyan_Turbo.xlsx` (multi-month, monthly format with חודש column) |
| January 2026 | `data/icedreams/icedream - January.xlsx` (individual branches, 573 rows) | `data/mayyan/Mayyan_Turbo.xlsx` |
| **February 2026** | **`data/icedreams/ice_feb_full.xlsx`** | **`data/mayyan/maay_feb_full.xlsx`** (weekly format, no חודש column — uses שבועי) |
| **March 2026 (W10-W12)** | **`data/icedreams/sales_week_12.xls`** (Format B weekly XLS, OLE2/BIFF8, created 19/3 by Rozit Israel — authoritative W10-W12 source). W12 extracted to `icedream_mar_w12.xlsx` (Format A). Also `icedream_15_3` (W10+W11) and `icedream_mar_w10_11.xlsx` (branch-level detail). | **`data/mayyan/maayan_sales_week_10_11.xlsx`** (weekly format, week numbers 10-11, auto-mapped to March) |

> ⚠️ Old partial Feb files are archived in `data/icedreams/_archive/`. Do NOT use.
> ⚠️ `icefream - January - CUSTOMERS .xlsx` was a duplicate — archived. Only `icedream - January.xlsx` should be used.

**Key insight about icedream Feb file format:**
The file title says "מכירות לעוגיפלצת חודשי לפי רשתות" — "עוגיפלצת" here refers to the **product brand**, not the customer. Each block is `סה"כ עוגיפלצת` + col2 = customer name. When col2 is None → the customer IS "עוגיפלצת" (the store chain).

### Inventory Files

| Location | File | Date |
|---|---|---|
| Karfree warehouse | `data/karfree/stock_24_3.pdf` (latest by mtime) | 24/03/2026 |
| Icedream distributor | `data/icedreams/icedream_stock_15.3.xlsx` (latest by mtime) | 15/03/2026 |
| Ma'ayan distributor | `data/mayyan/maayan_stock_15_3` (latest by mtime) | 15/03/2026 |

### Naming Convention (preferred for new files)

- `icedream_sales_FEB26.xlsx`
- `maayan_sales_FEB26.xlsx`
- `karfree_stock_23FEB26.pdf`

Avoid: Hebrew filenames, spaces, missing extensions, date formats like `19:2`.

---

## Code Architecture

All scripts in `scripts/` directory:

| File | Role |
|---|---|
| **SSOT Engines (Phase 1 — March 2026 Refactor)** | |
| `pricing_engine.py` | **Pricing SSOT** — All price lookups. Two-tier API: `get_b2b_price(sku)` for SP/BO, `get_customer_price(sku, customer)` for CC. Also: Ma'ayan price-DB integration (`load_mayyan_price_table`, `get_mayyan_chain_price`), JS code-gen helpers for injecting prices into templates. No other module may hardcode prices. |
| `business_logic.py` | **Status & Trend SSOT** — Canonical `compute_status(dec,jan,feb,mar)` and `compute_trend(dec,jan,feb,mar)`. Option A design: pre-computed in Python, JS receives values in JSON (no JS-side logic). Also: `compute_ordering_pattern`, `enrich_salepoint` batch helper. |
| `registry.py` | **Product & Customer Registry** — Product catalog (`PRODUCTS` dict of `Product` objects), brand memberships (`BRANDS`), distributor metadata (`DISTRIBUTORS`), customer hierarchy (`CUSTOMER_NAMES_EN`, `CUSTOMER_PREFIXES`). Validation: `validate_sku()` raises on unknown SKUs. Prepared for future SQL migration. |
| **Core Modules** | |
| `config.py` | System settings (paths, months, formatting), `classify_product()`, `extract_chain_name()` (delegates customer mapping to `registry.py`). Re-exports `CHAIN_NAMES_EN` for backward compat. |
| `parsers.py` | All file parsers (Icedream, Ma'ayan, Biscotti, Karfree, distributor stock) + `consolidate_data()` |
| `master_data_parser.py` | Parses Master Data Excel into structured dicts. Auto-detects export vs original format. Two-file strategy: export for 7 sheets, original for Portfolio + Config. |
| **Dashboard Generators** | |
| `dashboard.py` | BO tab content generator — KPI cards, SVG charts (revenue, units, flavor), donut charts, tables. All inline HTML with styles. |
| `unified_dashboard.py` | **Main dashboard generator** — combines BO + CC + SP + MD tabs into single HTML. Sidebar nav, CSS theming, CC tab processing, password gate. Injects B2B prices from `pricing_engine` into SP Excel export JS. Run this to regenerate. |
| `cc_dashboard.py` | CC tab generator — fully dynamic. `build_cc_tab(data)` accepts the shared `data` dict (same object as BO). All customer revenue/units/margins computed dynamically from parsed files — zero hardcoded price literals or static customer totals. Single pipeline complete (25 Mar 2026). |
| `salepoint_dashboard.py` | **Sale Points tab generator** — builds SP HTML tab. Uses `pricing_engine` for all revenue calculations and `business_logic.enrich_salepoint` for pre-computed status/trend (Option A). Includes brand filter with engine-injected prices. |
| `salepoint_excel.py` | **Sale Points Excel export** → `docs/sale_points_deep_dive.xlsx`. Uses `pricing_engine.get_b2b_price_safe` and delegates status/trend to `business_logic` (SSOT). Per-customer-group sheets with dark navy headers, alternating row fills. |
| **Geo Analysis Tab** | |
| `geo_dashboard.py` | **GEO tab generator** — builds the Geo Analysis HTML tab. Google Maps with choropleth, two boundary layers (District from `municipalities_geo`, City from `cities_geo`), POS drill-down, inline address editing, CSV export/upload. All JS inline in Python f-strings (use `\\x27` for JS single quotes, not `\'`). |
| `geo_api.py` | **GEO Flask API** — Blueprint at `/api/geo/*`. Endpoints: `/municipalities` (district GeoJSON), `/cities` (city GeoJSON, simplified via `ST_Simplify`), `/choropleth` + `/choropleth-city` (KPI aggregation), `/pos` (POS drill-down, supports `layer=district\|city`), `/export-addresses` (CSV), `/upload-addresses` (bulk CSV import + re-geocode), `/update-pos` (inline edit). Distributor filtering uses DB subquery (`WHERE key LIKE %s`) not hardcoded IDs. |
| `fetch_city_boundaries.py` | **One-time script** — downloads 429 Israeli city/town boundary polygons from GitHub (`idoivri/israel-municipalities-polygons`), creates `cities_geo` table with PostGIS geometry, links cities to districts via `ST_Within(centroid, district.geom)`. Run via Cloud Shell against Cloud SQL. |
| **Other** | |
| `excel_report.py` | Excel summary generator → `docs/supply_chain_summary.xlsx` |
| `excel_dashboard.py` | Full Excel dashboard → `docs/Raito_Business_Overview.xlsx` |
| `process_data.py` | Orchestrator for old standalone dashboard (less used now) |

### Key Functions

**pricing_engine.py (SSOT):**
- `get_b2b_price(sku)` — Flat B2B list price. Raises `KeyError` on unknown SKU (catches silent failures).
- `get_b2b_price_safe(sku, fallback=0.0)` — Safe variant, returns fallback instead of raising.
- `get_customer_price(sku, customer_en)` — Negotiated per-customer price for CC. Falls back to B2B.
- `load_mayyan_price_table()` → `{product: {chain: price}}` from latest price DB Excel. Cached.
- `get_mayyan_chain_price(price_table, chain_raw, sku)` — Invoiced price for Ma'ayan chain+product.
- `js_brand_rev_function()` — Generates JS `spBrandRev()` with engine-sourced prices.

**business_logic.py (SSOT):**
- `compute_status(dec, jan, feb, mar)` → `'Active'|'New'|'No Mar order'|'Churned'`
- `compute_trend(dec, jan, feb, mar)` → integer % or `None`. Last two consecutive non-zero months.
- `compute_trend_fraction(dec, feb)` → float fraction for Excel formatting.
- `enrich_salepoint(sp_dict)` — Batch helper: adds `status`, `trend`, `months_active` to a sale-point dict.

**registry.py:**
- `PRODUCTS` — `dict[str, Product]` with all 7 SKUs. Product objects have `.brand`, `.status`, `.is_turbo()`, etc.
- `CUSTOMER_NAMES_EN` — Hebrew→English customer name mapping (canonical source for config.CHAIN_NAMES_EN).
- `validate_sku(sku)` — Raises `KeyError` on unknown SKU. Call at data-ingestion boundaries.
- `get_brand_skus(brand)` — Returns SKU list for a brand filter ('turbo', 'danis', 'ab').

**config.py:**
- `classify_product(name)` — Hebrew SKU name → product key. Excludes באגסו and דובאי.
- `extract_chain_name(customer_name, source_chain=None)` — Branch name → customer name with all splits/normalizations, then translates to English via `CUSTOMER_NAMES_EN` (from registry.py). `source_chain` is used for Ma'ayan accounts to fall back to customer name when account doesn't match patterns.
- `extract_units_per_carton(name)` — Extracts multiplier from SKU name (e.g., "* 10 יח'" → 10)
- `compute_kpis(data, month_list, filter_products=None)` — Returns `(tu, tr, tc, tgm, tmy, tic, tbi, mp, ip, bp)` — total units/revenue/cost/margin, per-distributor units (Ma'ayan/Icedream/Biscotti), and percentage splits.

**dashboard.py:**
- `_build_svg_timeline_chart(…, show_mom=False)` — Smooth bezier curve SVG chart with gradient fill, value labels on dots, no grid lines. When `show_mom=True`, renders per-month MoM % change below each x-axis label (green/red). Revenue and Units charts both use `show_mom=True`. Overall trend badge removed from chart header.
- `_smooth_path(points)` — Generates cubic bezier SVG path from data points (30% control point offsets).
- `_build_flavor_analysis()` — Donut chart (SVG) with hover tooltips showing % share, legend, and "By Distributor" breakdown table. Uses `FLAVOR_COLORS` for natural flavor colors.
- Tables (Detailed Summary, Icedream Customers, Ma'ayan Chains) show top 10 rows with "Show More" toggle button.
- **Warehouse Inventory KPI cube** — Shows total units (big number) + per-flavor breakdown below (colored dot + EN name + units + % share). Uses `FLAVOR_COLORS` and `PRODUCT_NAMES`.
- **Creators KPI cube** — Shows creator count + total SKUs, then 2-column grid of brand cards separated by a vertical divider line. Each column: brand name (bold) + creator name + colored SKU dots with full EN names (`PRODUCT_NAMES`).
- **Total Revenue / Units Sold KPI cards** — MoM trend badge removed; shows "all time" label instead.

**master_data_parser.py:**
- `parse_master_data()` — Returns dict with keys: `brands`, `products`, `manufacturers`, `distributors`, `customers`, `logistics`, `pricing`, `portfolio`, `config`.
- Auto-detects `Raito_Master_Data_export.xlsx`; uses it as primary source if present. Falls back to original.
- Export column layouts differ from original (no `#` prefix column, different row offsets). Parser handles both.
- `op_margin` computed from `gross_margin + commission + sale_price` when reading export (since export doesn't include pre-computed op_margin).

**unified_dashboard.py:**
- `_read_cc_dashboard()` — Reads CC HTML source, converts dark→light theme, scopes CSS under `#tab-cc`, modernizes KPI cards/panels/tables/charts, reorders Weekly chart below KPI grid.
- `_build_master_data_tab(master_data)` — Returns full interactive HTML string for MD tab. Embeds all data as JSON via `template.replace('__MD_DATA__', json.dumps(...))` (avoids f-string escaping). Includes sub-nav, brand cards, CRUD tables, portfolio matrix, config table, unsaved-changes banner, and client-side Save to Excel (SheetJS).
- `generate_unified_dashboard()` — Builds the full HTML with sidebar nav, 3 tab containers, password gate, all CSS.
- `DASHBOARD_PASSWORD` — Set password for the login gate (default: `raito2026`). Hash is computed at generation time.

**parsers.py:**
- `parse_icedreams_file(filepath)` — Returns `{month: {totals, by_customer}}`. Returns handling: `sign * -1`.
- `parse_mayyan_file(filepath, price_table=None)` — Returns `{month: {totals, by_chain, by_account, by_customer_type, branches}}`. Supports both monthly (חודש) and weekly (שבועי) formats. When `price_table` is provided, computes actual value per row using per-chain prices.
- `_load_mayyan_price_table()` — Loads latest `price data/price db*.xlsx`, returns `{product: {pricedb_customer: price}}` for Maayan rows only.
- `_MAAYAN_CHAIN_TO_PRICEDB` — Dict mapping raw Maayan chain names (שם רשת) → price DB customer names.
- `_mayyan_chain_price(price_table, chain_raw, product)` — Looks up actual price for a chain+product from price DB; falls back to `get_b2b_price_safe()` if not found. Called per row when building `by_account` to apply pricing at parse time.
- `parse_all_mayyan()` — Loads price table once, passes to each `parse_mayyan_file()` call. `by_account` now stores `{product: {units: int, value: float}}` (pre-priced) instead of `{product: units_int}`.
- `parse_all_icedreams()` — After processing all `.xlsx` files, checks for Format B `.xls` files (e.g. `sales_week_12.xls`) and merges early-week per-customer data (all except last week column) into `by_customer` for any month where flat totals exceed customer-attributed totals. This fills in months like March where a partial-period file (`icedream_mar_w10_11.xlsx`) has no customer summary rows.
- `parse_all_biscotti()` — Parses `daniel_amit_weekly_biscotti.xlsx`. Multi-sheet: "סיכום כללי" + per-week sheets. Maps everything to `dream_cake_2` at `BISCOTTI_PRICE_DREAM_CAKE = ₪80.0`.
- `consolidate_data()` — Merges all sources. `icedreams_customers` filter passes customers with `total_u != 0` (changed from `> 0` on 25 Mar 2026 — allows returns/credit-note customers through). Ma'ayan uses actual `value` from parser when >0; falls back to units × `get_b2b_price_safe()` estimate.

### Running

```bash
# Regenerate unified dashboard (BO + CC + MD tabs)
python3 scripts/unified_dashboard.py

# Then copy to deployment folder
cp docs/unified_dashboard.html github-deploy/index.html

# Push to GitHub Pages
cd github-deploy && git add -A && git commit -m "Update" && git push origin main --force
```

### Outputs

| File | Description |
|---|---|
| `docs/unified_dashboard.html` | **Main output** — Unified 3-tab dashboard with sidebar nav, password protection |
| `github-deploy/index.html` | Deployment copy for GitHub Pages |
| `docs/dashboard.html` | Old standalone BO dashboard (superseded by unified) |
| `docs/Raito_Business_Overview.xlsx` | Full Excel dashboard (6 sheets) |
| `docs/sale_points_deep_dive.xlsx` | Sale Points deep-dive Excel — Summary + All Sale Points + per-group sheets. Run: `python3 scripts/salepoint_excel.py` |

---

## Unified Dashboard Architecture

**URL:** `https://or-raito.github.io/raito-dashboard/` (password: `raito2026`)

**Layout:** Left sidebar (240px) + main content area. Gridle CRM-inspired modern design.

**Sidebar Navigation (grouped sections):**
- Dashboard → Business Overview (BO)
- Analytics → Customer Performance (CC)
- Data → Master Data (MD)

### Tab 1: Business Overview (BO)
Generated dynamically by `dashboard.py` from parsed data.

**Filters:** Year (All Years / 2025 / 2026) × Period (Overview / Dec / Jan / Feb / Mar) × Brand (All Brands / Turbo / Dani's). Year filter controls which months are visible in Period — selecting 2025 shows only Dec, selecting 2026 shows Jan/Feb/Mar. Overview aggregates visible months for the selected year.

**Design:** Modern card-based layout, Inter font, soft shadows, rounded 16-24px corners.

**Sections:**
1. **KPI Cards** (5 columns) — Revenue, Units Sold, Points of Sale, Creators, Warehouse Inventory. Big centered numbers with trend badges.
2. **Monthly Revenue Chart** — SVG smooth bezier curves with gradient fill, value labels on dots, no grid lines. Color: green (#10b981). Only shown in Overview.
3. **Monthly Sales Chart** — Same style, purple (#5D5FEF). Only shown in Overview.
4. **Units Sold by Flavor — Monthly** — Donut chart (SVG, 210px) with hover tooltips showing flavor name + % share. Three-column layout: Donut | Legend (with color dots, units, %) | "By Distributor" table (Icedream/Ma'ayan/Biscotti breakdown per flavor). Below: monthly units table + inventory coverage. **Per-month view** additionally includes a "By Customer" breakdown table showing each customer's per-flavor units (top 10 with Show More toggle). Revenue card removed from per-month view (18 Mar 2026).
5. **Detailed Summary** — Top 10 rows (sorted by revenue desc) with "Show More" button.
6. **Icedream Customers** — Top 10 with "Show More".
7. **Ma'ayan Chains** — Top 10 with "Show More".
8. **Biscotti Customers** — First data live (9 branches, 121 units, Mar 2026). Formal launch 10 Apr 2026.
9. **Top Customers** — Combined ranking from all distributors.
10. **Inventory** (overview only) — Karfree + Icedream + Ma'ayan stock.

### Tab 2: Customer Performance (CC)
Source: `scripts/cc_dashboard.py` — fully dynamic Python generator (migrated from static HTML on 25 Mar 2026).
`build_cc_tab(data)` receives the same `data` dict as the BO tab and injects live `customers[]`, `productMix{}`, and `productPricing{}` JS constants. All revenue, units, avgPrice, grossMargin, opMargin, and momGrowth are computed dynamically from parsed transaction data — zero hardcoded price literals or static totals. Old HTML source file (`dashboards/customer centric dashboard 11.3.26.html`) is legacy/unused.

**Filters:** Year (All Years / 2025 / 2026, default 2026) × Customer, Distributor, Status, Month (default All Months), Brand (Turbo / Dani's). Year filter controls which months are visible in the Month dropdown — selecting 2025 shows only Dec, selecting 2026 shows Jan/Feb/Mar. Weekly Sales Trend chart filters by both year AND month — selecting a specific month shows only weeks belonging to that month. Implemented via `ccSetYear()` and `_ccFilteredWeekIndices()` JS functions injected by `_read_cc_dashboard()`.

**Sections:** KPI cards (6: Revenue, Units, Gross Profit, Op Profit, Returns — All, Portfolio MoM), Weekly Sales Trend chart (moved below KPIs, year+month filtered), Customer table, Product Mix, Inactive customers panel. Returns KPI card translated from Hebrew to English (labels: "Returns — All/Icedreams/Ma'ayan", "Revenue Loss", "Return Rate").

### Tab 3: Master Data (MD)
Generated by `_build_master_data_tab()` in `unified_dashboard.py`, using data from `master_data_parser.py`.

**Sub-navigation (9 sections):** Brands · Products · Manufacturers · Distributors · Customers · Logistics · Pricing · Portfolio · Config

**Brand Cards view:** Top of the Brands section shows coloured card grid — one card per brand with a coloured accent bar, icon, name, category, product count, active SKU count, and owner footer strip.

**CRUD operations:** Every editable sheet (Brands, Products, Manufacturers, Distributors, Customers, Logistics, Pricing) supports Add (+), Edit (✏️), and Delete (🗑). Changes are tracked client-side as JSON mutations.

**Unsaved-changes banner:** Appears after any add/edit/delete. Shows a 3-step instruction: (1) click Save to Excel → (2) replace `Raito_Master_Data_export.xlsx` in the `data/master data/` folder → (3) run `python3 scripts/unified_dashboard.py`.

**Portfolio tab:** Read-only matrix from the original Excel (Portfolio sheet). Always loaded from `Raito_Master_Data.xlsx` (not the export).

**Config tab:** Read-only parameter table from the original Excel. Always loaded from `Raito_Master_Data.xlsx`.

**Data source — two-file strategy:**
- `data/master data/Raito_Master_Data_export.xlsx` — Primary source for 7 sheets (Brands, Products, Manufacturers, Distributors, Customers, Logistics, Pricing). Created by clicking "Save to Excel" in the MD tab. Clean format: row 1 = headers, data row 2+, no # column.
- `data/master data/Raito_Master_Data.xlsx` — Original master source. Used for Portfolio + Config only (these sheets are not exported by the dashboard). Also used as fallback for all sheets if the export file doesn't exist.

**Workflow to update Master Data:**
1. Open unified dashboard → MD tab → make edits
2. Click **Save to Excel** (downloads `Raito_Master_Data_export.xlsx`)
3. Replace `data/master data/Raito_Master_Data_export.xlsx` with the downloaded file
4. Run `python3 scripts/unified_dashboard.py` to regenerate the dashboard

### Tab 4: Sale Points (SP)
Generated by `salepoint_dashboard.py`. Displays a customer-level view of active, churning, and reactivated sale points across both distributors.

**Filters:**
- **Brand** — All Brands / Turbo / Dani's Dream Cake (top bar above KPI summary)
- **Status** — All / Active / Reactivated / Mar gap / Churned / New
- **Customer Group** — All groups or a specific group (chain)
- **Distributor** — All / Icedream / Ma'ayan

**Status taxonomy:**
| Status | Definition | Row fill |
|---|---|---|
| Active | Mar > 0 AND Feb > 0 | White |
| Reactivated | Mar > 0 AND Feb == 0 | EAFAF1 (light green) |
| Mar gap | Mar == 0 AND Feb > 0 | White |
| Churned | Mar == 0 AND Feb == 0 AND any prior month > 0 | FDEDEC (light red) |
| New | Fallback (first appearance) | White |

**Brand filter logic:**
- **Turbo units:** `choc + van + mango + pist`
- **Dani's units:** `dc`
- **Turbo revenue:** brand_units × ₪13.80 (fixed B2B price)
- **Dani's revenue:** brand_units × ₪81.10 (fixed B2B price)
- Monthly breakdown columns use proportional fraction: `round(month_units × (brand_units / total_units))`

**KPI cards:** Total Sale Points | Active | Reactivated | Churned | Total Units | Revenue

**Excel export:** `python3 scripts/salepoint_excel.py` → `docs/sale_points_deep_dive.xlsx`
- Sheet "Summary" — one row per customer group, 17 columns, dark navy 2C3E50 header
- Sheet "All Sale Points" — one row per individual sale point, FDEDEC for Churned, EAFAF1 for Reactivated
- Per-group sheets (e.g., "שוק פרטי", "וולט מרקט", "דומינוס") — one sheet per customer group; title merged A1:F1, stats in row 2, active-point progression in row 3, headers in row 5, data from row 6

**Icedream chain extraction (`_ICE_CHAIN_PREFIXES`):** Branch names like "דומינוס פיצה X" → "דומינוס"; "וולט מרקט X" → "וולט מרקט"; "גוד פארם X" → "גוד פארם" etc. Uses longest-prefix-first matching.

**Ma'ayan chain normalisation (`_MAAYAN_CHAIN_NORM`):** `{'פז יילו': 'פז ילו', 'פז  ילו': 'פז ילו'}` — prevents duplicate sheets from inconsistent spelling across months.

### UX/UI Design System
- **Colors:** Primary #5D5FEF (purple), Success #10b981 (green), Danger #ef4444
- **Flavor Colors:** Chocolate #8B4513, Vanilla #DAA520, Mango #FF8C00, Pistachio #93C572, Dream Cake #DB7093, Magadat #9CA3AF
- **Typography:** Inter font, big numbers 22-24px/800, labels 9-11px/700 uppercase, body 12-13px
- **Cards:** White bg, 1px #f1f5f9 border, 16-20px radius, soft shadow
- **Tables:** 11-12px font, uppercase headers, hover highlight, overflow-x scroll for wide tables
- **Charts:** SVG with smooth cubic bezier curves, gradient area fill (22% opacity), no grid lines, value pill labels on data points
- **Password Gate:** Client-side hash check, session-persisted via sessionStorage

---

## Phase 4 — Cloud Infrastructure (Added 27 Mar 2026)

### Overview

The project has been migrated to a cloud-hosted, SQL-backed architecture. The live dashboard runs on Google Cloud Run, backed by Cloud SQL (PostgreSQL). Local Excel files remain the source of truth for ingestion, but all query-time data is served from PostgreSQL.

**Live dashboard URL:** `https://raito-dashboard-20004010285.me-west1.run.app`
**Upload page URL:** `https://raito-dashboard-20004010285.me-west1.run.app/upload`
**GCP project:** `raito-house-of-brands`
**Cloud SQL instance:** `raito-db` (region: `me-west1`, PostgreSQL 15)
**Cloud Run service:** `raito-dashboard` (region: `me-west1`)
**Artifact Registry:** `me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-dashboard`

---

### Authentication & Access

**Dashboard access:** Protected by Google IAP (Identity-Aware Proxy). Only `@raito.ai` domain users can access. No `--allow-unauthenticated` flag — all traffic goes through IAP.

**Cloud SQL (local dev):** Uses Cloud SQL Auth Proxy binary (`cloud-sql-proxy`) on port 5433 (port 5432 is in use locally):
```bash
./cloud-sql-proxy raito-house-of-brands:me-west1:raito-db --port 5433
export DATABASE_URL="postgresql://raito:raito@localhost:5433/raito"
```

**ADC credentials:** Run once per machine: `gcloud auth application-default login`. Credentials saved to `~/.config/gcloud/application_default_credentials.json`. The proxy picks these up automatically — no JSON service account key needed (org policy `constraints/iam.disableServiceAccountKeyCreation` blocks key creation anyway).

---

### Database Schema (scripts/db/schema.sql)

Four layers:

**Layer 1 — Reference tables:** `distributors`, `products`, `customers`, `sale_points`
**Layer 2 — Ingestion tracking:** `ingestion_batches` (tracks every file load — idempotency key)
**Layer 3 — Sales transactions:** `sales_transactions` (one row per product per customer per month)
**Layer 4 — Inventory:** `inventory_snapshots` (one row per product per distributor per date)

Key constraints:
- `ingestion_batches.source_file_name + distributor_id` — prevents double-ingestion
- `inventory_snapshots`: UNIQUE on `(distributor_id, product_id, snapshot_date)`
- `sales_transactions.ingestion_batch_id` → FK to `ingestion_batches` (CASCADE on --force)

**`source_type` enum in `inventory_snapshots`:** `'warehouse'` (Karfree PDF) vs `'distributor'` (Icedream/Ma'ayan XLSX stock files)

**`karfree` distributor row:** Inventory-only. No sales transactions. Added to `distributors` table as key `'karfree'`.

**GEO tables (PostGIS):**
- `municipalities_geo` — ~15 Israeli district boundaries (municipality_id, name_he, name_en, region, geom). Loaded from GeoJSON file.
- `cities_geo` — 429 city/town boundaries (city_id, name_he, name_en, muni_id, district_id, geom). Loaded via `fetch_city_boundaries.py` from GitHub. Requires `GRANT ALL ON TABLE cities_geo TO raito` (table owned by `raito_app`).

---

### SQL Pipeline Files (scripts/db/)

| File | Role |
|---|---|
| `schema.sql` | Full schema DDL — drop and recreate all tables |
| `migrate_inventory_schema.sql` | Standalone migration — adds `inventory_snapshots` + `karfree` distributor to existing DB |
| `seed_reference_data.py` | Seeds `distributors`, `products`, `customers` from hardcoded Python dicts. Includes karfree. |
| `migrate_transactions.py` | One-time bulk migration: parses all historical Excel files via `parsers.py`, inserts into PostgreSQL. Also migrates Icedream/Ma'ayan inventory snapshots. |
| `database_manager.py` | Query layer for the Flask dashboard. `get_consolidated_data()` returns the same shape as `parsers.consolidate_data()` — both `warehouse` and `dist_inv` keys populated from DB. |
| `raito_loader.py` | **Weekly ingestion CLI** — loads a single distributor file into Cloud SQL. See below. |
| `db_dashboard.py` | Flask app — serves the dashboard from PostgreSQL data. Also hosts `/upload` and `/refresh`. |

---

### Flask App Routes (scripts/db/db_dashboard.py)

| Route | Method | Description |
|---|---|---|
| `/` | GET | Serves unified dashboard HTML (cached in memory; regenerated on first request) |
| `/refresh` | GET | Clears cache, re-queries PostgreSQL, regenerates dashboard HTML |
| `/upload` | GET | Drag-and-drop file upload UI |
| `/upload` | POST | Accepts distributor file, ingests into PostgreSQL, returns JSON summary |
| `/health` | GET | Health check for Cloud Run |

**Upload page behaviour:**
- Auto-detects distributor and file type (sales vs stock) from filename patterns
- Supports: Icedream, Ma'ayan, Biscotti (sales); Icedream stock, Ma'ayan stock, Karfree PDF (inventory)
- `force=true` deletes existing batch (+ its child rows) before re-inserting
- On success: invalidates dashboard HTML cache so next `/` visit shows fresh data

---

### raito_loader.py — Weekly Ingestion CLI

**Location:** `scripts/db/raito_loader.py`
**Run from:** Project root (`~/dataset/`) — NOT from `scripts/` or `scripts/db/`

```bash
# Standard weekly load (auto-detects distributor + type from filename)
python3 scripts/db/raito_loader.py --target local --file data/icedreams/week14.xlsx

# Force re-import (overwrites existing data for same period)
python3 scripts/db/raito_loader.py --target local --file data/icedreams/week14.xlsx --force

# Dry run (parse only, no DB writes)
python3 scripts/db/raito_loader.py --target local --dry-run --file data/icedreams/week14.xlsx

# Stock/inventory file
python3 scripts/db/raito_loader.py --target local --file data/icedreams/stock26.3.xlsx

# Explicit distributor override
python3 scripts/db/raito_loader.py --target local --distributor mayyan --file data/mayyan/w13.xlsx
```

**`--target local`** uses `DATABASE_URL` env var (set to `postgresql://raito:raito@localhost:5433/raito` when using proxy).
**`--target cloud`** uses `google-cloud-sql-connector` — currently NOT installable on Mac M4 or Linux ARM (package not found). Use `--target local` with the proxy instead.

**Auto-detection patterns:**
- Filename contains `icedream`, `ice_dream` → icedream
- Filename contains `maayan`, `mayyan` → mayyan
- Filename contains `biscotti`, `daniel` → biscotti
- Filename contains `karfree` → karfree (always inventory)
- Parent folder name is checked if filename is ambiguous
- `stock`, `מלאי`, `inventory` in filename → inventory/stock type

**Idempotency:** Batch key = `icedream_{month_str}` (e.g. `icedream_march`). Existing complete batches are skipped. Use `--force` to overwrite.

---

### Docker Build & Deploy

**Dockerfile** at project root. Build for Cloud Run (linux/amd64):

```bash
# Build (must have Docker Desktop running)
cd ~/dataset
docker build --platform linux/amd64 -t me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-dashboard:latest .

# Push to Artifact Registry
docker push me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-dashboard:latest

# Deploy to Cloud Run
gcloud run deploy raito-dashboard \
  --image=me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-dashboard:latest \
  --region=me-west1 \
  --project=raito-house-of-brands
```

**requirements.txt** — `google-cloud-sql-connector` intentionally excluded (not installable on ARM/Mac M4 or Linux ARM). Packages used: Flask, gunicorn, pandas, openpyxl, psycopg2-binary, pdfplumber, tqdm.

**Gunicorn entrypoint:** `scripts.db.db_dashboard:app` (set in Dockerfile).

**Cloud SQL connection in container:** Via Unix socket (`/cloudsql/project:region:instance/.s.PGSQL.5432`). Cloud Run revision must have `--add-cloudsql-instances=raito-house-of-brands:me-west1:raito-db` configured.

---

### Known Issues (Phase 4)

1. **`google-cloud-sql-connector` not installable** on Mac M4 or Docker linux/amd64 — package returns "no versions found". Use Cloud SQL Auth Proxy binary instead for all local dev connections.
2. **`raito_loader.py` must run from project root** — relative imports for `parsers`, `config`, `migrate_transactions` depend on the CWD being `~/dataset/`. Running via absolute path (`python3 ~/dataset/scripts/...`) breaks the import chain.
3. **Files without `.xlsx` extension are invisible to parsers** — `parse_all_icedreams()` globs `*.xlsx` only. Always ensure distributor files have the correct extension before dropping into the data folder.
4. **Icedream batch names are month-level** (e.g. `icedream_march`), not file-level — adding a new weekly file and running `--force` will re-ingest the entire month by combining all `.xlsx` files in the folder.
5. **GitHub Pages deprecated** — Cloud Run is the sole production deployment as of 27 Mar 2026. The `/refresh` endpoint force-regenerates the dashboard from Excel parsers.
6. **`weekly_chart_overrides` is the only live SQL table** — `sales_transactions`, `ingestion_batches`, `products`, `customers`, `distributors` (Phase 4 schema) were never deployed to Cloud SQL. NEVER re-add `get_consolidated_data()` to `_generate_dashboard_html()` without first verifying all Phase-4 tables exist and are populated.
7. **Local dev environment** — `raito-dev` alias starts Flask at `localhost:8080`. Requires `~/dataset/venv` activated. Run `./cloud-sql-proxy raito-house-of-brands:me-west1:raito-db` in a second tab to enable `/api/weekly-overrides` DB queries locally. Always test here before docker build + deploy.

### Parser Traps — Do Not Repeat These Mistakes

These are things that look reasonable but are wrong. Verified through painful experience.

**Ma'ayan: always use the detail sheet, never the pivot sheet**
The Ma'ayan Excel files contain two sheets: `טבלת ציר` (pivot) and `דוח_הפצה_גלידות_טורבו__אל_פירוט` (detail). `parsers.py` explicitly skips the pivot sheet via `SKIP_KEYWORDS = ('ציר', 'סיכום', 'summary', 'pivot', 'totals')` because it double-counts rows. Any code that reads Ma'ayan files must use the detail sheet only. The sheet-selection priority in `parse_mayyan_file()` is: sheet containing 'פירוט' → sheet containing 'דוח' but not in SKIP_KEYWORDS → any non-pivot sheet → last sheet as fallback.

**Ma'ayan: revenue is per-row from price DB, never a flat rate**
Ma'ayan files have no revenue column. Revenue is calculated row-by-row: `_load_mayyan_price_table()` loads the latest price DB file from `data/price data/price db*.xlsx`, then `_mayyan_chain_price(price_table, chain_raw, product)` looks up the per-chain price for each transaction row. ₪13.80 is the last-resort fallback only (used when a chain has no entry in the price DB at all). Using ₪13.80 as a default produces materially wrong revenue — chains like פז ילו are ₪11.00, שוק פרטי is ₪14.10, דור אלון is ₪12.27.

**Weekly overrides must reuse parsers.py, not re-implement parsing**
`_extract_week_overrides()` in `db_dashboard.py` is responsible for extracting per-week unit and revenue totals from uploaded files. For Ma'ayan this means calling `parse_mayyan_file()` (or its sub-functions) from `parsers.py` — grouping the result by week number from the 'שבועי' column. Never build a parallel parser inline in `db_dashboard.py`.

**Icedream sign convention: negative = sale**
Icedream reports use negative quantities for sales and positive for returns. Always flip the sign (`-q`, `-r`) when summing — never use `abs()`.
