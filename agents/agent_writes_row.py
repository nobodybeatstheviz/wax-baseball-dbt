#!/usr/bin/env python3
"""
Baseball attendance write-agent: parse game statement, resolve attendees, write rows to BigQuery.
Built 2026-08-21 to demonstrate CCAR-F Domains 1 (enforcement), 2 (tool design), 4 (structured output).

Usage:
    from agent_writes_row import run_write_agent_with_parsed_input

    game_input = {
        "date": "2026-08-17",
        "opponent": "BOS",
        "venue": "Fenway Park",
        "attendees": ["Melissa", "solo"],
        "context": "squishy dumpling giveaway",
    }
    result = run_write_agent_with_parsed_input(game_input)
    print(result)

Gate logic:
1. Resolve all attendees against dim_attendee (must all exist)
2. Check game date is ≤ today (temporal sanity)
3. Look up game in fct_games by (date, opponent)
4. Check co-occurrence rule: no (wax_game_id, attendee_key) duplicate in fct_game_attendee
5. If all pass, write rows; else return structured error with isRetryable flag
"""

import json
from datetime import datetime
from typing import Optional, TypedDict, Any
from google.cloud import bigquery

# BigQuery setup
bq_client = bigquery.Client(project="augmented-world-262319")
dataset_id = "wax_baseball_dbt"


class ErrorResponse(TypedDict):
    """Structured error response."""
    success: bool
    error: dict
    data: Optional[dict]


class SuccessResponse(TypedDict):
    """Structured success response."""
    success: bool
    data: dict
    error: None


def query_attendee_roster() -> dict[str, str]:
    """Load canonical attendee names → keys from dim_attendee."""
    query = f"""
    SELECT attendee_key, attendee_name
    FROM `augmented-world-262319.{dataset_id}.dim_attendee`
    ORDER BY attendee_name
    """
    result = bq_client.query(query).result()
    roster = {row.attendee_name: row.attendee_key for row in result}
    return roster


def query_game_by_date_opponent(date_str: str, opponent: str) -> Optional[str]:
    """Look up wax_game_id by date and opponent (team abbreviation)."""
    query = f"""
    SELECT wax_game_id
    FROM `augmented-world-262319.{dataset_id}.fct_games`
    WHERE game_date = @date AND (home_team_id_wax = @opp OR away_team_id_wax = @opp)
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("date", "DATE", date_str),
            bigquery.ScalarQueryParameter("opp", "STRING", opponent),
        ]
    )
    result = bq_client.query(query, job_config=job_config).result()
    rows = list(result)
    return rows[0].wax_game_id if rows else None


def check_duplicate_attendance(wax_game_id: str, attendee_key: str) -> bool:
    """Check if (wax_game_id, attendee_key) already exists in fct_game_attendee (co-occurrence rule)."""
    query = f"""
    SELECT COUNT(*) as count
    FROM `augmented-world-262319.{dataset_id}.fct_game_attendee`
    WHERE wax_game_id = @game_id AND attendee_key = @att_key
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("game_id", "STRING", wax_game_id),
            bigquery.ScalarQueryParameter("att_key", "STRING", attendee_key),
        ]
    )
    result = bq_client.query(query, job_config=job_config).result()
    rows = list(result)
    return rows[0].count > 0 if rows else False


