"""FastAPI wrapper (task 18).

Run:   uvicorn gateway.api:app --port 8000
Docs:  http://127.0.0.1:8000/docs

POST /process   run one document through the gateway (writes an audit row)
GET  /audit     most recent audit rows (no raw values, ever)
GET  /audit/summary  counts by status: ok / flagged / blocked / error
GET  /health    liveness + which NER backend is active
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .audit import recent, summary
from .backends import GeminiBackend, MockBackend
from .pipeline import process
from .prompt import DEFAULT_TASK


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .detect import detect

    detect("Warm-up for Rahul Sharma, PAN ABCPK1234F.")  # load models once at startup
    yield


app = FastAPI(
    title="PS-02 Privacy Gateway",
    description="Masks Indian PII before text reaches an LLM, then restores it in the answer.",
    version="1.0.0",
    lifespan=lifespan,
)


class ProcessRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50_000,
                      examples=["Mera naam Rahul Sharma hai, PAN ABCPK1234F."])
    backend: Literal["mock", "gemini"] = "mock"
    mock_mode: Literal["echo", "paraphrase", "reorder", "drop", "fake"] = "echo"
    task: str = Field(DEFAULT_TASK, max_length=2_000)
    # Failure drills for demos: inject a fault on purpose.
    simulate: Literal["none", "detector_miss", "llm_outage"] = "none"
    # Check Aadhaar / PAN / GSTIN / passport / voter ID / phone; reject invalid ones.
    validate_ids: bool = True


def _detector_that_misses_a_repeat(text: str):
    """DRILL: real detection, then forget the last repeat of a value."""
    from .detect import detect
    from .values import normalize

    ents = detect(text)
    seen = {}
    for i, e in enumerate(ents):
        seen.setdefault((e.type, normalize(e.text)), []).append(i)
    repeats = [idx[-1] for idx in seen.values() if len(idx) > 1]
    if repeats:
        ents = [e for i, e in enumerate(ents) if i != max(repeats)]
    return ents


class _OutageBackend(MockBackend):
    """DRILL: an LLM provider that cannot be reached."""

    name = "gemini"

    def __init__(self):
        super().__init__("echo")
        self.model = "gemini (simulated outage)"

    def generate(self, prompt):
        raise ConnectionError("simulated outage")


@app.get("/health")
def health() -> dict:
    from .ner import ner_backend

    return {"status": "ok", "ner": ner_backend()}


@app.post("/process")
def process_endpoint(req: ProcessRequest) -> dict:
    if req.simulate == "llm_outage":
        backend = _OutageBackend()
    elif req.backend == "gemini":
        try:
            backend = GeminiBackend()
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
    else:
        backend = MockBackend(req.mock_mode)
    detector = _detector_that_misses_a_repeat if req.simulate == "detector_miss" else None
    try:
        result = process(req.text, backend, task=req.task, audit=True, detector=detector,
                         validate_ids=req.validate_ids)
    except Exception as e:  # noqa: BLE001 - surface LLM failures as 502, not 500
        raise HTTPException(status_code=502, detail=f"LLM call failed: {type(e).__name__}") from e
    out = result.to_dict()
    from .audit import status_of

    out["status"] = status_of(result)
    return out


@app.get("/", include_in_schema=False)
def demo_page():
    from fastapi.responses import FileResponse

    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "demo.html"))


@app.get("/audit")
def audit_endpoint(limit: int = 50) -> list[dict]:
    return recent(max(1, min(limit, 500)))


@app.get("/audit/summary")
def audit_summary_endpoint() -> dict:
    """Requests by status (ok / flagged / blocked / error), leaks blocked, LLM errors."""
    return summary()
