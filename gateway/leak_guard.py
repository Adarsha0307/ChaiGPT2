"""Leakage guard (M1). STUB: always passes.

Phase 3: search the outbound payload for every original value in the
mapping (normalized), and block the request if any is found.
"""
from __future__ import annotations

from .contracts import LeakCheck


def check_outbound(outbound: str, mapping: dict[str, str]) -> LeakCheck:
    return LeakCheck(passed=True, leaked_types=[])
