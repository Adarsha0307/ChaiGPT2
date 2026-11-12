"""Task 7: 2 valid + 1 invalid string per ID type, plus phone and email.

Uses Presidio only (detect_structured), so GLiNER is not loaded here.
Aadhaar and GSTIN test values are generated with valid check digits;
they are synthetic, not real people's IDs.
"""
import pytest

from gateway.detect import detect_structured
from gateway.recognizers import registered_entities

# --- check-digit helpers for synthetic test IDs ---------------------------
_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
      [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
      [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
      [9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]
_INV = [0,4,3,2,1,5,6,7,8,9]


def aadhaar(first11: str) -> str:
    """Append the Verhoeff check digit and format as XXXX XXXX XXXX."""
    c = 0
    for i, ch in enumerate(reversed(first11)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    n = first11 + str(_INV[c])
    return f"{n[:4]} {n[4:8]} {n[8:]}"


def gstin(first14: str) -> str:
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    total = 0
    for i, ch in enumerate(first14):
        p = chars.index(ch) * (1 if i % 2 == 0 else 2)
        total += p // 36 + p % 36
    return first14 + chars[(36 - total % 36) % 36]


A1, A2 = aadhaar("49911866524"), aadhaar("73028419360")
G1, G2 = gstin("27ABCPK1234F1Z"), gstin("29AAGCB7383J1Z")

VALID = [
    ("AADHAAR", f"Mera Aadhaar number {A1} hai", A1),
    ("AADHAAR", f"Ref {A2} attached", A2),  # checksum alone is enough
    ("AADHAAR", "Aadhaar 2345 6789 0123", "2345 6789 0123"),  # bad checksum, but context
    ("PAN", "PAN ABCPK1234F", "ABCPK1234F"),
    ("PAN", "pan card no. BNZPM2501F diya hai", "BNZPM2501F"),
    ("GSTIN", f"GSTIN {G1}", G1),
    ("GSTIN", f"Supplier GST number: {G2}", G2),
    ("VOTER_ID", "voter ID ABC1234567", "ABC1234567"),
    ("VOTER_ID", "EPIC number XYZ7654321", "XYZ7654321"),
    ("PASSPORT", "passport no A1234567", "A1234567"),
    ("PASSPORT", "Passport number: Z9876543", "Z9876543"),
    ("PHONE", "mobile 98765 43210", "98765 43210"),
    ("PHONE", "call me on +91-9123456789", "+91-9123456789"),
    ("EMAIL", "email rahul.s@example.com", "rahul.s@example.com"),
    ("EMAIL", "contact priya_nair99@mail.co.in today", "priya_nair99@mail.co.in"),
]

INVALID = [
    ("AADHAAR", "Aadhaar 1234 5678 901"),          # 11 digits
    ("AADHAAR", "order 2345 6789 0123 shipped"),   # bad checksum, no context
    ("PAN", "PAN ABCP1234F"),                      # 9 characters
    ("GSTIN", "GSTIN 27ABCPK1234F1X5"),            # 14th char must be Z
    ("GSTIN", "GSTIN 99ABCPK1234F1Z5"),            # no state code 99
    ("VOTER_ID", "voter id AB12345"),              # too short
    ("PASSPORT", "passport no 12345678"),          # must start with a letter
    ("PHONE", "call 12345"),                       # too short
    ("EMAIL", "rahul.s@@example"),                 # malformed
]


def test_india_recognizers_registered():
    ents = registered_entities()
    for name in ("IN_AADHAAR", "IN_PAN", "IN_PASSPORT", "IN_VOTER", "IN_GSTIN",
                 "PHONE_NUMBER", "EMAIL_ADDRESS"):
        assert name in ents
    # nothing we did not ask for (credit cards, IPs, US IDs, dates...)
    assert len(ents) == 7


@pytest.mark.parametrize("etype,text,value", VALID, ids=[f"{t}-{i}" for i, (t, *_ ) in enumerate(VALID)])
def test_valid_ids_detected(etype, text, value):
    found = [(e.type, e.text) for e in detect_structured(text)]
    assert (etype, value) in found, found


@pytest.mark.parametrize("etype,text", INVALID, ids=[f"{t}-{i}" for i, (t, _) in enumerate(INVALID)])
def test_invalid_ids_rejected(etype, text):
    assert detect_structured(text) == []


def test_offsets_point_at_the_value():
    text = f"PAN ABCPK1234F aur Aadhaar {A1}"
    for e in detect_structured(text):
        assert text[e.start:e.end] == e.text


def test_plain_numbers_are_not_pii():
    assert detect_structured("Invoice 2026 total 45000 INR, order ref XJ-22") == []
