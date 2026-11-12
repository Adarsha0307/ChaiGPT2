"""Failure paths: audit status, LLM errors, summary, schema upgrade."""
import sqlite3

import pytest

from gateway.audit import recent, summary
from gateway.backends import MockBackend
from gateway.contracts import Entity
from gateway.pipeline import process

DOC = "Loan applicant Priya Nair, PAN ABCPK1234F, mobile 98765 43210."


class Down(MockBackend):
    def generate(self, prompt):
        raise ConnectionError("network down: Priya Nair")  # message even echoes input


@pytest.mark.parametrize("mode,status", [("echo", "ok"), ("paraphrase", "ok"),
                                         ("drop", "flagged"), ("fake", "flagged")])
def test_status_per_outcome(tmp_path, mode, status):
    db = str(tmp_path / "a.db")
    process(DOC, MockBackend(mode), audit=True, audit_db=db)
    assert recent(1, db)[0]["status"] == status


def test_blocked_status(tmp_path):
    db = str(tmp_path / "a.db")
    text = "Rahul Sharma applied. RAHUL SHARMA signed."
    process(text, MockBackend("echo"), audit=True, audit_db=db,
            detector=lambda t: [Entity("PERSON", 0, 12, "Rahul Sharma")])
    row = recent(1, db)[0]
    assert row["status"] == "blocked" and row["sanitized_payload"] == ""


def test_llm_error_is_audited_and_reraised(tmp_path):
    db = str(tmp_path / "a.db")
    with pytest.raises(ConnectionError):
        process(DOC, Down("echo"), audit=True, audit_db=db)
    row = recent(1, db)[0]
    assert row["status"] == "error" and row["error"] == "ConnectionError"
    assert "<PERSON_1>" in row["sanitized_payload"]
    blob = open(db, "rb").read().decode("utf-8", "ignore")
    assert "Priya" not in blob and "ABCPK1234F" not in blob  # message not stored


def test_summary_counts(tmp_path):
    db = str(tmp_path / "a.db")
    process(DOC, MockBackend("echo"), audit=True, audit_db=db)
    process(DOC, MockBackend("drop"), audit=True, audit_db=db)
    process(DOC, MockBackend("fake"), audit=True, audit_db=db)
    with pytest.raises(ConnectionError):
        process(DOC, Down("echo"), audit=True, audit_db=db)
    s = summary(db)
    assert s["total_requests"] == 4
    assert s["by_status"] == {"ok": 1, "flagged": 2, "rejected": 0, "blocked": 0, "error": 1}
    assert s["placeholders_dropped_by_llm"] == 1 and s["placeholders_invented_by_llm"] == 1
    assert s["llm_errors_by_type"] == {"ConnectionError": 1}


def test_old_database_is_upgraded(tmp_path):
    db = str(tmp_path / "old.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE audit (request_id TEXT PRIMARY KEY, ts_utc TEXT NOT NULL, backend TEXT NOT NULL,"
                 " model TEXT NOT NULL, entity_counts TEXT NOT NULL, entity_total INTEGER NOT NULL,"
                 " sanitized_payload TEXT NOT NULL, blocked INTEGER NOT NULL, leaked_types TEXT NOT NULL,"
                 " restored INTEGER NOT NULL, dropped INTEGER NOT NULL, unknown INTEGER NOT NULL,"
                 " gateway_ms REAL NOT NULL, llm_ms REAL NOT NULL)")
    conn.execute("INSERT INTO audit VALUES ('old1','2026-01-01','mock','m','{}',0,'',0,'[]',0,0,0,1,1)")
    conn.commit()
    conn.close()
    process(DOC, MockBackend("drop"), audit=True, audit_db=db)
    statuses = sorted(r["status"] for r in recent(10, db))
    assert statuses == ["flagged", "ok"]
