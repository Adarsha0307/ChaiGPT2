"""Task 19 tuning: postal-address rule, false-positive filters, Elector ID."""
import pytest

from gateway.contracts import Entity
from gateway.detect import detect, detect_structured
from gateway.ner import POSTAL_ADDRESS_RE, _plausible


@pytest.mark.parametrize("addr", [
    "House No. 401, Neelgiri Bhavan, Lakefront Avenue, Saket, New Delhi, Delhi - 110017",
    "Plot 61, Lotus Residency, Banyan Grove Street, Satellite, Ahmedabad, Gujarat 380015",
    "Flat B-388, Deccan Court, Station Cross Lane, Edappally, Kochi, Kerala - 682024",
    "Unit 59, Gulmohar Greens, MG Link Road, Shivaji Nagar, Nagpur, Maharashtra - 440010",
    "H.No 12/3, Ward 7, Civil Lines, Bareilly 243001",
])
def test_postal_rule_matches_whole_address(addr):
    m = POSTAL_ADDRESS_RE.search(f"Address: {addr}. PAN follows.")
    assert m and m.group() == addr


def test_postal_rule_needs_a_pin_code():
    assert POSTAL_ADDRESS_RE.search("Flat 4 is on the second floor, near the lift") is None


def test_hinglish_address_found_whole():
    text = ("Naya address House No. 100, Parijat Arcade, MG Link Road, Indiranagar, "
            "Bengaluru, Karnataka 560038 update kar dijiye.")
    addrs = [e.text for e in detect(text) if e.type == "ADDRESS"]
    assert addrs == ["House No. 100, Parijat Arcade, MG Link Road, Indiranagar, Bengaluru, Karnataka 560038"]


@pytest.mark.parametrize("etype,text,ok", [
    ("PERSON", "Hi Team", False),
    ("PERSON", "Technical Support", False),
    ("PERSON", "Rahul Sharma", True),
    ("ADDRESS", "Address", False),
    ("ADDRESS", "Permanent Address", False),
    ("ADDRESS", "12 MG Road, Pune 411001", True),
])
def test_generic_words_filtered(etype, text, ok):
    assert _plausible(Entity(type=etype, start=0, end=len(text), text=text)) is ok


def test_greeting_is_not_a_person():
    assert not [e for e in detect("Hi Team,\nOTP screen par timer ruk jaata hai.") if e.type == "PERSON"]


def test_elector_id_keyword():
    assert [(e.type, e.text) for e in detect_structured("6. Elector ID: TLG9671271")] == [
        ("VOTER_ID", "TLG9671271")]
