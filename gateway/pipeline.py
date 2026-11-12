"""process(): Detect -> Mask -> Leak guard -> Forward -> Reinsert.

This is the one function the UI, the API and the eval call.
"""
from __future__ import annotations

import time
import uuid

from .backends import MockBackend
from .contracts import LLMBackend, ProcessResult, ReinsertResult
from .detect import detect
from .leak_guard import check_outbound
from .mask import mask
from .prompt import DEFAULT_TASK, build_prompt
from .reinsert import reinsert


def process(text: str, backend: LLMBackend | None = None, task: str = DEFAULT_TASK) -> ProcessResult:
    backend = backend or MockBackend()
    request_id = uuid.uuid4().hex[:12]

    t0 = time.perf_counter()
    entities = detect(text)
    masked = mask(text, entities)
    prompt = build_prompt(masked.masked_text, task)
    leak = check_outbound(prompt, masked.mapping)
    pre_ms = (time.perf_counter() - t0) * 1000

    if not leak.passed:
        # Never forward a payload that still holds a raw value.
        return ProcessResult(
            request_id=request_id,
            original_text=text,
            sanitized_text=masked.masked_text,
            outbound_payload="",
            llm_output="",
            final_text="",
            entities=masked.entities,
            reinsertion=ReinsertResult(text=""),
            leak_check=leak,
            backend=backend.name,
            model=getattr(backend, "model", backend.name),
            gateway_ms=pre_ms,
            llm_ms=0.0,
            blocked=True,
        )

    resp = backend.generate(prompt)

    t1 = time.perf_counter()
    result = reinsert(resp.text, masked.mapping)
    post_ms = (time.perf_counter() - t1) * 1000

    return ProcessResult(
        request_id=request_id,
        original_text=text,
        sanitized_text=masked.masked_text,
        outbound_payload=resp.outbound_payload,
        llm_output=resp.text,
        final_text=result.text,
        entities=masked.entities,
        reinsertion=result,
        leak_check=leak,
        backend=backend.name,
        model=resp.model,
        gateway_ms=pre_ms + post_ms,
        llm_ms=resp.latency_ms,
    )
