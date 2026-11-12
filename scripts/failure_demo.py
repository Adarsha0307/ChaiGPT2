"""Failure drill: fill a demo audit log with what goes wrong, and how it's handled.

Run:  python scripts/failure_demo.py
Out:  reports/demo_audit.db (fresh each run) and reports/failure_demo.md

Scenarios marked SIMULATED inject a fault on purpose (a detector that misses
something, an LLM that is down). The rest use the real gateway unchanged.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gateway.audit import recent, summary  # noqa: E402
from gateway.backends import MockBackend  # noqa: E402
from gateway.contracts import Entity  # noqa: E402
from gateway.pipeline import process  # noqa: E402

DB = os.path.join(ROOT, "reports", "demo_audit.db")
DOC = ("Loan applicant Priya Nair, PAN ABCPK1234F, Aadhaar 4991 1866 5246, "
       "mobile 98765 43210. Priya Nair requests a top-up loan.")


class DownBackend(MockBackend):
    """SIMULATED: an LLM provider that is unreachable or times out."""

    def __init__(self, exc):
        super().__init__("echo")
        self.exc = exc
        self.model = "gemini (simulated outage)"

    def generate(self, prompt):
        raise self.exc


def first_mention_only(text):
    """SIMULATED detector failure: finds the name once, misses its re-cased repeat."""
    i = text.index("Rahul Sharma")
    return [Entity("PERSON", i, i + 12, "Rahul Sharma")]


SCENARIOS = [
    ("Normal request", "real", lambda: process(DOC, MockBackend("echo"), audit=True, audit_db=DB),
     "Sent masked, every value restored."),
    ("LLM rewrites placeholders", "real",
     lambda: process(DOC, MockBackend("paraphrase"), audit=True, audit_db=DB),
     "AI wrote PERSON_1, [PAN_1], <Aadhaar 1>; all restored, so still ok."),
    ("LLM drops a placeholder", "real", lambda: process(DOC, MockBackend("drop"), audit=True, audit_db=DB),
     "Answer is missing one value; flagged so staff know it was left out."),
    ("LLM invents a placeholder", "real", lambda: process(DOC, MockBackend("fake"), audit=True, audit_db=DB),
     "AI made up <PERSON_9>; left as is and flagged, never filled with a guess."),
    ("Detector misses a repeat in CAPITALS", "SIMULATED",
     lambda: process("Rahul Sharma applied. RAHUL SHARMA signed the form.", MockBackend("echo"),
                     audit=True, audit_db=DB, detector=first_mention_only),
     "Leak guard found the raw name in the outgoing text; request blocked, nothing sent."),
    ("Gemini unreachable", "SIMULATED",
     lambda: process(DOC, DownBackend(ConnectionError("network down")), audit=True, audit_db=DB),
     "Error recorded with its type only; the caller gets a clear failure, not a crash."),
    ("Gemini timeout", "SIMULATED",
     lambda: process(DOC, DownBackend(TimeoutError("timed out")), audit=True, audit_db=DB),
     "Same: recorded as an error row; the masked payload had already passed the guard."),
    ("Unseen phrasing: first name alone", "real",
     lambda: process("Applicant Sunita Rao called today. Sunita said the claim is pending.",
                     MockBackend("echo"), audit=True, audit_db=DB),
     "Real limitation: 'Sunita' alone was not detected, so the guard could not know it. "
     "Status shows ok; the stress test reports this leak."),
]


def main():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    outcomes = []
    for name, kind, run, meaning in SCENARIOS:
        try:
            run()
            raised = ""
        except Exception as e:  # noqa: BLE001 - errors are part of the drill
            raised = type(e).__name__
        outcomes.append((name, kind, raised, meaning))

    rows = list(reversed(recent(100, DB)))
    s = summary(DB)
    L = ["# Failure drill: audit log\n",
         "Each scenario below ran through the real gateway and wrote one row to "
         "`reports/demo_audit.db`. Scenarios marked SIMULATED inject a fault on purpose. "
         "Re-create with `python scripts/failure_demo.py`.\n",
         "## Summary (from GET /audit/summary)\n",
         "| Status | Requests |\n|---|---:|"]
    L += [f"| {k} | {v} |" for k, v in s["by_status"].items()]
    L += [f"\nLeaks blocked by type: {s['leaks_blocked_by_type'] or 'none'}. "
          f"Placeholders dropped by the LLM: {s['placeholders_dropped_by_llm']}. "
          f"Placeholders invented by the LLM: {s['placeholders_invented_by_llm']}. "
          f"LLM errors: {s['llm_errors_by_type'] or 'none'}.\n",
          "## Every row\n",
          "| # | Scenario | Kind | Status | Entities | Leaked types | Dropped | Invented | Error | What it means |",
          "|---:|---|---|---|---|---|---:|---:|---|---|"]
    for i, ((name, kind, _, meaning), r) in enumerate(zip(outcomes, rows), 1):
        ents = ", ".join(f"{k}×{v}" for k, v in r["entity_counts"].items()) or "none"
        L.append(f"| {i} | {name} | {kind} | **{r['status']}** | {ents} | "
                 f"{', '.join(r['leaked_types']) or 'none'} | {r['dropped']} | {r['unknown']} | "
                 f"{r['error'] or 'none'} | {meaning} |")
    L.append("\nThe audit database holds no raw values: blocked rows store an empty payload, "
             "error rows store only the error's type, and every payload is already masked.")
    open(os.path.join(ROOT, "reports", "failure_demo.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(s)


if __name__ == "__main__":
    main()
