"""Detection (M2): Presidio for IDs, GLiNER for names and addresses, merged.

    detect(text) -> list[Entity], sorted by start, non-overlapping.

Steps:
  1. detect_structured: Presidio with India recognizers + phone + email
  2. detect_names_addresses: GLiNER (or the spaCy + regex fallback)
  3. merge_spans: IDs win overlaps, partial overlaps widen, nothing flagged
     is left unmasked
  4. propagate: every other exact occurrence of a found value is marked too
"""
from __future__ import annotations

from .contracts import Entity
from .merge import merge_spans, propagate
from .ner import detect_names_addresses
from .recognizers import SCORE_THRESHOLD, TYPE_MAP, get_analyzer


def detect_structured(text: str) -> list[Entity]:
    """Indian IDs, phone and email via Presidio (no NER model)."""
    if not text.strip():
        return []
    results = get_analyzer().analyze(text=text, language="en", score_threshold=SCORE_THRESHOLD)
    return [
        Entity(type=TYPE_MAP[r.entity_type], start=r.start, end=r.end,
               text=text[r.start:r.end], score=round(float(r.score), 3), source="presidio")
        for r in results
        if r.entity_type in TYPE_MAP
    ]


def detect(text: str) -> list[Entity]:
    """Return PII spans in `text`, sorted by start, non-overlapping."""
    if not text.strip():
        return []
    found = detect_structured(text) + detect_names_addresses(text)
    merged = merge_spans(found, text)
    return propagate(merged, text)
