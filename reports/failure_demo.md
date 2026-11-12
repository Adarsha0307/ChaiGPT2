# Failure drill: audit log

Each scenario below ran through the real gateway and wrote one row to `reports/demo_audit.db`. Scenarios marked SIMULATED inject a fault on purpose. Re-create with `python scripts/failure_demo.py`.

## Summary (from GET /audit/summary)

| Status | Requests |
|---|---:|
| ok | 3 |
| flagged | 2 |
| blocked | 1 |
| error | 2 |

Leaks blocked by type: {'PERSON': 1}. Placeholders dropped by the LLM: 1. Placeholders invented by the LLM: 1. LLM errors: {'ConnectionError': 1, 'TimeoutError': 1}.

## Every row

| # | Scenario | Kind | Status | Entities | Leaked types | Dropped | Invented | Error | What it means |
|---:|---|---|---|---|---|---:|---:|---|---|
| 1 | Normal request | real | **ok** | AADHAAR×1, PAN×1, PERSON×2, PHONE×1 | none | 0 | 0 | none | Sent masked, every value restored. |
| 2 | LLM rewrites placeholders | real | **ok** | AADHAAR×1, PAN×1, PERSON×2, PHONE×1 | none | 0 | 0 | none | AI wrote PERSON_1, [PAN_1], <Aadhaar 1>; all restored, so still ok. |
| 3 | LLM drops a placeholder | real | **flagged** | AADHAAR×1, PAN×1, PERSON×2, PHONE×1 | none | 1 | 0 | none | Answer is missing one value; flagged so staff know it was left out. |
| 4 | LLM invents a placeholder | real | **flagged** | AADHAAR×1, PAN×1, PERSON×2, PHONE×1 | none | 0 | 1 | none | AI made up <PERSON_9>; left as is and flagged, never filled with a guess. |
| 5 | Detector misses a repeat in CAPITALS | SIMULATED | **blocked** | PERSON×1 | PERSON | 0 | 0 | none | Leak guard found the raw name in the outgoing text; request blocked, nothing sent. |
| 6 | Gemini unreachable | SIMULATED | **error** | AADHAAR×1, PAN×1, PERSON×2, PHONE×1 | none | 0 | 0 | ConnectionError | Error recorded with its type only; the caller gets a clear failure, not a crash. |
| 7 | Gemini timeout | SIMULATED | **error** | AADHAAR×1, PAN×1, PERSON×2, PHONE×1 | none | 0 | 0 | TimeoutError | Same: recorded as an error row; the masked payload had already passed the guard. |
| 8 | Unseen phrasing: first name alone | real | **ok** | PERSON×1 | none | 0 | 0 | none | Real limitation: 'Sunita' alone was not detected, so the guard could not know it. Status shows ok; the stress test reports this leak. |

The audit database holds no raw values: blocked rows store an empty payload, error rows store only the error's type, and every payload is already masked.
