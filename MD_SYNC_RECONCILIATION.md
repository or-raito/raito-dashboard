# Master Data Sync — Reconciliation Report

**Generated:** 2026-04-16 (during Phase 0 while dev env was being deployed)
**Source:** Static analysis of `scripts/registry.py` + `scripts/master_data_parser.py`
**Companion doc:** `MASTERDATA_SYNC_PLAN.md`

## Purpose

Before Phase 1 makes `registry.py` DB-backed, identify every piece of data currently hardcoded in `registry.py` and classify it as: (a) safely migratable to the `master_data` JSONB, (b) logic/rules that must stay in code, or (c) missing from the Excel schema and would be lost without action.

---

## TL;DR — Phase 1 blockers (must address BEFORE migration)

| Item | Where today | Decision needed |
|---|---|---|
| **`CUSTOMER_PREFIXES`** (14 entries, Icedream branch-prefix matching) | `registry.py:158-164`, manually longest-first ordered | **Keep in code or new `customer_matching_rules` table.** NOT master data. |
| **`FLAVOR_COLORS`, `PRODUCT_COLORS`** (chart hex colors) | `registry.py:76-80` | **Keep in code.** Visualization config, not operational data. |
| **`PRODUCT_SHORT`** (display-short names for table rendering) | `registry.py:71` | **Keep in code or add column to Products sheet.** |
| **`CREATORS`** (brand owners: 'דני אבדיה', 'דניאל עמית') | `registry.py:103-106` | **Clarify** — belongs in MD Brands.owner or stays in code? |
| **Manufacturer key↔name mapping** | `registry.py` stores only name strings (`'Raito'`, `'Piece of Cake'`, `'Biscotti'`) inside Product objects | **Verify:** every manufacturer name used in PRODUCTS must correspond to a `key` in the Excel Manufacturers sheet. |

---

## Full inventory: `scripts/registry.py`

### Classes and data structures

| Name | Line | Size | Kind |
|---|---|---|---|
| `Product` (class) | 28-46 | 1 class, 3 methods | Class — `is_active()`, `is_turbo()`, `is_danis()` |
| `PRODUCTS` | 57-65 | 7 SKUs | Core product registry |
| `PRODUCT_NAMES` | 70 | 7 | Derived from PRODUCTS |
| `PRODUCT_SHORT` | 71 | 7 | Derived — but "short name" is display-only |
| `PRODUCT_STATUS` | 72 | 7 | Derived from PRODUCTS |
| `PRODUCT_COLORS` | 73 | 7 | Derived — hex colors |
| `FLAVOR_COLORS` | 76-80 | 7 | Hand-crafted alternative colors |
| `PRODUCTS_ORDER` | 83-86 | 7 | Display ordering |
| `ACTIVE_SKUS` | 88 | 6 | Computed filter |
| `TURBO_SKUS` | 89 | 5 | Computed filter |
| `DANIS_SKUS` | 90 | 2 | Computed filter |
| `BRANDS` | 97-101 | 3 | `ab` (all), `turbo`, `danis` |
| `CREATORS` | 103-106 | 2 | Brand owners (Hebrew names) |
| `DISTRIBUTORS` | 113-117 | 3 | `icedream`, `mayyan`, `biscotti` |
| `CUSTOMER_NAMES_EN` | 132-155 | 22 | HE → EN name mapping |
| `CUSTOMER_PREFIXES` | 158-164 | 14 | Branch-prefix list, longest-first |
| Functions | 171-205 | 5 | `validate_sku()`, `get_product()`, `get_brand_skus()`, `is_turbo_sku()`, `is_danis_sku()` |

### Sample data (verbatim)

**PRODUCTS** (all 7, lines 58-65):
```python
'chocolate':    Product('chocolate',    'Turbo Chocolate',       'Chocolate',   'turbo', 'active',       '#8B4513', 'Raito'),
'vanilla':      Product('vanilla',      'Turbo Vanilla',         'Vanilla',     'turbo', 'active',       '#F5DEB3', 'Raito'),
'mango':        Product('mango',        'Turbo Mango',           'Mango',       'turbo', 'active',       '#FF8C00', 'Raito'),
'pistachio':    Product('pistachio',    'Turbo Pistachio',       'Pistachio',   'turbo', 'new',          '#93C572', 'Raito'),
'magadat':      Product('magadat',      'Turbo Magadat',         'Magadat',     'turbo', 'discontinued', '#999999', 'Raito'),
'dream_cake':   Product('dream_cake',   "Dani's Dream Cake",     'Dream Cake',  'danis', 'discontinued', '#4A0E0E', 'Piece of Cake'),
'dream_cake_2': Product('dream_cake_2', 'Dream Cake - Biscotti', 'Dream Cake',  'danis', 'active',       '#C2185B', 'Biscotti'),
```

