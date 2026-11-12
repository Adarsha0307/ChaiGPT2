"""Phase 1 setup check: imports, offline models, Gemini key, stub pipeline.

Run:  python scripts/check_setup.py
"""
from __future__ import annotations

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results: list[tuple[str, bool, str]] = []


def check(name, fn):
    try:
        results.append((name, True, fn() or ""))
    except Exception as e:  # noqa: BLE001 - report everything
        results.append((name, False, f"{type(e).__name__}: {e}"[:200]))


for mod in ["presidio_analyzer", "presidio_anonymizer", "spacy", "fastapi", "uvicorn",
            "streamlit", "google.genai", "google.protobuf"]:
    check(f"import {mod}", lambda m=mod: (importlib.import_module(m), "ok")[1])

check("import gliner", lambda: (importlib.import_module("gliner"), "ok")[1])


def spacy_model():
    import spacy
    for name in ("en_core_web_lg", "en_core_web_sm"):
        try:
            spacy.load(name)
            return f"{name} loads"
        except OSError:
            continue
    raise RuntimeError("no spaCy English model installed")


check("spaCy model", spacy_model)


def gliner_model():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from gliner import GLiNER
    GLiNER.from_pretrained("urchade/gliner_multi_pii-v1")
    return "urchade/gliner_multi_pii-v1 loads offline"


check("GLiNER model", gliner_model)


def gemini():
    from gateway.backends import GeminiBackend
    r = GeminiBackend().generate("Reply with the single word: pong")
    return f"{r.model} replied {r.text.strip()[:30]!r} in {r.latency_ms:.0f} ms"


check("Gemini API call", gemini)


def stub_pipeline():
    from gateway.pipeline import process
    r = process("Test doc for Rahul, PAN ABCDE1234F")
    assert r.final_text
    return f"process() ok, request {r.request_id}"


check("process() on stubs", stub_pipeline)

width = max(len(n) for n, _, _ in results)
for name, ok, msg in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  {msg}")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
