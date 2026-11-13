"""Purpose-bound masking and response reinsertion policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .contracts import ENTITY_TYPES

Purpose = Literal["support_summary", "eligibility_review", "document_classification"]
MaskAction = Literal["placeholder", "redact"]

DEFAULT_PURPOSE: Purpose = "support_summary"
PURPOSES: tuple[Purpose, ...] = (
    "support_summary",
    "eligibility_review",
    "document_classification",
)


@dataclass(frozen=True)
class EntityPolicy:
    action: MaskAction
    restore: bool = False


_PLACEHOLDER = EntityPolicy("placeholder")
_REDACT = EntityPolicy("redact")

POLICY_TABLE: dict[Purpose, dict[str, EntityPolicy]] = {
    "support_summary": {
        "PERSON": EntityPolicy("placeholder", restore=True),
        "ADDRESS": _PLACEHOLDER,
        "AADHAAR": _PLACEHOLDER,
        "PAN": _PLACEHOLDER,
        "GSTIN": _PLACEHOLDER,
        "VOTER_ID": _PLACEHOLDER,
        "PASSPORT": _PLACEHOLDER,
        "PHONE": _PLACEHOLDER,
        "EMAIL": _PLACEHOLDER,
    },
    "eligibility_review": {
        "PERSON": _PLACEHOLDER,
        "ADDRESS": _PLACEHOLDER,
        "AADHAAR": _PLACEHOLDER,
        "PAN": _PLACEHOLDER,
        "GSTIN": _PLACEHOLDER,
        "VOTER_ID": _PLACEHOLDER,
        "PASSPORT": _PLACEHOLDER,
        "PHONE": _PLACEHOLDER,
        "EMAIL": _PLACEHOLDER,
    },
    "document_classification": {
        "PERSON": _REDACT,
        "ADDRESS": _REDACT,
        "AADHAAR": _REDACT,
        "PAN": _REDACT,
        "GSTIN": _REDACT,
        "VOTER_ID": _REDACT,
        "PASSPORT": _REDACT,
        "PHONE": _REDACT,
        "EMAIL": _REDACT,
    },
}

if any(set(policy) != set(ENTITY_TYPES) for policy in POLICY_TABLE.values()):
    raise RuntimeError("Every purpose policy must explicitly cover every entity type.")


def validate_purpose(purpose: str) -> Purpose:
    if purpose not in POLICY_TABLE:
        raise ValueError(f"Unknown purpose {purpose!r}; use one of {', '.join(PURPOSES)}")
    return purpose  # type: ignore[return-value]


def policy_for(purpose: str, entity_type: str) -> EntityPolicy:
    checked_purpose = validate_purpose(purpose)
    try:
        return POLICY_TABLE[checked_purpose][entity_type]
    except KeyError as exc:
        raise ValueError(f"Unknown entity type {entity_type!r}") from exc
