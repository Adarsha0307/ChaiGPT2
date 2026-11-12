"""Leakage guard (task 11): last check before anything leaves the laptop.

Searches the exact outbound payload for every original value in the
mapping, tolerant to re-spacing, dashes and case. If any is found, the
request is blocked and only the leaked TYPES are reported, never values.
"""
from __future__ import annotations

from .contracts import LeakCheck
from .values import value_pattern


def find_leaks(outbound: str, values: dict[str, str]) -> list[str]:
    """Return the keys of `values` (placeholder or label) found in `outbound`."""
    hits = []
    for key, value in values.items():
        pat = value_pattern(value)
        if pat is not None and pat.search(outbound):
            hits.append(key)
    return hits


def _type_of(placeholder: str) -> str:
    return placeholder.strip("<>").rsplit("_", 1)[0]


def check_outbound(outbound: str, mapping: dict[str, str]) -> LeakCheck:
    leaked = find_leaks(outbound, mapping)
    return LeakCheck(passed=not leaked, leaked_types=sorted({_type_of(p) for p in leaked}))
