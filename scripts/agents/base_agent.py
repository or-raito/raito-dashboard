"""
base_agent.py — Raito Agent Base Class
Every agent inherits from RaitoAgent. Provides DB connection, state tracking,
structured logging, and a standard run() lifecycle.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    stream=sys.stdout,
)


def _get_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://raito:raito@localhost:5432/raito"
    )


# ── State manager (processed_logs table) ─────────────────────────────────────

BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS agent_state (
    agent_name   TEXT        NOT NULL,
    key          TEXT        NOT NULL,
    value        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_name, key)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id           SERIAL      PRIMARY KEY,
    agent_name   TEXT        NOT NULL,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at  TIMESTAMPTZ,
    status       TEXT        NOT NULL DEFAULT 'running',   -- running | success | error
    summary      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    error        TEXT
);

CREATE TABLE IF NOT EXISTS agent_signals (
    id           SERIAL      PRIMARY KEY,
    from_agent   TEXT        NOT NULL,
    to_agent     TEXT        NOT NULL,
    signal       TEXT        NOT NULL,   -- e.g. 'new_data_ingested'
    payload      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consumed     BOOLEAN     NOT NULL DEFAULT FALSE
);
"""


class StateManager:
    """Simple key-value state persisted to agent_state table."""

    def __init__(self, agent_name: str, conn: psycopg2.extensions.connection):
        self._agent = agent_name
        self._conn = conn
        self._ensure_schema()

    def _ensure_schema(self):
        with self._conn.cursor() as cur:
            cur.execute(BOOTSTRAP_SQL)
        self._conn.commit()

    def get(self, key: str, default: Any = None) -> Any:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM agent_state WHERE agent_name=%s AND key=%s",
                (self._agent, key),
            )
            row = cur.fetchone()
        return row[0] if row else default

    def set(self, key: str, value: Any):
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO agent_state (agent_name, key, value, updated_at)
                   VALUES (%s, %s, %s::jsonb, NOW())
                   ON CONFLICT (agent_name, key)
                   DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()""",
                (self._agent, key, json.dumps(value)),
            )
        self._conn.commit()

    # ── Signal bus ──────────────────────────────────────────────────────────

    def emit_signal(self, to_agent: str, signal: str, payload: dict = None):
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO agent_signals (from_agent, to_agent, signal, payload)
                   VALUES (%s, %s, %s, %s::jsonb)""",
                (self._agent, to_agent, signal, json.dumps(payload or {})),
            )
        self._conn.commit()

    def consume_signals(self, signal: str) -> list[dict]:
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """UPDATE agent_signals SET consumed=TRUE
                   WHERE to_agent=%s AND signal=%s AND consumed=FALSE
                   RETURNING *""",
                (self._agent, signal),
            )
            rows = cur.fetchall()
        self._conn.commit()
        return [dict(r) for r in rows]


# ── Base Agent ────────────────────────────────────────────────────────────────

class RaitoAgent(ABC):
    """
    Base class for all Raito agents.

    Lifecycle:
        run() → before_run() → execute() → after_run()

    Subclasses must implement execute() and return a summary dict.
    """

    name: str = "base"

    def __init__(self):
        self.log = logging.getLogger(self.name)
        self._conn: psycopg2.extensions.connection | None = None
        self._run_id: int | None = None
        self.state: StateManager | None = None

    # ── DB helpers ────────────────────────────────────────────────────────

    def _connect(self) -> psycopg2.extensions.connection:
        url = _get_db_url()
        self.log.info(f"Connecting to DB …")
        conn = psycopg2.connect(url)
        conn.autocommit = False
        return conn

    def query(self, sql: str, params=None) -> list[dict]:
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def execute_sql(self, sql: str, params=None):
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
        self._conn.commit()

    # ── Run lifecycle ─────────────────────────────────────────────────────

    def before_run(self):
        """Override to add setup logic."""
        pass

    @abstractmethod
    def execute(self) -> dict:
        """Main agent logic. Must return a summary dict."""

    def after_run(self, summary: dict):
        """Override to add teardown / notification logic."""
        pass

    def run(self) -> dict:
        start = time.time()
        self._conn = self._connect()
        self.state = StateManager(self.name, self._conn)

        # Record run start
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO agent_runs (agent_name) VALUES (%s) RETURNING id",
                (self.name,),
            )
            self._run_id = cur.fetchone()[0]
        self._conn.commit()

        summary: dict = {}
        status = "success"
        error_text = None

        try:
            self.before_run()
            summary = self.execute()
            self.after_run(summary)
        except Exception as exc:
            status = "error"
            error_text = traceback.format_exc()
            self.log.error(f"Agent failed: {exc}\n{error_text}")
            summary = {"error": str(exc)}

        elapsed = round(time.time() - start, 2)
        summary["elapsed_s"] = elapsed

        # Update run record
        with self._conn.cursor() as cur:
            cur.execute(
                """UPDATE agent_runs
                   SET finished_at=NOW(), status=%s, summary=%s::jsonb, error=%s
                   WHERE id=%s""",
                (status, json.dumps(summary), error_text, self._run_id),
            )
        self._conn.commit()
        self._conn.close()

        self.log.info(f"Done in {elapsed}s — status={status} summary={summary}")
        return {"status": status, **summary}
