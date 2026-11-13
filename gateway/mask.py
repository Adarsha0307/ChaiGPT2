"""Masking (task 10): typed <TYPE_N> placeholders.

- Numbering is per type and per request: <PERSON_1>, <PERSON_2>, <PAN_1>.
- The same value always gets the same placeholder, after normalizing spaces,
  dashes and case ("5652 7833 7667" == "5652-7833-7667").
- The mapping (placeholder -> original value) lives only for this request.
"""
from __future__ import annotations

from .contracts import Entity, MaskResult
from .policy import DEFAULT_PURPOSE, policy_for, validate_purpose
from .values import normalize


def placeholder(entity_type: str, n: int) -> str:
    return f"<{entity_type}_{n}>"


def mask(text: str, entities: list[Entity], purpose: str = DEFAULT_PURPOSE) -> MaskResult:
    purpose = validate_purpose(purpose)
    counters: dict[str, int] = {}
    by_value: dict[tuple[str, str], str] = {}
    mapping: dict[str, str] = {}
    leak_values: dict[str, str] = {}
    restore: set[str] = set()
    kept: list[Entity] = []
    parts: list[str] = []
    cursor = 0
    previous: Entity | None = None

    for e in sorted(entities, key=lambda x: (x.start, -x.end)):
        if e.start < 0 or e.end > len(text) or e.end <= e.start or text[e.start:e.end] != e.text:
            raise ValueError(f"Invalid {e.type} entity span ({e.start}, {e.end})")
        if e.start < cursor:
            if previous is not None and (e.start, e.end, e.type) == (
                    previous.start, previous.end, previous.type):
                continue
            raise ValueError("Overlapping entity spans cannot be masked safely")
        policy = policy_for(purpose, e.type)
        key = (e.type, normalize(e.text))
        ph = by_value.get(key)
        if ph is None:
            counters[e.type] = counters.get(e.type, 0) + 1
            ph = placeholder(e.type, counters[e.type])
            by_value[key] = ph
            original = text[e.start:e.end]
            leak_values[ph] = original
            if policy.action == "placeholder":
                mapping[ph] = original
            if policy.restore:
                restore.add(ph)
        parts.append(text[cursor:e.start])
        parts.append(ph if policy.action == "placeholder" else f"[REDACTED_{e.type}]")
        cursor = e.end
        kept.append(e)
        previous = e

    parts.append(text[cursor:])
    return MaskResult(masked_text="".join(parts), mapping=mapping, leak_values=leak_values,
                      restore=restore, entities=kept)
