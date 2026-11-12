"""Value normalization and tolerant matching, shared by mask and leak guard."""
from __future__ import annotations

import re

_SEP = r"[\s\-–—.,/]*"  # spaces, dashes, dots, commas, slashes between chunks


def normalize(value: str) -> str:
    """Key for "same value": case-folded, spaces and dashes removed.

    "5652 7833 7667", "5652-7833-7667" and "565278337667" are one value.
    """
    return re.sub(r"[\s\-–—]+", "", value).casefold()


def value_pattern(value: str) -> re.Pattern | None:
    """Regex that finds `value` even if re-spaced, re-dashed or re-cased.

    Built from the value's letter/digit chunks with optional separators in
    between, anchored so "Ram" does not match inside "Ramesh".
    """
    chunks = re.findall(r"[^\W_]+", value)
    if not chunks:
        return None
    body = _SEP.join(re.escape(c) for c in chunks)
    return re.compile(r"(?<![^\W_])" + body + r"(?![^\W_])", re.IGNORECASE)
