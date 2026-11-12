"""SQLite audit log (task 17): one row per request, including failures.

Stored: request id, UTC time, status, backend/model, entity types + counts,
the exact sanitized payload that was sent, leak-check result, placeholder
bookkeeping counts, error type (if any) and timings.

status:
  ok       sent, every placeholder restored, nothing odd
  flagged  sent, but the LLM dropped or invented placeholders
  rejected an ID was invalid (format / check digit); nothing sent, user asked to re-enter
  blocked  leak guard found a raw value; nothing was sent
  error    the LLM call failed (outage, timeout, bad key...)

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

from .contracts import Entity, ProcessResult

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
    llm_ms          REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'ok',
    error           TEXT NOT NULL DEFAULT ''
)
"""

COLUMNS = ("request_id", "ts_utc", "backend", "model", "entity_counts", "entity_total",
           "sanitized_payload", "blocked", "leaked_types", "restored", "dropped", "unknown",
           "gateway_ms", "llm_ms", "status", "error")


def _connect(db_path: str | None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DEFAULT_DB)
    conn.execute(SCHEMA)
    have = {r[1] for r in conn.execute("PRAGMA table_info(audit)")}
    for col in ("status", "error"):  # upgrade a database made before these existed
        if col not in have:
            default = "'ok'" if col == "status" else "''"
            conn.execute(f"ALTER TABLE audit ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}")
    return conn


def status_of(result: ProcessResult) -> str:
    if getattr(result, "needs_correction", False):
        return "rejected"
    if result.blocked:
        return "blocked"
    if result.reinsertion.dropped or result.reinsertion.unknown:
        return "flagged"
    return "ok"


def _counts(entities: list[Entity]) -> tuple[str, int]:
    c = Counter(e.type for e in entities)
    return json.dumps(dict(sorted(c.items()))), sum(c.values())


def _insert(row: tuple, db_path: str | None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute(f"INSERT INTO audit ({','.join(COLUMNS)}) "
                         f"VALUES ({','.join('?' * len(COLUMNS))})", row)
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def log_request(result: ProcessResult, db_path: str | None = None) -> None:
    counts, total = _counts(result.entities)
    status = status_of(result)
    note = ""
    if status == "rejected":  # types only, never the invalid values
        note = "invalid: " + ", ".join(sorted({i["type"] for i in result.invalid_ids}))
    _insert((
        result.request_id, _now(), result.backend, result.model, counts, total,
        "" if status in ("blocked", "rejected") else result.outbound_payload,
        int(result.blocked), json.dumps(result.leak_check.leaked_types),
        len(result.reinsertion.restored), len(result.reinsertion.dropped),
        len(result.reinsertion.unknown),
        round(result.gateway_ms, 2), round(result.llm_ms, 2),
        status, note,
    ), db_path)


def log_error(request_id: str, backend: str, model: str, entities: list[Entity],
              sanitized_payload: str, error: Exception, gateway_ms: float,
              db_path: str | None = None) -> None:
    """The LLM call failed after the payload passed the leak guard.

    Only the error's class name is stored: exception messages can echo input.
    """
    counts, total = _counts(entities)
    _insert((
        request_id, _now(), backend, model, counts, total, sanitized_payload,
        0, "[]", 0, 0, 0, round(gateway_ms, 2), 0.0, "error", type(error).__name__,
    ), db_path)


def recent(limit: int = 50, db_path: str | None = None) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT {','.join(COLUMNS)} FROM audit ORDER BY ts_utc DESC, rowid DESC LIMIT ?",
            (limit,),
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


def summary(db_path: str | None = None) -> dict:
    """Counts by status, leaks blocked by type, and LLM errors by type."""
    conn = _connect(db_path)
    try:
        by_status = dict(conn.execute("SELECT status, COUNT(*) FROM audit GROUP BY status"))
        leaked = Counter()
        for (lt,) in conn.execute("SELECT leaked_types FROM audit WHERE blocked = 1"):
            leaked.update(json.loads(lt))
        errors = dict(conn.execute(
            "SELECT error, COUNT(*) FROM audit WHERE status = 'error' GROUP BY error"))
        flagged = conn.execute(
            "SELECT COALESCE(SUM(dropped),0), COALESCE(SUM(unknown),0) FROM audit").fetchone()
        total = conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
    finally:
        conn.close()
    return {
        "total_requests": total,
        "by_status": {s: by_status.get(s, 0) for s in ("ok", "flagged", "rejected", "blocked", "error")},
        "leaks_blocked_by_type": dict(leaked),
        "placeholders_dropped_by_llm": flagged[0],
        "placeholders_invented_by_llm": flagged[1],
        "llm_errors_by_type": errors,
    }
