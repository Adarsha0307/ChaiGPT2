"""ID validation: is each Indian ID actually well-formed and real-looking?

Detection answers "is this personal data?". Validation answers "is this ID
valid?". A request with an invalid ID is stopped before anything is sent,
and the user is asked to re-enter the value, with the exact reason.

Rules (official structures):
  AADHAAR   12 digits, first digit 2-9, Verhoeff check digit correct
  PAN       5 letters + 4 digits + 1 letter; 4th letter = holder type
            (P person, C company, H HUF, F firm, A AOP, T trust, B BOI,
             L local authority, J artificial juridical person, G govt, E LLP)
  GSTIN     15 chars: state code 01-38, a valid PAN, entity number 1-9/A-Z,
            'Z', then a mod-36 check character
  PASSPORT  1 letter + 7 digits, digits after the letter not starting/ending in 0
  VOTER_ID  3 letters + 7 digits (EPIC)
  PHONE     a valid Indian number (Google phonenumbers)

Also finds "claimed" IDs: a value written right after a keyword such as
"Aadhaar:" or "PAN no." even when its format is wrong, so a mistyped ID is
never sent unmasked.
"""
from __future__ import annotations

import re

from .contracts import Entity

ID_TYPES = ("AADHAAR", "PAN", "GSTIN", "PASSPORT", "VOTER_ID", "PHONE")

LABEL = {"AADHAAR": "Aadhaar number", "PAN": "PAN", "GSTIN": "GSTIN",
         "PASSPORT": "passport number", "VOTER_ID": "Voter ID (EPIC)", "PHONE": "phone number"}

PAN_HOLDER = "ABCEFGHJLPT"
HOLDER_NAMES = "P = individual, C = company, H = HUF, F = firm, T = trust, A = AOP"

