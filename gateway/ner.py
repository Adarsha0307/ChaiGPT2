"""PERSON and ADDRESS detection (task 8).

Primary: GLiNER (urchade/gliner_multi_pii-v1), offline, multilingual, so it
copes with Hinglish. Long texts are split into overlapping word windows.

Fallback (the plan's 6:50 checkpoint rule): if GLiNER cannot load, or
PII_NER=spacy is set, use spaCy's PERSON entities plus an Indian address
regex (house number / locality keyword ... PIN code).
"""
from __future__ import annotations

import os
import re
from functools import lru_cache

from .contracts import Entity

GLINER_MODEL = "urchade/gliner_multi_pii-v1"
GLINER_LABELS = {"person": "PERSON", "address": "ADDRESS"}
GLINER_THRESHOLD = 0.5
WINDOW_WORDS = 200   # GLiNER sees at most ~384 tokens; stay well under
OVERLAP_WORDS = 30   # so a name on a window edge is still seen whole once

ADDRESS_KEYWORDS = (
    r"Nagar|Road|Rd|Marg|Sector|Colony|Street|St|Lane|Chowk|Layout|Enclave|Vihar|Bagh|"
    r"Puram|Gali|Society|Apartments?|Apts?|Residency|Complex|Phase|Block|Mohalla|Basti|"
    r"Gaon|Village|Taluka|Tehsil|District|Dist|Cross|Main"
)
_ADDRESS_RE = re.compile(
    r"(?:\b(?:Flat|House|H\.?\s?No\.?|Plot|Door|Shop)\s*[\w/-]+,?\s*)?"
    r"(?:\b\d{1,5}[A-Za-z]?(?:/\d+)?,?\s+)?"
    r"(?:[A-Z][\w.'-]*\s+){0,4}"
    r"(?:" + ADDRESS_KEYWORDS + r")\b"
    r"(?:[ ,]+[A-Z0-9][\w.'-]*){0,6}"
    r"(?:[ ,-]+[1-9][0-9]{2}\s?[0-9]{3})?",
)
_PIN_RE = re.compile(r"\b[1-9][0-9]{2}\s?[0-9]{3}\b")


@lru_cache(maxsize=1)
def _gliner():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from gliner import GLiNER

    return GLiNER.from_pretrained(GLINER_MODEL)


def ner_backend() -> str:
    """'gliner' when the model is usable, otherwise 'spacy-fallback'."""
    if os.environ.get("PII_NER", "").lower() == "spacy":
        return "spacy-fallback"
    try:
        _gliner()
        return "gliner"
    except Exception:  # noqa: BLE001 - any load failure means fallback
        return "spacy-fallback"


def _windows(text: str):
    """Yield (char_offset, chunk) word windows that overlap a little."""
    words = list(re.finditer(r"\S+", text))
    if not words:
        return
    step = WINDOW_WORDS - OVERLAP_WORDS
    for i in range(0, len(words), step):
        chunk = words[i:i + WINDOW_WORDS]
        start, end = chunk[0].start(), chunk[-1].end()
        yield start, text[start:end]
        if i + WINDOW_WORDS >= len(words):
            break


def _detect_gliner(text: str) -> list[Entity]:
    model = _gliner()
    out = []
    for offset, chunk in _windows(text):
        for p in model.predict_entities(chunk, list(GLINER_LABELS), threshold=GLINER_THRESHOLD):
            s, e = offset + p["start"], offset + p["end"]
            out.append(Entity(type=GLINER_LABELS[p["label"]], start=s, end=e,
                              text=text[s:e], score=float(p["score"]), source="gliner"))
    return out


def _detect_fallback(text: str) -> list[Entity]:
    from .recognizers import get_analyzer

    out = []
    artifacts = get_analyzer().nlp_engine.process_text(text, "en")
    for ent in artifacts.entities:
        if ent.label_ == "PERSON":
            out.append(Entity(type="PERSON", start=ent.start_char, end=ent.end_char,
                              text=ent.text, score=0.6, source="spacy"))
    for m in _ADDRESS_RE.finditer(text):
        out.append(Entity(type="ADDRESS", start=m.start(), end=m.end(),
                          text=m.group(), score=0.6, source="regex"))
    for m in _PIN_RE.finditer(text):  # a bare PIN code still narrows down a home
        out.append(Entity(type="ADDRESS", start=m.start(), end=m.end(),
                          text=m.group(), score=0.4, source="regex"))
    return out


def detect_names_addresses(text: str) -> list[Entity]:
    if ner_backend() == "gliner":
        return _detect_gliner(text)
    return _detect_fallback(text)
