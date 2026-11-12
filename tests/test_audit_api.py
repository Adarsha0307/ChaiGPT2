"""Phase 4: audit log never stores raw values; API endpoints work."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from gateway.audit import recent
from gateway.backends import MockBackend
from gateway.pipeline import process

SAMPLE = "Mera naam Rahul Sharma hai. PAN BNZPM2501F, mobile 98765 43210."
RAW = ["Rahul Sharma", "BNZPM2501F", "98765 43210", "98765"]


def test_one_row_per_request_without_raw_values(tmp_path):
    db = str(tmp_path / "audit.db")
    r1 = process(SAMPLE, MockBackend("echo"), audit=True, audit_db=db)
    process(SAMPLE, MockBackend("reorder"), audit=True, audit_db=db)
    rows = recent(10, db)
    assert len(rows) == 2
    row = next(x for x in rows if x["request_id"] == r1.request_id)
    assert row["entity_counts"] == {"PAN": 1, "PERSON": 1, "PHONE": 1}
    assert row["sanitized_payload"] == r1.outbound_payload and "<PERSON_1>" in row["sanitized_payload"]
    # scan every byte of the database file for raw values
    blob = open(db, "rb").read().decode("utf-8", "ignore")
    for v in RAW:
        assert v not in blob, v


def test_blocked_request_stores_empty_payload(tmp_path, monkeypatch):
    import gateway.pipeline as pl
    from gateway.contracts import Entity
    db = str(tmp_path / "audit.db")
    text = "Rahul Sharma applied. RAHUL SHARMA signed."
    monkeypatch.setattr(pl, "detect", lambda t: [Entity("PERSON", 0, 12, "Rahul Sharma")])
    r = pl.process(text, MockBackend("echo"), audit=True, audit_db=db)
    row = recent(1, db)[0]
    assert r.blocked and row["blocked"] and row["sanitized_payload"] == ""
    assert row["leaked_types"] == ["PERSON"]
    assert "RAHUL" not in open(db, "rb").read().decode("utf-8", "ignore")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import gateway.audit as audit
    db = str(tmp_path_factory.mktemp("api") / "audit.db")
    old = audit.DEFAULT_DB
    audit.DEFAULT_DB = db
    from gateway.api import app
    with TestClient(app) as c:
        yield c
    audit.DEFAULT_DB = old


def test_api_process_and_audit(client):
    r = client.post("/process", json={"text": SAMPLE, "backend": "mock", "mock_mode": "echo"})
    assert r.status_code == 200
    body = r.json()
    assert body["final_text"] == SAMPLE and "<PAN_1>" in body["sanitized_text"]
    a = client.get("/audit?limit=5")
    assert a.status_code == 200 and a.json()[0]["request_id"] == body["request_id"]
    assert "Rahul" not in a.text


def test_api_validates_input(client):
    assert client.post("/process", json={"text": ""}).status_code == 422
    assert client.post("/process", json={"text": "x", "mock_mode": "nope"}).status_code == 422


def test_api_docs_and_health(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/health").json()["status"] == "ok"


def test_api_summary_counts_flagged(client):
    client.post("/process", json={"text": SAMPLE, "mock_mode": "fake"})
    s = client.get("/audit/summary").json()
    assert s["by_status"]["flagged"] >= 1 and s["placeholders_invented_by_llm"] >= 1
