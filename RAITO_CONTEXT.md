# Raito Project — Context & Business Model

> **When to load:** First conversation, onboarding, or when you need company/product/distributor context.

---

## Company Overview

**Raito** — Israeli house of brands building and distributing consumer goods across multiple categories: frozen (ice cream, cakes), protein snacks, coffee, and beverage capsules. Currently active with frozen products through three distributors (Icedream, Ma'ayan, Biscotti), expanding into additional categories in 2026.

---

## Master Data Model (canonical entity hierarchy)

> **Authoritative definition of how Raito entities relate.** All parsers, dashboards, and DB schema must respect these rules.

### Entity Hierarchy

```
Creator (person, commercial agreement with Raito)
  └─[1:1]─► Brand (one brand per creator — the creator IS the brand)
             └─[1:many]─► Category (ice_cream, protein_snacks, frozen_cakes, ...)
                           └─[1:many]─► SKU (product, defined by recipe)
                                         └─[1:1]─► Manufacturer (factory producing that SKU)
                                                    └─[manufacturer sells to]─► Distributor
                                                                                 └─[distributor assortment]

Customer Root (commercial entity, e.g. Wolt Market, Tiv Taam)
  ├─[pricing at (Customer × Distributor × SKU) grain]
  └─[1:many]─► Sale Point (physical branch, tied to the distributor that serves the order)
```

### Key Rules

**1. Creator : Brand is 1:1.**
Each creator has exactly one brand — the brand IS the creator's name/persona. Extensions happen via **categories within the same brand**, not via new brands. Example: Deni Avdjia's brand is **"Turbo by Deni Avdjia"** — today it carries the *ice_cream* category (Vaniglia-made SKUs), and from ~June 2026 it will also carry the *protein_snacks* category (Din Shiwuk-made SKUs, aka "Turbo Mix"). Daniel Amit's brand is **"Dani's"** — today *frozen_cakes* only, but the brand name is deliberately category-agnostic so future categories (e.g. frozen cookies) can live under it.

**2. Brand : Category : SKU is 1:many:many. SKU : Manufacturer is 1:1.**
A single brand can span multiple product categories, and each category contains many SKUs. Every SKU is produced by exactly one manufacturer. Different categories under the same brand can be produced by different manufacturers (Turbo ice cream = Vaniglia; Turbo Mix protein snacks = Din Shiwuk — both under brand "turbo").

**3. Manufacturer ↔ Distributor.**
A manufacturer sells its SKUs to one or more distributors. A manufacturer may also BE a distributor — Biscotti is both (manufactures Dani's Dream Cake and distributes it direct). Pure distributors (Icedream, Ma'ayan) source from a separate manufacturer (Vaniglia).

**4. Assortment Rule (CRITICAL).**
A Customer Root can only order a SKU from a distributor whose assortment carries that SKU. In practice:
- `dream_cake_*` (brand=danis, category=frozen_cakes) → only from Biscotti (Biscotti is the only distributor carrying Dani's)
- `turbo_*` ice cream SKUs (brand=turbo, category=ice_cream) → only from Icedream or Ma'ayan Frozen (they carry Vaniglia's output)
- `turbo_mix_*` protein-snack SKUs (brand=turbo, category=protein_snacks, launching ~Jun 2026) → only from Ma'ayan Ambient (carrying Din Shiwuk's output)

Wolt Market ordering Dream Cake + Turbo ice cream simultaneously means two separate distributor relationships (Biscotti for cake, Icedream/Ma'ayan for ice cream) — not one distributor serving both. The assortment is bounded by manufacturer-distributor pairing.

**5. Pricing Grain: (Customer Root × Distributor × SKU).**
Price and commission (`dist_pct`) are defined per `(Customer Root, Distributor, SKU)` triple. The same customer can have different price/commission for the same SKU depending on which distributor delivers it — though in practice the assortment rule collapses many combinations to a single valid distributor per SKU. A transaction without a negotiated price for its (customer, distributor, SKU) triple is an error state that **cannot occur** in normal operations; if it does, treat as a data-ingest bug.

**6. Customer Root : Sale Point is 1:many.**
A Customer Root (e.g. Wolt Market) has many physical branches (sale points). Each sale point appears in the system only once it shows up in distributor sales data — sale points are data-discovered, not pre-registered.

**7. New Sale Point workflow — Smart Suggest Inbox.**
When ingest sees a `branch_name_he` not in master data:
- System proposes a Customer Root based on prefix/similarity (e.g. "וולט מרקט הרצליה" → Wolt Market, high confidence)
- MD tab surfaces an **Unassigned Sale Points inbox** with pre-filled suggestions
- User confirms or overrides; mapping persists to master data
- The transaction's `sale_point_id` resolves to the correct Customer Root

Mapping lives in master data (editable), never hardcoded.

**8. Creator Commercial Terms.**
Creators earn via royalty (e.g. Biscotti pays Daniel Amit ₪10 per Dream Cake sold) or other negotiated terms. Tracking creator earnings in the dashboard is a **future requirement** — not implemented in the current scope.

---

### Brands

**Model:** Creator:Brand is 1:1. Category (product line) is a dimension of the product, NOT a separate brand. Category spans within a single brand (see **Categories per brand** below).

| Brand Key | Brand Name | Creator | Status | First Launch |
|---|---|---|---|---|
| turbo | Turbo by Deni Avdjia | דני אבדיה (Deni Avdjia) | Active | Dec 2025 |
| danis | Dani's | דניאל עמית (Daniel Amit) | Active | Dec 2025 |
| ahlan | Ahlan | Ma Kashur | Planned | Jul 2026 |
| w | W | The Cohen | Planned | Aug 2026 |

**Categories per brand:**

| Brand | Category | Manufacturer | Status | Launch |
|---|---|---|---|---|
| turbo | ice_cream | Vaniglia | Active | Dec 2025 |
| turbo | protein_snacks (Turbo Mix) | Din Shiwuk | Planned | ~Jun 2026 |
| danis | frozen_cakes | Biscotti | Active | Mar 2026 (moved from Piece of Cake) |
| ahlan | coffee | Rajuan | Planned | Jul 2026 |
| w | beverage_capsules | TBD | Planned | Aug 2026 |

> **Retired brand key:** `turbo_nuts` was an interim brand key — it has been collapsed into brand=`turbo` with category=`protein_snacks`. Do not use `turbo_nuts` for new SKUs.

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
| turbo_mix_1 | Turbo Mix SKU 1 | turbo (category=protein_snacks) | ~Jun 2026 | ₪3.35 prod cost, 60g, ambient (24°C). Manufactured by Din Shiwuk. |
| turbo_mix_2 | Turbo Mix SKU 2 | turbo (category=protein_snacks) | ~Jun 2026 | ₪3.35 prod cost, 60g, ambient (24°C). Manufactured by Din Shiwuk. |
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