**DISTRIBUTORS** (all 3):
```python
'icedream': {'name': 'Icedream',               'name_heb': 'אייסדרים',       'brands': ['turbo', 'danis']},
'mayyan':   {'name': "Ma'ayan",                'name_heb': 'מעיין נציגויות', 'brands': ['turbo']},
'biscotti': {'name': 'Biscotti (ביסקוטי)',     'name_heb': 'ביסקוטי',        'brands': ['danis']},
```

**CUSTOMER_PREFIXES** (verbatim, hand-ordered):
```python
CUSTOMER_PREFIXES: list[str] = [
    'דומינוס פיצה', 'דומינוס', 'גוד פארם', 'חוות נעמי', 'נוי השדה',
    'וואלט', 'וולט', 'ינגו',
    'חן כרמלה', 'כרמלה',          # 'חן כרמלה' MUST come before 'כרמלה' (longest-prefix-first)
    'מתילדה', 'דלישס',             # Biscotti-only customers
    'עוגיפלצת',
]
```

---

## Excel Master Data schema (from `master_data_parser.py`)

| Sheet | Columns (in order) |
|---|---|
| Brands | Brand Key, Name, Category, Status, Launch Date, Owner, Notes |
| Products | SKU Key, Barcode, Name HE, Name EN, Brand Key, Category, Status, Launch Date, Manufacturer, Cost |
| Manufacturers | Key, Name, Products, Contact, Location, Lead Time, MOQ, Payment Terms, Notes |
| Distributors | Key, Name, Products, Commission %, Report Format, Report Freq, Contact, Notes |
| Customers | Customer Key, Name HE, Name EN, Type, Distributor, Chain/Group, Status, Contact, Phone, Notes |
| Logistics | Product Key, Product Name, Storage Type, Temp, Units/Carton, Cartons/Pallet, Units/Pallet, Pallet Divisor, Warehouse, Notes |
| Pricing | Barcode, SKU Key, Name EN, Name HE, Customer, Distributor, Commission%, Sale Price, Cost, Gross Margin |

---

## Overlap & drift analysis

### Products — SAFE to migrate
| Registry field | In Excel? |
|---|---|
| `sku` (key) | ✅ `SKU Key` |
| `full_name` | ✅ `Name EN` |
| `short_name` | ❌ Not in Excel — **add a column or keep derived in code** |
| `brand` | ✅ `Brand Key` |
| `status` | ✅ `Status` |
| `color` | ❌ Not in Excel — **keep in code as display config** |
| `manufacturer` (name string) | ⚠️ Excel has `Manufacturer` column but we need to verify it's the *key*, not the *name* |
| — | ➕ Excel has more: `Barcode`, `Name HE`, `Launch Date`, `Cost` (net additions) |

**Action for Phase 1:** `PRODUCTS` dict becomes a DB-backed loader. `PRODUCT_NAMES`, `PRODUCT_STATUS`, `ACTIVE_SKUS`, `TURBO_SKUS`, `DANIS_SKUS` stay derived. `PRODUCT_SHORT`, `PRODUCT_COLORS`, `FLAVOR_COLORS` stay hardcoded in a separate `scripts/display_config.py`.

### Brands — SAFE to migrate
| Registry field | In Excel? |
|---|---|
| `key` | ✅ `Brand Key` |
| `label` | ✅ `Name` |
| `skus` | ❌ Derived at runtime from PRODUCTS — **keep derived** |
| — | ➕ Excel has more: `Category`, `Status`, `Launch Date`, `Owner`, `Notes` |

**Action:** Migrate; keep `BRANDS[x]['skus']` as a dynamic filter.

### Distributors — SAFE to migrate
| Registry field | In Excel? |
|---|---|
| `key` | ✅ |
| `name` | ✅ `Name` |
| `name_heb` | ⚠️ Excel has only `Name` — **ensure HE names land somewhere**, probably add a `Name HE` column or use `Notes` |
| `brands` | ❌ Derived — can be computed from which SKUs each distributor carries |

**Action:** Add `Name HE` column to Distributors sheet before migration, OR keep `DISTRIBUTORS[x]['name_heb']` as a sidecar dict in code.

### Customers — PARTIAL — reconciliation needed
Registry `CUSTOMER_NAMES_EN` is a 22-entry HE → EN map. Excel Customers sheet has `Name HE` and `Name EN` per row (plus full contact, type, status).

**Drift risk:** If a customer exists in `CUSTOMER_NAMES_EN` but not in Excel Customers, migrating loses them. **Manual reconciliation required** — I'll produce a script in Phase 1 that prints any registry customer not present in the Excel data after seeding.

