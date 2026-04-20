# Master Data → BO/CC/SP/GEO Sync — Implementation Plan

**Status:** Phases 0–5 COMPLETE. QA passed on dev. Ready for prod promotion. Phase 6 (Customer↔SP linkage) planned.
**Last updated:** 2026-04-20 (night)
**Owner:** or@raito.ai
**Resume checklist:** bottom of this file

---

## TL;DR — The Vision

Every edit the user makes on the Master Data tab of the live dashboard — price change, new customer, commission adjustment — has a Save button that updates Postgres immediately. All other tabs (BO, CC, SP, GEO) reflect the change on next navigation via soft refresh. Bulk updates supported via Excel upload. All built & tested in a dev environment first, then promoted to prod.

**Postgres = Single Source of Truth. Excel = import/export convenience, not the database.**

---

## Decisions already made in this conversation

### Architecture
- **SSOT:** Postgres `master_data` table (JSONB per entity). `registry.py` will be refactored to read from this table instead of hardcoded dicts.
- **Refresh strategy:** Soft refresh (option 2). Save → write to DB → background `generate_unified_dashboard()` rebuild → next nav/tab switch picks up new HTML.
- **Editing UX:** Inline edit widgets for simple fields, modal forms for complex adds (new customer, new product). Bulk price operations (% change across a filter).
- **Dev env first:** Full parity environment before anything touches prod.

### Dev environment shape
- **DB:** Same Cloud SQL instance (`raito-db`), new database `raito_dev`. Zero extra cost.
- **Seed:** Empty at start. `_md_seed()` will populate from Excel on first `GET /` request. No prod snapshot.
- **Cloud Run:** New service `raito-dashboard-dev` in `me-west1`.
- **Git:** `dev` branch already exists (`origin/dev`). Cloud Build trigger on push → auto-deploy to `raito-dashboard-dev`.

### Bulk price operations: INCLUDED in Phase 3
Convenience actions like "apply +5% to all Wolt prices" or "apply cost +3₪ to all vanilla SKUs."

### New distributor flow: two-gated
- "Register distributor (pending parser)" — visible to user, creates entity row with `parser_status='pending'`. Harmless, visible in MD tab, hidden from BO/CC/SP filters until activated.
- "Activate distributor" — developer-only action, flipped after parser ships to `parsers.py` + `ingest_to_db.py`. Requires a sample file from the distributor first.

---

## Current state (audited 2026-04-16)

### What already exists in prod

| Component | Location | Notes |
|---|---|---|
| Flask app | `scripts/db/db_dashboard.py` (1149 lines) | Gunicorn entry: `scripts.db.db_dashboard:app` |
| Cached index | `GET /` | `_cached_html` set on first request |
| Force rebuild | `GET /refresh` | Regenerates from Excel |
| CRUD API | `GET/POST/PUT/DELETE /api/<entity>` (line 932–1015) | All 7 entities wired |
| Portfolio API | `GET /api/portfolio` (line 1020) | Auto-rebuilds matrix |
| Lookup API | `GET /api/lookup/<entity>` (line 1035) | For FK dropdowns |
| Weekly overrides | `GET/POST /api/weekly-overrides` (line 1049, 1081) | Chart override storage |
| Rebuild trigger | `POST /api/rebuild` (line 1124) | Regenerates portfolio |
| Distributor upload | `GET/POST /upload` (line 594) | Ingests sales Excel files (NOT master data) |
| Health | `GET /health`, `GET /api/health` | For Cloud Run probes |
| Geo API | Blueprint `/api/geo/*` (line 47) | Separate module |
| DB schema — MD | `master_data (entity TEXT PK, data JSONB, updated_at TIMESTAMPTZ)` | Line 793 |
| DB schema — weekly | `weekly_chart_overrides` | Line 769 |
| Entity list | `_MD_PK` (line 742) | `brands`, `products`, `manufacturers`, `distributors`, `customers`, `logistics`, `pricing` |

### Infrastructure facts

