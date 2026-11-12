"""Phase 1 gate: process() runs end to end on stubs."""
from gateway.backends import MockBackend
from gateway.contracts import ProcessResult
from gateway.pipeline import process
from gateway.prompt import build_prompt

DOC = "Mera naam Rahul Sharma hai. PAN BNZPM2501F, Aadhaar 4991 1866 5246."

CONTRACT_FIELDS = {
    "request_id", "original_text", "sanitized_text", "outbound_payload",
    "llm_output", "final_text", "entities", "reinsertion", "leak_check",
    "backend", "model", "gateway_ms", "llm_ms", "blocked", "needs_correction", "invalid_ids",
}


def test_process_runs_end_to_end_on_stubs():
    r = process(DOC, MockBackend("echo"))
    assert isinstance(r, ProcessResult)
    assert r.final_text == DOC  # stubs mask nothing, echo returns it
    assert r.leak_check.passed and not r.blocked
    assert r.backend == "mock" and r.model == "mock-echo"
    assert r.gateway_ms >= 0 and r.llm_ms >= 0


def test_result_has_every_contract_field():
    d = process(DOC).to_dict()
    assert set(d) == CONTRACT_FIELDS
    assert set(d["reinsertion"]) == {"text", "restored", "dropped", "unknown"}


def test_prompt_keeps_placeholders_instruction():
    p = build_prompt("Hello <PERSON_1>")
    assert "<PERSON_1>" in p and "exactly as written" in p
