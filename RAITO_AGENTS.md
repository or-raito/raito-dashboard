# Raito Agent System

Read this file at the start of any conversation about agents, monitoring, Cloud Run Jobs, or Slack alerts.
For dashboard/data context, read `RAITO_BRIEFING.md`.

---

## Overview

Five autonomous agents run as **Cloud Run Jobs** on GCP, triggered by **Cloud Scheduler**.
They monitor the dashboard, analyse data trends, and fire Slack alerts when something needs attention.
All agents share a PostgreSQL database (`raito-db`) accessed via Cloud SQL Unix socket.

**Agent image:** `me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-agents:latest`
**Dockerfile:** `deploy/agents/Dockerfile.agents`
**Agent source:** `scripts/agents/`
**Deploy script:** `deploy/agents/deploy_agents.sh`

---

## Infrastructure

| Resource | Value |
|---|---|
| GCP project | `raito-house-of-brands` |
| Region | `me-west1` |
| Cloud SQL instance | `raito-db` (PostgreSQL 15) |
| DB connection | Unix socket `?host=/cloudsql/raito-house-of-brands:me-west1:raito-db` |
| Artifact Registry | `me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-agents` |
| Slack webhook secret | GCP Secret Manager: `raito-slack-webhook` (version 2) |
| Slack channel | `#raito-alerts` on `raitocorp.slack.com` |

**CRITICAL — Cloud SQL socket:** All `gcloud run jobs create/update` commands **must** include:
```
--set-cloudsql-instances=raito-house-of-brands:me-west1:raito-db
```
Without this flag the job starts but fails immediately: `No such file: /cloudsql/.../s.PGSQL.5432`.

---

## The Five Agents

### 1. Data Steward (`raito-data-steward`)
**Role:** Watches `weekly_chart_overrides` for new uploads. Validates revenue/unit totals. Emits `new_data_ingested` signal to trigger the Insight Analyst.

**Schedule:** `0 7 * * *` (daily 07:00 IL)

**Key logic:**
- Compares total revenue across distributors to known seasonal baselines
- Flags gaps where expected weekly data is missing
- Validates that unit-to-revenue ratios are within expected bounds

---

### 2. Insight Analyst (`raito-insight-analyst`)
**Role:** Generates the weekly intelligence report. Queries `weekly_chart_overrides` + fetches live SP data from Cloud Run dashboard. Stores JSON report in `weekly_intelligence_reports` table.

**Schedule:** `0 6 * * 0` (Sundays 06:00 IL) + triggered by `new_data_ingested` signal.

**KPIs computed:**
| KPI | Source | Detail |
|---|---|---|
| Distributor weekly trend | `weekly_chart_overrides` | All W1–W13, revenue + units + WoW% |
| WoW anomalies | `weekly_chart_overrides` | Flag ±40% change per distributor |
| Biscotti growth | `weekly_chart_overrides` | 4-week rolling avg, direction (growing/stable/declining) |
| Consecutive drop alert | `weekly_chart_overrides` | 3+ weeks falling = at-risk flag |
| Missing upload detection | `weekly_chart_overrides` | Distributor absent from latest week |
| Latest vs season average | `weekly_chart_overrides` | Weak-week flag (<-20% below avg) |
| SP status breakdown | `window.__SP_DATA__` (Cloud Run dashboard) | Active/New/No Mar order/Churned counts + % |
| SP at-risk list | `window.__SP_DATA__` (Cloud Run dashboard) | Top 20 churned/no-mar-order by historical volume |
| SP new salepoints | `window.__SP_DATA__` (Cloud Run dashboard) | First-order salepoints, sorted by Mar units |
| SP trend summary | `window.__SP_DATA__` (Cloud Run dashboard) | Count growing/flat/declining (±10% threshold) |
| SP by distributor | `window.__SP_DATA__` (Cloud Run dashboard) | Active/new/at-risk/churned per Icedream/Ma'ayan/Biscotti |

