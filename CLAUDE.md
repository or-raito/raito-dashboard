# Raito Project — Claude Context

## Which file to read

| Task | Read |
|---|---|
| First conversation / onboarding / product & distributor context | `RAITO_CONTEXT.md` |
| Dashboard changes, code work, build pipeline, DB schema, deploy | `RAITO_ARCHITECTURE.md` |
| Data parsing, ingestion, QA, weekly updates, CC tab details | `RAITO_DATA.md` |
| Debugging historical choices ("why does X work this way?") | `RAITO_DECISIONS.md` |
| Agent system, Cloud Run Jobs, Slack alerts, deploy commands | `RAITO_AGENTS.md` |

**Load only the file you need — each is 200-400 lines.** For complex tasks, load 2 files max. `RAITO_BRIEFING.md` still exists as the combined original but is no longer the primary reference.

This is the Raito data/dashboard project. Quick orientation:

- **What this is:** Israeli consumer goods brand (Turbo ice cream, Dani's Dream Cake). Three active distributors: Icedream + Ma'ayan + Biscotti. Dashboards track weekly sales.
- **CC tab source:** `scripts/cc_dashboard_v2.py` — fully dynamic Python generator (imported by `unified_dashboard.py:22` as `from cc_dashboard_v2 import build_cc_tab`). The older `cc_dashboard.py` is an orphan — DO NOT edit it, changes will not reach production. The old HTML file (`dashboards/customer centric dashboard 11.3.26.html`) is also legacy/unused since 25 Mar 2026.
- **BO tab source:** `scripts/dashboard.py` (Biscotti/Icedream/Ma'ayan aggregation logic) — layout/shell lives in `scripts/unified_dashboard.py`.
- **SP tab source:** `scripts/salepoint_dashboard.py`; **GEO:** `scripts/geo_dashboard.py` (`build_geo_tab`); **Agents:** `scripts/agents_dashboard.py` (`build_agents_tab`). Both geo & agents tabs embed their own `<div id="tab-X" class="tab-content">` wrapper — do not double-wrap in `unified_dashboard.py`. Keep every tab id in the `switchTab` list (`['bo','cc','sp','ap','md','geo','agents']`) so inactive tabs get hidden correctly.
- **Build pipeline:** make changes in `scripts/` → `python3 scripts/unified_dashboard.py` → output to `docs/unified_dashboard.html`. Deploy via `gcloud builds submit --tag gcr.io/raito-house-of-brands/raito-dashboard` then `gcloud run deploy raito-dashboard --image gcr.io/raito-house-of-brands/raito-dashboard --region me-west1`. Do NOT pass `--no-cache` unless kaniko is enabled.
- **Current data state:** W13 integrated for Icedream (970 units, ₪13,493). Ma'ayan W10–W13 integrated (`maayan_sales_week_10_11.xlsx` + `week12_13.xlsx`), March 2026 total 30,524 units / ₪416,555. BO/CC/SP parity confirmed.
- **Context files (split for cache efficiency):**
  - `RAITO_CONTEXT.md` — company, products, brands, distributors, business model
  - `RAITO_ARCHITECTURE.md` — code architecture, file map, build pipeline, DB schema, deploy
  - `RAITO_DATA.md` — data state, quality, returns, CC tab weekly details, update checklists
  - `RAITO_DECISIONS.md` — all 115 decisions log entries
  - `RAITO_AGENTS.md` — 5 Cloud Run Jobs, DB schema, KPI definitions, rebuild/deploy commands

## Key rules

### CRITICAL — Dashboard build & deploy pipeline
**The unified dashboard is served by Cloud Run at `https://raito-dashboard-20004010285.me-west1.run.app`. GitHub Pages is deprecated.**
1. Make changes in individual dashboard tabs or in `scripts/` (parsers, config, dashboard.py, etc.)
2. **ALWAYS regenerate locally via:** `cd scripts && python3 unified_dashboard.py` (for testing)
3. **Deploy to Cloud Run:** rebuild Docker image → push → `gcloud run deploy` (see `RAITO_AGENTS.md` for full commands)
4. The Flask server at `/` calls `generate_unified_dashboard()` from `unified_dashboard.py` — same output as the local build.
5. **NEVER** call `dashboard.generate_dashboard()` directly as the final build step — always use `unified_dashboard.py`
6. **NEVER edit `docs/unified_dashboard.html` directly for visual/CSS/JS fixes** — it is overwritten on every rebuild. All visual changes must go into the source scripts: CC tab (CSS/JS/data) → `scripts/cc_dashboard_v2.py` (NOT `cc_dashboard.py` — that's the orphan), unified layout/overrides → `scripts/unified_dashboard.py`, SP styles → `scripts/salepoint_dashboard.py`, BO layout → `scripts/dashboard.py`, GEO → `scripts/geo_dashboard.py`, Agents → `scripts/agents_dashboard.py`. If you do quick-test in the generated file, always backport to the source script before the next rebuild.

### CRITICAL — Parsing & ingestion rules
**Never implement distributor parsing logic from scratch.** All parsing lives in `scripts/parsers.py`. Before writing any code that reads distributor Excel files, read that file first.

Key traps that have already burned us:
- **Ma'ayan sheet selection:** Always use the detail sheet (`דוח_הפצה_גלידות_טורבו__אל_פירוט`). The pivot sheet (`טבלת ציר`) is **explicitly skipped** via `SKIP_KEYWORDS = ('ציר', ...)` because it double-counts rows. Never read from `טבלת ציר`.
- **Ma'ayan revenue:** Calculated **row-by-row** using `_mayyan_chain_price(price_table, chain_raw, product)` from the price DB. Never use a flat average (₪13.80 is only the absolute last-resort fallback for unknown chains). Always call `_load_mayyan_price_table()` first.
- **Weekly overrides (`_extract_week_overrides` in `db_dashboard.py`):** Must reuse `parsers.py` functions — `parse_mayyan_file()`, `_load_mayyan_price_table()`, `_mayyan_chain_price()`. Do not re-implement parsing inline.

### CRITICAL — Customer aggregation & multi-distributor rules
- **Customer aggregation** across distributors uses `extract_customer_name()` from `config.py`, backed by `CUSTOMER_NAMES_EN` + `CUSTOMER_PREFIXES` in `registry.py`. Longest-prefix-first ordering MUST be preserved (`'חן כרמלה'` before `'כרמלה'`; `'דומינוס פיצה'` before `'דומינוס'`). When adding a Biscotti-only customer, add it to BOTH dicts.
- **Multi-distributor customers** (Wolt/Carmela/Naomi buy turbo from Icedream AND danis from Biscotti): in CC JSON, emit `distributors[]` array + per-brand `turboRev`/`turboUnits`/`danisRev`/`danisUnits` slices. `distributor:"Multiple"` is a label, not filterable — filter UI must check `c.distributors.includes(...)`.
- **Brand/distributor filter coupling**: when Brand=all and distributor is specific, `_effectiveBrand()` picks the implied brand (Biscotti→danis, Icedream/Ma'ayan→turbo) so revenue/units aren't double-counted. See `getBrandRev`/`getBrandUnits` in cc_dashboard_v2.
- **Assortment rule** (enforced by parsers/resolvers): `dream_cake_2` only flows via Biscotti; `turbo` SKUs only via Icedream or Ma'ayan. Never mix in the BO/CC/SP tables.

### Other rules
- Never use flavor keywords alone (`שוקולד`, `מנגו`) to filter Icedream products — use strict `טורבו` OR `דרים קייק` filter only
- Ma'ayan revenue: applied per-row at parse time via `_mayyan_chain_price()` from price DB (falls back to ₪13.80/unit). `by_account` stores `{product: {units, value}}` — do NOT re-price when reading `mayyan_accounts`. For weekly chart history (`weeklyDetailHistory`), distribute proportionally from `_maayWkRev` totals when no per-line data is available.
- Always validate parsed totals against `_iceWkUnits` / `_maayWkUnits` dashboard values before writing to history
