"""
devops_watchdog.py — DevOps Watchdog Agent
Role: Monitors Cloud Run logs, DB CPU/memory, endpoint latency, and
      connection health. Sends alerts via email/Slack and auto-restarts
      the Cloud SQL proxy if transient errors are detected.

Trigger: Cloud Scheduler → every 10 minutes
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from agents.base_agent import RaitoAgent


class DevOpsWatchdogAgent(RaitoAgent):
    """
    Health monitor for the Raito Cloud Run service and Cloud SQL backend.

    State keys:
        last_alert_at       → ISO timestamp of last alert sent (rate-limit)
        consecutive_fails   → int (how many checks have failed in a row)
        proxy_restarts      → int (total proxy auto-restarts)
    """

    name = "devops_watchdog"

    # ── Config (all overridable via env) ──────────────────────────────────
    CLOUD_RUN_URL        = os.environ.get("CLOUD_RUN_URL", "https://raito-dashboard-20004010285.me-west1.run.app")
    HEALTH_ENDPOINT      = os.environ.get("HEALTH_ENDPOINT", "/health")
    LATENCY_WARN_MS      = int(os.environ.get("LATENCY_WARN_MS",  "2000"))
    LATENCY_CRIT_MS      = int(os.environ.get("LATENCY_CRIT_MS",  "5000"))
    MAX_CONSECUTIVE_FAIL = int(os.environ.get("MAX_CONSECUTIVE_FAIL", "3"))
    ALERT_COOLDOWN_MIN   = int(os.environ.get("ALERT_COOLDOWN_MIN", "15"))

    # Alerting
    SLACK_WEBHOOK        = os.environ.get("RAITO_SLACK_WEBHOOK", "")
    ALERT_EMAIL          = os.environ.get("RAITO_ALERT_EMAIL", "")
    SENDGRID_API_KEY     = os.environ.get("SENDGRID_API_KEY", "")

    # GCP
    GCP_PROJECT          = os.environ.get("GCP_PROJECT", "raito-house-of-brands")
    GCP_REGION           = os.environ.get("GCP_REGION", "me-west1")
    CLOUD_RUN_SERVICE    = os.environ.get("CLOUD_RUN_SERVICE", "raito-dashboard")

    # ── Alert helpers ─────────────────────────────────────────────────────

    def _should_alert(self) -> bool:
        """Rate-limit: only alert once per ALERT_COOLDOWN_MIN minutes."""
        last = self.state.get("last_alert_at")
        if not last:
            return True
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(last)
        return delta.total_seconds() > self.ALERT_COOLDOWN_MIN * 60

    def _send_slack(self, message: str):
        if not self.SLACK_WEBHOOK:
            self.log.warning("No SLACK_WEBHOOK configured — skipping Slack alert")
            return
        payload = json.dumps({"text": f"🚨 *RAITO Watchdog*\n{message}"}).encode()
        req = urllib.request.Request(
            self.SLACK_WEBHOOK,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            self.log.info("Slack alert sent")
        except Exception as exc:
            self.log.error(f"Slack alert failed: {exc}")

    def _send_email(self, subject: str, body: str):
        if not self.SENDGRID_API_KEY or not self.ALERT_EMAIL:
            self.log.warning("No email config — skipping email alert")
            return
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail
            sg = sendgrid.SendGridAPIClient(api_key=self.SENDGRID_API_KEY)
            mail = Mail(
                from_email="noreply@raito.ai",
                to_emails=self.ALERT_EMAIL,
                subject=f"[RAITO Watchdog] {subject}",
                plain_text_content=body,
            )
            sg.client.mail.send.post(request_body=mail.get())
            self.log.info("Email alert sent")
        except Exception as exc:
            self.log.error(f"Email alert failed: {exc}")

    def _alert(self, level: str, message: str):
        """Send alert via all configured channels (rate-limited)."""
        if not self._should_alert():
            self.log.info(f"Alert suppressed (cooldown): {message}")
            return
        self.log.warning(f"[{level}] {message}")
        self._send_slack(f"[{level}] {message}")
        self._send_email(f"{level} Alert", message)
        self.state.set("last_alert_at", datetime.now(timezone.utc).isoformat())

    # ── Health checks ─────────────────────────────────────────────────────

    def _check_endpoint_latency(self) -> dict:
        url = self.CLOUD_RUN_URL.rstrip("/") + self.HEALTH_ENDPOINT
        try:
            t0 = time.time()
            with urllib.request.urlopen(url, timeout=10) as resp:
                status = resp.status
                body   = resp.read(512).decode(errors="replace")
            latency_ms = round((time.time() - t0) * 1000)
            return {
                "ok": True,
                "status_code": status,
                "latency_ms": latency_ms,
                "body_snippet": body[:100],
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "latency_ms": None}

    def _check_db_connection(self) -> dict:
        try:
            t0 = time.time()
            rows = self.query("SELECT 1 AS ping, NOW() AS ts")
            latency_ms = round((time.time() - t0) * 1000)
            return {"ok": True, "latency_ms": latency_ms, "ts": str(rows[0]["ts"])}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _check_db_stats(self) -> dict:
        """Query pg_stat_database for connection count and cache hit rate."""
        try:
            rows = self.query(
                """
                SELECT numbackends AS connections,
                       ROUND(100.0 * blks_hit / NULLIF(blks_hit + blks_read, 0), 1) AS cache_hit_pct,
                       xact_commit, xact_rollback
                FROM   pg_stat_database
                WHERE  datname = current_database()
                """
            )
            return rows[0] if rows else {}
        except Exception as exc:
            return {"error": str(exc)}

    def _check_cloud_run_logs(self) -> list[str]:
        """
        Pull recent Cloud Run error logs via gcloud CLI.
        Returns list of error message snippets from the last 10 minutes.
        """
        try:
            since = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            cmd = [
                "gcloud", "logging", "read",
                f'resource.type="cloud_run_revision" '
                f'resource.labels.service_name="{self.CLOUD_RUN_SERVICE}" '
                f'severity>=ERROR '
                f'timestamp>="{since}"',
                "--project", self.GCP_PROJECT,
                "--format", "value(textPayload)",
                "--limit", "20",
            ]
            out = subprocess.check_output(cmd, timeout=15, stderr=subprocess.DEVNULL)
            lines = [l.strip() for l in out.decode().splitlines() if l.strip()]
            return lines
        except Exception as exc:
            self.log.warning(f"Could not fetch Cloud Run logs: {exc}")
            return []

    def _attempt_service_redeploy(self):
        """Trigger a Cloud Run redeploy as a last resort for persistent failures."""
        self.log.warning("Attempting Cloud Run redeploy …")
        try:
            cmd = [
                "gcloud", "run", "services", "update", self.CLOUD_RUN_SERVICE,
                "--region", self.GCP_REGION,
                "--project", self.GCP_PROJECT,
                "--update-env-vars", f"WATCHDOG_RESTART={datetime.now(timezone.utc).isoformat()}",
            ]
            subprocess.run(cmd, timeout=60, check=True, capture_output=True)
            self.log.info("Cloud Run service updated (forced restart)")
            restarts = self.state.get("proxy_restarts", 0)
            self.state.set("proxy_restarts", restarts + 1)
        except Exception as exc:
            self.log.error(f"Redeploy failed: {exc}")

    def _persist_metrics(self, metrics: dict):
        """Store health check metrics to DB for historical tracking."""
        self.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS watchdog_metrics (
                id           SERIAL      PRIMARY KEY,
                checked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                endpoint_ok  BOOLEAN,
                endpoint_ms  INTEGER,
                db_ok        BOOLEAN,
                db_ms        INTEGER,
                db_conns     INTEGER,
                error_count  INTEGER,
                raw          JSONB
            )
            """
        )
        self.execute_sql(
            """INSERT INTO watchdog_metrics
               (endpoint_ok, endpoint_ms, db_ok, db_ms, db_conns, error_count, raw)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)""",
            (
                metrics.get("endpoint", {}).get("ok"),
                metrics.get("endpoint", {}).get("latency_ms"),
                metrics.get("db_conn",  {}).get("ok"),
                metrics.get("db_conn",  {}).get("latency_ms"),
                metrics.get("db_stats", {}).get("connections"),
                len(metrics.get("error_logs", [])),
                json.dumps(metrics, default=str),
            ),
        )

    # ── Main execute ──────────────────────────────────────────────────────

    def execute(self) -> dict:
        metrics = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "endpoint":   self._check_endpoint_latency(),
            "db_conn":    self._check_db_connection(),
            "db_stats":   self._check_db_stats(),
            "error_logs": self._check_cloud_run_logs(),
        }

        self.log.info(f"Endpoint: {metrics['endpoint']}")
        self.log.info(f"DB conn:  {metrics['db_conn']}")

        issues = []
        consecutive = self.state.get("consecutive_fails", 0)

        # ── Endpoint check ──────────────────────────────────────────────
        ep = metrics["endpoint"]
        if not ep["ok"]:
            issues.append(f"Endpoint DOWN: {ep.get('error')}")
            consecutive += 1
        elif ep["latency_ms"] and ep["latency_ms"] > self.LATENCY_CRIT_MS:
            issues.append(f"Endpoint CRITICAL latency: {ep['latency_ms']}ms")
            consecutive += 1
        elif ep["latency_ms"] and ep["latency_ms"] > self.LATENCY_WARN_MS:
            issues.append(f"Endpoint SLOW: {ep['latency_ms']}ms (warn threshold)")
        else:
            consecutive = 0  # Reset on healthy check

        # ── DB check ────────────────────────────────────────────────────
        db = metrics["db_conn"]
        if not db["ok"]:
            issues.append(f"DB connection FAILED: {db.get('error')}")
            consecutive += 1

        db_stats = metrics["db_stats"]
        if db_stats.get("connections", 0) > 80:
            issues.append(f"DB connection count HIGH: {db_stats['connections']}")

        # ── Error logs ──────────────────────────────────────────────────
        err_logs = metrics["error_logs"]
        if err_logs:
            issues.append(f"{len(err_logs)} ERROR log lines in last 10 min")
            for line in err_logs[:3]:
                issues.append(f"  → {line[:120]}")

        self.state.set("consecutive_fails", consecutive)

        # ── Alert & auto-recovery ────────────────────────────────────────
        if issues:
            severity = "CRITICAL" if consecutive >= self.MAX_CONSECUTIVE_FAIL else "WARNING"
            msg = "\n".join(issues)
            self._alert(severity, msg)

            if consecutive >= self.MAX_CONSECUTIVE_FAIL and not ep["ok"]:
                self._alert("ACTION", "Triggering Cloud Run restart due to persistent failure")
                self._attempt_service_redeploy()
                self.state.set("consecutive_fails", 0)
        else:
            self.log.info("All systems healthy ✅")

        self._persist_metrics(metrics)

        return {
            "healthy": len(issues) == 0,
            "issues": issues,
            "endpoint_ms": ep.get("latency_ms"),
            "db_ok": db.get("ok"),
            "consecutive_fails": consecutive,
            "error_log_count": len(err_logs),
        }


if __name__ == "__main__":
    agent = DevOpsWatchdogAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))
