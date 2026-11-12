"""Task 9: merging overlapping spans. Pure logic, no models."""
from gateway.contracts import Entity
from gateway.merge import merge_spans, propagate


def ent(text, t, value, score=0.9, source="x", nth=0):
    start = -1
    for _ in range(nth + 1):
        start = text.index(value, start + 1)
    return Entity(type=t, start=start, end=start + len(value), text=value, score=score, source=source)


def spans(ents):
    return [(e.type, e.text) for e in ents]


def test_exact_duplicates_collapse():
    t = "PAN ABCPK1234F"
    out = merge_spans([ent(t, "PAN", "ABCPK1234F", 0.5), ent(t, "PAN", "ABCPK1234F", 0.85)], t)
    assert spans(out) == [("PAN", "ABCPK1234F")]
    assert out[0].score == 0.85


def test_longer_span_wins():
    t = "GSTIN 27ABCPK1234F1Z5"
    out = merge_spans([ent(t, "GSTIN", "27ABCPK1234F1Z5"), ent(t, "PAN", "ABCPK1234F")], t)
    assert spans(out) == [("GSTIN", "27ABCPK1234F1Z5")]


def test_partial_overlap_widens_instead_of_dropping():
    t = "ref 9876543210123 end"
    out = merge_spans([ent(t, "PHONE", "98765432101"), ent(t, "AADHAAR", "543210123")], t)
    assert spans(out) == [("PHONE", "9876543210123")]  # every flagged char still covered


def test_id_beats_model_span_and_rest_of_address_is_kept():
    t = "Address 12 MG Road Pune 411001 ph 9876543210 thanks"
    model = ent(t, "ADDRESS", "12 MG Road Pune 411001 ph 9876543210", source="gliner")
    phone = ent(t, "PHONE", "9876543210", source="presidio")
    out = merge_spans([model, phone], t)
    assert spans(out) == [("ADDRESS", "12 MG Road Pune 411001 ph"), ("PHONE", "9876543210")]


def test_model_span_inside_id_is_dropped():
    t = "email rahul.sharma@example.com"
    out = merge_spans([ent(t, "EMAIL", "rahul.sharma@example.com"),
                       ent(t, "PERSON", "rahul.sharma", source="gliner")], t)
    assert spans(out) == [("EMAIL", "rahul.sharma@example.com")]


def test_person_vs_address_longer_wins():
    t = "Priya Nair, Nair Bhavan, Kochi"
    out = merge_spans([ent(t, "PERSON", "Priya Nair"),
                       ent(t, "ADDRESS", "Nair Bhavan, Kochi")], t)
    assert spans(out) == [("PERSON", "Priya Nair"), ("ADDRESS", "Nair Bhavan, Kochi")]


def test_result_is_sorted_and_non_overlapping():
    t = "A Rahul Sharma B ABCPK1234F C 98765 43210"
    out = merge_spans([ent(t, "PHONE", "98765 43210"), ent(t, "PERSON", "Rahul Sharma"),
                       ent(t, "PAN", "ABCPK1234F")], t)
    assert [e.start for e in out] == sorted(e.start for e in out)
    assert all(a.end <= b.start for a, b in zip(out, out[1:]))


def test_propagate_marks_repeated_values():
    t = "Rahul Sharma ne loan liya. Baad mein Rahul Sharma ne call kiya."
    out = propagate([ent(t, "PERSON", "Rahul Sharma")], t)
    assert spans(out) == [("PERSON", "Rahul Sharma")] * 2
    assert out[1].start == t.rindex("Rahul Sharma")


def test_propagate_respects_word_boundaries():
    t = "Ram met Ramesh"
    out = propagate([ent(t, "PERSON", "Ram")], t)
    assert spans(out) == [("PERSON", "Ram")]
