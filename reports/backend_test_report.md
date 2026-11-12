# Backend Test Report

## Scope and method

- Ran the complete offline pytest suite.
- Evaluated the backend against the repository's 50-document synthetic dataset (328 labeled PII spans), in memory. No metrics or existing reports were rewritten.
- Ran the separate 18-case hard-input stress checks and direct API/backend parameter-boundary checks.
- Did not make a live Gemini API call. Gemini retry and configuration behavior were checked using mocks.
- The excluded `metrics_report.md` was not read or modified.

## Results

| Check | Result |
|---|---:|
| Pytest suite | **115 passed**, 0 failed |
| Synthetic dataset | 50 documents, 328 labeled spans |
| Detection precision / recall / F1 | **100% / 100% / 100%** |
| Exact detection spans | **328 / 328** |
| Labeled values found in outbound payloads | **0** |
| Leak-guard blocks on that dataset | 0 |
| Echo / paraphrase / reorder round-trip | **50 / 50 documents each** |
| Drop / fake mock-mode handling | **50 / 50 documents each** |
| Gateway latency on echo evaluation | mean 481 ms; p50 477 ms; max 791 ms |

The dataset evaluator ran each document through echo and checked all five
mock modes. For `drop`, intentionally dropped placeholders were correctly
reported as dropped; for `fake`, invented placeholders were kept unfilled and
flagged.

## Parameter coverage

The direct checks passed for:

- Process request text lengths at 1 and 50,000 characters; rejected empty text
  and 50,001 characters.
- Task lengths at 0 and 2,000 characters; rejected 2,001 characters.
- Both backend choices (`mock`, `gemini`) and all mock modes (`echo`,
  `paraphrase`, `reorder`, `drop`, `fake`); rejected invalid values.
- Audit limit clamping to 1–500.
- Gemini constructor model, explicit key forwarding, `max_attempts`, and
  `base_delay` without making a network request.
- Existing tests also exercise retry delays, retryable 429/503 errors,
  exhausted attempts, non-retryable errors, API responses, audit outcomes,
  failure handling, and privacy of stored audit data.

## Hard-input stress findings

The 18 hand-written stress cases resulted in 13 PASS, 4 LEAK, and 1
OVER-MASKED. Of the 22 expected in-scope values, 19 were protected and 3
were missed:

- First-name-only repeat: `Sunita` (PERSON).
- Aadhaar written as spaced digit pairs: `49 91 18 66 52 46`.
- Passport number without a keyword: `K8765432`.

The remaining LEAK verdict includes three out-of-scope values (bank account,
IFSC, and date of birth), which are not among the gateway's nine supported
entity types. Two branch/place names (`Rajiv Chowk`, `Indira Nagar`) were
over-masked as addresses. No hard-input requests were blocked by the leak
guard.

This contrast with the synthetic dataset's perfect score shows the detector
is sensitive to phrasing and formatting: dataset results should not be treated
as broad real-world guarantees.

## Warnings and limitations

- Pytest emitted two dependency warnings: a PyTorch TorchScript compatibility
  future warning and a Hugging Face `resume_download` deprecation warning.
- The real Gemini service, credentials, network behavior, and live API
  response were not tested. Retry and constructor tests were offline mocks.
- No source code was changed as part of this test run.
