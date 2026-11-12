"""Reinsertion (M1). STUB: returns the LLM text unchanged.

Phase 3: tolerant regex for <PERSON_1>, PERSON_1, [PERSON_1], <Person 1>;
keep + flag unknown placeholders, report dropped ones.
"""
from __future__ import annotations

from .contracts import ReinsertResult


def reinsert(llm_text: str, mapping: dict[str, str]) -> ReinsertResult:
    return ReinsertResult(text=llm_text, restored=[], dropped=list(mapping), unknown=[])