**Note on duplicates:** In registry, `'דור אלון'` → `'Alonit'` and `'אלונית'` → `'Alonit'` both map to the same EN name. Excel Customers might have separate rows with different Customer Keys. Decide at Phase 1: unify (one customer with multiple HE aliases) or keep separate (two customers, both show as "Alonit" in EN filters).

### Manufacturers — VERIFY, then safe
Registry stores manufacturer as a name string on each Product (`'Raito'`, `'Piece of Cake'`, `'Biscotti'`). Excel Manufacturers sheet has full records keyed by `Key`.

**Blocker:** Every string in PRODUCTS['*'].manufacturer must correspond to a row in Excel Manufacturers. Verify 3 values exist: Raito, Piece of Cake, Biscotti.

### Logistics, Pricing — NOT in registry at all
These exist only in Excel today. Post-Phase 1, `parsers.py` and `cc_dashboard_v2.py` should fetch from `master_data` JSONB instead of Excel.

**Drift risk zero** — nothing in registry to lose.

### CUSTOMER_PREFIXES — KEEP IN CODE (not master data)
This is prefix-matching *logic*, not data. Fourteen prefix strings hand-ordered longest-first, used by `extract_customer_name()` to aggregate Icedream branches under a canonical customer name.

**Decision:** stays in `registry.py` (or moves to `scripts/matching_rules.py`). Phase 1 does NOT migrate this to DB.

### CREATORS — KEEP IN CODE (for now)
Two entries — brand owners/creators. Excel Brands sheet has `Owner` column which may cover this, but the registry's CREATORS has richer structure (Hebrew name, brand label, SKU list).

**Decision:** clarify with user — either (a) populate Brands.Owner with the Hebrew names and drop CREATORS, or (b) keep CREATORS hardcoded as descriptive metadata. Default: (a), simpler.

---

## Phase 1 action list (derived from this report)

Pre-migration checks — ALL DECIDED 2026-04-19:
1. ✅ Manufacturers: keys are `vaniglia` (not Raito!), `poc`, `biscotti`. User confirmed "turbo not raito."
2. ✅ All 7 active SKUs in registry exist in Excel Products (plus 4 planned: nuts_sku1/2, dream_cake_3, ahlan_sku1).
3. ✅ 15 of 22 overlap directly. `דלישס`/`מתילדה` are SPs under `חנויות ביסקוטי` (not separate customers). Spelling variants (`דלק מנטה`→`דלק`, `ינגו`→`ינגו דלי`, etc.) handled by prefix matching.
4. ✅ Merge `דור אלון` into `alonit`. One customer, `alonit` is canonical.
5. ✅ Drop CREATORS, use Brands.Owner (already has `Deni Avdija`, `Daniel Amit`).
6. ✅ Add `Name HE` column to Distributors sheet.
7. ✅ (Bonus) Fix distributor keys in Excel: `icedreams`→`icedream`, `mayyan_froz`→`mayyan` (code wins over Excel).

Code changes:
7. ☐ Create `scripts/display_config.py` to hold PRODUCT_COLORS, FLAVOR_COLORS, PRODUCT_SHORT, PRODUCTS_ORDER (display-only config).
8. ☐ Create `scripts/matching_rules.py` to hold CUSTOMER_PREFIXES (and the longest-prefix-first regression test).
9. ☐ Rewrite `registry.py`:
   - `PRODUCTS`, `BRANDS`, `DISTRIBUTORS`, `CUSTOMER_NAMES_EN` → DB-backed lazy loaders.
   - Fallback to hardcoded values if DB unreachable.
   - Keep `Product` class and helper functions.
   - Keep derived dicts/lists (`ACTIVE_SKUS`, `TURBO_SKUS`, `DANIS_SKUS`, `PRODUCT_NAMES`, `PRODUCT_STATUS`) as runtime computations over the DB-backed PRODUCTS.
   - Add a module-level `reload()` function for Phase 4's soft-refresh invalidation.
10. ☐ Write regression tests: longest-prefix order, `extract_customer_name()` parity on known strings, `ACTIVE_SKUS`/`TURBO_SKUS`/`DANIS_SKUS` equivalence.

Post-migration:
11. ☐ Any `from registry import ...` call site that expects a module-level dict (not a callable) gets verified. Module lazy-load means first access triggers DB query; all callers currently read at import time so a cache-on-first-read pattern is fine.
12. ☐ Benchmark: measure dashboard build time before and after. DB-backed should add <1s if cached properly.

---

_End of reconciliation report. Phase 1 can begin once the above decisions are answered._
