"""SQLite audit log (task 17): one row per request.

Stored: request id, UTC time, backend/model, entity types + counts, the
exact sanitized payload that was sent, leak-check result, placeholder
bookkeeping counts and timings.

NEVER stored: the mapping, the original text, the LLM's restored output,
or any raw value. A blocked request stores an empty payload, because the
payload it would have sent contained a raw value.
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone

from .contracts import ProcessResult

DEFAULT_DB = os.environ.get(
    "AUDIT_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audit.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    request_id      TEXT PRIMARY KEY,
    ts_utc          TEXT NOT NULL,
    backend         TEXT NOT NULL,
    model           TEXT NOT NULL,
    entity_counts   TEXT NOT NULL,   -- JSON {"PERSON": 2, "PAN": 1}
    entity_total    INTEGER NOT NULL,
    sanitized_payload TEXT NOT NULL, -- exact text sent to the LLM ('' if blocked)
    blocked         INTEGER NOT NULL,
    leaked_types    TEXT NOT NULL,   -- JSON list of types, never values
    restored        INTEGER NOT NULL,
    dropped         INTEGER NOT NULL,
    unknown         INTEGER NOT NULL,
    gateway_ms      REAL NOT NULL,
    llm_ms          REAL NOT NULL
)
"""

COLUMNS = ("request_id", "ts_utc", "backend", "model", "entity_counts", "entity_total",
           "sanitized_payload", "blocked", "leaked_types", "restored", "dropped", "unknown",
           "gateway_ms", "llm_ms")


def _connect(db_path: str | None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DEFAULT_DB)
    conn.execute(SCHEMA)
    return conn


def log_request(result: ProcessResult, db_path: str | None = None) -> None:
    counts = Counter(e.type for e in result.entities)
    row = (
        result.request_id,
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
        result.backend,
        result.model,
        json.dumps(dict(sorted(counts.items()))),
        sum(counts.values()),
        "" if result.blocked else result.outbound_payload,
        int(result.blocked),
        json.dumps(result.leak_check.leaked_types),
        len(result.reinsertion.restored),
        len(result.reinsertion.dropped),
        len(result.reinsertion.unknown),
        round(result.gateway_ms, 2),
        round(result.llm_ms, 2),
    )
    with _connect(db_path) as conn:
        conn.execute(f"INSERT INTO audit VALUES ({','.join('?' * len(COLUMNS))})", row)
    conn.close()


def recent(limit: int = 50, db_path: str | None = None) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM audit ORDER BY ts_utc DESC, rowid DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(zip(COLUMNS, r))
        d["entity_counts"] = json.loads(d["entity_counts"])
        d["leaked_types"] = json.loads(d["leaked_types"])
        d["blocked"] = bool(d["blocked"])
        out.append(d)
    return out
