"""Masking (task 10): typed <TYPE_N> placeholders.

- Numbering is per type and per request: <PERSON_1>, <PERSON_2>, <PAN_1>.
- The same value always gets the same placeholder, after normalizing spaces,
  dashes and case ("5652 7833 7667" == "5652-7833-7667").
- The mapping (placeholder -> original value) lives only for this request.
"""
from __future__ import annotations

from .contracts import Entity, MaskResult
from .values import normalize


def placeholder(entity_type: str, n: int) -> str:
    return f"<{entity_type}_{n}>"


def mask(text: str, entities: list[Entity]) -> MaskResult:
    counters: dict[str, int] = {}
    by_value: dict[tuple[str, str], str] = {}
    mapping: dict[str, str] = {}
    kept: list[Entity] = []
    parts: list[str] = []
    cursor = 0

    for e in sorted(entities, key=lambda x: (x.start, -x.end)):
        if e.start < cursor or e.end <= e.start:
            continue  # overlapping or empty span; detect() should never send these
        key = (e.type, normalize(e.text))
        ph = by_value.get(key)
        if ph is None:
            counters[e.type] = counters.get(e.type, 0) + 1
            ph = placeholder(e.type, counters[e.type])
            by_value[key] = ph
            mapping[ph] = text[e.start:e.end]
        parts.append(text[cursor:e.start])
        parts.append(ph)
        cursor = e.end
        kept.append(e)

    parts.append(text[cursor:])
    return MaskResult(masked_text="".join(parts), mapping=mapping, entities=kept)