**SP data extraction:** Fetches `https://raito-dashboard-20004010285.me-west1.run.app`, extracts `window.__SP_DATA__` via regex, parses as JSON. Always reflects the latest dashboard build.

**Report storage:**
- DB: `weekly_intelligence_reports` table (JSONB `report` column)
- File: `docs/reports/weekly_report_YYYY-MM-DD.json`

---

### 3. DevOps Watchdog (`raito-devops-watchdog`)
**Role:** Monitors Cloud Run health, checks that the Flask dashboard server is reachable, verifies DB connectivity.

**Schedule:** `0 */6 * * *` (every 6 hours)

**Checks:**
- Flask server (`https://raito-dashboard-20004010285.me-west1.run.app/health`) responds 200
- Cloud SQL connection can execute a simple SELECT
- Emits Slack alert on any failure

---

### 4. UX Architect (`raito-ux-architect`)
**Role:** Receives `anomalies_detected` signals from the Insight Analyst and formats them into human-readable Slack messages.

**Trigger:** Signal-driven only (no schedule)

**Input:** `{anomalies: [...], drop_streaks: [...], week_label: "W13/2026"}`

**Output:** Formatted Slack message to `#raito-alerts`

---

### 5. QA Agent (`raito-qa-agent`)
**Role:** Cross-tab parity checks and dashboard health validation.

**Schedule:** `0 8 * * *` (daily 08:00 IL)

**Checks (17 total):**
| Check | Source | Threshold |
|---|---|---|
| BO total extractable | Cloud Run dashboard HTML | Must find `_iceWkRev` array |
| CC total extractable | Cloud Run dashboard HTML | Must find `_maayWkRev` dict |
| SP total extractable | Cloud Run dashboard HTML | Must find `window.__SP_DATA__` |
| BO↔SP revenue parity | Cloud Run dashboard HTML | warn >0.5%, fail >2% |
| BO↔CC revenue parity | Cloud Run dashboard HTML | warn >3%, fail >10% (CC uses different pricing methodology) |
| DB row count | `weekly_chart_overrides` | ≥1 row (table only populated on file upload) |
| Flask server reachable | `https://raito-dashboard-20004010285.me-west1.run.app` | HTTP 200 |
| Cloud Run dashboard reachable | `https://raito-dashboard-20004010285.me-west1.run.app` | HTTP 200 |

**Two URLs used (important distinction):**
- `CLOUD_RUN_URL = "https://raito-dashboard-20004010285.me-west1.run.app"` — Flask server (endpoint check only)
- `DASHBOARD_HTML_URL = "https://raito-dashboard-20004010285.me-west1.run.app"` — same as CLOUD_RUN_URL (parity checks — has the actual BO/CC/SP data)

**Known parity snapshot (28 Mar 2026):** BO=₪4,010,667 | CC=₪4,018,097 | SP=₪4,010,622. BO↔SP gap ₪45 (0.00%). BO↔CC gap ₪7,430 (0.18%) — acceptable, within warn threshold. CC uses different pricing methodology.

---

## Database Tables (Agent-Owned)

| Table | Purpose | Key Columns |
|---|---|---|
| `weekly_chart_overrides` | Primary data table. One row per distributor per week. | `distributor`, `week_num`, `units`, `revenue`, `label`, `source_file` |
| `master_data` | Metadata/reference. | (schema TBD) |
| `agent_state` | Per-agent key-value store. | `agent_name`, `key`, `value` |
| `agent_runs` | Run history + results. | `agent_name`, `run_at`, `result_json`, `status` |
| `agent_signals` | Inter-agent signal queue. | `from_agent`, `to_agent`, `signal`, `payload`, `consumed_at` |
| `qa_results` | QA check history. | `check_name`, `status`, `detail`, `run_at` |
| `weekly_intelligence_reports` | Insight Analyst reports. | `report_date`, `week_label`, `distributor`, `report` (JSONB) |

