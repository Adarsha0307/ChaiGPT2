# Live Gemini run

Model: `gemini-3.5-flash`. 5 documents from M3's dataset. Only the sanitized prompt was sent; leak check and restoration were checked for each.

| Doc | Category | Result | Restored | Dropped by LLM | Invented by LLM | Gateway ms | LLM s |
|---|---|---|---:|---|---|---:|---:|
| DOC-001 | KYC Form | OK | 6/6 | none | none | 15536 | 6.5 |
| DOC-002 | Loan Application | OK | 7/7 | none | none | 628 | 5.5 |
| DOC-005 | Customer Support Ticket | OK | 5/5 | none | none | 481 | 5.2 |
| DOC-007 | Insurance Claim | OK | 9/9 | none | none | 787 | 5.8 |
| DOC-006 | Customer Support Ticket | OK | 6/6 | none | none | 395 | 298.1 |

*Dropped* placeholders are ones a summary legitimately leaves out; they are reported, never guessed. Errors: 0.