| Thing | Value |
|---|---|
| GCP project | `raito-house-of-brands` |
| Region | `me-west1` |
| Cloud SQL instance | `raito-db` (PostgreSQL 15) |
| Prod DB | `raito` |
| Dev DB (to create) | `raito_dev` |
| Cloud Run prod | `raito-dashboard` → `https://raito-dashboard-20004010285.me-west1.run.app` |
| Cloud Run dev (to create) | `raito-dashboard-dev` → URL auto-generated |
| Image registry | `me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-dashboard` |
| Dockerfile | `/Dockerfile` (at repo root) |
| Python | 3.12-slim base |
| Server | Gunicorn, 1 worker × 4 threads, 120s timeout, port 8080 |
| Env vars | `DATABASE_URL`, `PORT`, `GOOGLE_MAPS_API_KEY`, `RAITO_DATA_SOURCE` (opt), `CLOUD_SQL_INSTANCE` (opt) |
| Git repo | `https://github.com/or-raito/raito-dashboard.git` |
| Git branches | `main` (prod), `dev` (exists, tracks origin/dev) |

### What's missing vs the vision

| Gap | Blocks | Phase |
|---|---|---|
| Server-side auth on write routes (currently only client-side JS password `raito2026` in `unified_dashboard.py:1879`) | Anyone with the URL can POST/PUT/DELETE | 2 |
| Validation layer (assortment rule, longest-prefix customer HE name, required fields) | Bad edits can silently break parsers | 2 |
| Audit log (`master_data_audit` table: who, when, old, new) | Can't answer "why did this price change?" | 2 |
| Inline edit UI on MD tab | No way to trigger the CRUD API from the page | 3 |
| Bulk Excel upload for master data (separate from `/upload` which is for distributor sales) | No bulk edit path | 3 |
| Bulk price operations UI (% change across filtered set) | User has to click 40 rows individually | 3 |
| Soft refresh — `/api/<entity>` writes don't invalidate `_cached_html` | Other tabs stay stale until manual `/refresh` | 4 |
| `registry.py` still reads hardcoded dicts, not the `master_data` JSONB | Parsers / CC / BO / SP don't pick up DB edits | 1 |
| Dev env | Can't safely test any of the above | 0 (in progress) |

---

## Field editability matrix (all approved)

### Brands
| Field | Access | Rationale |
|---|---|---|
| Key | Locked | FK on products/sales |
| Name | Editable | Display |
| Category | Editable | Display |
| Status | Gated | Retires brand from BO/CC filters |
| Launch Date | Editable | Informational |
| Owner | Editable | Free text |
| Notes | Editable | Free text |
| **Add new brand** | Yes, modal (Key+Name+Category+Status required) | — |

### Products
| Field | Access | Rationale |
|---|---|---|
| SKU Key | Locked | FK on invoices |
| Barcode | Locked | Scanned on invoices |
| Name HE / EN | Editable | Display |
| Brand | Gated | Re-classifies history |
| Category | Editable | Display |
| Status | Gated | Hides from assortment |
| Launch Date | Editable | Informational |
| Manufacturer | Gated | Changes production partner |
| Cost | Editable | Affects margins |
| **Add new product** | Yes, modal. **Assortment rule validated:** `dream_cake_2` → must route via Biscotti; `turbo` → must route via Icedream/Ma'ayan | — |

### Manufacturers
| Field | Access | Rationale |
|---|---|---|
| Key | Locked | FK on products |
| Name | Editable | Display |
| Products | Read-only (derived) | Edit by editing products |
| Contact, Location, Lead Time, MOQ, Payment Terms, Notes | Editable | Operational metadata |
| **Add new manufacturer** | Yes | — |

### Distributors
| Field | Access | Rationale |
|---|---|---|
| Key | Locked | Hardcoded in parser routing |
| Name | Editable | Display |
| Products | Read-only (derived) | — |
| Commission % | Editable | Affects BO/CC profitability math |
| Report Format / Frequency | Editable | Operational note |
| Contact, Notes | Editable | Free text |
| **Add new distributor** | Two-gated: "Register pending" in UI; "Activate" developer-only after parser exists | — |

