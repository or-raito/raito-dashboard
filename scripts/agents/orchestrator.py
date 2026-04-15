"""
orchestrator.py — Raito Agent Orchestrator
CLI entry point for running any single agent or the full pipeline.

Usage:
    python3 -m agents.orchestrator --agent data_steward
    python3 -m agents.orchestrator --agent all
    python3 -m agents.orchestrator --agent watchdog --once

Cloud Run Job / Cloud Scheduler invokes this with AGENT_NAME env var set.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone

# Flush stdout immediately so Cloud Run captures all output even on crash
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

print("=== Raito Agent Orchestrator starting ===", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'not set')}", flush=True)
print(f"AGENT_NAME: {os.environ.get('AGENT_NAME', 'not set')}", flush=True)
print(f"CWD: {os.getcwd()}", flush=True)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

log = logging.getLogger("orchestrator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")


AGENT_REGISTRY = {
    "data_steward":    "agents.data_steward:DataStewardAgent",
    "insight_analyst": "agents.insight_analyst:InsightAnalystAgent",
    "devops_watchdog": "agents.devops_watchdog:DevOpsWatchdogAgent",
    "ux_architect":    "agents.ux_architect:UXArchitectAgent",
    "qa_agent":        "agents.qa_agent:QAAgent",
}


def load_agent(name: str):
    if name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {name!r}. Choose from: {list(AGENT_REGISTRY)}")
    module_path, class_name = AGENT_REGISTRY[name].rsplit(":", 1)
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def run_agent(name: str) -> dict:
    AgentClass = load_agent(name)
    agent = AgentClass()
    log.info(f"Starting agent: {name}")
    result = agent.run()
    log.info(f"Agent {name} finished: {result}")
    return result


def run_all_pipeline() -> dict:
    """
    Full pipeline:
      1. DataSteward  — ingest new files, emit signals
      2. InsightAnalyst — consume signals, generate report
      3. DevOpsWatchdog — health check
      4. UXArchitect  — consume anomaly signals, generate proposals
    """
    results = {}
    pipeline = ["data_steward", "insight_analyst", "devops_watchdog", "ux_architect"]
    for name in pipeline:
        log.info(f"━━━ Running {name} ━━━")
        try:
            results[name] = run_agent(name)
        except Exception as exc:
            log.error(f"Agent {name} crashed: {exc}")
            results[name] = {"status": "error", "error": str(exc)}
    return results


def main():
    # Support both CLI args and environment variable (for Cloud Scheduler/Cloud Run Jobs)
    agent_env = os.environ.get("AGENT_NAME", "")

    parser = argparse.ArgumentParser(description="Raito Agent Orchestrator")
    parser.add_argument(
        "--agent",
        choices=list(AGENT_REGISTRY.keys()) + ["all"],
        default=agent_env or "all",
        help="Which agent to run (default: all)",
    )
    parser.add_argument(
        "--output", default="",
        help="Optional path to write JSON result",
    )
    args = parser.parse_args()

    started = datetime.now(timezone.utc).isoformat()
    if args.agent == "all":
        result = run_all_pipeline()
    else:
        result = run_agent(args.agent)

    output = {
        "orchestrator_run": {
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "agent": args.agent,
        },
        "result": result,
    }

    print(json.dumps(output, indent=2, default=str))

    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2, default=str))
        log.info(f"Result written to {args.output}")

    # Exit 1 if any agent errored (Cloud Run Job picks this up)
    if isinstance(result, dict):
        results_to_check = result.values() if args.agent == "all" else [result]
        if any(r.get("status") == "error" for r in results_to_check if isinstance(r, dict)):
            sys.exit(1)


if __name__ == "__main__":
    main()
