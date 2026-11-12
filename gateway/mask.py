"""Masking (M1). STUB: masks nothing, empty mapping.

Phase 3: typed <TYPE_N> placeholders, same value -> same placeholder,
normalize spaces and dashes before comparing values.
"""
from __future__ import annotations

from .contracts import Entity, MaskResult


def mask(text: str, entities: list[Entity]) -> MaskResult:
    return MaskResult(masked_text=text, mapping={}, entities=list(entities))