### Customers (highest edit volume)
| Field | Access | Rationale |
|---|---|---|
| Key | Locked | FK |
| Name HE | Gated | `extract_customer_name()` matches on this. Longest-prefix-first regression test runs at save; refuses save on regression. |
| Name EN | Editable | Display |
| Type | Editable | CC/SP filter category |
| Distributor | Gated | Multi-dist customers need `distributors[]` array handling |
| Chain / Group | Editable | Rollup key |
| Status (active/reactivated/dormant/closed) | Editable | SP status taxonomy |
| Contact, Phone, Notes | Editable | Free text |
| **Add new customer** | Yes, modal. HE name auto-appended to prefix registry in longest-first position. | — |

### Logistics
| Field | Access | Rationale |
|---|---|---|
| Product Key, Product Name | Read-only | Derived from products |
| Storage Type, Temp, Units/Carton/Pallet, Warehouse | Editable | Operational specs |
| Notes | Editable | Free text |

### Pricing (highest stakes)
| Field | Access | Rationale |
|---|---|---|
| Barcode, SKU Key, Name EN/HE, Customer, Distributor | Read-only | Derived |
| Commission % | Gated | Overrides distributor default, affects CC profitability |
| Sale Price | Editable | Core use case |
| Cost | Editable | Affects gross margin |
| Gross Margin | Read-only (computed) | Sale Price − Cost |
| **Add new (customer × SKU)** | Yes | — |
| **Bulk price ops** | "Apply %/₪ change to filtered set" | Phase 3 |

---

## Phase 0 — Dev environment setup (IN PROGRESS)

### Commands to run in Cloud Shell (`raito-house-of-brands` project selected)

**Step 1 — Create the dev database** ✅ DONE 2026-04-16
```bash
gcloud sql databases create raito_dev \
  --instance=raito-db \
  --project=raito-house-of-brands
```
_Output was: `Created database [raito_dev]`. Database exists, empty, ready to seed on first `GET /` request._

**Step 2 — Skipped** (Option B: dev starts empty, seeds from Excel on first request)

**Step 3 — Build dev image from the `dev` branch** ✅ DONE 2026-04-16
```bash
# In ~/raito-repo (if not present: git clone https://github.com/or-raito/raito-dashboard.git ~/raito-repo)
cd ~/raito-repo
git fetch origin
git checkout dev
git pull origin dev

gcloud builds submit \
  --tag me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-dashboard-dev:latest \
  --project=raito-house-of-brands
```
_Build succeeded in 1m36s. Image `raito-dashboard-dev:latest` pushed to Artifact Registry. Build ID `6e4156ed-68d8-4420-bfae-450c0bf4df4a`._

**Step 4 — Deploy `raito-dashboard-dev` Cloud Run service**

⚠️ **CONTEXT LEARNED 2026-04-16:**
- Prod `DATABASE_URL` lives in **Secret Manager** (secret `raito-db-url`, not a plain env var).
- Prod env vars found: `GOOGLE_MAPS_API_KEY=AIzaSyAb5SZBgElJOQ3GCbCrXiRJLcfdjt0hT_w`, `RAITO_DATA_SOURCE=db`, `DATABASE_URL` from `raito-db-url:latest`.
- Therefore dev needs a parallel secret `raito-db-url-dev` with `/raito` → `/raito_dev` substituted, plus SA binding to access it.

**✅ ALL BLOCKS DONE 2026-04-19.** Dev service live at `https://raito-dashboard-dev-20004010285.me-west1.run.app`. Org policy blocks `allUsers` IAM — access via `gcloud run services proxy raito-dashboard-dev --region=me-west1 --port=8080` + Cloud Shell Web Preview.

**Block B1 — Create dev DB URL secret (~1 min)**
```bash
# Fetch prod URL → transform raito → raito_dev → save to temp
gcloud secrets versions access latest \
  --secret=raito-db-url \
  --project=raito-house-of-brands > /tmp/prod_url.txt

sed 's|/raito\([?"]\)|/raito_dev\1|g; s|/raito$|/raito_dev|' \
  /tmp/prod_url.txt > /tmp/dev_url.txt

# Sanity check — shows the URL with password masked
sed 's|:[^:@]*@|:****@|' /tmp/dev_url.txt
# Expected: postgresql://raito_app:****@/raito_dev?host=/cloudsql/raito-house-of-brands:me-west1:raito-db

# Create the dev secret
gcloud secrets create raito-db-url-dev \
  --data-file=/tmp/dev_url.txt \
  --project=raito-house-of-brands

# Grant the default Compute SA permission to read the dev secret
PROJECT_NUM=$(gcloud projects describe raito-house-of-brands --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding raito-db-url-dev \
  --member="serviceAccount:${PROJECT_NUM}-compute@developer.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor \
  --project=raito-house-of-brands

# Clean up temp files
rm /tmp/prod_url.txt /tmp/dev_url.txt
```

