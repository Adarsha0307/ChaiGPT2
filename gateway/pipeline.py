"""process(): Detect -> Mask -> Leak guard -> Forward -> Reinsert (task 16).

This is the one function the UI, the API and the eval call.
gateway_ms covers detect + mask + leak guard + reinsert; llm_ms is the
backend call alone, so the gateway's own overhead is visible.
"""
from __future__ import annotations

import time
import uuid

from .backends import MockBackend
from .contracts import LLMBackend, ProcessResult, ReinsertResult
from .detect import detect
from .leak_guard import check_outbound
from .mask import mask
from .policy import DEFAULT_PURPOSE, Purpose, validate_purpose
from .prompt import DEFAULT_TASK, build_prompt
from .reinsert import reinsert
from .validate import check_ids


def process(
    text: str,
    backend: LLMBackend | None = None,
    task: str = DEFAULT_TASK,
    audit: bool = False,
    audit_db: str | None = None,
    detector=None,
    validate_ids: bool = True,
    purpose: str = DEFAULT_PURPOSE,
) -> ProcessResult:
    """`detector` replaces detect() for tests and failure drills only.

    validate_ids: check every Indian ID (format + check digit). If any is
    invalid, nothing is sent and the result asks the user to re-enter it.
    purpose selects a fixed masking policy, independent of the free-form task.
    """
    purpose: Purpose = validate_purpose(purpose)
    backend = backend or MockBackend()
    request_id = uuid.uuid4().hex[:12]

    t0 = time.perf_counter()
    entities = (detector or detect)(text)
    invalid: list[dict] = []
    if validate_ids:
        entities, invalid = check_ids(text, entities)
    masked = mask(text, entities, purpose)
    prompt = build_prompt(masked.masked_text, task)
    leak = check_outbound(prompt, masked.leak_values)
    pre_ms = (time.perf_counter() - t0) * 1000

    if invalid:
        # Ask the user to correct the IDs; never forward a request built on bad input.
        result = ProcessResult(
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
            needs_correction=True,
            invalid_ids=invalid,
        )
    elif not leak.passed:
        # Never forward a payload that still holds a raw value.
        result = ProcessResult(
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
    else:
        try:
            resp = backend.generate(prompt)
        except Exception as e:
            if audit:  # record the failure (payload already passed the leak guard)
                from .audit import log_error

                log_error(request_id, backend.name, getattr(backend, "model", backend.name),
                          masked.entities, prompt, e, pre_ms, audit_db)
            raise
        t1 = time.perf_counter()
        restored = reinsert(resp.text, masked.mapping, restore=masked.restore)
        post_ms = (time.perf_counter() - t1) * 1000
        result = ProcessResult(
            request_id=request_id,
            original_text=text,
            sanitized_text=masked.masked_text,
            outbound_payload=resp.outbound_payload,
            llm_output=resp.text,
            final_text=restored.text,
            entities=masked.entities,
            reinsertion=restored,
            leak_check=leak,
            backend=backend.name,
            model=resp.model,
            gateway_ms=pre_ms + post_ms,
            llm_ms=resp.latency_ms,
        )

    if audit:
        from .audit import log_request

        log_request(result, audit_db)
    return result
