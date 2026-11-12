"""FastAPI wrapper (task 18).

Run:   uvicorn gateway.api:app --port 8000
Docs:  http://127.0.0.1:8000/docs

POST /process   run one document through the gateway (writes an audit row)
GET  /audit     most recent audit rows (no raw values, ever)
GET  /health    liveness + which NER backend is active
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .audit import recent
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


@app.get("/health")
def health() -> dict:
    from .ner import ner_backend

    return {"status": "ok", "ner": ner_backend()}


@app.post("/process")
def process_endpoint(req: ProcessRequest) -> dict:
    if req.backend == "gemini":
        try:
            backend = GeminiBackend()
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
    else:
        backend = MockBackend(req.mock_mode)
    try:
        result = process(req.text, backend, task=req.task, audit=True)
    except Exception as e:  # noqa: BLE001 - surface LLM failures as 502, not 500
        raise HTTPException(status_code=502, detail=f"LLM call failed: {type(e).__name__}") from e
    return result.to_dict()


@app.get("/audit")
def audit_endpoint(limit: int = 50) -> list[dict]:
    return recent(max(1, min(limit, 500)))