**Block B2 — Deploy `raito-dashboard-dev` (~2 min)**
```bash
gcloud run deploy raito-dashboard-dev \
  --image=me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-dashboard-dev:latest \
  --region=me-west1 \
  --project=raito-house-of-brands \
  --add-cloudsql-instances=raito-house-of-brands:me-west1:raito-db \
  --set-env-vars=GOOGLE_MAPS_API_KEY=AIzaSyAb5SZBgElJOQ3GCbCrXiRJLcfdjt0hT_w,RAITO_DATA_SOURCE=db \
  --set-secrets=DATABASE_URL=raito-db-url-dev:latest \
  --memory=1Gi \
  --cpu=1 \
  --timeout=300 \
  --no-allow-unauthenticated
```

**Block B3 — Grant yourself access + get the URL**
```bash
gcloud run services add-iam-policy-binding raito-dashboard-dev \
  --region=me-west1 \
  --member='user:or@raito.ai' \
  --role='roles/run.invoker' \
  --project=raito-house-of-brands

gcloud run services describe raito-dashboard-dev \
  --region=me-west1 \
  --project=raito-house-of-brands \
  --format='value(status.url)'
```

**Expected result:** dev URL returned. Opening it (logged in as or@raito.ai) triggers `_md_seed()` on first request (10-30s).
**Known caveat:** BO/CC/SP/GEO tabs will be empty in dev because `raito_dev` has no `sales_transactions` data. Fine for Phase 1/2 work on sync mechanism. Snapshot prod sales → dev later when visual parity testing is needed.

**Step 6 — Create Cloud Build trigger on `dev` branch (auto-deploy)**
```bash
gcloud builds triggers create github \
  --name=raito-dashboard-dev-autodeploy \
  --repo-owner=or-raito \
  --repo-name=raito-dashboard \
  --branch-pattern='^dev$' \
  --build-config=cloudbuild-dev.yaml \
  --project=raito-house-of-brands
```

Then create `cloudbuild-dev.yaml` in the repo root on the `dev` branch (I will write this file in Phase 0 close-out):
```yaml
steps:
  - name: gcr.io/cloud-builders/docker
    args:
      - build
      - -t
      - me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-dashboard-dev:$COMMIT_SHA
      - -t
      - me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-dashboard-dev:latest
      - .
  - name: gcr.io/cloud-builders/docker
    args: ['push', '--all-tags', 'me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-dashboard-dev']
  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    entrypoint: gcloud
    args:
      - run
      - deploy
      - raito-dashboard-dev
      - --image=me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-dashboard-dev:$COMMIT_SHA
      - --region=me-west1
options:
  logging: CLOUD_LOGGING_ONLY
```

---

## Phase 1 — registry.py becomes DB-backed

**⚠️ Read `MD_SYNC_RECONCILIATION.md` first** — it has the full drift analysis and 6 decisions that must be answered before Phase 1 can start.

**Goal:** `registry.py` stops holding hardcoded `PRODUCTS`, `BRANDS`, `DISTRIBUTORS`, `CUSTOMER_NAMES_EN` dicts. Instead, it lazy-loads from the `master_data` JSONB table at module import, with the current hardcoded values retained as a fallback for when the DB is unreachable (local dev without Postgres).

**Stays in code (per reconciliation):** `CUSTOMER_PREFIXES`, `PRODUCT_COLORS`, `FLAVOR_COLORS`, `PRODUCT_SHORT`, `PRODUCTS_ORDER`, `CREATORS` (pending decision).

