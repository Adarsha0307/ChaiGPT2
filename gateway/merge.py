"""Merge overlapping spans from Presidio and the NER model (task 9).

Rules, in order:
1. ID-like entities (Aadhaar, PAN, GSTIN, ...) are resolved first. When two
   overlap, the longer span wins, then type priority, then score.
2. Partial overlaps are never resolved by dropping a span: the winner is
   widened to cover both, so no character that any detector flagged is
   left unmasked.
3. PERSON / ADDRESS spans from the model never override an ID. The parts of
   a model span that cover an ID are cut out and the rest is kept, so an
   address that contains a phone number becomes <ADDRESS_1> ... <PHONE_1>.
"""
from __future__ import annotations

from dataclasses import replace

from .contracts import Entity

STRUCTURED = ("AADHAAR", "GSTIN", "PAN", "PASSPORT", "VOTER_ID", "EMAIL", "PHONE")
MODEL_TYPES = ("PERSON", "ADDRESS")
# Lower number wins a tie on length.
PRIORITY = {t: i for i, t in enumerate(STRUCTURED + MODEL_TYPES)}

_TRIM = " \t\r\n,;:.-–()[]{}\"'/|"


def _overlaps(a: Entity, b: Entity) -> bool:
    return a.start < b.end and b.start < a.end


def _resolve(spans: list[Entity], text: str) -> list[Entity]:
    """Greedy non-overlapping selection; partial overlaps widen the winner."""
    order = sorted(spans, key=lambda e: (-(e.end - e.start), PRIORITY.get(e.type, 99), -e.score))
    kept: list[Entity] = []
    for e in order:
        hits = [k for k in kept if _overlaps(k, e)]
        if not hits:
            kept.append(e)
            continue
        if any(k.start <= e.start and e.end <= k.end for k in hits):
            continue  # fully inside something already kept
        # Partial overlap: widen the strongest hit to the union of everything touched.
        winner = hits[0]
        start = min([e.start] + [k.start for k in hits])
        end = max([e.end] + [k.end for k in hits])
        kept = [k for k in kept if k not in hits]
        kept.append(replace(winner, start=start, end=end, text=text[start:end],
                            score=max([e.score] + [k.score for k in hits])))
    return sorted(kept, key=lambda e: e.start)


def _subtract(span: Entity, blockers: list[Entity], text: str) -> list[Entity]:
    """Cut `blockers` out of `span`; return the trimmed leftover pieces."""
    pieces = [(span.start, span.end)]
    for b in blockers:
        nxt = []
        for s, e in pieces:
            if b.end <= s or e <= b.start:
                nxt.append((s, e))
                continue
            if s < b.start:
                nxt.append((s, b.start))
            if b.end < e:
                nxt.append((b.end, e))
        pieces = nxt
    out = []
    for s, e in pieces:
        while s < e and text[s] in _TRIM:
            s += 1
        while e > s and text[e - 1] in _TRIM:
            e -= 1
        if e - s >= 2 and any(ch.isalnum() for ch in text[s:e]):
            out.append(replace(span, start=s, end=e, text=text[s:e]))
    return out


def merge_spans(entities: list[Entity], text: str) -> list[Entity]:
    structured = _resolve([e for e in entities if e.type not in MODEL_TYPES], text)
    model_pieces: list[Entity] = []
    for e in entities:
        if e.type in MODEL_TYPES:
            model_pieces.extend(_subtract(e, structured, text))
    model = _resolve(model_pieces, text)
    return sorted(structured + model, key=lambda e: e.start)


def propagate(entities: list[Entity], text: str) -> list[Entity]:
    """Mark every other exact occurrence of a detected value with the same type.

    A name the model caught once in a long document is masked everywhere.
    """
    import re

    extra = []
    taken = list(entities)
    for e in entities:
        value = e.text.strip()
        if len(value) < 3:
            continue
        for m in re.finditer(r"(?<!\w)" + re.escape(value) + r"(?!\w)", text):
            cand = Entity(type=e.type, start=m.start(), end=m.end(), text=m.group(),
                          score=e.score, source=e.source)
            if not any(_overlaps(cand, t) for t in taken):
                extra.append(cand)
                taken.append(cand)
    return sorted(entities + extra, key=lambda e: e.start)
