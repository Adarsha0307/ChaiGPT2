"""Stress test on HARD, UNSEEN documents (not used for tuning).

The 50-document dataset was also used for tuning, so its 100% scores are an
upper bound. This script measures the gateway on cases written to break it:
lowercase names, first-name-only mentions, Devanagari, odd number spacing,
obfuscated email, addresses with no PIN, decoy codes, and data types that
are out of scope (bank account, IFSC, date of birth).

Run:  python scripts/stress_test.py
Out:  reports/stress_report.md  (real misses and false positives listed)
"""
from __future__ import annotations

import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gateway.backends import MockBackend  # noqa: E402
from gateway.leak_guard import find_leaks  # noqa: E402
from gateway.pipeline import process  # noqa: E402

IN_SCOPE = {"PERSON", "ADDRESS", "AADHAAR", "PAN", "GSTIN", "VOTER_ID", "PASSPORT", "PHONE", "EMAIL"}

# (id, what makes it hard, text, [(type, value), ...]); OUT_* types are outside the 9 we cover.
CASES = [
    ("S01", "All-lowercase Hinglish name and PAN",
     "mera naam rahul verma hai aur mera pan bkzpv4521m hai",
     [("PERSON", "rahul verma"), ("PAN", "bkzpv4521m")]),
    ("S02", "First name alone after the full name",
     "Applicant Sunita Rao called today. Sunita said the claim is still pending.",
     [("PERSON", "Sunita Rao"), ("PERSON", "Sunita")]),
    ("S03", "Name written with initials",
     "The form was signed by R. K. Menon on behalf of the firm.",
     [("PERSON", "R. K. Menon")]),
    ("S04", "Name in Devanagari script",
     "आवेदक का नाम राहुल शर्मा है और PAN ABCPK1234F है।",
     [("PERSON", "राहुल शर्मा"), ("PAN", "ABCPK1234F")]),
    ("S05", "Aadhaar with dashes, keyword 'UID'",
     "UID no: 4991-1866-5246 linked to the account.",
     [("AADHAAR", "4991-1866-5246")]),
    ("S06", "Aadhaar split into pairs of digits",
     "Aadhaar 49 91 18 66 52 46 submitted at branch.",
     [("AADHAAR", "49 91 18 66 52 46")]),
    ("S07", "Phone numbers in unusual formats",
     "Call me on +91 (98765) 43210 or the office line 022-2345-6789.",
     [("PHONE", "+91 (98765) 43210"), ("PHONE", "022-2345-6789")]),
    ("S08", "Email written out in words",
     "You can mail me at priya dot nair at gmail dot com for documents.",
     [("EMAIL", "priya dot nair at gmail dot com")]),
    ("S09", "Address with landmark and no PIN code",
     "Customer Meena Iyer lives near Hanuman Mandir, Sector 15, Noida.",
     [("PERSON", "Meena Iyer"), ("ADDRESS", "Hanuman Mandir, Sector 15, Noida")]),
    ("S10", "Address with PIN but no flat or house word",
     "Please deliver the card to 14 MG Road, Indiranagar, Bengaluru 560038 by Friday.",
     [("ADDRESS", "14 MG Road, Indiranagar, Bengaluru 560038")]),
    ("S11", "Passport number with no keyword",
     "Travel document K8765432 was verified at the counter.",
     [("PASSPORT", "K8765432")]),
    ("S12", "Voter ID in lowercase without keyword",
     "id card xyz1234567 attached for address proof.",
     [("VOTER_ID", "xyz1234567")]),
    ("S13", "GSTIN inside a sentence",
     "Our GST registration 29AAGCB7383J1Z4 appears on every invoice.",
     [("GSTIN", "29AAGCB7383J1Z4")]),
    ("S14", "Bank account, IFSC and date of birth (not in our 9 types)",
     "Refund to A/c 123456789012, IFSC SBIN0001234. DOB 14/08/1990. Holder Arjun Mehta.",
     [("OUT_BANK_ACCOUNT", "123456789012"), ("OUT_IFSC", "SBIN0001234"),
      ("OUT_DOB", "14/08/1990"), ("PERSON", "Arjun Mehta")]),
    ("S15", "No personal data at all",
     "The app crashes when I open the statements tab after the latest update.",
     []),
    ("S16", "Decoy: order code shaped like a PAN",
     "Your order ABCDE1234F has shipped and will arrive in two days.",
     []),
    ("S17", "Decoy: place names that look like person names",
     "Branches in Rajiv Chowk and Indira Nagar will stay closed on Monday.",
     []),
    ("S18", "Several people with the same surname",
     "Nominees: Kavita Joshi (wife) and Rohan Joshi (son). Kavita Joshi will sign.",
     [("PERSON", "Kavita Joshi"), ("PERSON", "Rohan Joshi"), ("PERSON", "Kavita Joshi")]),
]