def write_attendee_rows(
    wax_game_id: str, attendee_keys: list[tuple[str, str]], attendee_names: list[str]
) -> SuccessResponse:
    """Write attendee rows to fct_game_attendee. Gate checks must have passed.

    Args:
        wax_game_id: The game ID (e.g., "BOS202608170")
        attendee_keys: List of (name, attendee_key) tuples
        attendee_names: List of attendee names for response
    """
    # Get game details for context
    game_query = f"""
    SELECT game_date, game_type_wax
    FROM `augmented-world-262319.{dataset_id}.fct_games`
    WHERE wax_game_id = @game_id
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("game_id", "STRING", wax_game_id),
        ]
    )
    game_result = bq_client.query(game_query, job_config=job_config).result()
    game_rows = list(game_result)
    game_date = game_rows[0].game_date if game_rows else None

    # Prepare rows to insert
    rows_to_insert = [
        {
            "wax_game_id": wax_game_id,
            "attendee_key": att_key,
            "attendee_name": name,
            "attendee_type": "person",  # For new writes, assume person
            "game_date": str(game_date) if game_date else None,
        }
        for name, att_key in attendee_keys
    ]

    table_id = f"augmented-world-262319.{dataset_id}.fct_game_attendee"
    errors = bq_client.insert_rows_json(table_id, rows_to_insert)

    if errors:
        return {
            "success": False,
            "data": None,
            "error": {
                "category": "DATABASE_ERROR",
                "message": f"Failed to insert rows: {errors}",
                "isRetryable": True,
            },
        }

    return {
        "success": True,
        "data": {
            "wax_game_id": wax_game_id,
            "attendees": attendee_names,
            "rows_written": len(attendee_keys),
        },
        "error": None,
    }


def run_write_agent_with_parsed_input(parsed_input: dict[str, Any]) -> dict[str, Any]:
    """Main agent: use pre-parsed input, apply gate checks, write rows.

    Parsed input schema:
    {
        "date": "YYYY-MM-DD",
        "opponent": "TEAM_CODE",  # e.g., "BOS", "NYA"
        "venue": "venue name",
        "attendees": ["name1", "name2"],
        "context": "optional memory hook"
    }

    Returns: {"success": bool, "data": {wax_game_id, attendees, rows_written}, "error": {...}}
    """
    roster = query_attendee_roster()

    date_str = parsed_input["date"]
    opponent = parsed_input["opponent"]
    venue = parsed_input["venue"]
    attendee_names = parsed_input["attendees"]
    context = parsed_input.get("context")

    # Resolve attendees
    resolved_attendees = []
    unresolved = []
    for name in attendee_names:
        if name in roster:
            resolved_attendees.append((name, roster[name]))
        else:
            unresolved.append(name)

    # GATE 1: All attendees must resolve
    if unresolved:
        return {
            "success": False,
            "data": None,
            "error": {
                "category": "ATTENDEE_NOT_FOUND",
                "message": f"Attendee(s) not found: {', '.join(unresolved)}. Known attendees: {len(roster)}",
                "isRetryable": False,
            },
        }

    # GATE 2: Check temporal sanity
    game_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.now().date()
    if game_date > today:
        return {
            "success": False,
            "data": None,
            "error": {
                "category": "INVALID_GAME_DATE",
                "message": f"Game date {date_str} is in the future.",
                "isRetryable": False,
            },
        }

    # GATE 3: Look up game
    try:
        wax_game_id = query_game_by_date_opponent(date_str, opponent)
        if not wax_game_id:
            return {
                "success": False,
                "data": None,
                "error": {
                    "category": "GAME_NOT_FOUND",
                    "message": f"Game not found: {date_str} vs {opponent}. Note: retrosheet data may be lagged.",
                    "isRetryable": False,
                },
            }
    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": {
                "category": "DATABASE_ERROR",
                "message": f"Failed to look up game: {str(e)}",
                "isRetryable": True,
            },
        }

    # GATE 4: Check co-occurrence rule (no duplicate attendance)
    duplicates = []
    for name, attendee_key in resolved_attendees:
        if check_duplicate_attendance(wax_game_id, attendee_key):
            duplicates.append(name)

    if duplicates:
        return {
            "success": False,
            "data": None,
            "error": {
                "category": "DUPLICATE_ATTENDANCE",
                "message": f"Already recorded: {', '.join(duplicates)} attended this game.",
                "isRetryable": False,
            },
        }

    # All gates pass — write the rows
    return write_attendee_rows(wax_game_id, resolved_attendees, [name for name, _ in resolved_attendees])