### Tasks
1. Read current `registry.py` structure; note every public name.
2. Introduce `_load_from_db()` helper that queries `master_data` for customers/products/brands and reconstructs the existing public dicts.
3. Reconstruct `CUSTOMER_PREFIXES` deterministically by sorting keys `len desc` at load time — this preserves the longest-prefix trap (`'חן כרמלה'` before `'כרמלה'`).
4. Keep hardcoded dicts as `_FALLBACK_*`, used only if `_load_from_db()` fails or returns empty.
5. Add a module-level cache with a `reload()` function so Phase 4's soft refresh can invalidate it.
6. Regression test: feed known customer strings through `extract_customer_name()` — must resolve identically to today.

### Files touched
- `scripts/registry.py` (modify)
- `scripts/tests/test_registry_prefix_order.py` (new — regression test)

---

## Phase 2 — Harden existing `/api/<entity>` routes

### Tasks
1. **Server-side auth.** Introduce a decorator `@require_admin` that checks a session cookie or `Authorization` header. For dev: reuse the existing `raito2026` password but server-side (signed cookie on login). For prod: upgrade to a proper password or Cloud IAM.
2. **Audit log table.**
   ```sql
   CREATE TABLE master_data_audit (
     id          BIGSERIAL PRIMARY KEY,
     entity      TEXT NOT NULL,
     pk          TEXT NOT NULL,
     action      TEXT NOT NULL CHECK (action IN ('create','update','delete')),
     old_value   JSONB,
     new_value   JSONB,
     actor       TEXT,
     occurred_at TIMESTAMPTZ DEFAULT NOW()
   );
   CREATE INDEX ON master_data_audit (entity, pk, occurred_at DESC);
   ```
3. **Validation layer** per entity. New module `scripts/db/md_validation.py`:
   - Assortment rule: products where `sku_key` contains `dream_cake_2` must have `brand='danis'` and route only through `biscotti`; `turbo*` SKUs must route through Icedream or Ma'ayan.
   - Longest-prefix check: if a customer HE name is changed or added, run the prefix regression test in-memory before commit; reject save on regression.
   - Required-field check: per entity, reject if required fields are missing/empty.
   - Gated-field confirm: POST/PUT with a gated field change requires a `X-Confirm-Gate: true` header (frontend sends this after modal confirm).
4. **Audit log writes** inside existing `api_create`/`api_update`/`api_delete` handlers.

### Files touched
- `scripts/db/db_dashboard.py` (add decorator, audit writes, hook validation)
- `scripts/db/md_validation.py` (new)
- `scripts/db/auth.py` (new)
- Migration: `scripts/db/migrations/002_master_data_audit.sql` (new)

---

## Phase 3 — MD tab UI + bulk upload + bulk price ops

### Tasks
1. **Inline edit widgets** on MD tab per field per the matrix above.
   - Editable fields: click-to-edit with save/cancel per row.
   - Gated fields: click opens confirmation modal, reveals "apply change" only after explicit confirm.
   - Locked fields: rendered as read-only with a lock icon.
2. **Add new** modals per entity: Brand, Product (with assortment dropdown constrained by rule), Manufacturer, Customer (with distributor multi-select), Pricing (customer × SKU × price × commission).
3. **Bulk Excel upload** for master data. New route `POST /api/master-data/upload-excel`:
   - Accepts a `.xlsx` matching the current Master Data schema (7 sheets).
   - Validates every row.
   - Produces a **diff preview** (rows added / changed / removed) as JSON.
   - Frontend displays the diff.
   - User clicks "Confirm" → second call commits in a single transaction, logs audit entries per row.
4. **Bulk price ops**. New route `POST /api/pricing/bulk-apply`:
   - Body: `{filter: {...}, operation: 'pct'|'absolute', value: 5, field: 'sale_price'|'cost'}`
   - Preview first, then confirm.
5. **Excel export** for symmetry. New route `GET /api/master-data/export-excel` → generates `.xlsx` matching the schema, for business users who want to review offline.

### Files touched
- `scripts/db/db_dashboard.py` (new routes)
- `scripts/unified_dashboard.py` (MD tab HTML — `_build_master_data_tab`, lines 561-790)
- `scripts/md_excel_roundtrip.py` (new — upload diff + export)

---

## Phase 4 — Soft refresh on writes

