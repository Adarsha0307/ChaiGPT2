"""ID validation: wrong-format IDs are caught, explained, and never sent."""
import pytest

from gateway.backends import MockBackend
from gateway.detect import detect
from gateway.pipeline import process
from gateway.validate import check_ids, problem


@pytest.mark.parametrize("etype,value", [
    ("AADHAAR", "4991 1866 5246"), ("AADHAAR", "499118665246"), ("AADHAAR", "4991-1866-5246"),
    ("PAN", "BNZPM2501F"), ("PAN", "abcpk1234f"),
    ("GSTIN", "27ABCPK1234F1Z5"),
    ("PASSPORT", "K8765432"), ("VOTER_ID", "ABC1234567"),
    ("PHONE", "98765 43210"), ("PHONE", "+91-9123456789"), ("PHONE", "022-2345-6789"),
])
def test_valid_ids(etype, value):
    assert problem(etype, value) is None


@pytest.mark.parametrize("etype,value,why", [
    ("AADHAAR", "1234 5678 901", "has 11 digits"),
    ("AADHAAR", "2345 6789 0123", "Verhoeff"),
    ("AADHAAR", "0991 1866 5246", "starts with 0 or 1"),
    ("PAN", "ABCP1234F", "has 9 characters"),
    ("PAN", "ABCDE1234F", "4th letter"),
    ("PAN", "1BCPK1234F", "5 letters, then 4 digits"),
    ("GSTIN", "99ABCPK1234F1Z5", "state code 99"),
    ("GSTIN", "27ABCPK1234F1X5", "position 14"),
    ("GSTIN", "27ABCPK1234F1Z9", "check character"),
    ("GSTIN", "27ABCPK1234F1Z", "has 14 characters"),
    ("PASSPORT", "12345678", "1 letter followed by 7 digits"),
    ("VOTER_ID", "AB12345", "3 letters followed by 7 digits"),
    ("PHONE", "12345 67890", "start with 6, 7, 8 or 9"),
])
def test_invalid_ids_explained(etype, value, why):
    assert why in problem(etype, value)


def test_wrong_format_after_keyword_is_still_found_and_masked():
    text = "Aadhaar: 1234 5678 901 diya hai"
    ents, invalid = check_ids(text, detect(text))
    assert [(e.type, e.text) for e in ents] == [("AADHAAR", "1234 5678 901")]
    assert invalid[0]["message"].startswith("The Aadhaar number '1234 5678 901' has 11 digits")


def test_valid_id_missed_by_detector_is_added():
    text = "Aadhaar 49 91 18 66 52 46 submitted."
    ents, invalid = check_ids(text, detect(text))
    assert invalid == [] and [(e.type, e.text) for e in ents] == [("AADHAAR", "49 91 18 66 52 46")]


@pytest.mark.parametrize("text", ["my PAN card details are pending", "Aadhaar is linked to my bank",
                                  "GST registration 2023 pending"])
def test_keyword_without_an_id_is_not_flagged(text):
    assert check_ids(text, detect(text))[1] == []


def test_invalid_input_stops_the_request_and_asks_to_reenter(tmp_path):
    from gateway.audit import recent
    db = str(tmp_path / "a.db")
    calls = []

    class Spy(MockBackend):
        def generate(self, prompt):
            calls.append(prompt)
            return super().generate(prompt)

    text = "Mera naam Rahul Sharma hai. Aadhaar: 1234 5678 901, PAN ABCDE1234F."
    r = process(text, Spy("echo"), audit=True, audit_db=db)
    assert r.needs_correction and calls == [] and r.outbound_payload == "" and r.final_text == ""
    assert {i["type"] for i in r.invalid_ids} == {"AADHAAR", "PAN"}
    assert all("Please check it and enter it again" in i["message"] for i in r.invalid_ids)
    row = recent(1, db)[0]
    assert row["status"] == "rejected" and row["error"] == "invalid: AADHAAR, PAN"
    blob = open(db, "rb").read().decode("utf-8", "ignore")
    assert "1234 5678 901" not in blob and "ABCDE1234F" not in blob


def test_valid_input_goes_through():
    r = process("Mera naam Rahul Sharma hai. PAN BNZPM2501F, Aadhaar 4991 1866 5246.", MockBackend("echo"))
    assert not r.needs_correction and r.invalid_ids == [] and "<PAN_1>" in r.outbound_payload


def test_validation_can_be_switched_off():
    r = process("Aadhaar: 1234 5678 901", MockBackend("echo"), validate_ids=False)
    assert not r.needs_correction
