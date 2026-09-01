#!/usr/bin/env python3
"""
Keeping Score query-agent: answers questions about Wax's 178 attended games
THROUGH THE GOVERNED SEMANTIC LAYER, and stages (never sends) email drafts.

The query-side sibling of agent_writes_row.py (CCAR-F Exercise 1). Where that
script demonstrated gates on the write path, this one demonstrates the
semantic-layer thesis on the read path: the agent asks for METRICS BY NAME
(home_runs_witnessed, attended_win_rate) via MetricFlow — it has no SQL tool
at all, so it cannot reverse-engineer joins or magic numbers.

    py agents/agent_queries_metric.py --question "How many home runs have I witnessed?"
    py agents/agent_queries_metric.py --no-semantic-layer --question "..."   # contrast run
    py agents/agent_queries_metric.py --model haiku --question "..."         # A/B runtime

The contrast flag swaps the metric tools for a single raw run_sql tool
(read-only BigQuery) — same question, and the trace shows the difference:
a named-metric call versus hand-rolled SQL rediscovering EVENT_CD = 23.

Action layer (RETROactive-only rule): draft_email STAGES a draft under
target/agent_outbox/ (gitignored with target/). Nothing is ever sent —
a human moves it to Gmail and decides. That gate is the design, not a gap.

Auth: rides the Claude Code CLI login (no API key in code). Runtime model
defaults to Sonnet per the parity plan's Discernment ruling.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
MF_EXE = r"C:\Users\georg\Documents\CODING\dbt-core-sl-venv\Scripts\mf.exe"
MF_ENV = {"DBT_PROFILES_DIR": r"C:\Users\georg\.dbt", "PYTHONUTF8": "1"}
OUTBOX = PROJECT_DIR / "target" / "agent_outbox"
BQ_PROJECT = "augmented-world-262319"


def _run_mf(args: list[str]) -> str:
    # encoding/errors on the PARENT side: mf prints emoji spinners; without
    # this the pipe decodes as cp1252 and the reader thread dies mid-tool-call.
    result = subprocess.run(
        [MF_EXE, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=PROJECT_DIR, env={**os.environ, **MF_ENV},
    )
    if result.returncode != 0:
        return f"MetricFlow error:\n{(result.stderr or result.stdout).strip()[:800]}"
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Semantic-layer tools — the governed path. No SQL anywhere.
# ---------------------------------------------------------------------------

@tool(
    "list_metrics",
    "List the governed metrics of the Keeping Score semantic layer, with the dimensions each supports.",
    {},
)
async def list_metrics(args: dict[str, Any]) -> dict[str, Any]:
    out = _run_mf(["list", "metrics"])
    return {"content": [{"type": "text", "text": out}]}


@tool(
    "query_metrics",
    "Query governed metrics BY NAME via MetricFlow. metrics: comma-separated metric names. "
    "Optional: group_by (comma-separated dimension paths like game_attendee__attendee_name or metric_time__year), "
    "where (a filter like \"{{ Dimension('game_attendee__attendee_name') }} = 'Al'\"), "
    "order (e.g. -games_per_attendee), limit.",
    {
        "type": "object",
        "properties": {
            "metrics": {"type": "string"},
            "group_by": {"type": "string"},
            "where": {"type": "string"},
            "order": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["metrics"],
    },
)
async def query_metrics(args: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        out_csv = pathlib.Path(tmp) / "out.csv"
        cli = ["query", "--metrics", args["metrics"]]
        if args.get("group_by"):
            cli += ["--group-by", args["group_by"]]
        if args.get("where"):
            cli += ["--where", args["where"]]
        if args.get("order"):
            cli += ["--order", args["order"]]
        if args.get("limit"):
            cli += ["--limit", str(args["limit"])]
        cli += ["--csv", str(out_csv)]
        status = _run_mf(cli)
        if out_csv.exists():
            text = out_csv.read_text(encoding="utf-8").strip()
            return {"content": [{"type": "text", "text": f"CSV result:\n{text}"}]}
        return {"content": [{"type": "text", "text": status}]}


@tool(
    "draft_email",
    "Stage an email draft for HUMAN review. Nothing is sent — the draft lands in an outbox "
    "and a person decides whether it ever reaches Gmail. Use for retrospective reminders only.",
    {"to": str, "subject": str, "body": str},
)
async def draft_email(args: dict[str, Any]) -> dict[str, Any]:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = OUTBOX / f"draft-{stamp}.json"
    path.write_text(json.dumps(args, indent=2), encoding="utf-8")
    return {"content": [{"type": "text", "text": f"Draft staged at {path}. NOT sent — human send gate."}]}


# ---------------------------------------------------------------------------
# Contrast tool — the ungoverned path, for the with/without receipt.
# ---------------------------------------------------------------------------

@tool(
    "run_sql",
    "Run a read-only SELECT against BigQuery dataset wax_baseball_dbt. "
    "Discover schema via INFORMATION_SCHEMA if needed.",
    {"sql": str},
)
async def run_sql(args: dict[str, Any]) -> dict[str, Any]:
    sql = args["sql"].strip()
    if not sql.lower().lstrip("(").startswith(("select", "with")):
        return {"content": [{"type": "text", "text": "Rejected: SELECT-only tool."}]}
    from google.cloud import bigquery  # imported lazily; only the contrast run needs it

    client = bigquery.Client(project=BQ_PROJECT)
    try:
        rows = [dict(r) for r in client.query(sql).result(timeout=60)]
    except Exception as exc:  # noqa: BLE001 — surface the engine error to the agent
        return {"content": [{"type": "text", "text": f"BigQuery error: {str(exc)[:600]}"}]}
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows[:50]:
            writer.writerow({k: str(v) for k, v in r.items()})
    return {"content": [{"type": "text", "text": buf.getvalue() or "(0 rows)"}]}


SL_SYSTEM_PROMPT = """You are the Keeping Score analyst — the agent over Wax's 178 attended MLB games
(1984-2025), their plays, attendees, and Hall of Fame sightings.