### Tasks
1. In `scripts/db/db_dashboard.py`, add an `_invalidate_cache()` helper that:
   - Sets `_cached_html = None`
   - Spawns a background thread that calls `_generate_dashboard_html()` pre-emptively so the next `GET /` is fast.
2. Call `_invalidate_cache()` at the end of every successful `api_create` / `api_update` / `api_delete` / bulk route.
3. Add a small `GET /api/cache-status` endpoint so the frontend can show "Syncing..." until the rebuild completes.
4. Frontend: after Save, poll `/api/cache-status` briefly; hide Save spinner when ready.

### Files touched
- `scripts/db/db_dashboard.py` (modify)
- `scripts/unified_dashboard.py` (frontend polling JS)

---

## Phase 5 — QA & promote dev → prod

### Tasks
1. **Parity test script** (`scripts/tests/qa_md_parity.py`):
   - Pick 5 customers, 5 products from MD.
   - Assert the EN name / price / commission / category shown in BO, CC, SP, GEO all match the MD Excel and the `master_data` JSONB.
   - Fails the build if any diverge.
2. **Longest-prefix regression test** (from Phase 1).
3. **Audit log completeness test**: simulate 10 edits, assert 10 rows in `master_data_audit`.
4. **Concurrent-edit test**: two sessions editing the same customer simultaneously — last-write-wins with a visible warning.
5. **Merge `dev` → `main`** — standard PR review.
6. **Deploy to prod** via the documented flow (`gcloud builds submit` + `gcloud run deploy raito-dashboard`).
7. **Hit `/refresh` on prod** per the memory note.

---

## Key reference — don't forget

### Customer name prefix trap (from memory + CLAUDE.md)
`CUSTOMER_PREFIXES` must be sorted **longest-first**. Specifically:
- `'חן כרמלה'` must appear before `'כרמלה'`
- `'דומינוס פיצה'` before `'דומינוס'`

In Phase 1, reconstruction must do `sorted(prefixes.items(), key=lambda x: -len(x[0]))`.

### Assortment rule (from CLAUDE.md)
- `dream_cake_2` → only via Biscotti
- `turbo` SKUs → only via Icedream or Ma'ayan
- Never mixed across BO/CC/SP tables

Enforce in `md_validation.py` on every product/pricing create/update.

### Multi-distributor customer rule (from CLAUDE.md)
Wolt, Carmela, Naomi buy turbo from Icedream AND danis from Biscotti. In CC JSON:
- Emit `distributors[]` array
- Emit per-brand `turboRev`/`turboUnits`/`danisRev`/`danisUnits`
- `distributor:"Multiple"` is a label, not filterable

### Ma'ayan pricing (from CLAUDE.md)
Row-by-row via `_mayyan_chain_price(price_table, chain_raw, product)`. Never flat average. ₪13.80 is last-resort fallback only.

### Deploy commands for PROD (unchanged)
```bash
cd ~/raito-repo
git checkout main && git pull
gcloud builds submit --tag gcr.io/raito-house-of-brands/raito-dashboard
gcloud run deploy raito-dashboard \
  --image gcr.io/raito-house-of-brands/raito-dashboard \
  --region me-west1
# Then: hit /refresh on the prod URL
```

---

## Resume checklist (pick up here next session)

When you come back, run through this list in order:

