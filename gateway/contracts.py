"""Shared contracts for the PS-02 Privacy Gateway.

Everyone (M1/M2 backend, M3 UI + dataset) codes against these shapes.
Change them only by agreement, because the UI and the eval script read them.

Pipeline:  detect(text) -> mask(text, entities, purpose) -> backend.generate(prompt)
           -> reinsert(llm_text, mapping, permitted_restorations) -> ProcessResult
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Protocol

# Every entity type the gateway can detect. Placeholders are <TYPE_N>.
EntityType = Literal[
    "PERSON",
    "ADDRESS",
    "AADHAAR",
    "PAN",
    "GSTIN",
    "VOTER_ID",
    "PASSPORT",
    "PHONE",
    "EMAIL",
]
ENTITY_TYPES: tuple[str, ...] = EntityType.__args__  # type: ignore[attr-defined]


@dataclass(frozen=True)
class Entity:
    """One detected PII span in the ORIGINAL text. `end` is exclusive."""

    type: str
    start: int
    end: int
    text: str
    score: float = 1.0
    source: str = "regex"  # "presidio" | "gliner" | "regex" | "spacy"


@dataclass
class MaskResult:
    """Output of mask(). `mapping` maps emitted placeholders to originals.

    The mapping lives only for the duration of one request. It is never
    logged, never stored in the audit DB and never sent to the LLM.
    `leak_values` holds every detected original solely for the outbound check.
    """

    masked_text: str
    mapping: dict[str, str]
    leak_values: dict[str, str]
    restore: set[str]
    entities: list[Entity]


@dataclass
class LLMResponse:
    """What a backend returns. `outbound_payload` is the exact text sent out."""

    text: str
    outbound_payload: str
    model: str
    latency_ms: float


class LLMBackend(Protocol):
    """Any LLM the gateway can forward sanitized text to (Gemini, Mock...)."""

    name: str

    def generate(self, prompt: str) -> LLMResponse: ...


@dataclass
class ReinsertResult:
    """Output of reinsert().

    restored: placeholders found in the LLM output and replaced.
    dropped:  placeholders we sent that the LLM output no longer contains.
    unknown:  placeholder-looking tokens the LLM invented (left as-is, flagged).
    """

    text: str
    restored: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)


@dataclass
class LeakCheck:
    """Result of the leakage guard on the outbound payload."""

    passed: bool
    leaked_types: list[str] = field(default_factory=list)  # types only, never values


@dataclass
class ProcessResult:
    """Everything the UI, the API and the eval need from one request."""

    request_id: str
    original_text: str
    sanitized_text: str
    outbound_payload: str
    llm_output: str
    final_text: str
    entities: list[Entity]
    reinsertion: ReinsertResult
    leak_check: LeakCheck
    backend: str
    model: str
    gateway_ms: float  # detect + mask + reinsert, excludes the LLM call
    llm_ms: float
    blocked: bool = False  # True when the leakage guard stopped the request
    # True when an ID failed validation (wrong format / check digit); nothing
    # was sent and the user must re-enter the values listed in invalid_ids.
    needs_correction: bool = False
    invalid_ids: list[dict] = field(default_factory=list)  # {type, value, start, end, reason, message}

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Dataset JSON (built by M3, read by the eval script and the UI dropdown)
#
# {
#   "docs": [
#     {
#       "id": "loan_001",
#       "category": "loan" | "kyc" | "support_ticket" | "insurance_claim",
#       "tags": ["hinglish", "multi_person"],          # optional
#       "text": "Mera naam Rahul Sharma hai, PAN ABCDE1234F ...",
#       "entities": [
#         {"type": "PERSON", "start": 10, "end": 22, "text": "Rahul Sharma"},
#         {"type": "PAN",    "start": 31, "end": 41, "text": "ABCDE1234F"}
#       ]
#     }
#   ]
# }
# Offsets are character offsets into `text`, `end` exclusive.
# ---------------------------------------------------------------------------
