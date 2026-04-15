"""
data_steward.py — Data Steward Agent
Role: Monitors a GCS bucket (or local watch folder) for new distributor files,
      triggers raito_loader.py ingestion, validates integrity, deduplicates,
      and signals the Insight Analyst when new data lands.

Trigger: Cloud Scheduler → every 30 min (or on file arrival via GCS Pub/Sub)
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parents[1]))

from agents.base_agent import RaitoAgent

# Optional: GCS support
try:
    from google.cloud import storage as gcs
    HAS_GCS = True
except ImportError:
    HAS_GCS = False


class DataStewardAgent(RaitoAgent):
    """
    Watches for new distributor files and ingests them into Cloud SQL.

    State keys:
        processed_files  →  {file_path_or_gcs_uri: sha256_hash}
        last_run_at      →  ISO timestamp
        total_ingested   →  int (cumulative rows inserted)
    """

    name = "data_steward"

    # ── Config ────────────────────────────────────────────────────────────

    WATCH_BUCKET   = os.environ.get("RAITO_WATCH_BUCKET", "")          # GCS bucket name
    WATCH_PREFIX   = os.environ.get("RAITO_WATCH_PREFIX", "uploads/")  # GCS prefix
    LOCAL_INBOX    = os.environ.get("RAITO_LOCAL_INBOX", "")           # local fallback dir
    DISTRIBUTOR_MAP = {
        "icedream":  ["icedream", "ice_dream", "אייסדרים"],
        "mayyan":    ["mayyan", "maayan", "מעיין"],
        "biscotti":  ["biscotti", "ביסקוטי"],
    }

    # ── Helpers ───────────────────────────────────────────────────────────

    def _sha256(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _detect_distributor(self, filename: str) -> str | None:
        fn = filename.lower()
        for dist, keywords in self.DISTRIBUTOR_MAP.items():
            if any(kw.lower() in fn for kw in keywords):
                return dist
        return None

    def _list_gcs_new_files(self) -> list[tuple[str, bytes]]:
        """Returns list of (gcs_uri, file_bytes) for unprocessed files."""
        if not HAS_GCS or not self.WATCH_BUCKET:
            return []
        client = gcs.Client()
        bucket = client.bucket(self.WATCH_BUCKET)
        processed = self.state.get("processed_files", {})
        new_files = []
        for blob in bucket.list_blobs(prefix=self.WATCH_PREFIX):
            if not blob.name.endswith((".xlsx", ".xls", ".csv")):
                continue
            uri = f"gs://{self.WATCH_BUCKET}/{blob.name}"
            data = blob.download_as_bytes()
            sha = self._sha256(data)
            if processed.get(uri) == sha:
                continue  # already ingested
            new_files.append((uri, data, sha))
        return new_files

    def _list_local_new_files(self) -> list[tuple[str, bytes, str]]:
        """Scan LOCAL_INBOX for unprocessed files."""
        if not self.LOCAL_INBOX:
            return []
        inbox = Path(self.LOCAL_INBOX)
        if not inbox.is_dir():
            return []
        processed = self.state.get("processed_files", {})
        new_files = []
        for fp in sorted(inbox.glob("**/*.xlsx")) + sorted(inbox.glob("**/*.xls")):
            data = fp.read_bytes()
            sha = self._sha256(data)
            if processed.get(str(fp)) == sha:
                continue
            new_files.append((str(fp), data, sha))
        return new_files

    def _ingest_file(self, source_id: str, data: bytes, distributor: str) -> dict:
        """Write to temp file and call raito_loader ingestion pipeline."""
        suffix = Path(source_id).suffix or ".xlsx"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            from db.raito_loader import load_distributor_file
            result = load_distributor_file(
                filepath=tmp_path,
                distributor=distributor,
                conn=self._conn,
            )
            return result
        finally:
            os.unlink(tmp_path)

    def _validate_integrity(self, distributor: str, rows_inserted: int) -> dict:
        """
        Post-ingestion validation:
        - Check for duplicate rows (same distributor+week_num)
        - Confirm row count increased
        Uses weekly_chart_overrides (the only populated table in RAITO DB).
        """
        dupe_check = self.query(
            """
            SELECT COUNT(*) AS dupes FROM (
                SELECT distributor, week_num,
                       COUNT(*) AS cnt
                FROM   weekly_chart_overrides
                WHERE  distributor = %s
                GROUP  BY 1,2
                HAVING COUNT(*) > 1
            ) t
            """,
            (distributor,),
        )
        dupes = dupe_check[0]["dupes"] if dupe_check else 0

        total = self.query(
            "SELECT COUNT(*) AS n FROM weekly_chart_overrides WHERE distributor=%s",
            (distributor,),
        )
        return {
            "duplicate_groups": int(dupes),
            "total_rows_in_db": int(total[0]["n"]) if total else 0,
            "rows_inserted_this_run": rows_inserted,
        }

    # ── Main execute ──────────────────────────────────────────────────────

    def execute(self) -> dict:
        new_files = self._list_gcs_new_files() or self._list_local_new_files()
        self.log.info(f"Found {len(new_files)} new file(s) to process")

        if not new_files:
            self.state.set("last_run_at", datetime.now(timezone.utc).isoformat())
            return {"files_processed": 0, "rows_ingested": 0}

        processed = self.state.get("processed_files", {})
        total_rows = 0
        distributors_updated = []
        errors = []

        for source_id, data, sha in new_files:
            filename = Path(source_id).name
            distributor = self._detect_distributor(filename)
            if not distributor:
                self.log.warning(f"Could not detect distributor for {filename} — skipping")
                errors.append({"file": filename, "error": "unknown distributor"})
                continue

            self.log.info(f"Ingesting {filename} → distributor={distributor}")
            try:
                result = self._ingest_file(source_id, data, distributor)
                rows = result.get("rows_inserted", 0)
                total_rows += rows

                validation = self._validate_integrity(distributor, rows)
                self.log.info(f"Validation: {validation}")

                if validation["duplicate_groups"] > 0:
                    self.log.warning(
                        f"Found {validation['duplicate_groups']} duplicate groups for {distributor} — UPSERT may be needed"
                    )
                    # Auto-deduplicate: keep row with highest id
                    self.execute_sql(
                        """DELETE FROM weekly_chart_overrides a
                           USING weekly_chart_overrides b
                           WHERE a.id < b.id
                             AND a.distributor = b.distributor
                             AND a.week_num    = b.week_num"""
                    )
                    self.log.info("Deduplication complete")

                processed[source_id] = sha
                distributors_updated.append(distributor)

            except Exception as exc:
                self.log.error(f"Failed to ingest {filename}: {exc}")
                errors.append({"file": filename, "error": str(exc)})

        self.state.set("processed_files", processed)
        self.state.set("last_run_at", datetime.now(timezone.utc).isoformat())
        prev_total = self.state.get("total_ingested", 0)
        self.state.set("total_ingested", prev_total + total_rows)

        # Signal Insight Analyst that new data is ready
        if distributors_updated:
            self.state.emit_signal(
                to_agent="insight_analyst",
                signal="new_data_ingested",
                payload={
                    "distributors": list(set(distributors_updated)),
                    "rows_ingested": total_rows,
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.log.info(f"Signal emitted → insight_analyst: new_data_ingested")

        return {
            "files_processed": len(new_files) - len(errors),
            "files_errored": len(errors),
            "rows_ingested": total_rows,
            "distributors_updated": list(set(distributors_updated)),
            "errors": errors,
        }


if __name__ == "__main__":
    agent = DataStewardAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))
