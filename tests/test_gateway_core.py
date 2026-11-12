"""Phase 3: masker, leak guard, mock modes, reinserter, process()."""
import pytest

from gateway.backends import MockBackend
from gateway.contracts import Entity
from gateway.leak_guard import check_outbound
from gateway.mask import mask
from gateway.pipeline import process
from gateway.reinsert import reinsert


def ents(text, *pairs):
    out, pos = [], 0
    for t, v in pairs:
        s = text.index(v, pos)
        out.append(Entity(type=t, start=s, end=s + len(v), text=v))
        pos = s + len(v)
    return out


# ---- task 10: masker --------------------------------------------------------
def test_repeated_name_gets_same_placeholder():
    t = "Rahul Sharma signed. Later Rahul Sharma called. Priya Nair witnessed."
    m = mask(t, ents(t, ("PERSON", "Rahul Sharma"), ("PERSON", "Rahul Sharma"), ("PERSON", "Priya Nair")))
    assert m.masked_text == "<PERSON_1> signed. Later <PERSON_1> called. <PERSON_2> witnessed."
    assert m.mapping == {"<PERSON_1>": "Rahul Sharma", "<PERSON_2>": "Priya Nair"}


def test_same_value_with_different_spacing_and_dashes():
    t = "Aadhaar 5652 7833 7667, again 5652-7833-7667, again 565278337667."
    m = mask(t, ents(t, ("AADHAAR", "5652 7833 7667"), ("AADHAAR", "5652-7833-7667"),
                     ("AADHAAR", "565278337667")))
    assert m.masked_text == "Aadhaar <AADHAAR_1>, again <AADHAAR_1>, again <AADHAAR_1>."
    assert list(m.mapping) == ["<AADHAAR_1>"]


def test_numbering_is_per_type():
    t = "A ABCPK1234F B XYZPM9876Q C Rahul Sharma"
    m = mask(t, ents(t, ("PAN", "ABCPK1234F"), ("PAN", "XYZPM9876Q"), ("PERSON", "Rahul Sharma")))
    assert m.masked_text == "A <PAN_1> B <PAN_2> C <PERSON_1>"


def test_no_entities_means_no_change():
    m = mask("nothing private here", [])
    assert m.masked_text == "nothing private here" and m.mapping == {}


# ---- task 11: leak guard ----------------------------------------------------
def test_clean_payload_passes():
    lc = check_outbound("Summary of <PERSON_1> and <PAN_1>", {"<PERSON_1>": "Rahul Sharma", "<PAN_1>": "ABCPK1234F"})
    assert lc.passed and lc.leaked_types == []


@pytest.mark.parametrize("payload", [
    "planted leak: Rahul Sharma",
    "planted leak: RAHUL  SHARMA",
    "planted leak: abcpk1234f",
])
def test_planted_leak_is_caught(payload):
    lc = check_outbound(payload, {"<PERSON_1>": "Rahul Sharma", "<PAN_1>": "ABCPK1234F"})
    assert not lc.passed


def test_reformatted_number_is_caught():
    lc = check_outbound("id 5652-7833-7667", {"<AADHAAR_1>": "5652 7833 7667"})
    assert not lc.passed and lc.leaked_types == ["AADHAAR"]


def test_leak_check_reports_types_not_values():
    lc = check_outbound("Rahul Sharma ABCPK1234F", {"<PERSON_1>": "Rahul Sharma", "<PAN_1>": "ABCPK1234F"})
    assert lc.leaked_types == ["PAN", "PERSON"]
    assert "Rahul" not in repr(lc) and "ABCPK" not in repr(lc)


def test_no_false_leak_inside_longer_word():
    assert check_outbound("Ramesh program", {"<PERSON_1>": "Ram"}).passed


def test_process_blocks_when_masking_misses_a_repeat(monkeypatch):
    # Simulate a detector that found the name once but missed its repeat.
    import gateway.pipeline as pl
    text = "Rahul Sharma applied. RAHUL SHARMA signed."
    monkeypatch.setattr(pl, "detect", lambda t: ents(t, ("PERSON", "Rahul Sharma")))
    calls = []

    class Spy(MockBackend):
        def generate(self, prompt):
            calls.append(prompt)
            return super().generate(prompt)

    r = pl.process(text, Spy("echo"))
    assert r.blocked and r.outbound_payload == "" and calls == []  # nothing was sent
    assert r.leak_check.leaked_types == ["PERSON"]


