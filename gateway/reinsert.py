"""Reinsertion (task 15): put real values back into the LLM's answer.

Tolerant to how LLMs mangle placeholders:
    <PERSON_1>   PERSON_1   [PERSON_1]   {PERSON_1}   <Person 1>   <VOTER ID 2>
Rules:
- Only the per-request mapping is used; nothing else is ever substituted.
- Placeholder-looking tokens not in the mapping (e.g. an invented
  <PERSON_9>) are left as they are and reported in `unknown`.
- Placeholders we sent that are missing from the answer go in `dropped`.
"""
from __future__ import annotations

import re

from .contracts import ENTITY_TYPES, ReinsertResult

_TYPE_ALTS = "|".join(
    t.replace("_", r"[ _-]?") for t in sorted(ENTITY_TYPES, key=len, reverse=True)
)
PLACEHOLDER_RE = re.compile(
    r"[<\[{]{1,2}\s*(?P<t1>" + _TYPE_ALTS + r")[ _-]?(?P<n1>\d+)\s*[>\]}]{1,2}"   # bracketed
    r"|(?<![\w<\[{])(?P<t2>" + _TYPE_ALTS + r")_(?P<n2>\d+)(?![\w>\]}])",          # bare TYPE_N
    re.IGNORECASE,
)


def _canonical(m: re.Match) -> str:
    t = m.group("t1") or m.group("t2")
    n = m.group("n1") or m.group("n2")
    t = re.sub(r"[ _-]+", "", t).upper()
    t = "VOTER_ID" if t == "VOTERID" else t
    return f"<{t}_{int(n)}>"


def reinsert(llm_text: str, mapping: dict[str, str]) -> ReinsertResult:
    restored: list[str] = []
    unknown: list[str] = []

    def sub(m: re.Match) -> str:
        ph = _canonical(m)
        if ph in mapping:
            if ph not in restored:
                restored.append(ph)
            return mapping[ph]
        if m.group(0) not in unknown:
            unknown.append(m.group(0))
        return m.group(0)

    text = PLACEHOLDER_RE.sub(sub, llm_text)
    dropped = [ph for ph in mapping if ph not in restored]
    return ReinsertResult(text=text, restored=restored, dropped=dropped, unknown=unknown)
