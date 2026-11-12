"""Detection (M2). STUB: returns no entities.

Phase 2 replaces this with Presidio (India recognizers + custom regex)
plus GLiNER for PERSON / ADDRESS, merged by span overlap.
"""
from __future__ import annotations

from .contracts import Entity


def detect(text: str) -> list[Entity]:
    """Return PII spans in `text`, sorted by start, non-overlapping."""
    return []
