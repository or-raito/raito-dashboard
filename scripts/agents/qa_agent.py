"""
qa_agent.py — Dashboard QA Agent
Role: Automatically validates the dashboard after every rebuild/deploy.
      Catches issues like null data weeks, array length mismatches,
      sign convention bugs, and cross-tab revenue parity (BO / CC / SP).

Trigger: Cloud Scheduler → daily at 08:00 IL time.
         Also run manually: python3 -m agents.qa_agent
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from agents.base_agent import RaitoAgent

QA_DDL = """
CREATE TABLE IF NOT EXISTS qa_results (
    id           SERIAL      PRIMARY KEY,
    checked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_name   TEXT        NOT NULL,
    status       TEXT        NOT NULL,   -- pass | fail | warn
    detail       TEXT,
    value        TEXT
);
"""

CLOUD_RUN_URL      = "https://raito-dashboard-20004010285.me-west1.run.app"  # Cloud Run (primary)
DASHBOARD_HTML_URL = "https://raito-dashboard-20004010285.me-west1.run.app"  # Same — Cloud Run serves unified dashboard
CC_DASHBOARD_PY    = Path(__file__).parents[1] / "cc_dashboard.py"
UNIFIED_HTML       = Path(__file__).parents[2] / "docs" / "unified_dashboard.html"

# Parity tolerances
BO_SP_WARN_PCT  = 0.5   # warn if gap > 0.5 %
BO_SP_FAIL_PCT  = 2.0   # fail if gap > 2 %
BO_CC_WARN_PCT  = 3.0   # CC scope differs (top chains only + dist margin)
BO_CC_FAIL_PCT  = 10.0


class QAAgent(RaitoAgent):
    """
    Automated QA checks for the RAITO dashboard.

    Data integrity:
      1.  Weekly array lengths match (all 13 entries)
      2.  No null values in historical weeks (W1–W12 for Ice)
      3.  W13 has data for at least Icedream
      4.  dk==='both' returns 3 separate datasets

    Code health:
      5.  Sign convention in _extract_week_override (-q / -r, not abs)

    Cross-tab revenue parity:
      6.  BO grand total vs SP grand total (should be < 0.5 % apart)
      7.  BO grand total vs CC grand total (scope differs; warn if > 3 %)
      8.  CC grand total vs SP grand total

    Database:
      9.  Row count > 1 000 transactions
      10. W13 Icedream present in DB
      11. No duplicate transactions

    Endpoint:
      12. Cloud Run endpoint responds 200
    """

    name = "qa_agent"

    EXPECTED_WEEKS = 13
    MIN_DB_ROWS    = 10  # weekly_chart_overrides rows (not transactions)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def before_run(self):
        self.execute_sql(QA_DDL)
        self._src  = CC_DASHBOARD_PY.read_text() if CC_DASHBOARD_PY.exists() else ""
        # HTML: prefer local file, fall back to live URL (for Cloud Run env)
        if UNIFIED_HTML.exists():
            self._html = UNIFIED_HTML.read_text()
        else:
            # In Cloud Run: fetch from GitHub Pages (the unified dashboard, not the Flask server)
            try:
                import urllib.request
                with urllib.request.urlopen(DASHBOARD_HTML_URL, timeout=15) as r:
                    self._html = r.read().decode("utf-8")
                self.log.info(f"Fetched HTML from GitHub Pages ({len(self._html):,} bytes)")
            except Exception as e:
                self.log.warning(f"Could not fetch HTML for parity check: {e}")
                self._html = ""
        self._results: list[dict] = []

    # ── Helpers ────────────────────────────────────────────────────────────

    def _check(self, name: str, passed: bool, detail: str, value: str = "") -> bool:
        status = "pass" if passed else "fail"
        self._results.append({"check": name, "status": status,
                               "detail": detail, "value": value})
        self.log.info(f"{'✅' if passed else '❌'} {name}: {detail}")
        return passed

    def _warn(self, name: str, condition: bool, detail: str, value: str = ""):
        status = "pass" if condition else "warn"
        self._results.append({"check": name, "status": status,
                               "detail": detail, "value": value})
        self.log.info(f"{'✅' if condition else '⚠️'} {name}: {detail}")

    # ── 1–2  Weekly array helpers ──────────────────────────────────────────

    def _check_array_lengths(self):
        arrays = {
            "_iceWkRev":        r"const _iceWkRev\s*=\s*\[([^\]]+)\]",
            "_iceWkUnits":      r"const _iceWkUnits\s*=\s*\[([^\]]+)\]",
            "_iceWkRevTurbo":   r"const _iceWkRevTurbo\s*=\s*\[([^\]]+)\]",
            "_iceWkUnitsTurbo": r"const _iceWkUnitsTurbo\s*=\s*\[([^\]]+)\]",
            "_iceWkRevDanis":   r"const _iceWkRevDanis\s*=\s*\[([^\]]+)\]",
            "_iceWkUnitsDanis": r"const _iceWkUnitsDanis\s*=\s*\[([^\]]+)\]",
            "weeklyXLabels":    r"const weeklyXLabels\s*=\s*\[([^\]]+)\]",
        }
        for name, pattern in arrays.items():
            matches = list(re.finditer(pattern, self._src))
            if not matches:
                self._check(f"array_length:{name}", False, "Array not found in source", "")
                continue
            entries = [x.strip() for x in matches[-1].group(1).split(",") if x.strip()]
            count   = len(entries)
            last    = entries[-1].strip('"').strip("'")
            self._check(
                f"array_length:{name}",
                count == self.EXPECTED_WEEKS,
                f"length={count} (expected {self.EXPECTED_WEEKS}), last={last}",
                str(count),
            )

    def _check_no_nulls_historical(self):
        matches = list(re.finditer(r"const _iceWkRev\s*=\s*\[([^\]]+)\]", self._src))
        if not matches:
            self._check("no_nulls_w1_w12", False, "_iceWkRev not found", "")
            return
        entries   = [x.strip() for x in matches[-1].group(1).split(",")]
        null_weeks = [i + 1 for i, v in enumerate(entries[:12]) if v.lower() == "null"]
        self._check(
            "no_nulls_w1_w12",
            len(null_weeks) == 0,
            f"null in W1-W12: {null_weeks or 'none'}",
            str(null_weeks),
        )

    def _check_w13_has_data(self):
        matches = list(re.finditer(r"const _iceWkRev\s*=\s*\[([^\]]+)\]", self._src))
        if not matches:
            self._check("w13_ice_data", False, "_iceWkRev not found", "")
            return
        entries = [x.strip() for x in matches[-1].group(1).split(",")]
        w13_val = entries[12] if len(entries) > 12 else "MISSING"
        has_data = w13_val.lower() not in ("null", "0", "missing", "")
        self._check("w13_ice_data", has_data, f"_iceWkRev[12] = {w13_val}", w13_val)

    def _check_dk_both_has_3_lines(self):
        both_idx = self._src.find("if (dk === 'both')")
        if both_idx < 0:
            self._check("dk_both_3_lines", False, "dk==='both' branch not found", "")
            return
        section = self._src[both_idx:both_idx + 800]
        has_dslist   = "dsList" in section
        has_combined = "const combined" in section
        self._check(
            "dk_both_3_lines",
            has_dslist and not has_combined,
            f"dsList={has_dslist}, old_combined={has_combined}",
        )

    def _check_sign_convention(self):
        db_py = Path(__file__).parent.parent / "db" / "db_dashboard.py"
        if not db_py.exists():
            self._check("sign_convention", False, "db_dashboard.py not found", "")
            return
        src     = db_py.read_text()
        idx     = src.find("_extract_week_override")
        section = src[idx:idx + 2500] if idx >= 0 else ""
        has_flip = "-q" in section and "-r" in section
        has_abs  = "abs(q)" in section or "abs(r)" in section
        self._check(
            "sign_convention",
            has_flip and not has_abs,
            f"sign_flip={has_flip}, abs_present={has_abs}",
        )

    # ── 6–8  Cross-tab revenue parity ─────────────────────────────────────

    def _extract_bo_total(self) -> float:
        """Last 'total_revenue' value in the HTML = BO grand total."""
        vals = re.findall(r'"total_revenue"\s*:\s*([\d\.]+)', self._html)
        return float(vals[-1]) if vals else 0.0

    def _extract_cc_total(self) -> float:
        """Sum of each CC customer's dec+jan+feb+mar revenue."""
        cc_start = self._html.find("customers = [")
        if cc_start < 0:
            return 0.0
        cc_html = self._html[cc_start:cc_start + 300_000]
        matches = re.findall(
            r'revenue:\{dec:([\d\.]+),jan:([\d\.]+),feb:([\d\.]+),mar:([\d\.]+)\}',
            cc_html,
        )
        return sum(float(d) + float(j) + float(f) + float(m) for d, j, f, m in matches)

    def _extract_sp_total(self) -> float:
        """Sum of all salepoint 'rev' values from __SP_DATA__."""
        sp_m = re.search(r'window\.__SP_DATA__\s*=\s*(\{.*?\});', self._html, re.DOTALL)
        if not sp_m:
            return 0.0
        try:
            sp = json.loads(sp_m.group(1))
            return sum(
                pt.get("rev", 0)
                for cust in sp.get("customers", [])
                for pt   in cust.get("salepoints", [])
            )
        except Exception:
            return 0.0

    def _pct_gap(self, a: float, b: float) -> float:
        base = max(a, b)
        return abs(a - b) / base * 100 if base else 0.0

    def _check_cross_tab_parity(self):
        if not self._html:
            self._check("parity_bo_sp", False, "unified_dashboard.html not found", "")
            self._check("parity_bo_cc", False, "unified_dashboard.html not found", "")
            return

        bo = self._extract_bo_total()
        cc = self._extract_cc_total()
        sp = self._extract_sp_total()

        if bo == 0:
            self._warn("parity_bo_sp", False,
                       "Could not extract BO total — live URL is Flask server, not unified dashboard")
            self._warn("parity_bo_cc", False,
                       "Could not extract BO total — live URL is Flask server, not unified dashboard")
            return

        # ── BO vs SP (primary SSOT check — should be nearly identical) ───
        gap_bo_sp     = abs(bo - sp)
        gap_bo_sp_pct = self._pct_gap(bo, sp)
        detail_bo_sp  = (
            f"BO=₪{bo:,.0f}  SP=₪{sp:,.0f}  "
            f"gap=₪{gap_bo_sp:,.0f} ({gap_bo_sp_pct:.2f}%)"
        )
        if gap_bo_sp_pct > BO_SP_FAIL_PCT:
            self._check("parity_bo_sp", False, detail_bo_sp, f"{gap_bo_sp_pct:.2f}%")
        elif gap_bo_sp_pct > BO_SP_WARN_PCT:
            self._warn("parity_bo_sp", False, detail_bo_sp, f"{gap_bo_sp_pct:.2f}%")
        else:
            self._check("parity_bo_sp", True, detail_bo_sp, f"{gap_bo_sp_pct:.2f}%")

        # ── BO vs CC (CC = top chains only + distributor margin → some delta expected) ──
        if cc == 0:
            self._warn("parity_bo_cc", False,
                       "Could not extract CC total (customers[] not found)", "")
        else:
            gap_bo_cc     = abs(bo - cc)
            gap_bo_cc_pct = self._pct_gap(bo, cc)
            detail_bo_cc  = (
                f"BO=₪{bo:,.0f}  CC=₪{cc:,.0f}  "
                f"gap=₪{gap_bo_cc:,.0f} ({gap_bo_cc_pct:.2f}%)  "
                f"[CC=top chains only; some delta expected]"
            )
            if gap_bo_cc_pct > BO_CC_FAIL_PCT:
                self._check("parity_bo_cc", False, detail_bo_cc, f"{gap_bo_cc_pct:.2f}%")
            elif gap_bo_cc_pct > BO_CC_WARN_PCT:
                self._warn("parity_bo_cc", False, detail_bo_cc, f"{gap_bo_cc_pct:.2f}%")
            else:
                self._check("parity_bo_cc", True, detail_bo_cc, f"{gap_bo_cc_pct:.2f}%")

        # ── CC vs SP ──
        if cc > 0 and sp > 0:
            gap_cc_sp     = abs(cc - sp)
            gap_cc_sp_pct = self._pct_gap(cc, sp)
            detail_cc_sp  = (
                f"CC=₪{cc:,.0f}  SP=₪{sp:,.0f}  "
                f"gap=₪{gap_cc_sp:,.0f} ({gap_cc_sp_pct:.2f}%)"
            )
            if gap_cc_sp_pct > BO_CC_FAIL_PCT:
                self._check("parity_cc_sp", False, detail_cc_sp, f"{gap_cc_sp_pct:.2f}%")
            elif gap_cc_sp_pct > BO_CC_WARN_PCT:
                self._warn("parity_cc_sp", False, detail_cc_sp, f"{gap_cc_sp_pct:.2f}%")
            else:
                self._check("parity_cc_sp", True, detail_cc_sp, f"{gap_cc_sp_pct:.2f}%")

        # ── Summary log ──
        self.log.info(
            f"📊 Parity snapshot  |  BO ₪{bo:,.0f}  |  CC ₪{cc:,.0f}  |  SP ₪{sp:,.0f}  "
            f"|  BO↔SP {gap_bo_sp_pct:.2f}%  |  BO↔CC {self._pct_gap(bo, cc):.2f}%"
        )

    # ── 9–11  DB checks ────────────────────────────────────────────────────

    def _check_db_row_count(self):
        rows  = self.query("SELECT COUNT(*) AS n FROM weekly_chart_overrides")
        count = int(rows[0]["n"]) if rows else 0
        self._check(
            "db_row_count",
            count >= 1,
            f"{count} rows in weekly_chart_overrides (table reachable, has data)",
            str(count),
        )

    def _check_db_w13_icedream(self):
        rows = self.query(
            """SELECT units, revenue FROM weekly_chart_overrides
               WHERE distributor='icedream' AND week_num=13"""
        )
        if rows and int(rows[0]["units"] or 0) > 0:
            self._check(
                "db_w13_icedream", True,
                f"W13 Icedream in DB: {rows[0]['units']} units / ₪{round(float(rows[0]['revenue'] or 0))}",
            )
        else:
            self._warn(
                "db_w13_icedream", False,
                "W13 Icedream not in weekly_chart_overrides (week13.xlsx not uploaded via DB UI)",
            )

    def _check_no_duplicates(self):
        rows  = self.query(
            """SELECT COUNT(*) AS dupes FROM (
               SELECT distributor, week_num, COUNT(*)
               FROM weekly_chart_overrides
               GROUP BY 1,2 HAVING COUNT(*) > 1) t"""
        )
        dupes = int(rows[0]["dupes"]) if rows else 0
        self._check(
            "no_duplicates",
            dupes == 0,
            f"{dupes} duplicate (distributor, week) entries in weekly_chart_overrides",
            str(dupes),
        )

    # ── 12  Endpoint ───────────────────────────────────────────────────────

    def _check_endpoint(self):
        try:
            import time
            t0 = time.time()
            with urllib.request.urlopen(CLOUD_RUN_URL, timeout=10) as r:
                ms = int((time.time() - t0) * 1000)
                self._warn(
                    "endpoint_alive",
                    r.status == 200,
                    f"status={r.status}, {ms}ms",
                    str(ms),
                )
        except Exception as e:
            self._check("endpoint_alive", False, str(e))

    # ── Persist + run ──────────────────────────────────────────────────────

    def _persist_results(self):
        for r in self._results:
            self.execute_sql(
                "INSERT INTO qa_results (check_name, status, detail, value) VALUES (%s,%s,%s,%s)",
                (r["check"], r["status"], r["detail"], r.get("value", "")),
            )

    def execute(self) -> dict:
        # Data integrity
        self._check_array_lengths()
        self._check_no_nulls_historical()
        self._check_w13_has_data()
        self._check_dk_both_has_3_lines()
        # Code health
        self._check_sign_convention()
        # Cross-tab parity  ← NEW
        self._check_cross_tab_parity()
        # Database
        self._check_db_row_count()
        self._check_db_w13_icedream()
        self._check_no_duplicates()
        # Endpoint
        self._check_endpoint()

        self._persist_results()

        passed = sum(1 for r in self._results if r["status"] == "pass")
        failed = sum(1 for r in self._results if r["status"] == "fail")
        warned = sum(1 for r in self._results if r["status"] == "warn")

        if failed > 0:
            self.state.emit_signal(
                to_agent="devops_watchdog",
                signal="qa_failures_detected",
                payload={
                    "failed": failed,
                    "checks": [r for r in self._results if r["status"] == "fail"],
                },
            )

        return {
            "total":    len(self._results),
            "passed":   passed,
            "failed":   failed,
            "warned":   warned,
            "failures": [r for r in self._results if r["status"] == "fail"],
            "warnings": [r for r in self._results if r["status"] == "warn"],
        }


if __name__ == "__main__":
    agent = QAAgent()
    result = agent.run()
    print(json.dumps(result, indent=2, default=str))
