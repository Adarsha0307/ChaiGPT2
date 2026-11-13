"""Evaluation (task 20): leakage, detection precision/recall per type,
reinsertion accuracy per Mock mode, gateway overhead latency.

Run:  python scripts/evaluate.py [path/to/dataset.json]
Out:  metrics_report.md  and  reports/metrics.json

Reads M3's format ({"documents": [{"text", "annotations": [{entity_type,
value, start, end}]}]}) and the contract format ({"docs": [{"text",
"entities": [{type, text, start, end}]}]}).
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gateway.backends import MockBackend  # noqa: E402
from gateway.contracts import ENTITY_TYPES  # noqa: E402
from gateway.leak_guard import find_leaks  # noqa: E402
from gateway.pipeline import process  # noqa: E402
from gateway.policy import DEFAULT_PURPOSE, policy_for  # noqa: E402
from gateway.reinsert import PLACEHOLDER_RE, _canonical  # noqa: E402

CANDIDATES = [
    os.path.join(ROOT, "data", "dataset.json"),
    os.path.join(ROOT, "datasets management", "data", "synthetic_documents.json"),
]


# ---------------------------------------------------------------- loading
def load_dataset(path: str | None = None):
    path = path or next((p for p in CANDIDATES if os.path.exists(p)), None)
    if not path:
        raise SystemExit("No dataset found. Pass a path or add data/dataset.json.")
    raw = json.load(open(path, encoding="utf-8"))
    docs = []
    if "documents" in raw:  # M3 format
        labeled = set(raw.get("metadata", {}).get("entity_types", []))
        for d in raw["documents"]:
            gold = [{"type": a["entity_type"], "start": a["start"], "end": a["end"],
                     "text": a.get("value", d["text"][a["start"]:a["end"]])}
                    for a in d.get("annotations", [])]
            docs.append({"id": d["id"], "category": d.get("category", ""),
                         "tags": d.get("scenarios", []), "text": d["text"], "gold": gold})
    else:  # contract format
        labeled = set()
        for d in raw["docs"]:
            gold = [{"type": e["type"], "start": e["start"], "end": e["end"],
                     "text": e.get("text", d["text"][e["start"]:e["end"]])}
                    for e in d.get("entities", [])]
            docs.append({"id": d["id"], "category": d.get("category", ""),
                         "tags": d.get("tags", []), "text": d["text"], "gold": gold})
    if not labeled:
        labeled = {g["type"] for d in docs for g in d["gold"]}
    for d in docs:  # sanity: offsets must point at the value
        for g in d["gold"]:
            assert d["text"][g["start"]:g["end"]] == g["text"], (d["id"], g)
    return path, docs, labeled


# ---------------------------------------------------------------- metrics
def _overlap(a, b):
    return a["start"] < b["end"] and b["start"] < a["end"]


def score_detection(docs, preds_by_doc, labeled):
    tp, fp, fn, exact = Counter(), Counter(), Counter(), Counter()
    unlabeled = Counter()
    misses, false_pos = [], []
    for d in docs:
        preds = preds_by_doc[d["id"]]
        for g in d["gold"]:
            hit = [p for p in preds if p["type"] == g["type"] and _overlap(p, g)]
            if hit:
                tp[g["type"]] += 1
                if any(p["start"] == g["start"] and p["end"] == g["end"] for p in hit):
                    exact[g["type"]] += 1
            else:
                fn[g["type"]] += 1
                other = [p["type"] for p in preds if _overlap(p, g)]
                misses.append((d["id"], g["type"], g["text"], other))
        for p in preds:
            if p["type"] not in labeled:
                # e.g. PHONE / EMAIL: real PII the dataset does not label
                if not any(_overlap(p, g) for g in d["gold"]):
                    unlabeled[p["type"]] += 1
                    continue
            if not any(g["type"] == p["type"] and _overlap(p, g) for g in d["gold"]):
                fp[p["type"]] += 1
                false_pos.append((d["id"], p["type"], p["text"]))
    rows = {}
    for t in [t for t in ENTITY_TYPES if t in labeled]:
        P = tp[t] / (tp[t] + fp[t]) if tp[t] + fp[t] else 1.0
        R = tp[t] / (tp[t] + fn[t]) if tp[t] + fn[t] else 1.0
        F = 2 * P * R / (P + R) if P + R else 0.0
        rows[t] = {"gold": tp[t] + fn[t], "tp": tp[t], "fp": fp[t], "fn": fn[t],
                   "precision": P, "recall": R, "f1": F, "exact_span": exact[t]}
    T = {k: sum(r[k] for r in rows.values()) for k in ("gold", "tp", "fp", "fn", "exact_span")}
    P = T["tp"] / (T["tp"] + T["fp"]) if T["tp"] + T["fp"] else 1.0
    R = T["tp"] / (T["tp"] + T["fn"]) if T["tp"] + T["fn"] else 1.0
    T.update(precision=P, recall=R, f1=2 * P * R / (P + R) if P + R else 0.0)
    return rows, T, dict(unlabeled), misses, false_pos


def check_reinsertion(mode, result):
    mp = result.reinsertion
    mapping_keys = list(dict.fromkeys(
        [_canonical(m) for m in PLACEHOLDER_RE.finditer(result.sanitized_text)]))
    expected = list(mapping_keys)
    ok_extra = True
    if mode == "drop" and expected:
        # MockBackend("drop") removes the placeholder of the LAST occurrence in the text
        last = [_canonical(m) for m in PLACEHOLDER_RE.finditer(result.sanitized_text)][-1]
        expected = [p for p in expected if p != last]
        ok_extra = mp.dropped == [last]
    if mode == "fake":
        ok_extra = mp.unknown == ["<PERSON_9>"]
    permitted = {
        p for p in mapping_keys
        if policy_for(DEFAULT_PURPOSE, p[1:-1].rsplit("_", 1)[0]).restore
    }
    expected_restore = permitted.intersection(expected)
    remaining = {
        _canonical(m) for m in PLACEHOLDER_RE.finditer(result.final_text)
        if _canonical(m) in mapping_keys
    }
    doc_ok = (
        expected_restore.issubset(mp.restored)
        and not expected_restore.intersection(remaining)
        and (set(expected) - permitted).issubset(remaining)
        and ok_extra
    )
    return len(expected_restore.intersection(mp.restored)), len(expected_restore), doc_ok


def pct(x):
    return f"{100 * x:.1f}%"


# ---------------------------------------------------------------- main
def main(path=None):
    path, docs, labeled = load_dataset(path)
    print(f"Dataset: {os.path.relpath(path, ROOT)} ({len(docs)} docs)")

    process(docs[0]["text"], MockBackend("echo"))  # warm-up: load models before timing

    preds_by_doc, leaks, blocked, gw_ms = {}, [], 0, []
    t_all = time.perf_counter()
    echo_results = {}
    for d in docs:
        r = process(d["text"], MockBackend("echo"))
        echo_results[d["id"]] = r
        preds_by_doc[d["id"]] = [{"type": e.type, "start": e.start, "end": e.end, "text": e.text}
                                 for e in r.entities]
        gw_ms.append(r.gateway_ms)
        blocked += r.blocked
        gold_values = {f"{g['type']}#{i}": g["text"] for i, g in enumerate(d["gold"])}
        for key in find_leaks(r.outbound_payload, gold_values):
            leaks.append((d["id"], key.split("#")[0]))
    wall = time.perf_counter() - t_all

    rows, total, unlabeled, misses, false_pos = score_detection(docs, preds_by_doc, labeled)

    reins = {}
    for mode in MockBackend.MODES:
        ph_ok = ph_total = doc_ok = 0
        for d in docs:
            r = echo_results[d["id"]] if mode == "echo" else process(d["text"], MockBackend(mode))
            a, b, ok = check_reinsertion(mode, r)
            ph_ok += a
            ph_total += b
            doc_ok += ok
        reins[mode] = {"placeholders_restored": ph_ok, "placeholders_expected": ph_total,
                       "placeholder_accuracy": ph_ok / ph_total if ph_total else 1.0,
                       "docs_correct": doc_ok, "docs": len(docs)}

    q = statistics.quantiles(gw_ms, n=20)
    latency = {"mean_ms": statistics.mean(gw_ms), "p50_ms": statistics.median(gw_ms),
               "p95_ms": q[18], "max_ms": max(gw_ms), "docs_per_s": len(docs) / wall}

    leak_by_type = Counter(t for _, t in leaks)
    metrics = {"dataset": os.path.relpath(path, ROOT), "docs": len(docs),
               "gold_entities": total["gold"], "leaks": len(leaks),
               "leaks_by_type": dict(leak_by_type), "blocked": blocked,
               "detection": rows, "detection_total": total, "unlabeled_detections": unlabeled,
               "reinsertion": reins, "latency": latency,
               "misses": misses, "false_positives": false_pos}
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    json.dump(metrics, open(os.path.join(ROOT, "reports", "metrics.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    write_report(metrics)
    print(f"Leaks: {len(leaks)} | recall {pct(total['recall'])} | precision {pct(total['precision'])} "
          f"| gateway p50 {latency['p50_ms']:.0f} ms")
    return metrics


def write_report(m):
    L = []
    w = L.append
    w("# PS-02 Privacy Gateway: Metrics Report\n")
    w(f"Dataset: `{m['dataset']}`. {m['docs']} documents, {m['gold_entities']} labeled PII values. "
      "Backend: offline MockBackend (no network). Generated by `python scripts/evaluate.py`.\n")
    w("## Headline\n")
    w("| Metric | Result |\n|---|---|")
    w(f"| **Leakage**: labeled values found in what was sent to the LLM | **{m['leaks']}** of {m['gold_entities']} |")
    w(f"| Requests blocked by the leak guard | {m['blocked']} |")
    t = m["detection_total"]
    w(f"| Detection recall (all types) | {pct(t['recall'])} |")
    w(f"| Detection precision (all types) | {pct(t['precision'])} |")
    w(f"| Detection F1 | {pct(t['f1'])} |")
    w(f"| Purpose-policy reinsertion (echo) | {m['reinsertion']['echo']['docs_correct']} / {m['docs']} docs |")
    lat = m["latency"]
    w(f"| Gateway overhead per document (p50 / p95) | {lat['p50_ms']:.0f} ms / {lat['p95_ms']:.0f} ms |\n")
    if m["leaks_by_type"]:
        w(f"Leaks by type: {m['leaks_by_type']}\n")

    w("## Detection by entity type\n")
    w("A detection counts if it has the right type and overlaps the labeled span. "
      "*Exact* is how many also match the labeled boundaries character for character.\n")
    w("| Type | Labeled | Found | Missed | False pos. | Precision | Recall | F1 | Exact span |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k, r in m["detection"].items():
        w(f"| {k} | {r['gold']} | {r['tp']} | {r['fn']} | {r['fp']} | {pct(r['precision'])} | "
          f"{pct(r['recall'])} | {pct(r['f1'])} | {r['exact_span']} |")
    w(f"| **All** | {t['gold']} | {t['tp']} | {t['fn']} | {t['fp']} | {pct(t['precision'])} | "
      f"{pct(t['recall'])} | {pct(t['f1'])} | {t['exact_span']} |\n")
    if m["unlabeled_detections"]:
        w("Also masked, but not labeled in this dataset (so not scored): "
          + ", ".join(f"{k} × {v}" for k, v in m["unlabeled_detections"].items()) + ".\n")

    w("## Reinsertion accuracy by Mock mode\n")
    w("| Mode | What the fake LLM does | Placeholders restored | Docs fully correct |")
    w("|---|---|---:|---:|")
    what = {"echo": "returns text unchanged (must round-trip exactly)",
            "paraphrase": "rewrites placeholders as PERSON_1, [PAN_1], <Person 1>, {X_1}",
            "reorder": "reverses sentence order",
            "drop": "deletes one placeholder (must be reported as dropped)",
            "fake": "invents <PERSON_9> (must be flagged, never filled)"}
    for mode, r in m["reinsertion"].items():
        w(f"| {mode} | {what[mode]} | {r['placeholders_restored']} / {r['placeholders_expected']} "
          f"({pct(r['placeholder_accuracy'])}) | {r['docs_correct']} / {r['docs']} |")
    w("")
    w("## Latency\n")
    w(f"Gateway time = detect + mask + leak guard + reinsert, excluding the LLM call. "
      f"Mean {lat['mean_ms']:.0f} ms, median {lat['p50_ms']:.0f} ms, p95 {lat['p95_ms']:.0f} ms, "
      f"max {lat['max_ms']:.0f} ms on a laptop CPU, after a one-time model load.\n")

    if m["misses"]:
        w("## Missed values\n")
        w("| Doc | Type | Value | Overlapping detection |\n|---|---|---|---|")
        for doc, ty, val, other in m["misses"][:40]:
            w(f"| {doc} | {ty} | `{val}` | {', '.join(other) or 'none'} |")
        w("")
    if m["false_positives"]:
        w("## False positives\n")
        w("| Doc | Type | Text |\n|---|---|---|")
        for doc, ty, val in m["false_positives"][:40]:
            w(f"| {doc} | {ty} | `{val}` |")
        w("")
    w("All values in this report come from M3's synthetic dataset. None belong to real people.")
    open(os.path.join(ROOT, "metrics_report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