RULES:
- Answer every quantitative question THROUGH THE GOVERNED SEMANTIC LAYER: call
  list_metrics to see what exists, then query_metrics with metric NAMES. You have
  no SQL. The metric names are the contract; never estimate or recall numbers.
- Dimensions use MetricFlow paths (e.g. metric_time__year, game_attendee__attendee_name,
  attended_team_game__team). Filters use {{ Dimension('...') }} syntax in `where`.
- Team dimension values are Retrosheet codes (Yankees = 'NYA', Mets = 'NYN', Red Sox = 'BOS').
- Historical data only. Your one action is draft_email, which STAGES a draft for a
  human to review — never claim an email was sent.
- Be concise and lead with the number."""

RAW_SYSTEM_PROMPT = """You are a baseball data analyst over BigQuery dataset wax_baseball_dbt
(Wax's attended-games warehouse). Answer quantitative questions by writing SQL with the
run_sql tool. Discover schema as needed via INFORMATION_SCHEMA. Be concise and lead
with the number."""


async def main() -> None:
    # Console/redirect on Windows defaults to cp1252; agent text can carry
    # unicode. Never let a print kill the message stream.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="How many home runs have I witnessed live at games I attended?")
    parser.add_argument("--model", default="sonnet", help="runtime model (sonnet per plan; haiku for A/B)")
    parser.add_argument("--no-semantic-layer", action="store_true", help="contrast run: raw SQL tool instead")
    parser.add_argument("--use-api-key", action="store_true",
                        help="keep ANTHROPIC_API_KEY from the environment (default: drop it so the Claude Code CLI login is used)")
    args = parser.parse_args()

    # Ride the Claude Code CLI login by default. An ANTHROPIC_API_KEY in the user
    # environment silently overrides it in the spawned CLI (found 2026-08-31:
    # a stale zero-credit Console key produced "Credit balance is too low").
    if not args.use_api_key:
        os.environ.pop("ANTHROPIC_API_KEY", None)

    if args.no_semantic_layer:
        server_key = "baseball"
        server = create_sdk_mcp_server(name=server_key, version="1.0.0", tools=[run_sql])
        allowed = ["mcp__baseball__run_sql"]
        system_prompt = RAW_SYSTEM_PROMPT
        mode = "RAW SQL (no semantic layer)"
    else:
        server_key = "keeping_score"
        server = create_sdk_mcp_server(
            name=server_key, version="1.0.0",
            tools=[list_metrics, query_metrics, draft_email],
        )
        allowed = [
            "mcp__keeping_score__list_metrics",
            "mcp__keeping_score__query_metrics",
            "mcp__keeping_score__draft_email",
        ]
        system_prompt = SL_SYSTEM_PROMPT
        mode = "SEMANTIC LAYER (governed metrics)"

    options = ClaudeAgentOptions(
        model=args.model,
        system_prompt=system_prompt,
        mcp_servers={server_key: server},
        allowed_tools=allowed,
        permission_mode="dontAsk",
        max_turns=24,
    )

    print(f"=== {mode} · runtime={args.model} ===")
    print(f"Q: {args.question}\n")
    tool_calls = 0
    try:
        async for message in query(prompt=args.question, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        tool_calls += 1
                        print(f"[tool #{tool_calls}] {block.name}")
                        print(f"          {json.dumps(block.input)[:400]}")
                    elif isinstance(block, TextBlock) and block.text.strip():
                        print(f"[agent] {block.text.strip()}")
            elif isinstance(message, ResultMessage):
                final = getattr(message, "result", None)
                if final:
                    print(f"\n[final] {final}")
                print(f"\n=== DONE · {tool_calls} tool call(s) ===")
    except Exception as exc:  # noqa: BLE001 — show the partial trace's ending, not a stack
        print(f"\n=== ENDED WITH ERROR after {tool_calls} tool call(s): {exc} ===")


if __name__ == "__main__":
    asyncio.run(main())
