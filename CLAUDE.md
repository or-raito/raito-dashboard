# Raito Project — Claude Context

## Which file to read

| Task | Read |
|---|---|
| Dashboard changes, data parsing, product/distributor context | `RAITO_BRIEFING.md` |
| Agent system, Cloud Run Jobs, Slack alerts, Insight Analyst, QA agent | `RAITO_AGENTS.md` |
| Debugging unexpected behaviour ("why does X work this way?") | `RAITO_BRIEFING.md` → Decisions log |

**Always read the relevant file before starting work. Both files together are ~1,600 lines — skim the headers first and deep-read only the relevant section.**

This is the Raito data/dashboard project. Quick orientation:

- **What this is:** Israeli consumer goods brand (Turbo ice cream, Dani's Dream Cake). Three active distributors: Icedream + Ma'ayan + Biscotti. Dashboards track weekly sales.
- **CC tab source:** `scripts/cc_dashboard.py` — fully dynamic Python generator. The old HTML file (`dashboards/customer centric dashboard 11.3.26.html`) is legacy/unused since 25 Mar 2026.
- **Build pipeline:** make changes in `scripts/` → `python3 scripts/unified_dashboard.py` → output to `docs/unified_dashboard.html` → copy to `github-deploy/index.html`.
- **Current data state:** W13 integrated for Icedream (970 units, ₪13,493). Ma'ayan W10–W13 integrated (`maayan_sales_week_10_11.xlsx` + `week12_13.xlsx`), March 2026 total 30,524 units / ₪416,555. BO/CC/SP parity confirmed.
- **Briefing:** `RAITO_BRIEFING.md` — architecture, data sources, decisions log (103 entries), file map. Always read before dashboard changes.
- **Agents:** `RAITO_AGENTS.md` — 5 Cloud Run Jobs, DB schema, KPI definitions, rebuild/deploy commands. Always read before agent changes.

## Key rules

### CRITICAL — Dashboard build & deploy pipeline
**The unified dashboard is served by Cloud Run at `https://raito-dashboard-20004010285.me-west1.run.app`. GitHub Pages is deprecated.**
1. Make changes in individual dashboard tabs or in `scripts/` (parsers, config, dashboard.py, etc.)
2. **ALWAYS regenerate locally via:** `cd scripts && python3 unified_dashboard.py` (for testing)
3. **Deploy to Cloud Run:** rebuild Docker image → push → `gcloud run deploy` (see `RAITO_AGENTS.md` for full commands)
4. The Flask server at `/` calls `generate_unified_dashboard()` from `unified_dashboard.py` — same output as the local build.
5. **NEVER** call `dashboard.generate_dashboard()` directly as the final build step — always use `unified_dashboard.py`
6. **NEVER edit `docs/unified_dashboard.html` directly for visual/CSS/JS fixes** — it is overwritten on every rebuild. All visual changes must go into the source scripts: CC tab (CSS/JS/data) → `scripts/cc_dashboard.py`, unified layout/overrides → `scripts/unified_dashboard.py`, SP styles → `scripts/salepoint_dashboard.py`, BO layout → `scripts/dashboard.py`. If you do quick-test in the generated file, always backport to the source script before the next rebuild.

### CRITICAL — Parsing & ingestion rules
**Never implement distributor parsing logic from scratch.** All parsing lives in `scripts/parsers.py`. Before writing any code that reads distributor Excel files, read that file first.

Key traps that have already burned us:
- **Ma'ayan sheet selection:** Always use the detail sheet (`דוח_הפצה_גלידות_טורבו__אל_פירוט`). The pivot sheet (`טבלת ציר`) is **explicitly skipped** via `SKIP_KEYWORDS = ('ציר', ...)` because it double-counts rows. Never read from `טבלת ציר`.
- **Ma'ayan revenue:** Calculated **row-by-row** using `_mayyan_chain_price(price_table, chain_raw, product)` from the price DB. Never use a flat average (₪13.80 is only the absolute last-resort fallback for unknown chains). Always call `_load_mayyan_price_table()` first.
- **Weekly overrides (`_extract_week_overrides` in `db_dashboard.py`):** Must reuse `parsers.py` functions — `parse_mayyan_file()`, `_load_mayyan_price_table()`, `_mayyan_chain_price()`. Do not re-implement parsing inline.

### Other rules
- Never use flavor keywords alone (`שוקולד`, `מנגו`) to filter Icedream products — use strict `טורבו` OR `דרים קייק` filter only
- Ma'ayan revenue: applied per-row at parse time via `_mayyan_chain_price()` from price DB (falls back to ₪13.80/unit). `by_account` stores `{product: {units, value}}` — do NOT re-price when reading `mayyan_accounts`. For weekly chart history (`weeklyDetailHistory`), distribute proportionally from `_maayWkRev` totals when no per-line data is available.
- Always validate parsed totals against `_iceWkUnits` / `_maayWkUnits` dashboard values before writing to history
