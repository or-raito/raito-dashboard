"""
ux_architect.py — UX/UI Architect Agent
Role: Analyzes current Flask routes, reacts to anomalies from InsightAnalyst,
      and proposes concrete dashboard improvements: new chart types, KPI cards,
      and filter enhancements. Writes proposals as JSON + Markdown to docs/.

Trigger: Cloud Scheduler → weekly (Monday 07:00),
         OR immediately when signal 'anomalies_detected' is received.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from agents.base_agent import RaitoAgent


PROPOSAL_DDL = """
CREATE TABLE IF NOT EXISTS ux_proposals (
    id           SERIAL      PRIMARY KEY,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trigger      TEXT,
    proposals    JSONB       NOT NULL
);
"""


class UXArchitectAgent(RaitoAgent):
    """
    Proposes frontend improvements based on data patterns and anomalies.

    Reads:
      - 'anomalies_detected' signals from InsightAnalyst
      - Current Flask routes from db_dashboard.py
      - Latest weekly report from weekly_intelligence_reports table

    Outputs:
      - JSON proposals saved to DB + docs/proposals/
      - Markdown spec file ready to hand to a developer
    """

    name = "ux_architect"

    SCRIPTS_DIR = Path(__file__).parents[1]
    DASHBOARD_PY = SCRIPTS_DIR / "db" / "db_dashboard.py"
    CC_DASHBOARD_PY = SCRIPTS_DIR / "cc_dashboard.py"

    def before_run(self):
        self.execute_sql(PROPOSAL_DDL)

    # ── Route analyzer ────────────────────────────────────────────────────

    def _extract_flask_routes(self) -> list[dict]:
        """Parse db_dashboard.py for @app.route decorators."""
        if not self.DASHBOARD_PY.exists():
            return []
        src = self.DASHBOARD_PY.read_text()
        routes = []
        for m in re.finditer(
            r'@app\.route\(["\']([^"\']+)["\'](?:,\s*methods=\[([^\]]+)\])?\)',
            src,
        ):
            routes.append({
                "path":    m.group(1),
                "methods": m.group(2).replace('"', "").replace("'", "").split(", ")
                           if m.group(2) else ["GET"],
            })
        return routes

    def _count_chart_types(self) -> dict:
        """Count Chart.js chart types currently used in cc_dashboard.py."""
        if not self.CC_DASHBOARD_PY.exists():
            return {}
        src = self.CC_DASHBOARD_PY.read_text()
        types = ["line", "bar", "doughnut", "pie", "radar", "scatter", "bubble"]
        return {t: src.lower().count(f"type: '{t}'") for t in types if f"type: '{t}'" in src.lower()}

    def _get_latest_report(self) -> dict | None:
        rows = self.query(
            """SELECT report FROM weekly_intelligence_reports
               ORDER BY generated_at DESC LIMIT 1"""
        )
        return rows[0]["report"] if rows else None

    # ── Proposal generators ───────────────────────────────────────────────

    def _propose_for_anomalies(self, anomalies: list[dict]) -> list[dict]:
        proposals = []
        for a in anomalies:
            if a["flag"] == "drop":
                proposals.append({
                    "type":     "alert_banner",
                    "priority": "high",
                    "title":    f"Revenue Drop Alert — {a['distributor']}",
                    "description": (
                        f"Add a prominent red banner on the BO tab when WoW drop exceeds 30%."
                        f" Week {a['week']}: {a['change_pct']}% drop detected."
                    ),
                    "implementation": (
                        "In cc_dashboard.py renderKPI(), check _iceWkRev WoW ratio "
                        "and inject an alert div above the weekly chart when drop > 0.3."
                    ),
                })
            elif a["flag"] == "spike":
                proposals.append({
                    "type":     "annotation",
                    "priority": "medium",
                    "title":    f"Revenue Spike Annotation — {a['distributor']}",
                    "description": (
                        f"Annotate the weekly chart bar for week {a['week']} with a ⬆ icon "
                        f"and tooltip showing +{a['change_pct']}% WoW."
                    ),
                    "implementation": (
                        "Use Chart.js chartjs-plugin-annotation to add a label on the "
                        "spike bar index in renderWeeklyChart()."
                    ),
                })
        return proposals

    def _propose_new_charts(self, chart_counts: dict, report: dict | None) -> list[dict]:
        proposals = []

        if chart_counts.get("scatter", 0) == 0:
            proposals.append({
                "type":     "new_chart",
                "priority": "medium",
                "title":    "Distributor Revenue vs. Weeks Active Scatter Plot",
                "description": (
                    "Add a scatter plot (BO tab) with X=weeks reported, "
                    "Y=total season revenue per distributor. Size = total units. "
                    "Useful when more distributors are added."
                ),
                "api_endpoint": "/api/distributor-scatter",
                "implementation": (
                    "Query: SELECT distributor, COUNT(*) AS weeks_reported, "
                    "SUM(revenue) AS total_revenue, SUM(units) AS total_units "
                    "FROM weekly_chart_overrides GROUP BY 1"
                ),
            })

        if chart_counts.get("radar", 0) == 0:
            proposals.append({
                "type":     "new_chart",
                "priority": "low",
                "title":    "Distributor Performance Radar Chart",
                "description": (
                    "Spider/radar chart comparing Icedream, Ma'ayan, Biscotti across axes: "
                    "Revenue, Units, Weeks Active, WoW Growth. "
                    "Gives executives a single-glance competitive view."
                ),
                "implementation": (
                    "Chart.js type: 'radar' in BO tab. Data from "
                    "SELECT distributor, SUM(revenue), SUM(units), COUNT(*) "
                    "FROM weekly_chart_overrides GROUP BY 1"
                ),
            })

        if report:
            sp_kpis = report.get("salepoint_kpis", {})
            at_risk_count = sp_kpis.get("at_risk_count", 0)
            if at_risk_count > 10:
                proposals.append({
                    "type":     "new_section",
                    "priority": "high",
                    "title":    "At-Risk Sale Points Panel",
                    "description": (
                        f"{at_risk_count} sale points are Churned or No Mar order. "
                        "Add a collapsible 'At Risk' panel to the SP tab listing the top 20 "
                        "at-risk sale points with their last active month and total units."
                    ),
                    "implementation": (
                        "New JS section in salepoint_dashboard.py. Filter salepoints where "
                        "status == 'Churned' or 'No Mar order', sort by total desc, show top 20."
                    ),
                })

        return proposals

    def _propose_api_endpoints(self, existing_routes: list[dict]) -> list[dict]:
        existing_paths = {r["path"] for r in existing_routes}
        proposals = []
        needed = [
            {
                "path":   "/api/distributor-scatter",
                "method": "GET",
                "description": "Returns per-distributor season totals for scatter plot",
                "sql": (
                    "SELECT distributor, "
                    "COUNT(*) AS weeks_reported, "
                    "SUM(units) AS total_units, "
                    "SUM(revenue) AS total_revenue "
                    "FROM weekly_chart_overrides GROUP BY 1"
                ),
            },
            {
                "path":   "/api/distributor-wow",
                "method": "GET",
                "description": "Distributor week-over-week comparison for radar/trend charts",
                "sql": (
                    "SELECT distributor, week_num, units, revenue "
                    "FROM weekly_chart_overrides "
                    "ORDER BY distributor, week_num"
                ),
            },
        ]
        for endpoint in needed:
            if endpoint["path"] not in existing_paths:
                proposals.append({
                    "type":        "new_api_endpoint",
                    "priority":    "medium",
                    "title":       f"API: {endpoint['path']}",
                    **endpoint,
                })
        return proposals

    def _build_markdown_spec(self, proposals: list[dict], trigger: str) -> str:
        today = datetime.now(timezone.utc).date().isoformat()
        lines = [
            f"# RAITO Dashboard — UX Proposals",
            f"Generated: {today}  |  Trigger: {trigger}",
            "",
            f"## Summary",
            f"Total proposals: {len(proposals)}",
            f"- High priority: {sum(1 for p in proposals if p.get('priority') == 'high')}",
            f"- Medium priority: {sum(1 for p in proposals if p.get('priority') == 'medium')}",
            f"- Low priority: {sum(1 for p in proposals if p.get('priority') == 'low')}",
            "",
        ]
        for i, p in enumerate(sorted(proposals, key=lambda x: {'high':0,'medium':1,'low':2}.get(x.get('priority','low'), 2)), 1):
            lines += [
                f"## {i}. [{p.get('priority','').upper()}] {p.get('title', p.get('description','Untitled')[:60])}",
                f"**Type:** `{p.get('type','unknown')}`",
                "",
                p.get("description", ""),
                "",
            ]
            if p.get("implementation"):
                lines += [f"**Implementation:** {p['implementation']}", ""]
            if p.get("sql"):
                lines += [f"**SQL:**", f"```sql", p["sql"], f"```", ""]
            if p.get("api_endpoint"):
                lines += [f"**New API endpoint:** `GET {p['api_endpoint']}`", ""]
        return "\n".join(lines)

    # ── Main execute ──────────────────────────────────────────────────────

    def execute(self) -> dict:
        signals = self.state.consume_signals("anomalies_detected")
        trigger = "signal:anomalies_detected" if signals else "scheduled"
        anomalies_from_signals = []
        for s in signals:
            anomalies_from_signals.extend(s["payload"].get("anomalies", []))

        self.log.info(f"Running ({trigger}), anomalies from signals: {len(anomalies_from_signals)}")

        routes      = self._extract_flask_routes()
        chart_types = self._count_chart_types()
        report      = self._get_latest_report()

        self.log.info(f"Found {len(routes)} Flask routes, chart types: {chart_types}")

        proposals = (
            self._propose_for_anomalies(anomalies_from_signals)
            + self._propose_new_charts(chart_types, report)
            + self._propose_api_endpoints(routes)
        )

        # Save to DB
        today = datetime.now(timezone.utc).date().isoformat()
        self.execute_sql(
            "INSERT INTO ux_proposals (trigger, proposals) VALUES (%s, %s::jsonb)",
            (trigger, json.dumps(proposals)),
        )

        # Save Markdown spec
        out_dir = Path(__file__).parents[2] / "docs" / "proposals"
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / f"ux_proposals_{today}.md"
        md_path.write_text(self._build_markdown_spec(proposals, trigger), encoding="utf-8")

        json_path = out_dir / f"ux_proposals_{today}.json"
        json_path.write_text(json.dumps(proposals, indent=2, ensure_ascii=False), encoding="utf-8")

        self.log.info(f"Proposals saved → {md_path}")

        return {
            "trigger":         trigger,
            "proposals_count": len(proposals),
            "high_priority":   sum(1 for p in proposals if p.get("priority") == "high"),
            "routes_analyzed": len(routes),
            "chart_types":     chart_types,
            "output_md":       str(md_path),
            "output_json":     str(json_path),
        }


if __name__ == "__main__":
    agent = UXArchitectAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))