**IMPORTANT:** There is NO `sales_transactions` table in this DB. The schema described in the Phase 4 section of RAITO_BRIEFING.md (`sales_transactions`, `ingestion_batches`, `sale_points`, etc.) was planned but never fully populated. The only populated tables are `weekly_chart_overrides` and `master_data`. Any agent SQL query against `sales_transactions` will throw a PostgreSQL error.

---

## Rebuild & Redeploy

After modifying any agent file in `scripts/agents/`:

```bash
cd ~/dataset

# 1. Rebuild Docker image
docker build --platform linux/amd64 \
  -f deploy/agents/Dockerfile.agents \
  -t me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-agents:latest .

# 2. Push
docker push me-west1-docker.pkg.dev/raito-house-of-brands/raito-repo/raito-agents:latest

# 3. Deploy all 5 jobs (updates schedule + image)
bash deploy/agents/deploy_agents.sh
```

### Trigger an agent manually

```bash
# Run the Insight Analyst now
gcloud run jobs execute raito-insight-analyst \
  --region=me-west1 --project=raito-house-of-brands

# Run the QA agent now
gcloud run jobs execute raito-qa-agent \
  --region=me-west1 --project=raito-house-of-brands
```

### Monitor execution

```bash
# List recent executions
gcloud run jobs executions list \
  --job=raito-insight-analyst \
  --region=me-west1 --project=raito-house-of-brands

# View logs for a specific execution
gcloud logging read \
  'resource.type="cloud_run_job" resource.labels.job_name="raito-insight-analyst"' \
  --limit=50 --project=raito-house-of-brands
```

Or: GCP Console → Cloud Run → Jobs → select job → Executions tab.

---

## Cloud Run Job Schedule Reference

| Job name | Schedule | IL time |
|---|---|---|
| `raito-data-steward` | `0 7 * * *` | Daily 07:00 |
| `raito-insight-analyst` | `0 6 * * 0` | Sunday 06:00 |
| `raito-devops-watchdog` | `0 */6 * * *` | Every 6 hours |
| `raito-ux-architect` | Signal-driven | On anomaly detected |
| `raito-qa-agent` | `0 8 * * *` | Daily 08:00 |

---

## Slack Webhook

**Webhook URL:** Stored in GCP Secret Manager as `raito-slack-webhook` (version 2).
**Channel:** `#raito-alerts` on `raitocorp.slack.com`
**App name:** "Raito Alerts"

To update the webhook (if the URL changes):
```bash
echo -n "https://hooks.slack.com/services/YOUR/NEW/URL" | \
  gcloud secrets versions add raito-slack-webhook \
  --project=raito-house-of-brands --data-file=-
```

---

## Agent Architecture Notes

- All agents inherit from `RaitoAgent` in `scripts/agents/base_agent.py`
- Orchestrator registry: `scripts/agents/orchestrator.py` — `AGENT_REGISTRY` maps names to class paths
- Agents communicate via `agent_signals` table (not HTTP). `state.emit_signal(to_agent, signal, payload)` → `state.consume_signals(signal_name)`.
- Cloud Run Jobs are stateless — all state lives in `agent_state` table.
- Each run inserts a row into `agent_runs` with `status` = `success|error` and full `result_json`.

---

## Known Issues

1. **`window.__SP_DATA__` regex** in Insight Analyst uses `\{.*?\}` with `re.DOTALL`. If the JSON object contains a trailing semicolon on the same line as the closing brace, the match works. If the format changes (e.g. minified HTML removes the newline), the regex `;\s*\n` may not match — update to `;\s*` if needed.
2. **QA parity warns when BO=0** — If the Cloud Run dashboard dashboard can't be fetched (e.g. GitHub outage), the parity check produces `_warn` rather than `_fail`. This prevents false alarms during deploy but means a real parity break during an outage is masked. Accept this trade-off for now.
3. **Insight Analyst only runs Sunday** — If a critical anomaly happens Monday–Saturday, it won't surface until the following Sunday unless triggered manually or by a `new_data_ingested` signal from the Data Steward.
