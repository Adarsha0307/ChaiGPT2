# Stress test: hard, unseen documents

18 hand-written cases that were **not** used for tuning, built to break the gateway. Backend: offline Mock (echo). A value counts as leaked if it can be found in the exact text sent to the LLM.

## Summary

| Metric | Result |
|---|---|
| In-scope values protected | **19 / 22** (86%) |
| In-scope values leaked | **3** |
| Out-of-scope values sent (bank a/c, IFSC, DOB) | 3 |
| Over-masking (false positives) | 2 |
| Requests blocked by leak guard | 0 |
| Cases: PASS / LEAK / OVER-MASKED / BLOCKED | 13 / 4 / 1 / 0 |

## Protected by type

| Type | Protected | Total |
|---|---:|---:|
| AADHAAR | 1 | 2 |
| ADDRESS | 2 | 2 |
| EMAIL | 1 | 1 |
| GSTIN | 1 | 1 |
| PAN | 2 | 2 |
| PASSPORT | 0 | 1 |
| PERSON | 9 | 10 |
| PHONE | 2 | 2 |
| VOTER_ID | 1 | 1 |

## Every case

| Case | What makes it hard | Verdict | Leaked | Over-masked |
|---|---|---|---|---|
| S01 | All-lowercase Hinglish name and PAN | PASS | none | none |
| S02 | First name alone after the full name | LEAK | PERSON `Sunita` | none |
| S03 | Name written with initials | PASS | none | none |
| S04 | Name in Devanagari script | PASS | none | none |
| S05 | Aadhaar with dashes, keyword 'UID' | PASS | none | none |
| S06 | Aadhaar split into pairs of digits | LEAK | AADHAAR `49 91 18 66 52 46` | none |
| S07 | Phone numbers in unusual formats | PASS | none | none |
| S08 | Email written out in words | PASS | none | none |
| S09 | Address with landmark and no PIN code | PASS | none | none |
| S10 | Address with PIN but no flat or house word | PASS | none | none |
| S11 | Passport number with no keyword | LEAK | PASSPORT `K8765432` | none |
| S12 | Voter ID in lowercase without keyword | PASS | none | none |
| S13 | GSTIN inside a sentence | PASS | none | none |
| S14 | Bank account, IFSC and date of birth (not in our 9 types) | LEAK | BANK_ACCOUNT `123456789012` (out of scope); IFSC `SBIN0001234` (out of scope); DOB `14/08/1990` (out of scope) | none |
| S15 | No personal data at all | PASS | none | none |
| S16 | Decoy: order code shaped like a PAN | PASS | none | none |
| S17 | Decoy: place names that look like person names | OVER-MASKED | none | ADDRESS `Rajiv Chowk`; ADDRESS `Indira Nagar` |
| S18 | Several people with the same surname | PASS | none | none |

All names and numbers here are invented for testing.
