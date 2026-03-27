# Raito Project — Claude Context

**Read `RAITO_BRIEFING.md` at the start of every session for full project context.**

This is the Raito data/dashboard project. Quick orientation:

- **What this is:** Israeli consumer goods brand (Turbo ice cream, Dani's Dream Cake). Three active distributors: Icedream + Ma'ayan + Biscotti. Dashboards track weekly sales.
- **CC tab source:** `scripts/cc_dashboard.py` — fully dynamic Python generator. The old HTML file (`dashboards/customer centric dashboard 11.3.26.html`) is legacy/unused since 25 Mar 2026.
- **Build pipeline:** make changes in `scripts/` → `python3 scripts/unified_dashboard.py` → output to `docs/unified_dashboard.html` → copy to `github-deploy/index.html`.
- **Current data state:** W12 (15/3/2026) is the latest week. W13 data not yet received. BO/CC are revenue-parity (0 unit gap).
- **Briefing:** `RAITO_BRIEFING.md` — contains full architecture, data sources, decisions log, file map, and W13 update checklist. Always read it before making dashboard changes.

## Key rules

### CRITICAL — Dashboard build & deploy pipeline
**The unified dashboard (`docs/unified_dashboard.html`) is the ONLY production artifact. The team works on it live.**
1. Make changes in individual dashboard tabs or in `scripts/` (parsers, config, dashboard.py, etc.)
2. **ALWAYS regenerate via:** `cd scripts && python3 unified_dashboard.py`
3. **ALWAYS deploy from:** `cp docs/unified_dashboard.html github-deploy/index.html`
4. **NEVER** copy `docs/dashboard.html` to deploy — that is a raw sub-component, not the unified dashboard
5. **NEVER** call `dashboard.generate_dashboard()` directly as the final build step — always use `unified_dashboard.py`
6. After deploy: `cd github-deploy && git add index.html && git commit && git push`
7. **NEVER edit `docs/unified_dashboard.html` directly for visual/CSS/JS fixes** — it is overwritten on every rebuild. All visual changes must go into the source scripts: CC tab (CSS/JS/data) → `scripts/cc_dashboard.py`, unified layout/overrides → `scripts/unified_dashboard.py`, SP styles → `scripts/salepoint_dashboard.py`, BO layout → `scripts/dashboard.py`. If you do quick-test in the generated file, always backport to the source script before the next rebuild.

### Other rules
- Never use flavor keywords alone (`שוקולד`, `מנגו`) to filter Icedream products — use strict `טורבו` OR `דרים קייק` filter only
- Ma'ayan revenue: applied per-row at parse time via `_mayyan_chain_price()` from price DB (falls back to ₪13.80/unit). `by_account` stores `{product: {units, value}}` — do NOT re-price when reading `mayyan_accounts`. For weekly chart history (`weeklyDetailHistory`), distribute proportionally from `_maayWkRev` totals when no per-line data is available.
- Always validate parsed totals against `_iceWkUnits` / `_maayWkUnits` dashboard values before writing to history
