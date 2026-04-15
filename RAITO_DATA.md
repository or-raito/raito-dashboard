# Raito Project — Data State & Quality

> **When to load:** Data parsing, ingestion, QA, weekly updates, CC tab details.

---

## Current Data State (as of 1 April 2026)

### Sales

| Month | Total Units | Revenue (₪) | Ma'ayan units | Icedream units | Biscotti units |
|---|---|---|---|---|---|
| Nov '25 | 3,961 | 251,662 | 144 | 3,817 | 0 |
| Dec '25 | 83,753 | 1,530,339 | 61,739 | 22,014 | 0 |
| Jan '26 | 51,131 | 1,085,546 | 30,353 | 20,778 | 0 |
| Feb '26 | 58,331 | 1,073,851 | 43,777 | 14,554 | 0 |
| Mar '26 (W10-W13) | 36,382 | 590,541 | 30,524 | 5,315 | 543 |
| **Total** | **~233,558** | **~₪4,531,939** | **166,537** | **66,478** | **543** |

> **QA pass 1 Apr 2026:** Biscotti duplicate eliminated (was 121 old + 543 new overlapping → now 543 only from `week13.xlsx`). Old file `daniel_amit_weekly_biscotti.xlsx` archived. Icedream W13 now parsed via new weekly xlsx parser (970 units). Stock files sorted by report date, not mtime.

### Inventory Snapshot

| Location | Units | Report Date |
|---|---|---|
| Karfree warehouse | 71,120 | 24/03/2026 |
| Icedream distributor | 8,387 | 26/03/2026 |
| Ma'ayan distributor | 6,710 | 29/03/2026 |
| **Total** | **86,217** | |

Karfree breakdown (24/03/2026): Mango 26,400 · Vanilla 23,430 · Chocolate 14,400 · Pistachio 6,890.

### Current Data State (Phase 4 — as of 1 Apr 2026)

| Distributor | Source files in `data/` | Latest period |
|---|---|---|
| Icedream (sales) | Nov 2025–Mar 2026 | W13 via weekly xlsx parser — 5,315 total March units |
| Ma'ayan (sales) | Nov 2025–Mar 2026 | W13 — March total: 30,524 units / ₪416,555 |
| Biscotti (sales) | Mar 2026 | W13 (week13.xlsx, new format: שם לקוח + כמות) — 543 units |
| Icedream (stock) | snapshot 26/3/2026 | 8,387 units, 4 products |
| Ma'ayan (stock) | snapshot 15/3/2026 | 8,710 units, 4 products |
| Karfree (warehouse) | snapshot 24/3/2026 | 71,120 units |

**Ma'ayan W10–W13 note:** Two files cover March 2026 — `maayan_sales_week_10_11.xlsx` (W10+W11) and `week12_13.xlsx` (W12+W13). `parse_all_mayyan()` merges them. Prior to 29 Mar 2026 fix, a first-file-wins bug silently dropped `week12_13.xlsx`. See decision 109.

### DB Attribution State (as of 14 Apr 2026)

All 48 existing Biscotti `sales_transactions` are now fully attributed via `sale_point_id`:

| Customer | sale_points records | Transactions linked |
|---|---|---|
| Wolt Market (id=6) | 28 branches | 38 |
| Naomi's Farm (id=7) | 5 branches | 5 |
| Carmella (id=10) | 1 | — |
| Matilda Yehud (id=20) | 1 | 4 |
| Delicious Rishon LeZion (id=21) | 1 | 1 |

New customers Matilda Yehud and Delicious Rishon LeZion are `independent` type under Biscotti. Future uploads auto-create SP records via `_upsert_sale_point()` in `ingest_to_db.py`. See decisions 116–119.

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

## Sales Dashboard (CC tab) — Weekly Data Details

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

### W13 Update Checklist (SQL pipeline — supplement to existing checklist)

In addition to the CC weekly chart array updates documented above:

1. Load Icedream W13 sales: `python3 scripts/db/raito_loader.py --target local --file data/icedreams/week13.xlsx --force`
2. Load Ma'ayan W13 when received: `python3 scripts/db/raito_loader.py --target local --file data/mayyan/maayan_w13.xlsx`
3. Load any new stock files: `python3 scripts/db/raito_loader.py --target local --file data/icedreams/stock26.3.xlsx`
4. Refresh live dashboard: `https://raito-dashboard-20004010285.me-west1.run.app/refresh`
5. Alternatively: use the upload page at `/upload` to drag-and-drop files directly

**Or via /upload page:** Navigate to `https://raito-dashboard-20004010285.me-west1.run.app/upload`, drag in the file, select distributor if auto-detection fails, click "Upload & Ingest". Dashboard cache is automatically invalidated on success.