def _spans(text, gold):
    out, pos = [], {}
    for t, v in gold:
        start = text.index(v, pos.get(v, 0))
        pos[v] = start + len(v)
        out.append({"type": t, "text": v, "start": start, "end": start + len(v)})
    return out


def run():
    rows, misses, fps = [], [], []
    found_by_type, total_by_type = Counter(), Counter()
    out_scope_leaks, blocked = 0, 0
    for cid, why, text, gold in CASES:
        r = process(text, MockBackend("echo"))
        blocked += r.blocked
        g = _spans(text, gold)
        payload = r.outbound_payload if not r.blocked else ""
        leaked_keys = set(find_leaks(payload, {str(i): x["text"] for i, x in enumerate(g)}))
        case_missed = []
        for i, x in enumerate(g):
            if x["type"] in IN_SCOPE:
                total_by_type[x["type"]] += 1
                if str(i) in leaked_keys:
                    case_missed.append(f"{x['type']} `{x['text']}`")
                    misses.append((cid, x["type"], x["text"]))
                else:
                    found_by_type[x["type"]] += 1
            elif str(i) in leaked_keys:
                out_scope_leaks += 1
                case_missed.append(f"{x['type'][4:]} `{x['text']}` (out of scope)")
        case_fp = [f"{e.type} `{e.text}`" for e in r.entities
                   if not any(e.start < x["end"] and x["start"] < e.end for x in g)]
        fps += [(cid, f) for f in case_fp]
        if r.blocked:
            verdict = "BLOCKED"
        elif case_missed:
            verdict = "LEAK"
        elif case_fp:
            verdict = "OVER-MASKED"
        else:
            verdict = "PASS"
        rows.append((cid, why, verdict, "; ".join(case_missed) or "none", "; ".join(case_fp) or "none"))
    return rows, misses, fps, found_by_type, total_by_type, out_scope_leaks, blocked


def write(rows, misses, fps, found, total, out_leaks, blocked):
    n_in = sum(total.values())
    n_found = sum(found.values())
    verdicts = Counter(r[2] for r in rows)
    L = ["# Stress test: hard, unseen documents\n",
         f"{len(rows)} hand-written cases that were **not** used for tuning, built to break the gateway. "
         "Backend: offline Mock (echo). A value counts as leaked if it can be found in the exact text "
         "sent to the LLM.\n",
         "## Summary\n",
         "| Metric | Result |\n|---|---|",
         f"| In-scope values protected | **{n_found} / {n_in}** ({100 * n_found / n_in:.0f}%) |",
         f"| In-scope values leaked | **{n_in - n_found}** |",
         f"| Out-of-scope values sent (bank a/c, IFSC, DOB) | {out_leaks} |",
         f"| Over-masking (false positives) | {len(fps)} |",
         f"| Requests blocked by leak guard | {blocked} |",
         f"| Cases: PASS / LEAK / OVER-MASKED / BLOCKED | {verdicts['PASS']} / {verdicts['LEAK']} / "
         f"{verdicts['OVER-MASKED']} / {verdicts['BLOCKED']} |\n",
         "## Protected by type\n",
         "| Type | Protected | Total |\n|---|---:|---:|"]
    L += [f"| {t} | {found[t]} | {total[t]} |" for t in sorted(total)]
    L += ["\n## Every case\n",
          "| Case | What makes it hard | Verdict | Leaked | Over-masked |",
          "|---|---|---|---|---|"]
    L += ["| " + " | ".join(r) + " |" for r in rows]
    L.append("\nAll names and numbers here are invented for testing.")
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    open(os.path.join(ROOT, "reports", "stress_report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"Protected {n_found}/{n_in} in-scope | leaked {n_in - n_found} | out-of-scope sent {out_leaks} "
          f"| over-masked {len(fps)} | verdicts {dict(verdicts)}")


if __name__ == "__main__":
    write(*run())
