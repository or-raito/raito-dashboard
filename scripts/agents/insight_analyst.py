"""
insight_analyst.py — Insight Analyst Agent
Role: Periodically queries Cloud SQL to identify trends, anomalies, and
      distributor performance. Generates a Weekly Intelligence Report
      stored as JSON in `weekly_intelligence_reports` table.

DB schema used:
    weekly_chart_overrides(id, distributor, week_num, units, revenue,
                           label, source_file, updated_at)
    Distributors: 'Icedream', 'Ma'ayan', 'Biscotti'
    week_num:     1–13 (ISO week within the season, not calendar week)

Trigger: Cloud Scheduler → every Sunday at 06:00 IL time,
         OR immediately when signal 'new_data_ingested' is received.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal


class _DecimalEncoder(json.JSONEncoder):
    """Convert Decimal (returned by psycopg2 from NUMERIC columns) to float."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[1]))

from agents.base_agent import RaitoAgent

DASHBOARD_HTML_URL = "https://raito-dashboard-20004010285.me-west1.run.app"


REPORT_DDL = """
CREATE TABLE IF NOT EXISTS weekly_intelligence_reports (
    id           SERIAL      PRIMARY KEY,
    report_date  DATE        NOT NULL,
    week_label   TEXT        NOT NULL,
    distributor  TEXT        NOT NULL DEFAULT 'all',
    report       JSONB       NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# Known distributors — used to detect missing weekly uploads
DISTRIBUTORS = ["Icedream", "Ma'ayan", "Biscotti"]

# WoW anomaly threshold
ANOMALY_THRESHOLD_PCT = 0.40   # ±40% week-over-week change


class InsightAnalystAgent(RaitoAgent):
    """
    Generates weekly intelligence reports from weekly_chart_overrides.

    Raito KPIs tracked:
        1. Distributor revenue / units per week (all 13 weeks)
        2. WoW growth rates per distributor — anomaly flagging at ±40%
        3. Biscotti growth rate (focus: is the newest distributor growing?)
        4. Total season revenue split by distributor
        5. Latest-week performance vs season average
        6. Missing-upload detection (distributor not in last week's data)
        7. Consecutive-drop streaks (3+ weeks falling = at-risk flag)

    State keys:
        last_report_date  →  ISO date of last generated report
    """

    name = "insight_analyst"

    def before_run(self):
        self.execute_sql(REPORT_DDL)

    # ─────────────────────────────────────────────────────────────────────────
    # Data fetchers — all use weekly_chart_overrides
    # ─────────────────────────────────────────────────────────────────────────

    def _all_weekly_data(self) -> list[dict]:
        """Full weekly_chart_overrides table, ordered by distributor + week."""
        return self.query(
            """
            SELECT distributor, week_num, units, revenue, label, source_file
            FROM   weekly_chart_overrides
            ORDER  BY distributor, week_num
            """
        )

    def _latest_week_num(self) -> int | None:
        """Highest week_num that has data for at least one distributor."""
        rows = self.query(
            "SELECT MAX(week_num) AS max_week FROM weekly_chart_overrides"
        )
        if rows and rows[0]["max_week"] is not None:
            return int(rows[0]["max_week"])
        return None

    def _season_totals_by_distributor(self) -> list[dict]:
        """Full-season revenue + units per distributor."""
        return self.query(
            """
            SELECT distributor,
                   SUM(revenue) AS total_revenue,
                   SUM(units)   AS total_units,
                   COUNT(*)     AS weeks_reported
            FROM   weekly_chart_overrides
            GROUP  BY distributor
            ORDER  BY total_revenue DESC
            """
        )

    def _latest_week_data(self, week_num: int) -> list[dict]:
        """Revenue / units for a specific week."""
        return self.query(
            """
            SELECT distributor, week_num, units, revenue
            FROM   weekly_chart_overrides
            WHERE  week_num = %s
            ORDER  BY revenue DESC
            """,
            (week_num,),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # KPI analytics
    # ─────────────────────────────────────────────────────────────────────────

    def _build_distributor_trends(self, all_rows: list[dict]) -> dict[str, list[dict]]:
        """
        Returns {distributor: [{week_num, revenue, units, wow_pct}, ...]}
        sorted by week_num ascending.  wow_pct is None for week 1.
        """
        from collections import defaultdict
        by_dist: dict[str, list[dict]] = defaultdict(list)
        for row in all_rows:
            by_dist[row["distributor"]].append(row)

        result: dict[str, list[dict]] = {}
        for dist, rows in by_dist.items():
            rows = sorted(rows, key=lambda r: r["week_num"])
            enriched = []
            for i, row in enumerate(rows):
                prev_rev = float(rows[i - 1]["revenue"] or 0) if i > 0 else None
                curr_rev = float(row["revenue"] or 0)
                wow_pct: float | None = None
                if prev_rev is not None and prev_rev != 0:
                    wow_pct = round((curr_rev - prev_rev) / prev_rev * 100, 1)
                enriched.append({
                    "week_num": row["week_num"],
                    "label":    row.get("label", f"W{row['week_num']}"),
                    "revenue":  round(curr_rev, 2),
                    "units":    int(row["units"] or 0),
                    "wow_pct":  wow_pct,
                })
            result[dist] = enriched
        return result

    def _wow_anomalies(self, trends: dict[str, list[dict]]) -> list[dict]:
        """Flag weeks where WoW revenue change exceeds ±40%."""
        anomalies = []
        for dist, rows in trends.items():
            for row in rows:
                if row["wow_pct"] is None:
                    continue
                if abs(row["wow_pct"]) > ANOMALY_THRESHOLD_PCT * 100:
                    anomalies.append({
                        "distributor": dist,
                        "week_num":    row["week_num"],
                        "label":       row["label"],
                        "prev_revenue": round(
                            row["revenue"] / (1 + row["wow_pct"] / 100), 2
                        ),
                        "curr_revenue": row["revenue"],
                        "change_pct":  row["wow_pct"],
                        "flag":        "spike" if row["wow_pct"] > 0 else "drop",
                    })
        return sorted(anomalies, key=lambda a: (a["week_num"], a["distributor"]))

    def _biscotti_growth_kpi(self, trends: dict[str, list[dict]]) -> dict:
        """
        Biscotti-specific growth analysis:
        - 4-week rolling average revenue
        - Overall trend direction (growing / stable / declining)
        - Last 4 weeks WoW changes
        """
        rows = trends.get("Biscotti", [])
        if not rows:
            return {"status": "no_data", "note": "Biscotti not in weekly_chart_overrides"}

        last4 = rows[-4:]
        avg_rev = round(sum(r["revenue"] for r in last4) / len(last4), 2)

        wow_changes = [r["wow_pct"] for r in last4 if r["wow_pct"] is not None]
        avg_wow = round(sum(wow_changes) / len(wow_changes), 1) if wow_changes else None

        if avg_wow is None:
            direction = "unknown"
        elif avg_wow >= 5:
            direction = "growing"
        elif avg_wow <= -5:
            direction = "declining"
        else:
            direction = "stable"

        return {
            "status":         "ok",
            "weeks_reported": len(rows),
            "last_4_avg_revenue": avg_rev,
            "avg_wow_pct_last4":  avg_wow,
            "direction":          direction,
            "last_4_weeks":       last4,
        }

    def _consecutive_drop_alert(self, trends: dict[str, list[dict]]) -> list[dict]:
        """
        Flag any distributor with 3+ consecutive weeks of revenue decline.
        This is a leading indicator of a relationship problem or supply issue.
        """
        alerts = []
        for dist, rows in trends.items():
            streak = 0
            streak_start: int | None = None
            for row in rows:
                if row["wow_pct"] is not None and row["wow_pct"] < 0:
                    streak += 1
                    if streak_start is None:
                        streak_start = row["week_num"]
                    if streak >= 3:
                        alerts.append({
                            "distributor":   dist,
                            "streak_weeks":  streak,
                            "streak_from_week": streak_start,
                            "latest_week":   row["week_num"],
                            "latest_wow_pct": row["wow_pct"],
                        })
                else:
                    streak = 0
                    streak_start = None
        return alerts

    def _missing_upload_check(
        self, latest_week: int, latest_data: list[dict]
    ) -> list[str]:
        """
        Check which distributors have NO record for the latest week.
        Missing data = file not yet uploaded or ingestion error.
        """
        uploaded = {r["distributor"] for r in latest_data}
        missing = [d for d in DISTRIBUTORS if d not in uploaded]
        flags = []
        for d in missing:
            flags.append(
                f"⚠ {d}: no data for W{latest_week} — file may not have been uploaded"
            )
        return flags

    def _latest_vs_season_avg(
        self, latest_data: list[dict], season_totals: list[dict]
    ) -> list[dict]:
        """
        Compare each distributor's latest week revenue vs their season average.
        Helps spot a weak week even if not technically an anomaly.
        """
        avg_by_dist = {
            r["distributor"]: round(
                float(r["total_revenue"] or 0) / max(int(r["weeks_reported"]), 1), 2
            )
            for r in season_totals
        }
        result = []
        for row in latest_data:
            dist = row["distributor"]
            curr = float(row["revenue"] or 0)
            avg  = avg_by_dist.get(dist, 0)
            vs_avg_pct = round((curr - avg) / avg * 100, 1) if avg else None
            result.append({
                "distributor":    dist,
                "latest_revenue": round(curr, 2),
                "season_avg":     avg,
                "vs_avg_pct":     vs_avg_pct,
            })
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Sale Point KPIs — fetched from the live GitHub Pages dashboard HTML
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch_sp_data(self) -> dict | None:
        """
        Fetch the unified dashboard HTML from GitHub Pages and extract
        window.__SP_DATA__ — the complete sale-point JSON injected by
        salepoint_dashboard.py at build time.

        Returns the parsed dict, or None if fetch/parse fails.
        """
        try:
            with urllib.request.urlopen(DASHBOARD_HTML_URL, timeout=20) as r:
                html = r.read().decode("utf-8", errors="replace")
        except Exception as e:
            self.log.warning(f"Could not fetch dashboard HTML for SP KPIs: {e}")
            return None

        m = re.search(r"window\.__SP_DATA__\s*=\s*(\{.*?\});\s*\n", html, re.DOTALL)
        if not m:
            self.log.warning("window.__SP_DATA__ not found in dashboard HTML")
            return None

        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError as e:
            self.log.warning(f"Failed to parse __SP_DATA__ JSON: {e}")
            return None

    def _salepoint_kpis(self) -> dict:
        """
        Analyse the full sale-point dataset extracted from the live dashboard.

        KPIs returned:
            total_salepoints    — total individual sale points across all customers
            total_customers     — number of distinct customers
            status_breakdown    — {Active, New, No Mar order, Churned} counts + %
            at_risk_list        — 'No Mar order' + 'Churned' entries (top 20 by total)
            new_salepoints      — salepoints with status 'New' (first order ever)
            trend_summary       — count of growing / flat / declining salepoints
            by_distributor      — per-distributor salepoint + active counts
            top_churned_customers — customers with most churned/at-risk salepoints
        """
        sp_data = self._fetch_sp_data()
        if sp_data is None:
            return {"status": "unavailable", "note": "Could not fetch dashboard HTML"}

        customers = sp_data.get("customers", [])
        if not customers:
            return {"status": "empty", "note": "No customer data in __SP_DATA__"}

        # Flatten all sale points with customer context
        all_sp: list[dict] = []
        for cust in customers:
            for sp in cust.get("salepoints", []):
                all_sp.append({
                    **sp,
                    "_customer":    cust["name"],
                    "_distributor": cust["distributor"],
                })

        total_sp = len(all_sp)
        total_customers = len(customers)

        # ── Status breakdown ────────────────────────────────────────────────
        from collections import Counter, defaultdict
        status_counts = Counter(sp["status"] for sp in all_sp)
        status_breakdown = {
            st: {
                "count": cnt,
                "pct":   round(cnt / total_sp * 100, 1) if total_sp else 0,
            }
            for st, cnt in status_counts.most_common()
        }

        # ── At-risk list (No Mar order + Churned) ─────────────────────────
        at_risk = [
            sp for sp in all_sp
            if sp["status"] in ("No Mar order", "Churned")
        ]
        at_risk.sort(key=lambda s: -s.get("total", 0))
        at_risk_list = [
            {
                "name":        sp["name"],
                "customer":    sp["_customer"],
                "distributor": sp["_distributor"],
                "status":      sp["status"],
                "total_units": sp.get("total", 0),
                "last_active_month": (
                    "Feb" if sp.get("feb", 0) > 0 else
                    "Jan" if sp.get("jan", 0) > 0 else
                    "Dec" if sp.get("dec", 0) > 0 else "—"
                ),
            }
            for sp in at_risk[:20]
        ]

        # ── New salepoints ─────────────────────────────────────────────────
        new_sp = [
            {
                "name":        sp["name"],
                "customer":    sp["_customer"],
                "distributor": sp["_distributor"],
                "mar_units":   sp.get("mar", 0),
            }
            for sp in all_sp if sp["status"] == "New"
        ]
        new_sp.sort(key=lambda s: -s["mar_units"])

        # ── Trend summary ──────────────────────────────────────────────────
        growing   = sum(1 for sp in all_sp if (sp.get("trend") or 0) > 10)
        declining = sum(1 for sp in all_sp if (sp.get("trend") or 0) < -10)
        flat      = total_sp - growing - declining

        # ── By distributor ─────────────────────────────────────────────────
        by_dist: dict[str, dict] = defaultdict(lambda: {"total": 0, "active": 0, "new": 0, "at_risk": 0, "churned": 0})
        for sp in all_sp:
            d = sp["_distributor"]
            by_dist[d]["total"] += 1
            if sp["status"] == "Active":
                by_dist[d]["active"] += 1
            elif sp["status"] == "New":
                by_dist[d]["new"] += 1
            elif sp["status"] == "No Mar order":
                by_dist[d]["at_risk"] += 1
            elif sp["status"] == "Churned":
                by_dist[d]["churned"] += 1

        # ── Customers with most at-risk / churned salepoints ──────────────
        cust_risk: dict[str, int] = defaultdict(int)
        for sp in at_risk:
            cust_risk[sp["_customer"]] += 1
        top_churned_customers = sorted(
            [{"customer": k, "at_risk_count": v} for k, v in cust_risk.items()],
            key=lambda x: -x["at_risk_count"],
        )[:10]

        return {
            "status":                  "ok",
            "total_salepoints":        total_sp,
            "total_customers":         total_customers,
            "status_breakdown":        status_breakdown,
            "at_risk_count":           len(at_risk),
            "at_risk_list":            at_risk_list,
            "new_salepoints":          new_sp,
            "new_count":               len(new_sp),
            "trend_summary":           {
                "growing":   growing,
                "flat":      flat,
                "declining": declining,
            },
            "by_distributor":          dict(by_dist),
            "top_churned_customers":   top_churned_customers,
        }

    def _serialize(self, obj: Any) -> Any:
        """Make query results JSON-serialisable."""
        if isinstance(obj, list):
            return [self._serialize(i) for i in obj]
        if isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return obj

    # ─────────────────────────────────────────────────────────────────────────
    # Recommendations builder
    # ─────────────────────────────────────────────────────────────────────────

    def _build_recommendations(
        self,
        anomalies: list[dict],
        drop_streaks: list[dict],
        missing_flags: list[str],
        biscotti: dict,
        vs_avg: list[dict],
        sp_kpis: dict | None = None,
    ) -> list[str]:
        recs: list[str] = []

        # Missing uploads — highest priority
        recs.extend(missing_flags)

        # Consecutive drops
        for alert in drop_streaks:
            recs.append(
                f"🔴 {alert['distributor']} has been declining for "
                f"{alert['streak_weeks']} consecutive weeks "
                f"(from W{alert['streak_from_week']}) — investigate root cause."
            )

        # WoW anomalies
        drops  = [a for a in anomalies if a["flag"] == "drop"]
        spikes = [a for a in anomalies if a["flag"] == "spike"]
        if drops:
            d = drops[-1]  # most recent drop
            recs.append(
                f"Revenue drop at {d['distributor']} in {d['label']}: "
                f"{d['change_pct']}% WoW — verify file upload and check for missing deliveries."
            )
        if spikes:
            s = spikes[-1]
            recs.append(
                f"Revenue spike at {s['distributor']} in {s['label']}: "
                f"+{s['change_pct']}% WoW — confirm it is a real sale event, not a double-upload."
            )

        # Biscotti growth direction
        if biscotti.get("status") == "ok":
            if biscotti["direction"] == "growing":
                recs.append(
                    f"✅ Biscotti is growing: avg WoW +{biscotti['avg_wow_pct_last4']}% "
                    f"over last 4 weeks — consider increasing allocation."
                )
            elif biscotti["direction"] == "declining":
                recs.append(
                    f"⚠ Biscotti is declining: avg WoW {biscotti['avg_wow_pct_last4']}% "
                    f"over last 4 weeks — review distribution strategy."
                )

        # Latest week below season average
        for row in vs_avg:
            if row["vs_avg_pct"] is not None and row["vs_avg_pct"] < -20:
                recs.append(
                    f"⚠ {row['distributor']} latest week (₪{row['latest_revenue']:,.0f}) "
                    f"is {row['vs_avg_pct']}% below season average (₪{row['season_avg']:,.0f})."
                )

        # Sale point health
        if sp_kpis and sp_kpis.get("status") == "ok":
            at_risk_count = sp_kpis.get("at_risk_count", 0)
            total_sp      = sp_kpis.get("total_salepoints", 1)
            at_risk_pct   = round(at_risk_count / total_sp * 100, 1) if total_sp else 0

            if at_risk_count >= 20:
                top_cust = sp_kpis.get("top_churned_customers", [])[:3]
                cust_names = ", ".join(c["customer"] for c in top_cust)
                recs.append(
                    f"🔴 {at_risk_count} sale points ({at_risk_pct}%) are Churned or No Mar order. "
                    f"Worst customers: {cust_names}. Assign field follow-up."
                )
            elif at_risk_count > 0:
                recs.append(
                    f"⚠ {at_risk_count} sale points ({at_risk_pct}%) have no March order — review before month closes."
                )

            new_count = sp_kpis.get("new_count", 0)
            if new_count > 0:
                recs.append(
                    f"✅ {new_count} new sale point(s) placed their first order this season — "
                    f"flag for relationship building."
                )

            trend = sp_kpis.get("trend_summary", {})
            if trend.get("declining", 0) > trend.get("growing", 0):
                recs.append(
                    f"⚠ More sale points declining ({trend['declining']}) than growing "
                    f"({trend['growing']}) — check if this is seasonal or structural."
                )

        if not recs:
            recs.append("✅ No significant anomalies detected — system is healthy.")

        return recs

    # ─────────────────────────────────────────────────────────────────────────
    # Main execute
    # ─────────────────────────────────────────────────────────────────────────

    def execute(self) -> dict:
        # Check if triggered by DataSteward signal
        signals = self.state.consume_signals("new_data_ingested")
        triggered_by = [s["payload"] for s in signals] if signals else []
        self.log.info(
            f"Running {'(triggered by DataSteward)' if triggered_by else '(scheduled)'}"
        )

        today      = datetime.now(timezone.utc).date()
        week_label = f"W{today.isocalendar()[1]}/{today.year}"

        # ── Fetch raw data ──────────────────────────────────────────────────
        all_rows     = self._all_weekly_data()
        latest_week  = self._latest_week_num()
        season_tots  = self._season_totals_by_distributor()
        latest_data  = self._latest_week_data(latest_week) if latest_week else []

        if not all_rows:
            self.log.warning("weekly_chart_overrides is empty — no report generated")
            return {"status": "skipped", "reason": "no_data"}

        # ── KPI analytics ───────────────────────────────────────────────────
        trends        = self._build_distributor_trends(all_rows)
        anomalies     = self._wow_anomalies(trends)
        biscotti_kpi  = self._biscotti_growth_kpi(trends)
        drop_streaks  = self._consecutive_drop_alert(trends)
        missing_flags = self._missing_upload_check(latest_week or 0, latest_data)
        vs_avg        = self._latest_vs_season_avg(latest_data, season_tots)

        # ── Sale Point KPIs ─────────────────────────────────────────────────
        self.log.info("Fetching sale-point data from GitHub Pages dashboard…")
        sp_kpis = self._salepoint_kpis()

        # ── Build report ────────────────────────────────────────────────────
        report = {
            "report_date":        today.isoformat(),
            "week_label":         week_label,
            "generated_at":       datetime.now(timezone.utc).isoformat(),
            "triggered_by":       triggered_by,
            "latest_week_num":    latest_week,
            "season_totals":      self._serialize(season_tots),
            "latest_week":        self._serialize(latest_data),
            "latest_vs_season_avg": self._serialize(vs_avg),
            "distributor_trends": {
                k: self._serialize(v) for k, v in trends.items()
            },
            "anomalies":          self._serialize(anomalies),
            "biscotti_growth":    self._serialize(biscotti_kpi),
            "consecutive_drops":  self._serialize(drop_streaks),
            "missing_uploads":    missing_flags,
            "salepoint_kpis":     self._serialize(sp_kpis),
            "recommendations":    self._build_recommendations(
                anomalies, drop_streaks, missing_flags, biscotti_kpi, vs_avg, sp_kpis
            ),
        }

        # ── Persist to DB ───────────────────────────────────────────────────
        self.execute_sql(
            """INSERT INTO weekly_intelligence_reports
                   (report_date, week_label, distributor, report)
               VALUES (%s, %s, 'all', %s::jsonb)
               ON CONFLICT DO NOTHING""",
            (today, week_label, json.dumps(report, cls=_DecimalEncoder)),
        )

        # ── Save as JSON file ───────────────────────────────────────────────
        out_dir = Path(__file__).parents[2] / "docs" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"weekly_report_{today.isoformat()}.json"
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, cls=_DecimalEncoder))
        self.log.info(f"Report saved → {out_path}")

        self.state.set("last_report_date", today.isoformat())

        # ── Signal UX Architect if anomalies found ──────────────────────────
        if anomalies or drop_streaks:
            self.state.emit_signal(
                to_agent="ux_architect",
                signal="anomalies_detected",
                payload={
                    "anomalies":     anomalies[:5],
                    "drop_streaks":  drop_streaks,
                    "week_label":    week_label,
                },
            )

        return {
            "report_date":          today.isoformat(),
            "week_label":           week_label,
            "latest_week_num":      latest_week,
            "distributors_in_db":   list(trends.keys()),
            "anomalies_found":      len(anomalies),
            "consecutive_drops":    len(drop_streaks),
            "missing_uploads":      len(missing_flags),
            "biscotti_direction":   biscotti_kpi.get("direction", "no_data"),
            "salepoints_total":     sp_kpis.get("total_salepoints", "unavailable"),
            "salepoints_at_risk":   sp_kpis.get("at_risk_count", "unavailable"),
            "salepoints_new":       sp_kpis.get("new_count", "unavailable"),
            "report_path":          str(out_path),
        }


if __name__ == "__main__":
    agent = InsightAnalystAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))