1. ✅ **Phase 0 done (2026-04-19):** Dev env fully operational. raito_dev DB, dev Cloud Run service, secret, IAM all set.
2. ✅ **Phase 1 done (2026-04-19):** `registry.py` rewritten to load from DB with fallback. `display_config.py` + `matching_rules.py` split out.
3. ✅ **Phase 2 done (2026-04-19):** `auth.py` (session cookies), `md_validation.py` (validation layer), audit log table + writes, all wired into CRUD handlers.
4. ✅ **Phase 3 done (2026-04-19):** `md_excel_roundtrip.py` (upload diff/commit, bulk price preview/apply, server-side export). UI: auth login flow, bulk upload modal, bulk price ops modal, server export button. All wired into MD tab JS.
5. ✅ **Phase 4 done (2026-04-19):** `_invalidate_cache()` with background thread rebuild. `/api/cache-status` endpoint. Frontend polls after every write, shows "Syncing..." → "All tabs are up to date." All CRUD + bulk routes call `_invalidate_cache()`.
6. ✅ **Deployed to dev (2026-04-19).** All files committed to `dev` branch, Docker image built, deployed to `raito-dashboard-dev`. DB permissions granted (`raito_app` on `raito_dev`). IAM set for `domain:raito.ai` + `user:or@raito.ai`.
7. 🔄 **Phase 5 QA — in progress (session 2: 2026-04-20).** Access via Cloud Shell proxy.
   - ✅ API health + connection
   - ✅ Auth login (fixed: `d.status==='ok'` not `d.ok`)
   - ✅ Product CRUD: create, edit, delete
   - ✅ Brand field display (fixed: validation uses `brand` not `brand_key`)
   - ✅ Validation blocks missing required fields
   - ✅ FK delete protection (can't delete brand with products)
   - ✅ Audit log records all operations
   - ✅ Excel export returns valid .xlsx
   - ✅ Pricing CREATE works (tested: new record saved correctly)
   - ✅ Cache freeze fixed (keeps stale HTML while rebuilding, timeout 45s)
   - ✅ Pricing composite PK (`_pk = sku_key::customer::distributor`) — edit/delete now route correctly
   - ✅ Filters fixed (`window.mdRender` exposed — products/customers/pricing filters all work)
   - ✅ Form↔DB alignment: dropdowns send `key` for customer/distributor; tables resolve keys to display names
   - ✅ `/api/normalize` endpoint created — one-time data cleanup (display names → keys, dedup customers)
   - ☐ **← NEXT: Deploy + normalize.** Local files have all fixes, NOT yet pushed/deployed:
     1. `git push origin dev --force` from Mac
     2. Cloud Shell: `git fetch && git reset --hard origin/dev && gcloud builds submit ... && gcloud run deploy ...`
     3. Restart proxy: `pkill -f "proxy raito-dashboard-dev"; gcloud run services proxy raito-dashboard-dev --region me-west1 --port 8080`
     4. **Run normalization** (one-time, after deploy): login then `POST /api/normalize`
     5. Verify: pricing/customer tables show resolved display names, filters work, create/edit/delete all use keys
   - ☐ Re-test pricing edit + delete (now using composite PK — should work after deploy)
   - ☐ Test bulk Excel upload flow
   - ☐ Test bulk price update flow
8. ☐ **Promote to prod.** Merge `dev` → `main`, rebuild prod image, deploy to `raito-dashboard`.

---

## Bugs found & fixed in QA session 2 (2026-04-20)

| Bug | Root Cause | Fix |
|---|---|---|
| Page freezes 3+ min after every CRUD save | `_invalidate_cache()` nulled `_cached_html`; `GET /` blocked on `consolidate_data()` (no Excel in dev) | Keep stale HTML while rebuilding; timeout 180s → 45s |
| Pricing edit/delete 404 | Frontend PK was `id`, backend was `barcode`, neither existed reliably | Synthetic composite `_pk = sku_key::customer::distributor` on both sides |
| Filters silently broken (pricing, products, customers) | `mdRender` was local function, `onchange` couldn't reach it | Exposed as `window.mdRender` |
| Form sends wrong values for customer/distributor | Dropdown `valKey` was `key` but seed data stored display names | Normalized data to use keys; dropdowns send `key`; tables resolve to display names |
| Pricing table missing product name | `name_en` not stored in pricing records | Resolved from `S.products` at render time |
| Duplicate customer "Alonit" | Seed data had two entries with same key | `/api/normalize` deduplicates by key |
| Inconsistent distributor names (`Icedream` vs `icedreams`) | Seed data used display names, new records used keys | `/api/normalize` converts all to keys |
| Logistics PK mismatch | Frontend had `pk:'id'` but backend uses `product_key` | Aligned to `product_key` |

### Files changed (not yet committed/pushed)

- **`scripts/db/db_dashboard.py`**: pricing composite PK, cache keeps stale HTML (timeout 45s), `/api/normalize` endpoint, `_pk` injected on pricing GET, stripped on POST/PUT
- **`scripts/unified_dashboard.py`**: `window.mdRender`, ENTITY_MAP aligned (`_pk` for pricing, `product_key` for logistics), form dropdowns send `key`, display name resolvers for tables + filter dropdowns (`distLabel`, `custLabel`)

---

## Open questions (answer when we resume)

1. **Cloud Build trigger** — do you want it on every push to `dev`, or only on push to a specific `dev-deploy` tag? (Default: every push.)
2. **Dev IAM** — anyone besides or@raito.ai need access to the dev URL?
3. **Audit log retention** — keep forever, or purge after N days? (Default: forever.)

---

## Field editability matrix — approved as of 2026-04-16
(see full matrix above)

## Conversation summary

This plan emerged from a conversation covering:
1. Initial plan assumed Excel-as-SSOT; user pushed back correctly that SQL/cloud should be SSOT.
2. Revised vision: inline Save button + bulk Excel upload, everything live via soft refresh.
3. Auth clarified: prod URL is currently "password protected" only at a client-side JS level (`raito2026` hash). Real server-side auth needed for write routes.
4. Rebuild strategy chosen: soft refresh (option 2 of 3).
5. Dev env first; field matrix approved across all 7 entities; bulk price ops included; new distributor two-gated.
6. Post-exploration discovery: CRUD API already exists in `scripts/db/db_dashboard.py`. This collapses Phase 2 from "build backend" to "harden backend".

---

## Phase 6 — Customer ↔ Sale Point Linkage (planned)

**Goal:** Let the user attach sale points to customers, handling the fact that the same physical location can appear under multiple names across distributor reports.

### Data model changes

**New columns on `sale_points` table:**
- `customer_key TEXT` — FK to customers entity. Links this SP to a customer.
- `canonical_sp_id INTEGER` — self-referencing FK to `sale_points.id`. If NULL, this SP *is* the canonical (real physical location). If set, points to the canonical SP that represents the same physical store.

**Concepts:**
- **Canonical sale point** = the deduplicated real-world location (one record per physical store)
- **Alias sale points** = the various names a physical store appears under in different distributor reports (linked back to canonical via `canonical_sp_id`)
- A customer's sale points = all canonical SPs where `customer_key = X`, plus their aliases

### Implementation steps

1. **DB migration** — `ALTER TABLE sale_points ADD COLUMN customer_key TEXT, ADD COLUMN canonical_sp_id INTEGER REFERENCES sale_points(id)`
2. **Backend API routes:**
   - `GET /api/customer-salepoints/<customer_key>` — list SPs for a customer (canonical + aliases)
   - `POST /api/customer-salepoints/assign` — bulk assign SPs to a customer (by SP id list + customer_key)
   - `POST /api/customer-salepoints/merge` — merge alias SPs under a canonical SP
   - `GET /api/customer-salepoints/search?q=הולמס` — pattern search across unlinked SPs
   - `GET /api/customer-salepoints/export` — download Excel: Customer → Canonical SP → Aliases + metrics
   - `POST /api/customer-salepoints/upload` — re-upload edited Excel to update assignments
3. **MD tab UI (Customers section):**
   - Each customer row shows linked SP count as a clickable badge
   - Clicking the count opens SP dashboard pre-filtered to that customer
   - "Link Sale Points" button opens assignment modal:
     - Pattern search box (type Hebrew/English name, see matching unlinked SPs)
     - Checkboxes to select matches, "Assign to [customer]" button
     - "Merge duplicates" — select multiple SPs that are the same physical location, pick one as canonical
4. **SP dashboard integration:**
   - Accept `?customer=X` URL param to pre-filter
   - Show `customer_key` column in SP table (resolved to display name)
   - Group-by-canonical view: one row per physical location, expandable to show aliases
5. **Export/download:**
   - Excel file grouped by customer: Customer Name → Canonical SP (name, city, address) → Alias SPs (name, distributor source)
   - User can edit assignments in Excel (move SP to different customer, mark as alias) and re-upload

### Files to modify
- `scripts/db/db_dashboard.py` — new API routes
- `scripts/unified_dashboard.py` — MD tab customer-SP UI
- `scripts/salepoint_dashboard.py` — customer filter, canonical grouping
- `scripts/db/md_excel_roundtrip.py` — new export/import sheet for SP mapping

---

_End of plan. When resuming, read from the "Resume checklist" section._
