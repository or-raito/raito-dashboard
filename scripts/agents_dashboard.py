#!/usr/bin/env python3
"""
RAITO Agents Monitor — Tab 6: Agent Health & Activity
======================================================

Queries the agent_runs, agent_signals, and agent_state tables from the
Cloud SQL DB and renders a monitoring tab for the unified dashboard.

Call: build_agents_tab() → returns an HTML string to be embedded in
unified_dashboard.py as the 6th tab.

Falls back gracefully if DB is unreachable (shows empty state with message).
"""

from __future__ import annotations
import json
import os
from datetime import datetime, timezone

# ── Agent metadata ─────────────────────────────────────────────────────────────

AGENT_META = {
    "data_steward": {
        "label": "Data Steward",
        "schedule": "Daily 07:00 IL",
        "icon": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>""",
        "role": "Watches for new weekly uploads, validates revenue/unit totals, emits data-ready signals.",
        "color": "#6366f1",
    },
    "insight_analyst": {
        "label": "Insight Analyst",
        "schedule": "Sunday 06:00 IL",
        "icon": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>""",
        "role": "Generates weekly intelligence reports — trends, WoW anomalies, SP breakdowns.",
        "color": "#10b981",
    },
    "devops_watchdog": {
        "label": "DevOps Watchdog",
        "schedule": "Every 6 hours",
        "icon": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>""",
        "role": "Monitors Cloud Run health, DB connectivity, and endpoint latency. Sends Slack alerts on failure.",
        "color": "#f59e0b",
    },
    "qa_agent": {
        "label": "QA Agent",
        "schedule": "Daily 08:00 IL",
        "icon": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>""",
        "role": "Cross-tab parity checks — BO↔SP↔CC revenue alignment, dashboard reachability, data integrity.",
        "color": "#0ea5e9",
    },
    "ux_architect": {
        "label": "UX Architect",
        "schedule": "Signal-driven",
        "icon": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8h1a4 4 0 010 8h-1"/><path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/></svg>""",
        "role": "Formats anomaly alerts from the Insight Analyst into human-readable Slack messages.",
        "color": "#a855f7",
    },
}


def _get_db_conn():
    """Get a psycopg2 connection using the same env var as the agents."""
    try:
        import psycopg2
        url = os.environ.get("DATABASE_URL", "postgresql://raito:raito@localhost:5432/raito")
        conn = psycopg2.connect(url)
        conn.autocommit = True
        return conn
    except Exception:
        return None


def _fetch_agent_data() -> dict:
    """
    Query agent_runs and agent_signals from DB.
    Returns dict with keys: runs (list), signals (list), error (str|None).
    """
    conn = _get_db_conn()
    if conn is None:
        return {"runs": [], "signals": [], "error": "Could not connect to database"}

    try:
        import psycopg2.extras
        result = {"runs": [], "signals": [], "error": None}

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Last 3 runs per agent
            cur.execute("""
                SELECT agent_name, started_at, finished_at, status, summary, error,
                       ROW_NUMBER() OVER (PARTITION BY agent_name ORDER BY started_at DESC) AS rn
                FROM agent_runs
                WHERE started_at > NOW() - INTERVAL '30 days'
            """)
            all_runs = [dict(r) for r in cur.fetchall()]
            result["runs"] = [r for r in all_runs if r["rn"] <= 3]

            # Last 10 signals
            cur.execute("""
                SELECT from_agent, to_agent, signal, payload, created_at, consumed
                FROM agent_signals
                ORDER BY created_at DESC
                LIMIT 10
            """)
            result["signals"] = [dict(r) for r in cur.fetchall()]

        conn.close()
        return result
    except Exception as e:
        return {"runs": [], "signals": [], "error": str(e)}


def _fmt_dt(dt) -> str:
    """Format a datetime for display."""
    if dt is None:
        return "—"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return dt
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _elapsed(started, finished) -> str:
    if started is None or finished is None:
        return "—"
    try:
        if isinstance(started, str):
            started = datetime.fromisoformat(started.replace("Z", "+00:00"))
        if isinstance(finished, str):
            finished = datetime.fromisoformat(finished.replace("Z", "+00:00"))
        diff = (finished - started).total_seconds()
        return f"{diff:.1f}s"
    except Exception:
        return "—"