# Verhoeff tables
_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
      [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
      [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
      [9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]


def verhoeff_ok(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def gstin_check_char(first14: str) -> str:
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    total = 0
    for i, ch in enumerate(first14):
        p = chars.index(ch) * (1 if i % 2 == 0 else 2)
        total += p // 36 + p % 36
    return chars[(36 - total % 36) % 36]


def _compact(v: str) -> str:
    return re.sub(r"[\s\-.]", "", v).upper()


def _pan_problem(p: str) -> str | None:
    if len(p) != 10:
        return f"has {len(p)} characters; a PAN has exactly 10 (5 letters, 4 digits, 1 letter, e.g. ABCPK1234F)"
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", p):
        return "must be 5 letters, then 4 digits, then 1 letter (e.g. ABCPK1234F)"
    if p[3] not in PAN_HOLDER:
        return f"has '{p[3]}' as its 4th letter, which is not a valid holder type ({HOLDER_NAMES})"
    return None


def problem(etype: str, value: str) -> str | None:
    """None if the value is a valid ID of this type, else a plain-English reason."""
    v = _compact(value)
    if etype == "AADHAAR":
        if not v.isdigit():
            return "contains characters other than digits"
        if len(v) != 12:
            return f"has {len(v)} digits; an Aadhaar number has exactly 12"
        if v[0] in "01":
            return "starts with 0 or 1; real Aadhaar numbers start with 2-9"
        if not verhoeff_ok(v):
            return "fails the Aadhaar check digit (Verhoeff), so it cannot be a real Aadhaar number"
        return None
    if etype == "PAN":
        return _pan_problem(v)
    if etype == "GSTIN":
        if len(v) != 15:
            return f"has {len(v)} characters; a GSTIN has exactly 15"
        if not v[:2].isdigit() or not 1 <= int(v[:2]) <= 38:
            return f"starts with state code {v[:2]}, which does not exist (valid codes are 01-38)"
        pan = _pan_problem(v[2:12])
        if pan:
            return "contains an invalid PAN in positions 3-12: it " + pan
        if not re.fullmatch(r"[1-9A-Z]", v[12]):
            return "has an invalid entity number in position 13"
        if v[13] != "Z":
            return f"has '{v[13]}' in position 14; it must be 'Z'"
        if gstin_check_char(v[:14]) != v[14]:
            return "fails the GSTIN check character, so it cannot be a real GSTIN"
        return None
    if etype == "PASSPORT":
        if not re.fullmatch(r"[A-Z][0-9]{7}", v):
            return "must be 1 letter followed by 7 digits (e.g. K8765432)"
        if v[1] == "0" or v[7] == "0":
            return "has a 0 right after the letter or at the end, which Indian passport numbers do not use"
        return None
    if etype == "VOTER_ID":
        if not re.fullmatch(r"[A-Z]{3}[0-9]{7}", v):
            return "must be 3 letters followed by 7 digits (e.g. ABC1234567)"
        return None
    if etype == "PHONE":
        import phonenumbers

        try:
            n = phonenumbers.parse(value, "IN")
        except phonenumbers.NumberParseException:
            return "is not a phone number"
        if not phonenumbers.is_valid_number(n):
            return "is not a valid Indian phone number"
        digits = re.sub(r"\D", "", value)
        written_as_mobile = len(digits) == 10 and not value.strip().startswith(("0", "+"))
        if written_as_mobile and digits[0] not in "6789":
            return "looks like a 10-digit mobile number, but Indian mobile numbers start with 6, 7, 8 or 9"
        return None
    return None


# ---- values written after a keyword, even if malformed ---------------------
_SEP = r"(?:\s*(?:card|no\.?|number|num|ref\.?|id|#|is|hai|:|-)\s*){0,4}[:#.\-]?\s*"
_CLAIM = {
    "AADHAAR": (r"\b(?:aadhaar|aadhar|adhaar|adhar|uidai|uid)\b", r"[0-9][0-9 \-]{4,22}[0-9]"),
    "PAN": (r"\bpan\b", r"[A-Za-z0-9]{6,14}"),
    "GSTIN": (r"\b(?:gstin|gst)\b", r"[A-Za-z0-9]{10,20}"),
    "PASSPORT": (r"\bpassport\b", r"[A-Za-z0-9]{5,12}"),
    "VOTER_ID": (r"\b(?:voter\s*id|voter|epic|elector\s*id)\b", r"[A-Za-z0-9]{6,14}"),
    "PHONE": (r"\b(?:mobile|phone|mob|contact|whatsapp|ph)\b", r"\+?[0-9][0-9 ()\-]{5,18}[0-9]"),
}
_CLAIM_RE = {t: re.compile(kw + _SEP + r"(?P<v>" + val + r")", re.IGNORECASE) for t, (kw, val) in _CLAIM.items()}


def find_claimed(text: str) -> list[Entity]:
    out = []
    for etype, rx in _CLAIM_RE.items():
        for m in rx.finditer(text):
            v = m.group("v").strip(" -")
            if etype not in ("AADHAAR", "PHONE") and (not re.search(r"\d", v) or len(v) < 6):
                continue  # "PAN card details" or "GST registration" is not an ID
            if etype in ("AADHAAR", "PHONE") and len(re.sub(r"\D", "", v)) < 6:
                continue
            s = m.start("v") + m.group("v").index(v)
            out.append(Entity(type=etype, start=s, end=s + len(v), text=v, score=0.5, source="claimed"))
    return out


def check_ids(text: str, entities: list[Entity]) -> tuple[list[Entity], list[dict]]:
    """Add keyword-claimed IDs the detectors missed, then validate every ID.

    Returns (entities, invalid). Invalid IDs stay in `entities`, so they are
    masked even if the caller decides to continue.
    """
    ents = list(entities)
    for c in find_claimed(text):
        if not any(c.start < e.end and e.start < c.end for e in ents):
            ents.append(c)
    ents.sort(key=lambda e: e.start)
    invalid = []
    for e in ents:
        if e.type in ID_TYPES:
            why = problem(e.type, e.text)
            if why:
                invalid.append({
                    "type": e.type, "value": e.text, "start": e.start, "end": e.end, "reason": why,
                    "message": f"The {LABEL[e.type]} '{e.text}' {why}. Please check it and enter it again.",
                })
    return ents, invalid
