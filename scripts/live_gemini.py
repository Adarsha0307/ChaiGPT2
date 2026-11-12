"""Task 22: real Gemini run on a few dataset documents.

Run:  python scripts/live_gemini.py [N=5]
Out:  reports/gemini_run.md

For each document: masks it, sends ONLY the sanitized prompt to Gemini,
restores the answer, and checks:
  - leak check passed and no labeled value is in what was sent
  - every placeholder Gemini returned was restored (none left in the answer)
  - which placeholders Gemini dropped or invented
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gateway.backends import GeminiBackend  # noqa: E402
from gateway.leak_guard import find_leaks  # noqa: E402
from gateway.pipeline import process  # noqa: E402
from gateway.reinsert import PLACEHOLDER_RE, _canonical  # noqa: E402
from scripts.evaluate import load_dataset  # noqa: E402


def pick(docs, n):
    """One per category first, then Hinglish ones, for variety."""
    chosen, seen = [], set()
    for d in docs:
        if d["category"] not in seen and d["gold"]:
            chosen.append(d)
            seen.add(d["category"])
    for d in docs:
        if len(chosen) >= n:
            break
        if "hinglish" in d["tags"] and d not in chosen and d["gold"]:
            chosen.append(d)
    return chosen[:n]


def main(n=5):
    _, docs, _ = load_dataset()
    backend = GeminiBackend()
    rows, errors = [], 0
    for d in pick(docs, n):
        t0 = time.perf_counter()
        try:
            r = process(d["text"], backend)
        except Exception as e:  # noqa: BLE001 - record and continue
            errors += 1
            rows.append((d["id"], d["category"], f"ERROR {type(e).__name__}", "", "", "", "", ""))
            print(d["id"], "ERROR", type(e).__name__)
            continue
        gold = {f"{g['type']}#{i}": g["text"] for i, g in enumerate(d["gold"])}
        leaked = find_leaks(r.outbound_payload, gold)
        mapping = list(dict.fromkeys(_canonical(m) for m in PLACEHOLDER_RE.finditer(r.sanitized_text)))
        left = [m.group() for m in PLACEHOLDER_RE.finditer(r.final_text) if _canonical(m) in mapping]
        ok = r.leak_check.passed and not leaked and not left and not r.blocked
        rows.append((d["id"], d["category"], "OK" if ok else "CHECK",
                     f"{len(r.reinsertion.restored)}/{len(mapping)}",
                     ", ".join(r.reinsertion.dropped) or "none",
                     ", ".join(r.reinsertion.unknown) or "none",
                     f"{r.gateway_ms:.0f}", f"{r.llm_ms / 1000:.1f}"))
        print(d["id"], rows[-1][2], rows[-1][3], f"{time.perf_counter() - t0:.1f}s")

    L = ["# Live Gemini run\n",
         f"Model: `{backend.model}`. {len(rows)} documents from M3's dataset. Only the sanitized "
         "prompt was sent; leak check and restoration were checked for each.\n",
         "| Doc | Category | Result | Restored | Dropped by LLM | Invented by LLM | Gateway ms | LLM s |",
         "|---|---|---|---:|---|---|---:|---:|"]
    L += ["| " + " | ".join(r) + " |" for r in rows]
    L.append("\n*Dropped* placeholders are ones a summary legitimately leaves out; they are reported, "
             "never guessed. Errors: %d." % errors)
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    open(os.path.join(ROOT, "reports", "gemini_run.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    return rows, errors


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