# ---- task 14: mock modes ----------------------------------------------------
DOC = '"""\nMera naam <PERSON_1> hai. PAN <PAN_1>. Voter ID <VOTER_ID_1>.\n"""'


def test_mock_echo():
    assert MockBackend("echo").generate(DOC).text == "Mera naam <PERSON_1> hai. PAN <PAN_1>. Voter ID <VOTER_ID_1>."


def test_mock_paraphrase_changes_placeholder_forms():
    out = MockBackend("paraphrase").generate(DOC).text
    assert out.startswith("Summary: ") and "PERSON_1" in out and "[PAN_1]" in out and "<Voter Id 1>" in out


def test_mock_reorder():
    out = MockBackend("reorder").generate(DOC).text
    assert out.index("<VOTER_ID_1>") < out.index("<PERSON_1>")


def test_mock_drop_removes_last_placeholder():
    out = MockBackend("drop").generate(DOC).text
    assert "<VOTER_ID_1>" not in out and "<PAN_1>" in out


def test_mock_fake_invents_placeholder():
    assert "<PERSON_9>" in MockBackend("fake").generate(DOC).text


def test_mock_rejects_unknown_mode():
    with pytest.raises(ValueError):
        MockBackend("nope")


# ---- task 15: reinserter ----------------------------------------------------
MAP = {"<PERSON_1>": "Rahul Sharma", "<PAN_1>": "ABCPK1234F", "<VOTER_ID_1>": "ABC1234567"}


@pytest.mark.parametrize("form", ["<PERSON_1>", "PERSON_1", "[PERSON_1]", "{PERSON_1}",
                                  "<Person 1>", "<person_1>", "< PERSON_1 >", "<<PERSON_1>>"])
def test_tolerant_forms(form):
    r = reinsert(f"Hello {form}.", MAP)
    assert r.text == "Hello Rahul Sharma." and r.restored == ["<PERSON_1>"]


def test_voter_id_variants():
    for form in ("<VOTER_ID_1>", "<Voter Id 1>", "[VOTER-ID_1]", "VOTER_ID_1"):
        assert reinsert(form, MAP).text == "ABC1234567", form


def test_unknown_placeholder_kept_and_flagged():
    r = reinsert("Call <PERSON_9> about <PAN_1>.", MAP)
    assert r.text == "Call <PERSON_9> about ABCPK1234F." and r.unknown == ["<PERSON_9>"]


def test_dropped_placeholders_reported():
    r = reinsert("Only <PAN_1> survived.", MAP)
    assert r.dropped == ["<PERSON_1>", "<VOTER_ID_1>"]


def test_only_this_requests_mapping_is_used():
    r = reinsert("<PERSON_1> and <PERSON_2>", {"<PERSON_1>": "Priya Nair"})
    assert r.text == "Priya Nair and <PERSON_2>" and r.unknown == ["<PERSON_2>"]


def test_plain_words_are_not_placeholders():
    text = "Your PAN card and PERSON details, phone 1 and email us."
    assert reinsert(text, MAP).text == text


# ---- task 16: process() end to end with Mock ---------------------------------
SAMPLE = ("Mera naam Rahul Sharma hai. PAN BNZPM2501F, Aadhaar 4991 1866 5246. "
          "Rahul Sharma ka mobile 98765 43210 hai.")
RAW = ["Rahul Sharma", "BNZPM2501F", "4991 1866 5246", "98765 43210"]


def test_echo_round_trip_is_exact():
    r = process(SAMPLE, MockBackend("echo"))
    assert r.final_text == SAMPLE and not r.blocked and r.leak_check.passed
    assert r.reinsertion.dropped == [] and r.reinsertion.unknown == []


def test_nothing_raw_leaves_the_laptop():
    r = process(SAMPLE, MockBackend("echo"))
    for v in RAW:
        assert v not in r.outbound_payload and v not in r.sanitized_text


@pytest.mark.parametrize("mode", ["paraphrase", "reorder"])
def test_all_values_come_back(mode):
    r = process(SAMPLE, MockBackend(mode))
    for v in RAW:
        assert v in r.final_text
    assert r.reinsertion.dropped == []


def test_gateway_and_llm_timers_are_separate():
    r = process(SAMPLE, MockBackend("echo"))
    assert r.gateway_ms > 0 and r.llm_ms >= 0 and r.gateway_ms != r.llm_ms
