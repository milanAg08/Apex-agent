"""
Persistent Investigation History Store.
Keeps every completed investigation (thread_id, query, timeline, final state)
in a local SQLite table so the APEX chat UI survives browser refreshes and
server restarts, mirroring LangGraph's own thread-based checkpointing.
"""

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

HISTORY_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "investigation_history.sqlite")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(HISTORY_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(HISTORY_DB_PATH, check_same_thread=False, timeout=10)
    # WAL mode lets this short-lived connection write without blocking on
    # (or being blocked by) the long-lived LangGraph checkpointer connection.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investigations (
            thread_id TEXT PRIMARY KEY,
            user_query TEXT NOT NULL,
            timeline_json TEXT NOT NULL,
            state_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_investigation(thread_id: str, user_query: str, timeline: List[Dict[str, Any]], state: Dict[str, Any], created_at: str) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO investigations (thread_id, user_query, timeline_json, state_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                user_query=excluded.user_query,
                timeline_json=excluded.timeline_json,
                state_json=excluded.state_json
            """,
            (thread_id, user_query, json.dumps(timeline, default=str), json.dumps(state, default=str), created_at)
        )
        conn.commit()
    finally:
        conn.close()


def update_investigation_state(thread_id: str, state: Dict[str, Any]) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE investigations SET state_json = ? WHERE thread_id = ?",
            (json.dumps(state, default=str), thread_id)
        )
        conn.commit()
    finally:
        conn.close()


def load_all_investigations() -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT thread_id, user_query, timeline_json, state_json, created_at FROM investigations ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()

    results = []
    for thread_id, user_query, timeline_json, state_json, created_at in rows:
        results.append({
            "thread_id": thread_id,
            "user_query": user_query,
            "timeline": json.loads(timeline_json),
            "state": json.loads(state_json),
            "created_at": created_at
        })
    return results


def delete_investigation(thread_id: str) -> None:
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM investigations WHERE thread_id = ?", (thread_id,))
        conn.commit()
    finally:
        conn.close()
