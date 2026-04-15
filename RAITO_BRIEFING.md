# Raito Project Briefing

Upload this file at the start of every new conversation about Raito data/dashboards.

---

## Company Overview

**Raito** — Israeli house of brands building and distributing consumer goods across multiple categories: frozen (ice cream, cakes), protein snacks, coffee, and beverage capsules. Currently active with frozen products through three distributors (Icedream, Ma'ayan, Biscotti), expanding into additional categories in 2026.

### Brands

| Brand Key | Brand Name | Category | Status | Launch Date | Creator |
|---|---|---|---|---|---|
| turbo | Turbo by Deni Avdija | Ice Cream | Active | Dec 2025 | דני אבדיה |
| danis | Dani's Dream Cake | Frozen Cakes | Active | Dec 2025 | דניאל עמית |
| turbo_nuts | Turbo by Deni Avdija | Protein Snacks | Planned | Apr 2026 | דני אבדיה |
| ahlan | Ahlan | Coffee | Planned | Jul 2026 | Ma Kashur |
| w | W | Beverage Capsules | Planned | Aug 2026 | The Cohen |

### Active Products

| Product Key | Barcode | Full Name | Brand | Status | Prod. Cost (₪) | Units/Carton | Units/Pallet | Shelf Life | Storage |
|---|---|---|---|---|---|---|---|---|---|
| chocolate | 7290020531032 | Turbo Chocolate | turbo | Active | 6.5 | 10 | 2,400 | 12 months | -25°C |
| vanilla | 7290020531025 | Turbo Vanilla | turbo | Active | 6.5 | 10 | 2,400 | 12 months | -25°C |
| mango | 7290020531018 | Turbo Mango | turbo | Active | 6.5 | 10 | 2,400 | 12 months | -25°C |
| pistachio | 7290020531049 | Turbo Pistachio | turbo | New (Feb 2026) | 7.1 | 10 | 2,400 | 12 months | -25°C |
| dream_cake | 726529980677 | Dani's Dream Cake | danis | Discontinued | 53.5 | 3 | 600 (1,800 units) | 3 months | -18°C |
| dream_cake_2 | 7290117842973 | Dani's Dream Cake (Biscotti) | danis | Active | 58.0 | 3 | — | — | 0-4°C (chilled) |
| magadat | — | Turbo Magadat | turbo | Discontinued | — | — | — | — | -25°C |

### Planned Products

| SKU Key | Name | Brand | Target Launch | Notes |
|---|---|---|---|---|
| dream_cake_2 | דרים קייק - ביסקוטי (Dani's Dream Cake - biscotti) | danis | Active (from Mar 2026) | Biscotti manufacturer, chilled (0-4°C), GTIN 7290117842973, ₪58 prod cost, ₪80 B2B price, 950-1000g, 3 units/carton. **Now active in config.py and parsers.** Replaces dream_cake (Piece of Cake, discontinued). |
| dream_cake_3 | Dani's Cake SKU 3 | danis | 10 May 2026 | |
| nuts_sku1 | Turbo Nuts SKU 1 | turbo_nuts | Apr 2026 | ₪3.35 prod cost, 60g, ambient (24°C) |
| nuts_sku2 | Turbo Nuts SKU 2 | turbo_nuts | Apr 2026 | ₪3.35 prod cost, 60g, ambient (24°C) |
| ahlan_sku1 | Ahlan Coffee SKU 1 | ahlan | Jul 2026 | |
| w_sku1 | W Capsule SKU 1 | w | Aug 2026 | |

**Icedream SKU names (the only 7 counted):**
- דרים קייק- 3 יח'
- טורבו מארז גלידות 250 מל * 3 יח'*סגור קבוע*
- טורבו- גלידת וניל מדגסקר 250 מל * 6 יח'
- טורבו- גלידת מנגו מאיה 250 מל * 10 יח'
- טורבו- גלידת מנגו מאיה 250 מל * 6 יח'
- טורבו- גלידת פיסטוק 250 * 10 יח'
- טורבו- גלידת שוקולד אגוזי לוז 250 * 10 יח'

**Excluded products:** באגסו (שוקולד לבן), שוקולד דובאי — not Raito products. Excluded in Icedream parser (strict טורבו/דרים קייק filter), Karfree parser (יאבוד/וסגאב reversed-Hebrew check), and config.py (`classify_product`). magadat (triple pack barcode 11553) excluded from CP units/revenue, tracked separately.

### Manufacturers

| Manufacturer | Products | Status |
|---|---|---|
| Vaniglia | Turbo Ice Cream (chocolate, vanilla, mango, pistachio) | Active |
| Piece of Cake | Dani's Dream Cake (dream_cake) | Discontinued — no longer in use |
| Biscotti | Dani's Dream Cake (frozen + chilled) | Active manufacturer from 1.3.2026 — contact: dudi@biscotti.com, Bnei Brak, lead time 14 days, MOQ 0 |
| Din Shiwuk | Turbo Nuts | Planned |
| Rajuan | Ahlan Coffee | Planned |

### B2B Pricing

B2B prices vary per customer. Source of truth: `data/price data/price db - 24.2.xlsx` (70 rows, 18 unique customers, 5 products).

**Both BO and CC dashboards** now use actual per-chain prices for Ma'ayan revenue (loaded from price DB at parse time):

| Maayan file chain (שם רשת) | Dashboard name (EN) | Price DB customer | Ice cream price |
|---|---|---|---|
| דור אלון | AMPM / Alonit | AMPM / אלונית | ₪12.39 / ₪12.27 |
| שוק פרטי | Private Market / Tiv Taam | שוק פרטי | ₪14.10 |
| דלק מנטה | Delek Menta | דלק | ₪12.74 |
| פז ילו / פז יילו | Paz Yellow | פז יילו | ₪11.00 |
| פז חברת נפט- סופר יודה | Paz Super Yuda | פז סופר יודה | ₪11.00 |
| סונול | Sonol | סונול | ₪14.00 |

Ma'ayan reports don't include revenue — calculated from units × per-chain price (falls back to ₪13.8 for unknown chains).
Icedream reports include actual invoice values.

**BO vs CC revenue parity (achieved 25 Mar 2026):** Both tabs consume the identical `data` object from `consolidate_data()` — sub-₪1 rounding residual only. No gap expected.

### Distributors

| Key       | Name              | Commission | Report Format |
|-----------|-------------------|------------|---------------|
| icedreams | Icedream          | 15% | **Two formats exist (see below).** Negative qty = sales, positive qty = returns. |
| mayyan_froz | Ma'ayan (מעיין נציגויות) — Frozen | 25% | Excel: columns חודש (or שבועי)/פריט/בודדים/רשת/שם חשבון. Negative values = returns (handled by pandas sum). |
| biscotti | Biscotti (ביסקוטי) — Dream Cake | 0% | No standard report format yet. Creator commission model: ₪10 per cake sold (paid to Daniel Amit). |
| mayyan_amb | Ma'ayan (מעיין נציגויות) — Ambient | TBD | Turbo Nuts distribution (future). Weekly reports. Commission TBD. |

### Icedream Report Formats

Icedream sends two different Excel/XLS formats depending on context:

**Format A — "By Networks" monthly detail (`.xlsx`, standard parser)**
- File examples: `ICEDREAM- DECEMBER.xlsx`, `icedream - January.xlsx`, `ice_feb_full.xlsx`, `icedream_mar_w10_11.xlsx`
- Title: "מכירות לעוגיפלצת חודשי לפי רשתות"
- Structure: Rows per transaction/product per branch. Customer assigned when a **bold** `סה"כ` row appears in col A; col B = customer name.
- Key columns: col D (item name), col E (revenue ₪), col F (qty — negative = sale, positive = return)
- Parsed by: `parse_icedreams_file(filepath)` in `parsers.py`
- Units: col F is in **cartons/packs**. `extract_units_per_carton(item_name)` converts to individual units (e.g., `* 10 יח` → multiply by 10).

**Format B — Weekly comparison (`.xls` OLE2/BIFF8, custom parser required)**
- File examples: `11.3.26`, `icedream_15_3`, `sales_week_12.xls`
- Sent by Rozit Israel (Icedream) as `.xls` binary (OLE2 Compound Document, BIFF8 format)
- Structure: **One row per product per customer**, with multiple weeks side-by-side + grand total column
- Column layout (for a 3-week file like `sales_week_12.xls`):

| Col | Content |
|-----|---------|
| 0 | Customer/network name (appears only on first product row of each customer) |
| 1 | Product name (Hebrew SKU) |
| 2 | W10 quantity (cartons, negative = sales) |
| 3 | W10 revenue (₪, negative = sales) |
| 4 | W11 quantity (cartons) |
| 5 | W11 revenue (₪) |
| 6 | W12 quantity (cartons) |
| 7 | W12 revenue (₪) |
| 8 | Total quantity (cartons) |
| 9 | Total revenue (₪) |

- Summary rows: col 1 = `סה"כ` (total per customer) — **SKIP these rows**
- Grand total row: col 0 = `סה"כ` — **SKIP this row**
- **Important:** Some quantity cells may be empty (no delivery that week). Empty = 0, not an error.
- **Non-Raito products** present in file: `באגסו` variants, `שוקולד דובאי` (עוגיפלצת brand products) — these appear mixed in with Icedream accounts.
- **CRITICAL product filter:** Only include rows where product name contains `טורבו` OR `דרים קייק`. DO NOT use `שוקולד`, `מנגו` etc. alone as flavor filters — `שוקולד דובאי` and `באגסו שוקולד לבן` would be falsely classified as Chocolate.
- **עוגיפלצת בע"מ account rule:** In W12, עוגיפלצת bought Dream Cake (wholesale) — include as network `עוגיפלצת`. In W11, they also bought Dream Cake (6 cartons / 18u / ₪2700) — but this was **NOT** in the CC dashboard W11 total (dashboard shows 553u = excludes it). Follow dashboard convention: **exclude עוגיפלצת for all weeks except W12**.
- **Cannot be read by LibreOffice** (conversion fails) or standard `openpyxl` (wrong format). Requires custom OLE2/BIFF8 reader or `xlrd`.
- Custom parser: `/sessions/.../parse_xls.py` (reads FAT sectors, Workbook stream, SST, NUMBER/RK/MULRK/LABELSST records). `xlrd` also works.
- Quantity units are **cartons/packs** — apply pack sizes: Vanilla ×6, all others ×10, Dream Cake ×3.
- **Authority:** Format B files are the authoritative source (exported directly from Icedream's system by date). They supersede Format A files for the same period.

**Pack sizes (Icedream):**
| Flavor | Pack Size | Identifier |
|--------|-----------|------------|
| Vanilla | ×6 | `וניל` in product name |
| Mango | ×10 | `מנגו` |
| Pistachio | ×10 | `פיסטוק` |
| Chocolate | ×10 | `שוקולד` in Turbo product |
| Dream Cake | ×3 | `דרים` |

**Network name mapping (Format B → dashboard):**
| Raw account (col 0) | Dashboard network |
|---|---|
| `*גוד פארם X*` | `גוד פארם` |
| `*דומינוס פיצה X*` | `דומינוס` |
| `*וולט מרקט X*` | `וולט מרקט` |
| `*חוות נעמי X*` | `חוות נעמי` |
| `ינגו דלי ישראל בע"מ` | `ינגו` ← NOTE: dashboard uses short form |
| `כרמלה` | `כרמלה` |
| `פוט לוקר` | `פוט לוקר` |
| `עוגיפלצת בע"מ` | `עוגיפלצת` (W12 only) |

**Critical: Icedream returns handling** — The parser flips signs: negative raw values become positive sales, positive raw values become negative (returns). Uses `sign * -1` logic, NOT `abs()`.

### Warehouse & Logistics

- **Cold Storage:** Karfree (קרפריי) — PDF inventory reports with reversed Hebrew text
- **Dream Cake (frozen)** is NOT stored at Karfree — goes direct to distributors
- **Dream Cake - Biscotti (chilled, 0-4°C)** — mixed pallets stored at manufacturer site (Biscotti, Bnei Brak). Distributed by Biscotti.
- **Pallet Calculation:** `round(units / 2400, 1)` — applies to ice cream only (10 units/carton × 240 cartons/pallet). Dream Cake shows "-"
- **Target Stock:** 1 month of average sales

---

## Raito — Business Model & Strategic Context

### Current Operating Model

1. **Creator-led brand strategy** — Raito builds brands around creators (Deni Avdija → Turbo, Daniel Amit → Dani's Dream Cake, Ma Kashur → Ahlan). The creator defines the product narrative and drives consumer awareness. This is not influencer marketing — the creators are brand co-owners/faces.

2. **House of brands model** — Raito is not a single brand. It's an infrastructure company that launches and operates multiple consumer brands across categories (frozen, snacks, coffee, capsules), each with its own creator, manufacturer, and distribution path.

3. **Asset-light manufacturing** — Raito doesn't manufacture anything. All production is outsourced (Vaniglia for ice cream, Biscotti for cakes, Din Shiwuk for nuts). Raito controls brand, distribution relationships, and data.

4. **Multi-distributor architecture** — Each product category may use different distributors (Icedream & Ma'ayan for frozen, Biscotti direct for chilled cakes, Ma'ayan Ambient for nuts). Raito manages the complexity of different report formats, commission structures, and pricing models across all of them.

5. **Commission-based distribution** — Distributors earn commission on sales (Icedream 15%, Ma'ayan 25%, Biscotti 0% + creator commission). Raito always negotiates for the best possible rate — commission rates are actively optimized, not fixed.

6. **Offline-first, data-driven** — 100% of current sales happen in physical retail stores. Raito builds its own analytics layer (dashboards, parsers) on top of distributor reports because no standard attribution or reporting infrastructure exists in Israeli offline retail.

7. **Small team, AI-leveraged operations** — The company is designed to scale with a very lean team (8-12 people), using AI tools heavily for data processing, reporting, and operational tasks rather than hiring large ops/analytics teams.

### Future Vision — Mamba Platform

8. **Mamba** — Raito's long-term play is building an infrastructure layer that connects creator influence to physical retail sales — essentially affiliate marketing for offline commerce (a $20T market with zero attribution today).

9. **Creator swarm model** — An anchor creator (e.g., Deni for Turbo) defines the narrative, then hundreds/thousands of micro-creators (5k-50k followers) amplify it into retail demand. These creators behave like side-hustle entrepreneurs optimizing for commission and repeat earnings.

10. **Attribution layer** — Mamba plans to verify offline purchases via QR scan, receipt recognition, geolocation, POS integration, and retailer APIs — paying creators commission on verified retail sales.

11. **Retail Demand Graph** — Over time, the platform builds a data asset mapping which creators drive purchases, which stores convert, which cities trend, and which audiences influence retail demand.

12. **AI-native platform** — AI powers creator discovery, content performance prediction, campaign automation (e.g., "activate 500 gym creators in NYC"), and retail trend detection.

13. **Wedge categories** — Launching with impulse-driven, visually shareable, frequently purchased products (functional snacks, beverages, supplements) — which explains the current frozen/snack portfolio.

14. **Network flywheel** — More creators → more demand signals → more brands → more creator earnings → more creators joining. Every transaction improves the system's intelligence.

---

## Sub-Brand Split Rules (Ma'ayan)

Ma'ayan data has two relevant columns: `שם רשת` (chain) and `שם חשבון` (account/branch). Splits are applied at the account level:

| Chain in file (שם רשת) | Dashboard customer (EN) | Condition |
|---|---|---|
| דור אלון | **AMPM** | `'AM:PM'` in account name |
| דור אלון | **Alonit** | all other (incl. אלונית and דוכן branches) |
| שוק פרטי | **Tiv Taam** | `'טיב טעם'` in account name |
| שוק פרטי | **Private Market** | otherwise |
| פז יילו / פז ילו | **Paz Yellow** | normalized (Feb file uses יילו, Dec/Jan uses ילו) |
| שפר את אלי לוי | **Alonit** | 0-unit logistics company, folded into Alonit |

**Additional chain normalizations (Icedream + Ma'ayan):**
- All וולט / וואלט / וולט מרקט variants → **Wolt Market**
- דומינוס פיצה → **Domino's Pizza**
- All chain names translated to English via `CHAIN_NAMES_EN` dict in `config.py`

These rules are implemented in `config.py → extract_chain_name(customer_name, source_chain=None)`.

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

## Decisions Already Made

1. **November 2025 excluded** — pre-launch data, distorts averages
2. **Data starts December 2025** — official launch month
3. **Ma'ayan revenue** = units × per-chain actual price from price DB (falls back to ₪13.8 for unknown chains). Maayan reports contain no revenue column — always calculated.
4. **Ma'ayan stock format** differs from Icedream: units are individual (not cartons × factor), `1/10` notation in product names
5. **Karfree PDF** uses reversed Hebrew (right-to-left rendering issue) — parser handles this
6. **Dashboard name:** "Raito Business Overview" (renamed from "Raito Dashboard")
7. **GitHub Pages:** repo `or-raito/raito-dashboard`, URL: `https://or-raito.github.io/raito-dashboard/`
8. **Returns counted correctly** — Icedream parser uses sign-flip logic, NOT abs()
9. **Branch aggregation** — All tables aggregate branches into chains via `extract_chain_name()`
10. **Three-distributor dashboard** — Dashboard has separate sections for Icedream, Ma'ayan, and Biscotti. Biscotti is placeholder until reports arrive (starts 10 Apr 2026).
11. **Karfree PDF sorting** — Uses mtime (newest file), not alphabetical sort
12. **Dashboard "Last updated" date** — Auto-pulled from latest inventory report date, shown in header
13. **Din Shiwuk / Turbo Nuts deferred** — Products still in planning (no barcodes, prices, report format). Will add distributor infrastructure when concrete.
14. **dream_cake_2 launch date** — 10 Apr 2026 (corrected from May 2026 in Master Data)
15. **Biscotti commission model** — 0% distributor commission + ₪10/cake creator commission to Daniel Amit
16. **Sales Dashboard W10 + March** — W10 (1/3/2026) added to all weekly arrays, March added as 4th active month, 4M Total label, default view switched to March
17. **Export Excel button (Sales Dashboard)** — SheetJS-based client-side 4-sheet Excel export added to Sales Dashboard header (11 Mar 2026)
18. **Rolling 10-week window** — `WEEKLY_WINDOW = 10` constant for weekly chart; oldest week drops automatically when new week is added
19. **March 2026 partial data** — W10 (1/3) + W11 (8/3) data integrated for both Icedream and Ma'ayan. Icedream source was .xls (BIFF8), converted to .xlsx via custom reader. Ma'ayan parser updated with week-number-to-month mapping.
20. **Icedream .xls conversion** — `11.3.26` (BIFF8 .xls format) converted to `icedream_mar_w10_11.xlsx` in monthly format compatible with existing parser. Original file kept for reference.
21. **Export Excel button (Business Overview)** — SheetJS-based client-side 6-sheet Excel export button added to HTML dashboard header (15 Mar 2026).
22. **Icedream stock file exclusion** — `parse_all_icedreams()` now skips files with 'stock' in the filename.
23. **Unified Dashboard (17 Mar 2026)** — BO + CC + MD tabs combined into single HTML via `unified_dashboard.py`. Deployed to GitHub Pages with sidebar navigation (Gridle CRM style).
24. **Sidebar navigation** — Replaced top tab bar with 240px left sidebar, grouped sections (Dashboard/Analytics/Data), SVG icons, active state highlighting.
25. **Modern chart design** — SVG smooth bezier curves (`_smooth_path()`), gradient area fill, no grid lines, value pill labels on data points. Chart.js charts in CC tab also modernized.
26. **Donut chart for flavors** — Replaced share bar with interactive SVG donut chart. Hover shows flavor name + % share in center. Three-column layout with "By Distributor" breakdown table.
27. **Top 10 + Show More** — Detailed Summary, Icedream Customers, Ma'ayan Chains tables show top 10 rows by revenue with expandable "Show More (N)" button.
28. **Password protection** — Client-side login gate with hash check. Password: `raito2026`. Session-persisted via sessionStorage. Set via `DASHBOARD_PASSWORD` in `unified_dashboard.py`.
29. **CC tab light theme** — Dark theme converted to light (Gridle-style) via string replacements in `_read_cc_dashboard()`. All CSS scoped under `#tab-cc` to prevent conflicts.
30. **CC Weekly chart reordered** — Weekly Sales Trend chart moved below KPI grid via HTML string manipulation in `_read_cc_dashboard()`.
31. **MD tab CRUD + brand cards (17 Mar 2026)** — Master Data tab rebuilt as fully interactive editor. Brand cards with colour-coded accent bars, sub-navigation across 9 sections, inline add/edit/delete for all 7 editable sheets, portfolio matrix, config viewer.
32. **MD tab unsaved-changes banner (17 Mar 2026)** — Yellow banner appears after any edit, reminding user to Save → replace export file → rebuild dashboard.
33. **MD two-file parser strategy (17 Mar 2026)** — `master_data_parser.py` auto-detects `Raito_Master_Data_export.xlsx`. Export file is primary source for 7 operational sheets; original file always used for Portfolio + Config (not exported by dashboard Save).
34. **MD Save to Excel (17 Mar 2026)** — "Save to Excel" button in MD tab exports all 7 editable sheets as `Raito_Master_Data_export.xlsx` using SheetJS. User replaces the file in `data/master data/` then reruns `unified_dashboard.py` to update the dashboard.
35. **JS onclick safety pattern** — All action buttons in MD tab use `data-s` / `data-i` HTML attributes instead of embedding sheet names as string literals in onclick handlers, to avoid Python/JS quote escaping issues.
36. **Warehouse Inventory KPI — flavor split (17 Mar 2026)** — Per-flavor inventory breakdown added below the big number. Colored dot + short name + units + % share. Built from `wh.get('products', {})` in `_build_month_section()`.
37. **Creators KPI — 2-column brand layout (17 Mar 2026)** — Replaced single count with 2-column CSS grid (one column per brand). Each column: brand name bold + creator name small + flavor SKU dots. Columns separated by a single vertical `border-left` line (no frames).
38. **Chart MoM % on x-axis (17 Mar 2026)** — Monthly Revenue and Monthly Sales charts now show per-month MoM % change below each x-axis label (green = growth, red = decline). Overall trend badge removed from chart header totals. KPI card trend badges also removed — replaced with "all time" label.
39. **Maayan revenue fix — actual per-chain prices (17 Mar 2026)** — `parsers.py` now loads `price data/price db - 24.2.xlsx` at parse time and computes Maayan revenue using per-chain contract prices. Chain name mapping (`_MAAYAN_CHAIN_TO_PRICEDB`) translates raw `שם רשת` values to price DB customer keys. Reduced BO vs CC revenue gap from ₪57-64k/month to <₪10k (timing noise only).
40. **Icedream Format B (weekly XLS) — custom OLE2/BIFF8 parser (17 Mar 2026)** — `icedream_15_3` is a BIFF8-format `.xls` (OLE2 compound document) that LibreOffice and openpyxl cannot read. Built a custom binary parser (`parse_xls.py`) that reads FAT sectors, follows the Workbook stream chain, and decodes BIFF8 records (SST, LABELSST, NUMBER, RK, MULRK, FORMULA). This is the only way to parse Format B Icedream files in this environment.
41. **Icedream Format B column semantics (17 Mar 2026)** — In Format B files, col 6 = total cartons/packs and col 7 = total revenue (ILS). Apply `extract_units_per_carton(item_name)` to convert cartons to individual units (same logic as Format A). Non-Raito products (`באגסו`, `דובאי`) appear in the file but are excluded by `classify_product()`. Customer name resets in col 0 only on the first product row per customer (stays empty for subsequent rows of same customer).
42. **W11 Icedreams data integrated (17 Mar 2026)** — Parsed `icedream_15_3` (Format B, created 15/3/2026). Updated dashboard: חוות נעמי mar units 352→417, revenue ₪24,373→₪29,768, danisUnits 282→347, danisRev ₪23,407→₪28,802. Weekly arrays W11 slot (was `null`) filled: combined 553u/₪26,678, turbo 272u/₪3,354, danis 281u/₪23,324. Other customers (גוד פארם, דומינוס, ינגו) unchanged.
43. **Format B vs Format A authority rule** — When both formats exist for the same period, Format B (weekly XLS from Rozit) is authoritative for totals. Format A files (XLSX) may have partial data if exported mid-week. Use Format A only for branch-level drill-down (weeklyDetail) when Format B doesn't provide branch breakdown.
44. **Year filter added to BO dashboard (18 Mar 2026)** — New "Year" filter dimension: All Years | 2025 | 2026. Selecting a year filters visible month buttons and changes the Overview to aggregate only that year's months. Dec 2025 belongs to 2025; Jan/Feb/Mar 2026 belong to 2026. Year-specific overview sections generated as `y{year}-{brand}` IDs (e.g., `sec-y2025-ab`). JS function `boSetYear()` in unified dashboard, `setYear()` in standalone. Month buttons have `data-year` attribute for toggling.
45. **Customer split in per-month flavor view (18 Mar 2026)** — "Units Sold by Flavor" per-month view now includes a "By Customer" breakdown table below the donut chart. Shows each customer (aggregated by chain via `extract_chain_name()`) with per-flavor unit columns. Top 10 shown by default with "Show More" toggle. Data sourced from `icedreams_customers`, `mayyan_accounts_revenue`, and `biscotti_customers` in monthly data.
46. **Revenue card removed from per-month view (18 Mar 2026)** — The green Revenue bar chart card that appeared in single-month BO views has been removed. Revenue data is still visible in the Overview timeline charts and in the KPI card.
47. **Year filter added to CC dashboard (19 Mar 2026)** — Same year filtering concept as BO now applied to Customer Performance tab. Year dropdown (All Years / 2025 / 2026, default 2026) injected into CC filter bar via `_read_cc_dashboard()`. Selecting a year filters the Month dropdown (2025 → only Dec, 2026 → Jan/Feb/Mar) and filters the Weekly Sales Trend chart to show only weeks belonging to the selected year. Week "28/12" maps to 2025; weeks "4/1" through "8/3" map to 2026. Year state stored in `S.year`, handled by `ccSetYear()` JS function. Weekly chart override replaces `renderWeeklyChart()` to apply year-based index filtering before the rolling window.
48. **CC weekly chart month filtering (19 Mar 2026)** — Weekly Sales Trend chart now also filters by selected month (not just year). Each week label mapped to its month via `_ccWeekMonthMap`. Helper `_ccFilteredWeekIndices()` applies both year and month filters before the rolling window slice.
49. **CC month default changed to All Months (19 Mar 2026)** — Month dropdown now defaults to "All Months" (total) instead of March. State `S.month` initialised to `'total'`, `<select>` has `selected` on the "All Months" option, `resetFilters()` resets to `'total'`.
50. **Returns KPI card translated to English (19 Mar 2026)** — Hebrew labels in the Returns KPI card replaced via string substitution in `_read_cc_dashboard()`: "החזרות — כלל" → "Returns — All", "החזרות — אייסדרים" → "Returns — Icedreams", "החזרות — מעיין" → "Returns — Ma'ayan", "אבדן הכנסה" → "Revenue Loss", "שיעור החזרה" → "Return Rate".
51. **W12 Icedream data integrated (21 Mar 2026)** — New files: `sales_week_12.xls` (Format B, BIFF8, 19/3/2026) converted to `icedream_mar_w12.xlsx` (Format A) using `xlrd`. W12 totals: 3,067 units / ₪111,979 (Turbo 2,182u/₪29,872 + Dream Cake 885u/₪82,106). Major Wolt Market expansion: 28 branches active in W12. פוט לוקר first sales (84u/₪1,302, status changed negotiation→active). CC dashboard updated: W12 added to all weekly arrays, customer `mar` totals updated, `weeklyDetail` replaced with W12 branch-level data, `productMix` updated. Icedream stock updated to 19/3/2026 (4,357 units from `stock_19_3.xlsx`).
52. **Dani's by-customer donut (21 Mar 2026)** — When a brand has only one product (e.g. Dani's with `dream_cake`), the "Units Sold by Flavor" donut is replaced by a "Units Sold by Customer" donut. Top 10 customers shown as colored segments; remaining customers grouped as "Others". Hover over a segment shows customer name + % in donut center. Legend lists customer names, units, and % share. Applies to both the overview (aggregated across all months) and per-month views. Implemented in `_build_flavor_analysis()` in `dashboard.py` via `single_product_mode = len(products_order) == 1` check.
53. **SVG timeline chart label fixes (21 Mar 2026)** — Three rendering issues fixed in `_build_svg_timeline_chart()` in `dashboard.py`: (1) Y-axis tick labels now use abbreviated format (`₪1.09M`, `₪819K`) instead of full numbers that clipped in the left margin. `mx_l` widened from 38→52 to accommodate. (2) Value pill labels above data dots are now clamped within SVG bounds — pill center constrained to `[lbl_w/2+2, w-lbl_w/2-2]` so the last point's label never bleeds off the right edge. (3) X-axis month labels now use `text-anchor="start"` for the first label and `text-anchor="end"` for the last, preventing "Jan '26" and "Mar '26" from overflowing the SVG edges. MoM % labels inherit the same anchor as their month label.
54. **CC export "Weekly Detail" sheet (22 Mar 2026)** — New 4th sheet added to the CC Excel export (before "Product Mix"). Shows rolling last-4-weeks breakdown by week × flavor × customer (network level). Each week block: flavor subtotals + blank separator row. Grand total at bottom. Data source: `weeklyDetailHistory.slice(-4)`. `_flavorOrder = ['Chocolate','Vanilla','Mango','Pistachio','Dream Cake']` controls sort order.
55. **weeklyDetailHistory — week-by-week entries (22 Mar 2026)** — Replaced single wrong "W10-W11 combined" entry (used carton counts as unit values — off by 10×) with two separate validated entries: W10 (725u/₪21,830) and W11 (553u/₪26,679). Validated against dashboard `_iceWkUnits` totals. W12 remains dynamic (IIFE from weeklyDetail). For future weeks: add a new static entry `{label:'W13|22/3/2026', rows:[...]}` using Format B data from the new `.xls` file.
56. **Format B strict product filter (22 Mar 2026)** — When parsing Format B `.xls` files, only include rows where `טורבו` OR `דרים קייק` appears in the product name. Simple flavor keyword filters (`שוקולד`, `מנגו` etc.) are insufficient — non-Icedream products like `שוקולד דובאי` and `באגסו שוקולד לבן` exist in the same file and would be falsely matched.
57. **Dynamic CC labels via DATA_LAST_WEEK (22 Mar 2026)** — All hardcoded "W10" / "W12" labels in the CC dashboard replaced with `DATA_LAST_WEEK = weeklyXLabels.length`. This means filter badges, chart subtitles, Excel headers, and month labels auto-update whenever a new entry is appended to `weeklyXLabels`. No manual label hunting needed for future week updates.
58. **Duplicate check result (22 Mar 2026)** — Full CC dashboard checked for data duplicates: `weeklyDetail` has 107 rows, all unique (0 duplicate account×product combinations). All `const` variable re-declarations are function-scope local variables (normal JS), not data conflicts. File is clean.
59. **Multi-distributor Weekly Detail (22 Mar 2026)** — `weeklyDetailHistory` rows now carry a `distributor` field (`'Icedream'` or `'מעיין'`). W10 and W11 entries include both Icedream and Ma'ayan rows. W12 IIFE stamps `distributor:'Icedream'` on its aggregated rows (Ma'ayan W12 source file not yet received). Weekly Detail export sheet redesigned: new Distributor column, grouped by week → distributor → flavor → network, with per-distributor subtotals. Ma'ayan revenue distributed proportionally from `_maayWkRev` totals since source files lack per-line pricing.
60. **Project CLAUDE.md + commands setup (22 Mar 2026)** — Added `CLAUDE.md` at project root with short orientation + 4 key rules, pointing to this briefing. Created `.claude/commands/update-week.md` (`/project:update-week [N]`) for the full weekly update workflow and `.claude/commands/validate-week.md` (`/project:validate-week [N]`) for parse-and-validate only. These persist across sessions so the W13+ update procedure is always one command away.
61. **Weekly insights deck system (22 Mar 2026)** — Created `scripts/insights_data.py`
62. **Sale Points Excel rewrite — reference format (24 Mar 2026)** — `scripts/salepoint_excel.py` fully rewritten to match `raito_salepoints_deep_dive-810ac7ed.xlsx` reference. Key changes: per-customer-group sheets (not per-branch); dark navy 2C3E50 header fill; alternating F8F9F9 rows; FDEDEC Churned / EAFAF1 Reactivated row highlights; status font colours (Active=green 27AE60, Churned=red E74C3C, Reactivated=blue 2980B9); trend column in 0% format (green/red bold); 17-column structure with precise column widths per sheet type; `_MAAYAN_CHAIN_NORM` dict to normalise inconsistent Ma'ayan chain names before grouping (prevents duplicate "פז יילו"/"פז ילו" sheets).
63. **Sale Points brand filter (24 Mar 2026)** — Brand filter bar added to Sale Points tab (All Brands / Turbo / Dani's Dream Cake). Implemented via `brandFilter` JS state variable and helper functions `spMatchesBrand(s)`, `spBrandUnits(s)`, `spBrandRev(s)`. Filter gates `getFiltered()`, KPI totals, and per-row unit/revenue display. Apostrophe in "Dani's" requires double-quoted JS string literals — single-quoted strings cause SyntaxError.
64. **Brand-specific units/revenue for Sale Points (24 Mar 2026)** — When filtering by brand, units and revenue are computed from brand-specific fields only (not total). Turbo: `choc+van+mango+pist` units × ₪13.80. Dani's: `dc` units × ₪81.10. Monthly breakdown columns use proportional fraction `brand_units/total_units` applied to each month's raw count.
65. **dream_cake_2 now active product (24 Mar 2026)** — `dream_cake_2` (Biscotti-manufactured Dream Cake, GTIN 7290117842973) added to `config.py` as an active product: `PRODUCT_NAMES`, `PRODUCT_SHORT` ("Dream Cake"), `PRODUCT_STATUS` ("active"), `PRODUCT_COLORS` (#C2185B), `FLAVOR_COLORS`, `PRODUCTS_ORDER`, `PRODUCTION_COST` (₪58.0), `SELLING_PRICE_B2B` (₪80.0), `CREATORS` (under Daniel Amit), `BRAND_FILTERS` (in 'ab' and 'danis'). Original `dream_cake` (Piece of Cake) marked as discontinued. Master data export updated with barcode, chilled storage (0-4°C), and Biscotti Chain customer at ₪80/unit.
66. **Biscotti parser live (24 Mar 2026)** — `_parse_biscotti_file()` and `parse_all_biscotti()` in `parsers.py` now parse `daniel_amit_weekly_biscotti.xlsx`. Multi-sheet format: "סיכום כללי" summary + "שבוע N" weekly sheets. Maps all data to `dream_cake_2` product key at `BISCOTTI_PRICE_DREAM_CAKE = 80.0`. First data: 121 units across 9 branches (March 2026). `consolidate_data()` products list updated to include `dream_cake_2`.
67. **dashboard.py has local overrides — ALWAYS update both (24 Mar 2026)** — `dashboard.py` defines its own `BRAND_FILTERS`, `FLAVOR_COLORS`, and several hardcoded product lists (lines ~461, ~552, ~1303, ~1412, ~1603, ~1637, ~1706) that override the `config.py` imports. When adding new products, BOTH `config.py` AND these local definitions in `dashboard.py` must be updated. This caused a bug where `dream_cake_2` was in `config.py` but missing from `dashboard.py`'s local `BRAND_FILTERS`, making Biscotti data invisible.
68. **CRITICAL build pipeline rule (24 Mar 2026)** — `CLAUDE.md` updated with explicit build pipeline: always `python3 unified_dashboard.py` → copy `docs/unified_dashboard.html` to `github-deploy/index.html`. NEVER copy `docs/dashboard.html` (raw sub-component). NEVER use `dashboard.generate_dashboard()` as final build step. This rule was added after accidentally deploying the raw dashboard.html, breaking the live unified dashboard for the team.
69. **Karfree parser — Dubai product exclusion (24 Mar 2026)** — `_classify_product_karfree()` in `parsers.py` now excludes Dubai products (שוקולד דובאי עוגה/חלב/מריר) by checking for reversed Hebrew 'יאבוד' in product text. Also fixed: when classifier returns `None`, `current_product` is now reset to `None` so data lines under excluded products don't leak into the previous product's totals. Bug was adding ~1,150 false units to chocolate/pistachio.
70. **Full EN names throughout dashboard (24 Mar 2026)** — All `PRODUCT_SHORT` references in `dashboard.py` and `unified_dashboard.py` replaced with `PRODUCT_NAMES`. Product labels everywhere now show full English names ("Turbo Chocolate", "Turbo Vanilla", etc.) instead of short names ("Chocolate", "Vanilla"). Applies to: chart legends, table headers, donut charts, customer breakdowns, inventory tables, KPI cubes, and Excel export.
71. **English chain/customer names (24 Mar 2026)** — Added `CHAIN_NAMES_EN` dict in `config.py` mapping Hebrew chain names to English (e.g. שוק פרטי → Private Market, דומינוס → Domino's Pizza, וולט מרקט → Wolt Market). Applied via `_to_en()` helper at the end of `extract_chain_name()`, so all downstream code (BO dashboard, CC dashboard, Sale Points tab, Excel export) automatically gets EN names. CC dashboard content is also bulk-replaced in `_read_cc_dashboard()` in `unified_dashboard.py`. Salepoint branch-level names remain in Hebrew (individual business names/addresses). Apostrophes in names (Domino's, Naomi's, Dani's) are escaped in JS single-quoted contexts.
72. **Chain mapping cleanup + master data EN sync (24 Mar 2026)** — דור אלון non-AMPM branches (e.g. דוכן גן שמואל) folded into Alonit (no separate "Dor Alon" bucket). שפר את אלי לוי (0 units, logistics company) also folded into Alonit. Master data Excel `Customers` sheet updated with correct EN names: Good Pharm, Domino's Pizza, Delek Menta, Wolt Market, Naomi's Farm, Yango Deli, Carmella, Noy HaSade, Paz Yellow. Added missing customers: עוגיפלצת (Oogiplatset), דור אלון (Alonit).
73. **Private Market rename (24 Mar 2026)** — שוק פרטי EN name changed from "Shuk Prati" to "Private Market" per user instruction. Updated in `CHAIN_NAMES_EN` (config.py), master data Excel, CC dashboard source file, and `_read_cc_dashboard()` in `unified_dashboard.py` (added legacy name replacement: `content.replace('Shuk Prati', 'Private Market')`).
74. **Biscotti in Sale Points tab + Excel (24 Mar 2026)** — `salepoint_dashboard.py` and `salepoint_excel.py` now process `biscotti_customers` from `consolidate_data()`. All Biscotti branches grouped under "Biscotti Chain" customer (distributor: Biscotti). Pink distributor badge (`.sp-dist-bis`). DC column combines `dream_cake` + `dream_cake_2` in both dashboard and Excel. First data: 9 branches, 121 units, ₪9,680 revenue (Mar 2026). Dani's brand filter revenue updated to ₪80.0/unit (was ₪81.1 — now matches `dream_cake_2` B2B price). Total sale points now 1,261 across 18 customers.
75. **Export modal wired correctly (24 Mar 2026)** — `runExport()` reads brand via `_emcGetBrand()` (radio) and distributor via `_emcGetDist()` (radio) instead of stale checkbox selectors. `spExportToExcel` given a `selDist` parameter — filters by `c.distributor !== selDist` when not 'all'. CC brand filter operates at product level (`_ccFlavorIncluded`, `_ccProductIncluded`) not just customer level.
76. **Export button moved to sidebar footer (24 Mar 2026)** — All per-tab and global floating export buttons removed. Single "Export Excel" button in `.sidebar-footer` (already `position:fixed`) — immune to CSS scroll-container quirks. Root cause of old scrolling bug: `overflow-x:hidden` on `.main-content` implicitly creates a scroll container, making `position:fixed` anchor to `.main-content` instead of viewport. Sidebar approach bypasses this entirely.
77. **CC tab header/banner removed + filter bar restyled (24 Mar 2026)** — Removed `.header` div (title, ISR/Ice Cream/Frozen/Sales Data Loaded/W12 partial badges) and `.info-banner` green box from CC source file. Filter bar restyled to match BO: `padding:16px 32px`, uppercase bold labels with `letter-spacing:0.8px`, `var(--surface)`/`var(--border)`/`var(--text2)`. Override CSS block in `unified_dashboard.py` updated to match (was previously overriding the source CSS with old compact style).
78. **CC body extraction regex fix (24 Mar 2026)** — `_read_cc_dashboard()` in `unified_dashboard.py` was looking for `<div class="header">` to start body extraction. After header removal, regex matched nothing → blank CC tab. Fixed to match `<div class="filter-bar">` first, with `<div class="header">` as fallback for backward compatibility.
79. **CC filter bar two-row layout (24 Mar 2026)** — Added `flex-direction:column; gap:0; align-items:stretch` to `#tab-cc .filter-bar` in `unified_dashboard.py`. Old `align-items:center` with `flex-direction:column` caused each filter row to shrink-wrap its content and float horizontally centered. Also removed top gap: changed `position:sticky; top:49px` → `top:0` (no sticky header above the filter bar in the CC tab). Both fixes now live in `unified_dashboard.py` CSS override block and persist across rebuilds.
80. **Weekly chart visual overhaul (24 Mar 2026)** — Five improvements to the `renderWeeklyChart` override in `unified_dashboard.py`: (1) Removed "22/3" (W13) from `weeklyXLabels` in the CC source file — partial Biscotti data was collapsing the chart line to near-zero. (2) Replaced `toLocaleString()` with regex `_comma` formatter for comma thousands separators (Hebrew locale suppresses `toLocaleString`). (3) Added `weeklyValueLabels` inline Chart.js plugin (canvas `afterDraw`) drawing white pill + colored text value labels above each data point, font size 12px bold. (4) Added `ctx.clearRect(...)` before `new Chart()` to prevent ghost labels from the original `renderWeeklyChart` executing on page init. (5) Added `datalabels: false` in chart options to block global datalabels plugin. **Critical architecture note:** `unified_dashboard.py` injects a `renderWeeklyChart = function(){...}` override at build time. The CC source file (`customer centric dashboard 11.3.26.html`) also defines the original function — both exist in the final HTML. The override at the bottom wins, but the original runs once on page init before it is overwritten. All label/formatting work must be in the override in `unified_dashboard.py`.
81. **BO table alignment — all tables (24 Mar 2026)** — Replaced flat left-align CSS for `#tab-bo .tbl` headers and cells with column-specific rules in `unified_dashboard.py`: all `th` center-aligned with heavier weight (`font-weight:700`, `border-bottom:2px`, `color:var(--text2)`); `th:first-child` and `th:nth-child(2)` left-aligned (month/name columns); all `td` center-aligned; `td:first-child` and `td:nth-child(2)` left-aligned. Added `tbl-prod-rank` CSS class and override rule `nth-child(n+2)` center for product ranking tables which have only 1 text column. Also applied directly to bare inline-styled tables in the BO HTML via string replacement for `<th>` and `<td>` cells.
82. **SP table header improvements (24 Mar 2026)** — In `salepoint_dashboard.py`: `.sp-tbl thead th` color changed from `var(--text-muted)` → `var(--text2)` (more readable), letter-spacing `0.3px` → `0.5px`. `.sp-col-name` min-width `200px` → `120px` (was too wide). Summary table `<th>Customer</th>` and `<th>Distributor</th>` given `class="sp-col-name"` so their header cells left-align to match their data cells.
83. **All visual fixes backported to source scripts (24 Mar 2026)** — Items 79–82 above were first applied directly to `docs/unified_dashboard.html` during a visual QA session. They have been backported into `scripts/unified_dashboard.py` (CC filter bar, weekly chart, BO table CSS) and `scripts/salepoint_dashboard.py` (SP table CSS) so they survive every future `python3 unified_dashboard.py` rebuild. Verified by rebuilding from scripts and grepping for all fix markers in the output.
84. **CC filter bar layout correction (24 Mar 2026)** — After a CC source file update, the filter bar broke: every filter (Customer, Distributor, Status, Year, Month, Brand) appeared stacked on its own full-width line. Root cause: decision #79 set `flex-direction:column; align-items:stretch` which was appropriate when the filter bar had explicit row-wrapper divs. The updated CC source file has flat fgroups as direct children — no row wrappers — so `flex-direction:column` stacked each fgroup on its own line. Fixed in `unified_dashboard.py` to `flex-direction:row; flex-wrap:wrap; gap:10px 20px; align-items:center; padding:12px 24px`. **Rule: if the CC filter bar ever breaks into a vertical stack, check whether `flex-direction:column` is set and whether the source file still uses row-wrapper divs.**
85. **CC tab refactored to cc_dashboard.py (25 Mar 2026)** — The CC tab was migrated from an HTML source file (`dashboards/customer centric dashboard 11.3.26.html`) to a pure Python script `scripts/cc_dashboard.py` (2,332 lines). `unified_dashboard.py` now imports `from cc_dashboard import build_cc_tab` and calls `build_cc_tab()` at line ~1931. The old `_read_cc_dashboard()` function is still defined but is dead code. **All CC tab visual/CSS/JS changes must now go into `scripts/cc_dashboard.py`** — not the old HTML source file, not `unified_dashboard.py`. The refactor initially lost several visual fixes (Pareto K/M formatter, Portfolio dashed partial line, dynamic subtitle, W13 removal) which were restored in decisions 86–89.
86. **Pareto K/M formatter restored in cc_dashboard.py (25 Mar 2026)** — `renderPareto()` now uses `_fmtK`/`_fmtBar` helpers for K/M Y-axis ticks, bar datalabels, and tooltips. Same logic as before: `≥1M → xM`, `≥1K → xK`, else raw integer. Revenue mode prepends `₪`.
87. **Portfolio Revenue Trend — dashed partial + dynamic subtitle restored (25 Mar 2026)** — `renderTrend()` in `cc_dashboard.py` now: (1) uses `segment.borderColor`/`borderDash` to draw the last month's line segment in grey dashed style; (2) colors the last point grey (`ptColors`); (3) dynamically updates `#trend-subtitle` text to show last complete month and current partial month with `DATA_LAST_WEEK` label. Subtitle HTML element given `id="trend-subtitle"`.
88. **W13 ("22/3") removed from weeklyXLabels (25 Mar 2026)** — Biscotti W13 partial data (20 units) causes the combined weekly chart line to collapse near zero. "22/3" removed from `weeklyXLabels` in `cc_dashboard.py`. The commented-out line above the active definition serves as a reminder of the pre-W13 state. Re-add "22/3" only when full W13 data is available from all distributors.
89. **Top Customers chart — Icedream prefix + bar alignment (25 Mar 2026)** — In `dashboard.py`: (1) Icedream customers now prefixed `"Icedream: {chain}"` to match `"Ma'ayan: ..."` and `"Biscotti: ..."` format. (2) `_bar_html()` label column changed from `min-width:100px` to `width:200px;min-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis` so all bars start at the same horizontal position. (3) Karfree inventory bars similarly fixed: label column `min-width:80px` → `width:140px;min-width:140px;white-space:nowrap`.
90. **BO table alignment convention codified (25 Mar 2026)** — All numeric columns in BO tables must use `text-align:center` (never `right`). Two table types: (1) `.tbl` class tables — styled via CSS in `unified_dashboard.py`: default first 2 columns left, rest center. Product-only tables (single text column) use `class="tbl tbl-prod-rank"` so column 2+ overrides to center. (2) Inline-styled tables (no `.tbl` class, e.g. "By Distributor", "By Customer") — set `text-align:center` on every numeric `<th>` and `<td>` explicitly. Convention documented in `dashboard.py` docstring header. **Rule: when adding any new BO table, follow this convention.**
91. **CC `customers[]` and `productMix{}` wired to live parsers (25 Mar 2026)** — Added `_compute_cc_dynamic_data(data)` to `scripts/cc_dashboard.py`. Accepts the shared `data` dict — no independent file parsing. Sources: `icedreams_customers` for Icedream per-customer data; `mayyan_accounts` for Ma'ayan (all chains, correctly splits AMPM/Alonit and Tiv Taam/Private Market); `biscotti_customers` for Biscotti. Ma'ayan revenue comes pre-priced from `by_account` (applied at parse time via `_mayyan_chain_price()` per row). `build_cc_tab(data)` injects `customers[]`, `productMix{}`, and `productPricing{}` via `re.sub`. `_CC_CUSTOMER_META` retains only structural fields (name, status, distributor, dist_pct, activeSKUs, hasPricing, hasSales, brands) — all financial fields removed. avgPrice, grossMargin, opMargin, momGrowth computed dynamically from aggregated transaction data. **For W13+: drop new files into `data/icedreams/` and `data/mayyan/` — parsers auto-pick them up on next rebuild. No manual customer total updates needed.**
92. **CC weekly chart hidden when customer filter is active (25 Mar 2026)** — The Weekly Sales Trend chart uses portfolio-level arrays (`_iceWkRev`, `_maayWkRev`) with no per-customer breakdown. When a specific customer was selected (e.g. Foot Locker), the chart showed misleading ₪599K portfolio peaks. Fix: at the top of the active `renderWeeklyChart = function()` override (in `cc_dashboard.py`), check `S.cust !== 'all'`. If true: hide `#weekly-chart-wrap`, show `#weekly-no-cust` info banner ("Weekly trend shows portfolio-level data — select All Customers to view"), destroy any existing chart instance, and return early. Both div elements are in the weekly panel HTML in `_CC_HTML`. **Architecture note:** the `function renderWeeklyChart()` declaration is dead code (hoisted but overridden by the assignment block). All chart logic and guards must live in the `renderWeeklyChart = function()` override, not the declaration.
93. **SSOT Refactoring — Phase 1: Pricing & Business Logic Engines (25 Mar 2026)** — Created `scripts/pricing_engine.py` and `scripts/business_logic.py` as the Single Source of Truth for all pricing and status/trend logic. **Pricing engine** (`pricing_engine.py`): Two-tier API — `get_b2b_price(sku)` for SP/BO flat prices, `get_customer_price(sku, customer_en)` for CC negotiated prices. Absorbs all 14 previously scattered price declarations. Raises `KeyError` on unknown SKUs to prevent silent failures. Includes Ma'ayan price-DB integration (migrated from `parsers.py`). JS code-gen helpers inject prices into templates — no more `* 13.8` or `* 80.0` literals in JS. **Business logic engine** (`business_logic.py`): Canonical `compute_status()` and `compute_trend()` functions — Option A design (pre-compute in Python). SP dashboard now ships pre-computed status/trend in JSON (no JS-side re-derivation). Unified status taxonomy: "mar>0 AND any prior>0 → Active" (dashboard rule wins over Excel's stricter "feb>0" requirement). Both `salepoint_dashboard.py` and `salepoint_excel.py` refactored to import from engines. `unified_dashboard.py` SP Excel export JS also uses engine-injected prices.
94. **SSOT Refactoring — Phase 2: Product Registry (25 Mar 2026)** — Created `scripts/registry.py` as the single source for product catalog, brand memberships, and customer hierarchy. `Product` class with `sku`, `name`, `brand`, `status`, `manufacturer`, `is_turbo()`, `is_danis()`. Derived lookups (`PRODUCT_NAMES`, `PRODUCT_SHORT`, `ACTIVE_SKUS`, `TURBO_SKUS`, `DANIS_SKUS`, `BRANDS`) auto-generated from the master `PRODUCTS` dict. `validate_sku()` raises on unknown SKUs — call at data-ingestion boundaries. **Customer hierarchy** (semantic rename from "chain"): `CUSTOMER_NAMES_EN` and `CUSTOMER_PREFIXES` moved from `config.py` to `registry.py`. `config.py` re-exports `CHAIN_NAMES_EN = CUSTOMER_NAMES_EN` for backward compat. Terminology: "Customer" = top-level entity (AMPM, Alonit), "Branch" = sub-customer / sale point. Prepared for future SQL migration.

95. **Phase 4 — CC single data pipeline, zero hardcoding (25 Mar 2026)** — CC tab now consumes the exact same `data` dict as BO via `build_cc_tab(data)`. All static price literals removed from `_CC_CUSTOMER_META` (avgPrice, grossMargin, opMargin, momGrowth — all 20 entries). `_cc_customer_price()` function deleted. `by_account` format changed from `{product: units_int}` to `{product: {units: int, value: float}}` — pricing applied at parse time per row in `parse_all_mayyan()` via `_mayyan_chain_price()`. `_build_product_pricing_js()` generates `const productPricing = {...}` entirely from `load_mayyan_price_table()` and `get_customer_price()` — zero hardcoded literals. Added `_CC_ID_TO_PRICEDB_CUST`, `_CC_ID_TO_PRICING_EN`, `_CC_CUST_SKUS` mapping dicts. `salepoint_dashboard.py` and `salepoint_excel.py` updated for new `{units, value}` `by_account` format. `unified_dashboard.py` updated to pass `data` to `build_cc_tab(data)`.

96. **CC KPI year filter fix (25 Mar 2026)** — When Year=2026 and Month=All Months, CC KPIs were including Dec 2025 revenue (showing ₪4M+ instead of correct ₪2.5M). Root cause: `getRevField(c)`, `getUnitField(c)`, `portfolioMonthly()`, and `renderKPIs()` all ignored `S.year` in total mode. Fixed: `getRevField` returns `r.jan+r.feb+(r.mar||0)` when year=2026; `getUnitField` likewise; `portfolioMonthly()` filters to year-matching months only; `renderKPIs()` `curRev`/`curUnits` use `list.reduce(getRevField)` for total mode. KPI labels: "All Months '26" / "Total '26".

97. **BO/CC revenue parity — gap root causes fixed (25 Mar 2026)** — After Phase 4, a residual ₪50,190 / 1,154-unit gap remained. Two root causes found and fixed: (1) **March W10/W11 unattributed**: `icedream_mar_w10_11.xlsx` has no bold customer-summary rows → 1,278 units/₪48,509 landed in BO's flat `combined` totals but never in `icedreams_customers`. Fixed in `parse_all_icedreams()`: after all `.xlsx` files are parsed, scan for `.xls` Format B files and merge W0..W(N-2) per-customer data into `by_customer` for any month where flat totals exceed customer-attributed totals. (2) **Good Pharm Feb return filtered**: -124 units/+₪1,682 credit note was dropped by `consolidate_data()` `total_u > 0` guard. Fixed to `total_u != 0`. (3) **CC clamp updated**: clamp now zeroes units when negative but preserves positive revenue (credit-note scenario) — only zeros revenue when revenue itself is negative. Result: 0 unit gap, sub-₪1 rounding residual. Both BO and CC show 129,072 units / ₪2,536,266 for 2026.

98. **W13 Icedream data integrated (28 Mar 2026)** — File `data/icedreams/week13.xlsx` (15/3/2026). All Turbo, 970 individual units (correct: 120 cartons × pack-size multiplier via `extract_units_per_carton`; previous incorrect value was 1200 units which ignored pack sizes). Revenue ₪13,493 (from actual invoice values in the file). No Dani's Dream Cake in W13. Six JS arrays updated in `scripts/cc_dashboard.py`: `_iceWkRev`, `_iceWkUnits`, `_iceWkRevTurbo`, `_iceWkUnitsTurbo`, `_iceWkRevDanis` (0), `_iceWkUnitsDanis` (0). **Rule: always use `extract_units_per_carton(item_name)` to convert cartons → individual units. Never use raw carton quantity as the unit count.**

99. **CC Weekly Sales Trend — 3 separate distributor lines (28 Mar 2026)** — The "Weekly Sales Trend — Icedreams · Ma'ayan · Biscotti" chart was showing a single "All Distributors" line instead of 3 separate coloured lines. Root cause: `_mkWeeklyDatasets()` `dk === 'both'` branch was returning a single merged dataset. Fixed in `scripts/cc_dashboard.py`: `dk === 'both'` now builds a `dsList` array with one dataset per distributor (Ice blue, Ma'ayan green, Biscotti orange) and returns it, matching the same structure as the individual distributor branches. **Rule: any new distributor added to the CC tab must also be added to the `dsList` array in the `dk === 'both'` branch.**

100. **Agent system deployed to Cloud Run Jobs (27–28 Mar 2026)** — Five autonomous agents deployed as Cloud Run Jobs. See `RAITO_AGENTS.md` for full documentation. Key architecture decisions: (1) Cloud Run Jobs (not Services) — stateless, scheduled, cost-efficient. (2) All state in PostgreSQL `agent_state` table. (3) Inter-agent communication via `agent_signals` table, not HTTP. (4) Cloud SQL socket requires `--set-cloudsql-instances` flag on every job create/update — without it the job silently fails with a filesystem error. (5) Slack webhook stored in GCP Secret Manager as `raito-slack-webhook` v2. (6) Agent image is separate from the Flask dashboard image: `raito-agents:latest` (not `raito-dashboard:latest`).

101. **QA agent — cross-tab parity via GitHub Pages (28 Mar 2026)** — QA agent fetches `https://or-raito.github.io/raito-dashboard/` (not the Flask server URL) to extract BO/CC/SP revenue totals for parity checks. The Flask server HTML does not contain the BO regex patterns. Parity tolerances: BO↔SP warn>0.5%/fail>2%; BO↔CC warn>3%/fail>10% (CC uses different pricing, gap is structural). When `bo==0` (fetch failed) the check produces `_warn` not `_fail`. `db_row_count` threshold is ≥1 (not 1000 — `weekly_chart_overrides` only populated on upload). **Two-URL rule in QA agent: `CLOUD_RUN_URL` for endpoint check only; `DASHBOARD_HTML_URL` for all parity extraction.**

102. **Insight Analyst rewritten — correct DB schema + SP tracking (28 Mar 2026)** — Old version queried `sales_transactions` which does not exist. Rewritten to use `weekly_chart_overrides` exclusively for distributor-level KPIs. Added `_salepoint_kpis()` which fetches `window.__SP_DATA__` from GitHub Pages HTML and analyses all 1,200+ sale points for status breakdown, at-risk list, new salepoints, and trend summary. See `RAITO_AGENTS.md` for full KPI table. `DASHBOARD_HTML_URL` constant defined at module level. SP data extraction uses `re.search(r"window\.__SP_DATA__\s*=\s*(\{.*?\});\s*\n", html, re.DOTALL)`.

103. **Actual DB schema vs. planned schema (28 Mar 2026)** — The Phase 4 section of this briefing documents the full intended schema (`sales_transactions`, `ingestion_batches`, `sale_points`, etc.). In practice, only `weekly_chart_overrides` and `master_data` are populated. The planned schema tables exist in `scripts/db/schema.sql` but were never fully populated via `raito_loader.py`. Any new agent code must query `weekly_chart_overrides` (distributor/week_num/units/revenue), NOT `sales_transactions`. The full SQL pipeline (raito_loader, migrate_transactions) is still available for future use if the team decides to populate the transactional tables.

104. **GitHub Pages deprecated — Cloud Run is sole dashboard URL (29 Mar 2026)** — `https://raito-dashboard-20004010285.me-west1.run.app` is the only live dashboard. GitHub Pages (`or-raito.github.io/raito-dashboard`) is no longer maintained. All 5 agent URLs updated to Cloud Run. QA agent uses `CLOUD_RUN_URL` for endpoint check and `DASHBOARD_HTML_URL` (same URL) for parity extraction. CLAUDE.md updated to reflect Cloud Run as the deploy target. The `cp docs/unified_dashboard.html github-deploy/index.html` step is removed from the build pipeline.

105. **All 5 agents fixed — sales_transactions→weekly_chart_overrides (29 Mar 2026)** — Every agent referenced `sales_transactions` which doesn't exist. Fixed across: `insight_analyst.py` (full rewrite), `qa_agent.py` (URLs updated), `ux_architect.py` (`_propose_new_charts` + `_propose_api_endpoints` rewritten), `data_steward.py` (`_validate_integrity` + dedup SQL), `devops_watchdog.py` (placeholder URL replaced). All now query `weekly_chart_overrides` only.

106. **Mobile responsive v1 — initial layout (29 Mar 2026)** — Added `@media (max-width:768px)` block to `scripts/unified_dashboard.py` (source of truth for all CSS). Sidebar hidden on mobile, bottom tab bar shown, KPIs reflowed to 2-column grid, tables horizontally scrollable, filter bars wrapped, SVG charts responsive, CC drawer full-width. Desktop layout unchanged. First deploy confirmed functional but UX quality was poor ("looks like shit").

108. **Dashboard data source reverted to Excel parsers (29 Mar 2026)** — `_generate_dashboard_html()` in `db_dashboard.py` was using `get_consolidated_data()` (reads `sales_transactions` table in Cloud SQL). Root cause discovered: `sales_transactions` and related Phase-4 tables (`products`, `customers`, `distributors`, `ingestion_batches`) do NOT exist in the live Cloud SQL instance — only `weekly_chart_overrides` and `master_data` exist. Fix: replaced `get_consolidated_data()` with `parsers.consolidate_data()` (Excel-based SSOT). Upload route also simplified: removed `load_caches()` + `load_*_sales()` calls (which also need `products` table). Upload now does: (1) `_copy_to_data_folder()` → copies file to data/ subfolder so parsers pick it up on next cache miss, (2) writes to `weekly_chart_overrides` (for agents), (3) invalidates `_cached_html`. Result: uploading a file → dashboard regenerates from Excel parsers → BO/CC/SP update automatically. Limitation: uploaded files are lost on container restart (next Docker deploy). NEVER re-add `get_consolidated_data()` to `_generate_dashboard_html()` without first verifying that all Phase-4 tables (`sales_transactions`, `ingestion_batches`, `products`, `customers`, `distributors`) exist and are populated in Cloud SQL.

107. **Mobile responsive v2 — full UX redesign (29 Mar 2026)** — Complete rewrite of mobile CSS after v1 feedback. Key changes: (1) **Mobile header bar** — frosted-glass sticky header with Raito logo, dynamic page title (syncs on tab switch via `mobileTabSync()`), refresh button. (2) **Redesigned bottom tab bar** — 72px height, `env(safe-area-inset-bottom)` for notch phones, pill-shaped `.mtab-icon` containers with indigo highlight on active state, press-scale animation. (3) **Proper sizing** — base font 14px, KPI numbers 20px, labels 10px, card padding 16px, border-radius 16px throughout. (4) **Horizontal-scroll filter bars** — `flex-wrap:nowrap; overflow-x:auto` with hidden scrollbars instead of wrapping chaos. (5) **Touch targets** — minimum 34–36px height on all interactive elements; input fields 16px font to prevent iOS auto-zoom. (6) **UX polish** — scroll-to-top on tab switch, SP KPIs as 2×2 grid with background cards, CC drawer pull handle, modals capped at 85vh. (7) **400px breakpoint** — single-column KPIs + SP KPIs on very small phones. All changes in `scripts/unified_dashboard.py` only. **Rule: Dockerfile is at repo root (`./Dockerfile`), not `deploy/dashboard/Dockerfile`.**


---

## Current Data State (as of March 28, 2026)

### Sales

| Month | Total Units | Revenue (₪) | Ma'ayan units | Icedream units | Biscotti units |
|---|---|---|---|---|---|
| Dec '25 | 83,753 | 1,559,374 | 61,739 | 22,014 | 0 |
| Jan '26 | 51,131 | 1,092,105 | 30,353 | 20,778 | 0 |
| Feb '26 | 58,331 | 1,084,381 | 43,777 | 14,554 | 0 |
| Mar '26 (W10-W13) | ~20,580 | ~392,648 | 15,144 | ~5,315 | 121 |
| **Total** | **~213,795** | **~₪4,128,508** | **151,013** | **~62,661** | **121** |

> W13 (15/3/2026) added 28 Mar 2026: Icedream 970 units / ₪13,493, all Turbo, no Dani's Dream Cake. Source: `data/icedreams/week13.xlsx`. Ma'ayan W13 not yet received. Biscotti first data: 121 units of Dream Cake across 9 branches, `daniel_amit_weekly_biscotti.xlsx`.

**Cross-tab parity snapshot (28 Mar 2026):** BO=₪4,010,667 | CC=₪4,018,097 | SP=₪4,010,622 | BO↔SP gap ₪45 (0.00%) | BO↔CC gap ₪7,430 (0.18%) — all within acceptable thresholds.

### Inventory Snapshot (24/03/2026)

| Location | Units | Report Date |
|---|---|---|
| Karfree warehouse | 71,120 | 24/03/2026 |
| Icedream distributor | 4,357 | 19/03/2026 |
| Ma'ayan distributor | 8,710 | 15/03/2026 |
| **Total** | **84,187** | |

Karfree breakdown (24/03/2026): Mango 26,400 · Vanilla 23,430 · Chocolate 14,400 · Pistachio 6,890.

---

## Returns Data

### Identification in raw data
- **Ma'ayan:** Negative values in 'כמות בודדים' column (Mayyan_Turbo.xlsx + maay_feb_full.xlsx)
- **Icedream:** Positive quantity with negative revenue in monthly sales files

### Returns by month

| Month | Ma'ayan Units | Ma'ayan ₪ | Ma'ayan Rate | Icedream Units | Combined Rate |
|---|---|---|---|---|---|
| Dec '25 | 13,237 | ₪172,346 | 15.0% | 0 | 12.2% |
| Jan '26 | 1,453 | ₪18,918 | 4.4% | 0 | 2.8% |
| Feb '26 | 3,993 | ₪51,989 | 7.7% | 124 | 6.3% |
| **Total** | **18,683** | **₪243,253** | **10.8%** | **124** | **8.4%** |

### December returns anomaly
3 customers account for 57% of all December returns — likely credits on initial launch stock:
- **המתוקים של שטרית ב"ש**: 3,120 units (invoices: 4013854, 4016782, 4022185, 4025305)
- **דור אלון AM:PM הנשיא הרצליה**: 2,232 units (invoices: 4014793, 4019396, 4037205)
- **ארומה סלעית המדבר אילת**: 2,202 units (invoices: 4016780, 4032948, 4039343, 4039346)

These customers don't appear in November — likely credits for initial stock. Verification sent to Ma'ayan, pending response.

### Icedream Feb returns (Good Farm only)
- Vanilla 6-pack: 9 cartons = 54 units | ₪803.77
- Mango 6-pack: 5 cartons = 30 units | ₪451.88
- Chocolate 10-pack: 4 cartons = 40 units | ₪426.56
- **Total: 18 cartons = 124 units | ₪1,682**

### Sales Dashboard KPI
"Customers w/ Sales" KPI was replaced with a dynamic "Returns" KPI, filtered by distributor. Color coding: red ≥12% | orange ≥6% | green below.

---

## Parser Traps — Do Not Repeat These Mistakes

These are things that look reasonable but are wrong. Verified through painful experience.

**Ma'ayan: always use the detail sheet, never the pivot sheet**
The Ma'ayan Excel files contain two sheets: `טבלת ציר` (pivot) and `דוח_הפצה_גלידות_טורבו__אל_פירוט` (detail). `parsers.py` explicitly skips the pivot sheet via `SKIP_KEYWORDS = ('ציר', 'סיכום', 'summary', 'pivot', 'totals')` because it double-counts rows. Any code that reads Ma'ayan files must use the detail sheet only. The sheet-selection priority in `parse_mayyan_file()` is: sheet containing 'פירוט' → sheet containing 'דוח' but not in SKIP_KEYWORDS → any non-pivot sheet → last sheet as fallback.

**Ma'ayan: revenue is per-row from price DB, never a flat rate**
Ma'ayan files have no revenue column. Revenue is calculated row-by-row: `_load_mayyan_price_table()` loads the latest price DB file from `data/price data/price db*.xlsx`, then `_mayyan_chain_price(price_table, chain_raw, product)` looks up the per-chain price for each transaction row. ₪13.80 is the last-resort fallback only (used when a chain has no entry in the price DB at all). Using ₪13.80 as a default produces materially wrong revenue — chains like פז ילו are ₪11.00, שוק פרטי is ₪14.10, דור אלון is ₪12.27.

**Weekly overrides must reuse parsers.py, not re-implement parsing**
`_extract_week_overrides()` in `db_dashboard.py` is responsible for extracting per-week unit and revenue totals from uploaded files. For Ma'ayan this means calling `parse_mayyan_file()` (or its sub-functions) from `parsers.py` — grouping the result by week number from the 'שבועי' column. Never build a parallel parser inline in `db_dashboard.py`.

**Icedream sign convention: negative = sale**
Icedream reports use negative quantities for sales and positive for returns. Always flip the sign (`-q`, `-r`) when summing — never use `abs()`.

---

## Known Data Quality Notes

- **דלק Jan**: CP (Sales Dashboard) shows 1,504 (corrected), raw Ma'ayan parse gives 1,524 — 20-unit correction applied historically
- **טיב טעם Jan**: CP shows 944 (corrected), raw Ma'ayan parse gives 1,118 — 174-unit correction applied historically. Both corrections sum to correct chain totals — likely reclassification between branches.
- **גוד פארם**: Jan active (1,128 units). Feb: 124-unit return (credit note, +₪1,682). Mar W10+W11: 104 units, W12: 52 units (156 total). Returns now pass through to CC after filter fix (25 Mar 2026).
- **January duplicate**: Two files existed for January Icedream. `icefream - January - CUSTOMERS .xlsx` was identical to `icedream - January.xlsx` (20,778 each). CUSTOMERS file archived to prevent double-counting.
- **February partial files**: Multiple partial Feb files were uploaded before the complete ones. All archived in `_archive/` subfolder.
- **Upload file corruption**: Excel files uploaded via chat consistently become 0 bytes. Workaround: user places files directly in the workspace folder.
- **Karfree parser sort fix (10 Mar 2026)**: Was using alphabetical sort (picked `stock_4.3.pdf` over `10:3:26.pdf`). Fixed to mtime sort to always use newest report.
- **כרמלה Dream Cake (Sales Dashboard)**: Was counted per box instead of individual units (1 box = 3 units). Fixed: Jan 30→90, Feb 15→45, productMix dream_cake 45→135.

---

## Open Items

| Item | Status | Owner |
|---|---|---|
| Biscotti parser (`parse_all_biscotti`) | ✅ First data parsed (121 units, Mar 2026). Integrated into SP tab + Excel. | Done |
| Din Shiwuk / Turbo Nuts integration | Not started — no barcodes/prices yet | Waiting on product data |
| Ma'ayan W10+W11 data | ✅ Received and integrated (`maayan_sales_week_10_11.xlsx`) | Done |
| Dream Cake Biscotti launch | Early sales started Mar 2026 (121 units). Formal launch 10 Apr 2026 | On track |
| ינגו דלי (Dani's) pricing | Showing ₪150/unit vs expected ₪81.2 | Under investigation |
| December credits verification | Large returns from שטרית/ארומה/דור אלון הנשיא | Awaiting Ma'ayan response |

---

## Sales Dashboard (CC tab)

**Current source:** `scripts/cc_dashboard.py` (fully dynamic Python generator — old HTML source file `dashboards/customer centric dashboard 11.3.26.html` is legacy/unused since 25 Mar 2026).
All customer data (revenue, units, margins) computed dynamically from `consolidate_data()` output — same pipeline as BO tab. Zero hardcoded price literals or static customer totals.

**Current state (25 Mar 2026):**
- Sales Data: Dec 2025 | Jan 2026 | Feb 2026 | Mar 2026 (W10-W12) — all dynamic
- Weekly Data: W1–W12 (28/12/2025 – 15/3/2026), rolling 10-week window (`WEEKLY_WINDOW = 10`) — weekly arrays still hardcoded in `cc_dashboard.py`
- Active Distributors: Icedream | Ma'ayan | Biscotti (live — 9 branches, 121 units Mar 2026)
- Default View: Year 2026 | All Months | All customers | All brands
- KPI year filter: active — "All Months '26" shows Jan+Feb+Mar only (Dec '25 excluded)

**W12 weekly snapshot (Icedream, source: `icedream_mar_w12.xlsx` converted from `sales_week_12.xls`):**
- Combined revenue: ₪111,979 | units: 3,067
- Turbo: ₪29,872 / 2,182 units | Dream Cake: ₪82,106 / 885 units
- Returns: 0 (no returns in W12)
- Major Wolt Market expansion: 28 branches active

**W11 weekly snapshot (Icedream, source: `icedream_15_3`):**
- Combined revenue: ₪26,678 | units: 553
- Turbo: ₪3,354 / 272 units | Dream Cake: ₪23,324 / 281 units

**W10 weekly snapshot (Icedream):**
- Combined revenue: ₪21,831 | units: 725
- Turbo: ₪7,803 / 602 units | Dream Cake: ₪14,028 / 123 units

**March active customers (W10-W12, Icedream):**
- וולט מרקט: 2,077 units / ₪78,278 (W12 only — 28 branches, major expansion)
- ינגו דלי: 1,018 units / ₪35,037 (W10: 445u | W12: 573u)
- דומינוס: 472 units / ₪5,407 (W10: 164u | W11: 148u | W12: 160u)
- חוות נעמי: 417 units / ₪29,768 (W10: 116u | W11: 301u | W12: 0)
- גוד פארם: 156 units / ₪2,066 (W11: 104u | W12: 52u)
- פוט לוקר: 84 units / ₪1,302 (W12 only — first sales, moved from negotiation to active)
- כרמלה: 70 units / ₪980 (W12 only)
- עוגיפלצת: 51 units / ₪7,650 (W12 only — Dream Cake)

**Rolling 10-week window:** `WEEKLY_WINDOW = 10` constant. Chart uses `.slice(-WEEKLY_WINDOW)`. When W11 is added, W1 drops automatically — no manual cleanup needed.

**Dynamic Ma'ayan array:** `_maayDataArr` is length-aware (uses `_iceWkRev.length`). Ma'ayan weeks W6–W9 filled by index. Danis brand returns `Array(len).fill(null)`. No hardcoded length — safe for future weeks.

**Export Excel button (added 11 Mar 2026):**
Library: SheetJS (xlsx 0.18.5) via cdnjs CDN — client-side, no server needed. Button in header, `onclick="exportToExcel()"` (renamed `ccExportToExcel` in unified dashboard after `_read_cc_dashboard()` injection). Filename: `Sales Dashboard - Raito DD.MM.YYYY.xlsx`. 4-sheet structure:
1. Summary — Portfolio KPIs for all 4 months + MoM%; by-distributor revenue & units breakdown
2. Customer Performance — All 19 customers: revenue & units per month, margins, MoM growth, SKUs
3. Weekly Sales Trend — W1–W{DATA_LAST_WEEK} Icedream (combined/Turbo/Danis/returns) + Ma'ayan + combined; WoW%; **flavor × customer breakdown for W12**
4. **Weekly Detail** — Rolling last-4-weeks history: week × flavor × customer. Subtotals per flavor, grand total. Source: `weeklyDetailHistory` (see below).
5. Product Mix — Per-customer SKU breakdown: chocolate/vanilla/mango/pistachio/dream_cake; totals & %

**weeklyDetailHistory architecture (updated 22 Mar 2026 — all distributors):**
`const weeklyDetailHistory` in `scripts/cc_dashboard.py` holds the rolling weekly breakdown for the "Weekly Detail" export sheet. Format: array of `{label, rows: [{distributor, network, product, units, revenue}]}`. Uses `.slice(-4)` to always show the last 4 available weeks.
- W10 and W11 are **static entries** (hardcoded). Each entry contains rows for **both Icedream and Ma'ayan**.
- W12 is **dynamically appended** via an IIFE that aggregates `weeklyDetail` (branch-level) → network-level at page load. Currently Icedream only (Ma'ayan W12 file pending).
- Future weeks: add a new static entry for each new week with rows for all available distributors.
- `distributor` field values: `'Icedream'` or `'מעיין'`. Required for export grouping.

**weeklyDetailHistory validated totals (22 Mar 2026):**
| Week | Distributor | Units | Revenue | Source |
|------|-------------|-------|---------|--------|
| W10 \| 1/3/2026 | Icedream | 725u | ₪21,830 | `sales_week_12.xls` cols 2-3 |
| W10 \| 1/3/2026 | Ma'ayan | 7,204u | ₪99,415 | `maayan_sales_week_10_11.xlsx` |
| W11 \| 8/3/2026 | Icedream | 553u | ₪26,679 | `sales_week_12.xls` cols 4-5 |
| W11 \| 8/3/2026 | Ma'ayan | 7,940u | ₪109,572 | `maayan_sales_week_10_11.xlsx` |
| W12 \| 15/3/2026 | Icedream | 3,067u | ₪111,979 | dynamic from `weeklyDetail` |

**Ma'ayan revenue method:** `maayan_sales_week_10_11.xlsx` has no per-line prices. Revenue is distributed proportionally from `_maayWkRev` totals (avg ~₪13.80/unit, consistent across W10 and W11). Formula: `row_rev = round(row_units / week_total_units * week_total_rev, 2)`.

**weeklyDetailHistory W10 networks (Icedream):** דומינוס, חוות נעמי, ינגו
**weeklyDetailHistory W10 networks (Ma'ayan):** דור אלון, דלק מנטה, סונול, פז חברת נפט-סופר יודה, פז יילו, שוק פרטי
**weeklyDetailHistory W11 networks (Icedream):** גוד פארם, דומינוס, חוות נעמי
**weeklyDetailHistory W11 networks (Ma'ayan):** same 6 networks as W10 (דלק מנטה W11 also has Pistachio)

**Weekly Detail export sheet (updated 22 Mar 2026):**
- Columns: Week | Distributor | Flavor | Customer Network | Units | Revenue (₪)
- Grouped: week → distributor (Icedream first, then מעיין) → flavor → network
- Subtotals: per flavor, per distributor-week; Grand Total at bottom
- Header: `WEEKLY DETAIL — ALL DISTRIBUTORS` (removed "Icedreams only")

**Dynamic labels (DATA_LAST_WEEK):**
`const DATA_LAST_WEEK = weeklyXLabels.length` — used throughout to replace any hardcoded "W10" or "W12" labels. All Excel header strings, filter badges, and chart subtitles reference this constant so they auto-update when a new week is added to `weeklyXLabels`.

**W11 update checklist (✅ completed 17 Mar 2026):**
- ✅ `weeklyXLabels` already included "8/3" (W11 start date) — no change needed
- ✅ W11 values filled into all `_iceWkRev` / `_iceWkUnits` / Turbo / Danis arrays (were `null`)
- ✅ `mar` customer values updated (חוות נעמי units/revenue updated from `icedream_15_3`)
- ⬜ Run Export Excel button to verify all 4 sheets generate correctly
- ✅ Rolling window: W1 drops automatically — no manual action needed
- ✅ Returns array W11 slot remains `null` (no return data in Format B weekly file)

**W12 update checklist (✅ completed 22 Mar 2026):**
- ✅ "15/3" added to `weeklyXLabels`
- ✅ W12 appended to all `_iceWkRev` / `_iceWkUnits` / Turbo / Danis arrays
- ✅ `mar` customer totals updated from `weeklyDetail`
- ✅ `weeklyDetail` replaced with branch-level W12 data
- ✅ `weeklyDetailHistory` IIFE dynamically appends W12 from `weeklyDetail`
- ✅ `weeklyDetailHistory` static entries replaced with validated W10 + W11
- ✅ All W10/W12 hardcoded labels replaced with `DATA_LAST_WEEK`
- ✅ Weekly Detail sheet added to CC Excel export
- ✅ Multi-distributor: Ma'ayan rows added to W10+W11 entries (22 Mar 2026)
- ⬜ Ma'ayan W12 weekly breakdown not yet added (waiting for source file)

**W13 update checklist (next time — use this as template):**

> **Shortcut:** run `/project:update-week 13` — the command file has all steps below built in.

**BO dashboard note:** `parsers.py` globs `data/icedreams/*.xlsx` and `data/mayyan/*.xlsx` only — it ignores `.xls` files. The BO gets its monthly March totals by accumulating all matching `.xlsx` files in those folders. Every new week needs its own `.xlsx` extract alongside the CC updates so the BO also reflects the new week.

1. Receive Format B `.xls` from Rozit Israel (Icedream W13)
2. Receive Ma'ayan W12+W13 weekly report from Ma'ayan
3. **Drop new data files — BO and CC customer totals update automatically:**
   - Save Icedream W13 data as `data/icedreams/icedream_mar_w13.xlsx` (Format A, for customer attribution)
   - Save Ma'ayan W12+W13 as `data/mayyan/maayan_sales_week_12_13.xlsx` (weekly format)
   - `parse_all_icedreams()` / `parse_all_mayyan()` auto-pick up all new files on next rebuild
   - `_compute_cc_dynamic_data(data)` re-derives all customer revenue, units, margins, momGrowth automatically — no manual updates to `_CC_CUSTOMER_META`
   - ⚠️ If the new `.xlsx` file for W13 has no customer summary rows (like `icedream_mar_w10_11.xlsx`), the `parse_all_icedreams()` Format B supplement logic will fill `by_customer` from the Format B `.xls` W0..W(N-2) columns automatically
4. **CC weekly chart arrays — still manual in `scripts/cc_dashboard.py`:**
   - Add `"22/3"` to `weeklyXLabels` — only once full W13 data available from all distributors
   - Append new values to `_iceWkRev`, `_iceWkUnits`, `_iceWkRevTurbo`, `_iceWkUnitsTurbo`, `_iceWkRevDanis`, `_iceWkUnitsDanis`
   - Add Ma'ayan W12 rows to `weeklyDetailHistory[1]` (the W12 entry, currently Icedream-only)
   - Add new static entry to `weeklyDetailHistory`: `{label:'W13|22/3/2026', rows:[...]}` with **both** Icedream and Ma'ayan rows
   - Update `weeklyDetailLabel` to `'שבוע 13 | 22/3/2026'`
   - Update `weeklyDetail` with branch-level W13 data (if Format A available)
5. Regenerate: `python3 scripts/unified_dashboard.py`
6. Copy: `cp docs/unified_dashboard.html github-deploy/index.html`
7. Push: `cd github-deploy && git push`

> ⚠️ `DATA_LAST_WEEK` auto-updates from `weeklyXLabels.length` — no manual label changes needed.

**CC tab data methodology (fully dynamic as of 25 Mar 2026):**
- All customer revenue and units derived from `consolidate_data()` output — same data object as BO tab
- Icedream revenue = actual invoice values from XLSX files (sign-flipped: negative qty = sale)
- Ma'ayan revenue = units × per-chain contract price from price DB (applied at parse time per row via `_mayyan_chain_price()`; falls back to `get_b2b_price_safe()` for unknown chains)
- Biscotti revenue = units × ₪80.0 (`BISCOTTI_PRICE_DREAM_CAKE`)
- magadat included in CC customer totals where applicable (it appears in Icedream customer breakdowns)
- avgPrice, grossMargin, opMargin, momGrowth all computed post-aggregation — no static literals
- Returns (negative-unit customers) now pass through the `icedreams_customers` filter and are handled in CC (clamp zeroes units, preserves positive credit-note revenue)
- BO and CC are revenue-parity: 0 unit gap, sub-₪1 rounding residual (25 Mar 2026)

---




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

**Critical bug fixed (27 Mar 2026):** `raito_loader.load_caches()` now also calls `migrate_transactions.load_caches()` — required because `build_transaction_row()` uses `migrate_transactions._product_cache` (its own module-level dict), which was never populated in the loader flow. Without this fix, all rows return `None` and 0 rows are inserted even though batches are created.

**--force cascade (27 Mar 2026):** When `force=True`, `create_batch()` now deletes `sales_transactions` and `inventory_snapshots` child rows before deleting the parent `ingestion_batches` row (FK constraint enforcement).

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

### Current Data State (as of 29 Mar 2026)

| Distributor | Source files in `data/` | Latest period |
|---|---|---|
| Icedream (sales) | Dec 2025–Mar 2026 | W13 (22/3/2026) — 970 units / ₪13,493 |
| Ma'ayan (sales) | Dec 2025–Mar 2026 | W13 (22/3/2026) — March total: 30,524 units / ₪416,555 |
| Biscotti (sales) | Mar 2026 | W12–W13 (daniel_amit_weekly_biscotti.xlsx) |
| Icedream (stock) | snapshot 26/3/2026 | 8,387 units, 4 products |
| Ma'ayan (stock) | snapshot 15/3/2026 | 8,710 units, 4 products |
| Karfree (warehouse) | snapshot 24/3/2026 | 71,120 units |

**Ma'ayan W10–W13 note:** Two files cover March 2026 — `maayan_sales_week_10_11.xlsx` (W10+W11) and `week12_13.xlsx` (W12+W13). `parse_all_mayyan()` merges them. Prior to 29 Mar 2026 fix, a first-file-wins bug silently dropped `week12_13.xlsx`. See decision 109.

---

### W13 Update Checklist (SQL pipeline — supplement to existing checklist)

In addition to the CC weekly chart array updates documented above:

1. Load Icedream W13 sales: `python3 scripts/db/raito_loader.py --target local --file data/icedreams/week13.xlsx --force`
2. Load Ma'ayan W13 when received: `python3 scripts/db/raito_loader.py --target local --file data/mayyan/maayan_w13.xlsx`
3. Load any new stock files: `python3 scripts/db/raito_loader.py --target local --file data/icedreams/stock26.3.xlsx`
4. Refresh live dashboard: `https://raito-dashboard-20004010285.me-west1.run.app/refresh`
5. Alternatively: use the upload page at `/upload` to drag-and-drop files directly

**Or via /upload page:** Navigate to `https://raito-dashboard-20004010285.me-west1.run.app/upload`, drag in the file, select distributor if auto-detection fails, click "Upload & Ingest". Dashboard cache is automatically invalidated on success.

---

### Known Issues & Decisions (Phase 4)

1. **`google-cloud-sql-connector` not installable** on Mac M4 or Docker linux/amd64 — package returns "no versions found". Use Cloud SQL Auth Proxy binary instead for all local dev connections.
2. **`raito_loader.py` must run from project root** — relative imports for `parsers`, `config`, `migrate_transactions` depend on the CWD being `~/dataset/`. Running via absolute path (`python3 ~/dataset/scripts/...`) breaks the import chain.
3. **Files without `.xlsx` extension are invisible to parsers** — `parse_all_icedreams()` globs `*.xlsx` only. Always ensure distributor files have the correct extension before dropping into the data folder.
4. **Icedream batch names are month-level** (e.g. `icedream_march`), not file-level — adding a new weekly file and running `--force` will re-ingest the entire month by combining all `.xlsx` files in the folder.
5. **GitHub Pages deprecated** — Cloud Run is the sole production deployment as of 27 Mar 2026. The `/refresh` endpoint force-regenerates the dashboard from Excel parsers.
6. **`weekly_chart_overrides` is the only live SQL table** — `sales_transactions`, `ingestion_batches`, `products`, `customers`, `distributors` (Phase 4 schema) were never deployed to Cloud SQL. NEVER re-add `get_consolidated_data()` to `_generate_dashboard_html()` without first verifying all Phase-4 tables exist and are populated.
7. **Local dev environment** — `raito-dev` alias starts Flask at `localhost:8080`. Requires `~/dataset/venv` activated. Run `./cloud-sql-proxy raito-house-of-brands:me-west1:raito-db` in a second tab to enable `/api/weekly-overrides` DB queries locally. Always test here before docker build + deploy.

### Decisions log (Phase 4)

**Decision 108 (29 Mar 2026):** `_generate_dashboard_html()` reverted to `parsers.consolidate_data()` (Excel-based) after discovering Phase-4 SQL tables were never deployed to Cloud SQL. Root cause: upload button appeared to work (returned 200) but dashboard showed no change because `get_consolidated_data()` silently failed on missing tables. Fix: removed all PostgreSQL ingestion from the upload route; upload now copies file to `data/` subfolder + writes `weekly_chart_overrides` + invalidates `_cached_html`. Dashboard regenerates from Excel on next request.

**Decision 109 (29 Mar 2026):** Fixed `parse_all_mayyan()` first-file-wins bug. Files are processed alphabetically; `maayan_sales_week_10_11.xlsx` set March 2026 first (15,144 units), then `week12_13.xlsx` (15,380 units) was silently dropped because the month key already existed. Fix: replaced `if month not in results: results[month] = mdata` with a proper merge accumulating `totals`, `by_account`, and `branches`. March 2026 Ma'ayan total corrected: 30,524 units / ₪416,555.

**Decision 110 (29 Mar 2026):** Fixed `parse_mayyan_file(filepath, price_table=None)` crash when called without `price_table`. Added `if price_table is None: price_table = _load_mayyan_price_table()` guard at function entry. Root cause: `_mayyan_chain_price(None, chain, product)` raised `TypeError: argument of type 'NoneType' is not iterable` at `product in price_table`.

**Decision 111 (29 Mar 2026):** Weekly chart Option B (dynamic fetch) confirmed already implemented — JS at bottom of `cc_dashboard.py` calls `fetch('/api/weekly-overrides')` on every page load and patches the hardcoded arrays with DB values. Flask endpoint `/api/weekly-overrides` (GET) reads `weekly_chart_overrides` table. Future weekly uploads auto-update the chart without code changes. Hardcoded arrays in `cc_dashboard.py` remain as base/fallback values and must be kept current as of the latest integrated file.

**Decision 112 (31 Mar 2026):** GEO tab — City boundary layer added. 429 Israeli city/town polygons loaded into `cities_geo` table (PostGIS) from GitHub open data (`idoivri/israel-municipalities-polygons`). Boundaries dropdown in GEO controls bar switches between "District" (existing `municipalities_geo`, ~15 polygons) and "City" (new `cities_geo`, 416 visible). City geometries are simplified server-side via `ST_Simplify(geom, 0.001)` to reduce payload from ~30MB to ~3MB. Frontend fetches with `cache: 'no-store'` to avoid stale empty responses. POS drill-down passes `&layer=city` so spatial lookup uses `cities_geo` instead of `municipalities_geo`.

**Decision 113 (31 Mar 2026):** GEO tab — Export/Upload buttons wired into existing sidebar buttons. Export: CSV download of POS addresses (`pos_id, pos_name, address_city, address_street`) with "All POS" or "Missing only" filter, via `/api/geo/export-addresses`. Upload: CSV import of edited addresses back to DB via `/api/geo/upload-addresses`, with optional re-geocoding of changed addresses.

**Decision 114 (31 Mar 2026):** GEO tab — Distributor filter fixed. `DISTRIBUTOR_ID_MAP` (hardcoded `{icedream:1, mayyan:2, biscotti:3}`) was wrong — actual DB IDs depend on insert order and the key is `"icedreams"` (with 's'), not `"icedream"`. Replaced with `_build_dist_clause()` that generates `sp.distributor_id IN (SELECT id FROM distributors WHERE key LIKE %s)` using pattern map `DISTRIBUTOR_KEY_PATTERNS` (`icedream→'icedream%'`, `mayyan→'mayyan%'`, `biscotti→'biscotti%'`). Also replaced `DISTRIBUTOR_NAME_MAP` in POS endpoint with a JOIN to `distributors` table for correct labels.

**Decision 115 (31 Mar 2026):** GEO tab — Map/table layout changed to 50/50 split. Map: `height: calc(50vh - 50px)`, table: same. Previous: map fixed 300px, table `calc(100vh - 300px - 100px)`. Both have `min-height: 250px`.
