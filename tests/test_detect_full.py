"""Task 8 + checkpoint: full detect() on 3 sample docs (loads GLiNER), and
the spaCy + regex fallback."""
import pytest

from gateway import ner
from gateway.detect import detect

DOCS = [
    (
        "Mera naam Rahul Sharma hai. PAN ABCDE1234F, Aadhaar 2345 6789 0123. "
        "Rahul Sharma ka mobile 98765 43210 hai.",
        [("PERSON", "Rahul Sharma"), ("PAN", "ABCDE1234F"), ("AADHAAR", "2345 6789 0123"),
         ("PERSON", "Rahul Sharma"), ("PHONE", "98765 43210")],
    ),
    (
        "Loan applicant Priya Nair, residing at Flat 4B, Shanti Apartments, MG Road, "
        "Bengaluru 560001. Email priya.nair@example.com, GSTIN 27ABCPK1234F1Z5.",
        [("PERSON", "Priya Nair"),
         ("ADDRESS", "Flat 4B, Shanti Apartments, MG Road, Bengaluru 560001"),
         ("EMAIL", "priya.nair@example.com"), ("GSTIN", "27ABCPK1234F1Z5")],
    ),
    (
        "Support ticket: customer Mohammed Iqbal (voter ID ABC1234567, passport no A1234567) "
        "called from +91-9123456789 about his address 12 Gandhi Nagar, Sector 5, Jaipur 302015.",
        [("PERSON", "Mohammed Iqbal"), ("VOTER_ID", "ABC1234567"), ("PASSPORT", "A1234567"),
         ("PHONE", "+91-9123456789"), ("ADDRESS", "12 Gandhi Nagar, Sector 5, Jaipur 302015")],
    ),
]


@pytest.mark.parametrize("text,expected", DOCS, ids=["hinglish", "loan", "support"])
def test_detect_sample_docs(text, expected):
    out = detect(text)
    assert [(e.type, e.text) for e in out] == expected
    assert all(a.end <= b.start for a, b in zip(out, out[1:]))  # no overlaps
    for e in out:
        assert text[e.start:e.end] == e.text


def test_gliner_is_the_active_ner():
    assert ner.ner_backend() == "gliner"


def test_long_text_is_windowed():
    filler = "Kal bank gaya aur form bhara. " * 120  # ~720 words, beyond one window
    text = filler + "Applicant Anjali Verma signed the form."
    assert ("PERSON", "Anjali Verma") in [(e.type, e.text) for e in detect(text)]


def test_spacy_fallback(monkeypatch):
    monkeypatch.setenv("PII_NER", "spacy")
    text = "Customer Priya Nair lives at 12 Gandhi Nagar, Sector 5, Jaipur 302015."
    assert ner.ner_backend() == "spacy-fallback"
    assert [(e.type, e.text) for e in detect(text)] == [
        ("PERSON", "Priya Nair"), ("ADDRESS", "12 Gandhi Nagar, Sector 5, Jaipur 302015")]


def test_empty_text():
    assert detect("") == [] and detect("   ") == []
