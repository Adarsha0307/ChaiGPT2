# Purpose-aware masking

`POST /process` accepts a validated `purpose`, separate from the free-form
`task`. The default is `support_summary`. The task prompt does not select or
modify the policy.

| Purpose | PERSON | ADDRESS | AADHAAR | PAN | GSTIN | VOTER_ID | PASSPORT | PHONE | EMAIL | Restore |
|---|---|---|---|---|---|---|---|---|---|---|
| `support_summary` | Placeholder | Placeholder | Placeholder | Placeholder | Placeholder | Placeholder | Placeholder | Placeholder | Placeholder | PERSON only |
| `eligibility_review` | Placeholder | Placeholder | Placeholder | Placeholder | Placeholder | Placeholder | Placeholder | Placeholder | Placeholder | None |
| `document_classification` | Redact | Redact | Redact | Redact | Redact | Redact | Redact | Redact | Redact | None |

Placeholders retain only the type and request-local occurrence identity; no
original value is sent to the model. Redactions use a type label such as
`[REDACTED_PAN]`. The current detector cannot reliably derive generalized
values such as age bands or city-only addresses, so no policy claims to
generalize them.

The leak guard scans the complete prompt passed to the backend, including the
task text, against every detected original value. A leak blocks the backend
call. Placeholder-to-original mappings exist only during that request and
are not part of `ProcessResult` or audit records. Reinsertion recognizes
non-restorable placeholders but leaves them unchanged.

Detection coverage is limited to the configured Presidio/GLiNER recognizers
and fallback patterns. Undetected PII cannot be masked by a purpose policy;
detector limitations and measured misses are documented by the project test
reports.