def _build_run_history_html(runs: list, agent_name: str) -> str:
    """Build the run history rows for one agent."""
    agent_runs = [r for r in runs if r["agent_name"] == agent_name]
    if not agent_runs:
        return '<div class="ag-no-runs">No runs recorded yet</div>'

    rows = []
    for r in agent_runs:
        status = r.get("status", "unknown")
        status_cls = {"success": "ag-status-ok", "error": "ag-status-err", "running": "ag-status-run"}.get(status, "ag-status-unknown")
        status_icon = {"success": "✓", "error": "✗", "running": "◌"}.get(status, "?")

        summary = r.get("summary") or {}
        if isinstance(summary, str):
            try:
                summary = json.loads(summary)
            except Exception:
                summary = {}

        # Build summary detail line
        detail_parts = []
        if status == "error":
            err = r.get("error") or summary.get("error", "")
            detail_parts.append(f'<span class="ag-err-msg">{str(err)[:120]}</span>')
        else:
            # Show meaningful keys from summary
            skip_keys = {"elapsed_s", "error"}
            for k, v in summary.items():
                if k in skip_keys:
                    continue
                if isinstance(v, (int, float)):
                    detail_parts.append(f'<span class="ag-kv"><b>{k.replace("_", " ")}</b>: {v}</span>')
                elif isinstance(v, str) and len(v) < 60:
                    detail_parts.append(f'<span class="ag-kv"><b>{k.replace("_", " ")}</b>: {v}</span>')
                elif isinstance(v, list) and len(v) > 0:
                    detail_parts.append(f'<span class="ag-kv"><b>{k.replace("_", " ")}</b>: {len(v)} items</span>')

        elapsed = _elapsed(r.get("started_at"), r.get("finished_at"))
        when = _fmt_dt(r.get("started_at"))
        detail_html = ' &nbsp;·&nbsp; '.join(detail_parts[:6]) if detail_parts else '<span class="ag-no-detail">No summary data</span>'

        rows.append(f"""
        <div class="ag-run-row">
          <span class="ag-run-status {status_cls}">{status_icon}</span>
          <div class="ag-run-body">
            <div class="ag-run-meta"><span class="ag-run-when">{when}</span><span class="ag-run-elapsed">{elapsed}</span></div>
            <div class="ag-run-detail">{detail_html}</div>
          </div>
        </div>""")

    return '\n'.join(rows)


def _build_agent_card(agent_id: str, meta: dict, runs: list) -> str:
    """Build one agent status card."""
    agent_runs = [r for r in runs if r["agent_name"] == agent_id]
    latest = agent_runs[0] if agent_runs else None

    status = latest["status"] if latest else "never"
    pill_cls = {"success": "ag-pill-ok", "error": "ag-pill-err", "running": "ag-pill-run"}.get(status, "ag-pill-never")
    pill_label = {"success": "OK", "error": "ERROR", "running": "RUNNING"}.get(status, "NEVER RUN")
    last_run = _fmt_dt(latest["started_at"]) if latest else "—"

    run_history_html = _build_run_history_html(runs, agent_id)
    color = meta["color"]

    return f"""
    <div class="ag-card" data-agent="{agent_id}">
      <div class="ag-card-header" style="border-left: 4px solid {color}">
        <div class="ag-card-icon" style="color:{color}">{meta["icon"]}</div>
        <div class="ag-card-title">
          <div class="ag-card-name">{meta["label"]}</div>
          <div class="ag-card-schedule">{meta["schedule"]}</div>
        </div>
        <span class="ag-pill {pill_cls}">{pill_label}</span>
      </div>
      <div class="ag-card-role">{meta["role"]}</div>
      <div class="ag-card-last">Last run: <strong>{last_run}</strong></div>
      <div class="ag-run-history">
        {run_history_html}
      </div>
    </div>"""


def build_agents_tab() -> str:
    """Build the Agents Monitor tab HTML. Returns an HTML string."""

    data = _fetch_agent_data()
    runs = data["runs"]
    signals = data["signals"]
    db_error = data["error"]

    # Build agent cards
    cards_html = '\n'.join(
        _build_agent_card(agent_id, meta, runs)
        for agent_id, meta in AGENT_META.items()
    )

    # Build signals table
    if signals:
        sig_rows = []
        for s in signals:
            consumed = "✓" if s.get("consumed") else "◌"
            consumed_cls = "ag-sig-consumed" if s.get("consumed") else "ag-sig-pending"
            when = _fmt_dt(s.get("created_at"))
            payload = s.get("payload") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            payload_str = ", ".join(f"{k}: {v}" for k, v in list(payload.items())[:3]) if payload else "—"
            sig_rows.append(f"""
            <tr>
              <td>{when}</td>
              <td><span class="ag-agent-badge">{s.get("from_agent","?")}</span></td>
              <td>→ <span class="ag-agent-badge">{s.get("to_agent","?")}</span></td>
              <td><code>{s.get("signal","?")}</code></td>
              <td class="ag-payload">{payload_str}</td>
              <td><span class="{consumed_cls}">{consumed}</span></td>
            </tr>""")
        signals_html = f"""
        <table class="ag-sig-table">
          <thead><tr><th>When</th><th>From</th><th>To</th><th>Signal</th><th>Payload</th><th>Consumed</th></tr></thead>
          <tbody>{''.join(sig_rows)}</tbody>
        </table>"""
    else:
        signals_html = '<div class="ag-empty">No signals in the last 30 days</div>'

    # DB error banner
    error_banner = ""
    if db_error:
        error_banner = f'<div class="ag-db-error">⚠ DB connection issue: {db_error} — showing empty state. Agents will still run on schedule.</div>'

    # Summary stats
    total_runs = len(runs)
    success_runs = sum(1 for r in runs if r.get("status") == "success")
    error_runs = sum(1 for r in runs if r.get("status") == "error")

    return f"""
<!-- =========================================================
     TAB 6: Agent Monitor
     ========================================================= -->
<div id="tab-agents" class="tab-content">

<style>
/* ── Agent Monitor Tab Styles ──────────────────────────────── */
#tab-agents {{
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background: #F8F9FB;
  min-height: 100vh;
  padding: 0;
}}
.ag-header {{
  background: #fff;
  border-bottom: 1px solid #E2E8F0;
  padding: 20px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.ag-header-left h2 {{
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 2px 0;
}}
.ag-header-left p {{
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
}}
.ag-stats-bar {{
  display: flex;
  gap: 20px;
}}
.ag-stat {{
  text-align: center;
}}
.ag-stat-val {{
  font-size: 22px;
  font-weight: 800;
  color: #1e293b;
  line-height: 1;
}}
.ag-stat-val.ok {{ color: #10b981; }}
.ag-stat-val.err {{ color: #ef4444; }}
.ag-stat-label {{
  font-size: 10px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-top: 2px;
}}
.ag-refresh-btn {{
  background: #f1f5f9;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 7px 14px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}}
.ag-refresh-btn:hover {{ background: #e2e8f0; }}

.ag-body {{ padding: 24px 28px; }}
.ag-section-title {{
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin: 0 0 14px 0;
}}
.ag-cards-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}}
.ag-card {{
  background: #fff;
  border-radius: 16px;
  border: 1px solid #E2E8F0;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}}
.ag-card-header {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px 12px;
  background: #fff;
}}
.ag-card-icon svg {{
  width: 20px;
  height: 20px;
}}
.ag-card-title {{
  flex: 1;
}}
.ag-card-name {{
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}}
.ag-card-schedule {{
  font-size: 11px;
  color: #94a3b8;
  margin-top: 1px;
}}
.ag-pill {{
  font-size: 10px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 20px;
  letter-spacing: 0.4px;
}}
.ag-pill-ok {{ background: rgba(16,185,129,0.1); color: #10b981; }}
.ag-pill-err {{ background: rgba(239,68,68,0.1); color: #ef4444; }}
.ag-pill-run {{ background: rgba(245,158,11,0.1); color: #f59e0b; }}
.ag-pill-never {{ background: #f1f5f9; color: #94a3b8; }}
.ag-card-role {{
  font-size: 12px;
  color: #64748b;
  padding: 0 18px 10px;
  line-height: 1.5;
}}
.ag-card-last {{
  font-size: 11px;
  color: #94a3b8;
  padding: 0 18px 10px;
}}
.ag-card-last strong {{ color: #475569; }}
.ag-run-history {{
  border-top: 1px solid #f1f5f9;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}}
.ag-run-row {{
  display: flex;
  align-items: flex-start;
  gap: 10px;
}}
.ag-run-status {{
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 1px;
}}
.ag-status-ok {{ background: rgba(16,185,129,0.12); color: #10b981; }}
.ag-status-err {{ background: rgba(239,68,68,0.12); color: #ef4444; }}
.ag-status-run {{ background: rgba(245,158,11,0.12); color: #f59e0b; }}
.ag-status-unknown {{ background: #f1f5f9; color: #94a3b8; }}
.ag-run-body {{ flex: 1; min-width: 0; }}
.ag-run-meta {{
  display: flex;
  justify-content: space-between;
  margin-bottom: 2px;
}}
.ag-run-when {{ font-size: 11px; color: #475569; font-weight: 600; }}
.ag-run-elapsed {{ font-size: 11px; color: #94a3b8; }}
.ag-run-detail {{ font-size: 11px; color: #94a3b8; line-height: 1.4; word-break: break-word; }}
.ag-kv b {{ color: #475569; font-weight: 600; }}
.ag-err-msg {{ color: #ef4444; }}
.ag-no-detail {{ color: #cbd5e1; font-style: italic; }}
.ag-no-runs {{ font-size: 12px; color: #cbd5e1; font-style: italic; padding: 4px 4px; }}

/* Signals section */
.ag-signals-section {{
  background: #fff;
  border-radius: 16px;
  border: 1px solid #E2E8F0;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  margin-bottom: 24px;
}}
.ag-signals-header {{
  padding: 14px 18px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.ag-sig-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}}
.ag-sig-table th {{
  text-align: left;
  padding: 8px 16px;
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  border-bottom: 1px solid #f1f5f9;
  background: #fafafa;
}}
.ag-sig-table td {{
  padding: 9px 16px;
  color: #475569;
  border-bottom: 1px solid #f8f9fb;
}}
.ag-sig-table code {{
  background: #f1f5f9;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 11px;
  color: #6366f1;
}}
.ag-agent-badge {{
  background: #f1f5f9;
  border-radius: 6px;
  padding: 2px 7px;
  font-size: 10px;
  font-weight: 600;
  color: #475569;
  white-space: nowrap;
}}
.ag-payload {{ color: #94a3b8; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.ag-sig-consumed {{ color: #10b981; font-weight: 700; }}
.ag-sig-pending {{ color: #f59e0b; font-weight: 700; }}

.ag-db-error {{
  background: rgba(239,68,68,0.06);
  border: 1px solid rgba(239,68,68,0.2);
  border-radius: 10px;
  padding: 10px 16px;
  font-size: 12px;
  color: #ef4444;
  margin-bottom: 20px;
}}
.ag-empty {{ padding: 16px 18px; font-size: 12px; color: #cbd5e1; font-style: italic; }}
</style>

<!-- Header -->
<div class="ag-header">
  <div class="ag-header-left">
    <h2>Agent Monitor</h2>
    <p>5 autonomous agents running on Cloud Run — showing last 30 days of activity</p>
  </div>
  <div style="display:flex;align-items:center;gap:20px">
    <div class="ag-stats-bar">
      <div class="ag-stat">
        <div class="ag-stat-val">{total_runs}</div>
        <div class="ag-stat-label">Total Runs</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val ok">{success_runs}</div>
        <div class="ag-stat-label">Succeeded</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val err">{error_runs}</div>
        <div class="ag-stat-label">Errors</div>
      </div>
    </div>
    <button class="ag-refresh-btn" onclick="window.location.reload()">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
      Refresh
    </button>
  </div>
</div>

<div class="ag-body">
  {error_banner}

  <!-- Agent Cards -->
  <div class="ag-section-title">Agents</div>
  <div class="ag-cards-grid">
    {cards_html}
  </div>

  <!-- Signal Bus -->
  <div class="ag-section-title">Signal Bus — Recent Inter-Agent Signals</div>
  <div class="ag-signals-section">
    <div class="ag-signals-header">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      Last 10 signals
    </div>
    {signals_html}
  </div>
</div>

</div><!-- /tab-agents -->
"""
