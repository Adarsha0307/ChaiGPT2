# Synthetic Indian PII Dataset Generator

A standalone, deterministic synthetic dataset generator and validator producing **50 fictional Indian financial, KYC, support, and insurance documents** with exact character-level ground-truth PII annotations for DPDP hackathon evaluation.

All identities, names, addresses, and identifier numbers in this repository are completely synthetic and generated programmatically.

## Project Structure

```text
D:\datasets management\
├── data/
│   └── synthetic_documents.json
├── reports/
│   └── dataset_validation_report.json
├── scripts/
│   ├── generate_dataset.py
│   └── validate_dataset.py
├── README.md
└── requirements.txt
```

## Dataset Overview

- **Total Documents:** 50 (`DOC-001` through `DOC-050`)
- **Total Ground-Truth Annotations:** 328
- **Document Categories:**
  - `Loan Application` (13)
  - `KYC Form` (13)
  - `Customer Support Ticket` (12)
  - `Insurance Claim` (12)
- **PII Entity Types:**
  - `PERSON` (95)
  - `ADDRESS` (51)
  - `AADHAAR` (52)
  - `PAN` (57)
  - `GSTIN` (22)
  - `VOTER_ID` (29)
  - `PASSPORT` (22)
- **Challenging Scenarios Covered:**
  - `english` (36 documents)
  - `hinglish` (14 documents)
  - `multiple_people` (28 documents)
  - `repeated_names` (15 documents)
  - `multiple_pii_entities` (44 documents)
  - `similar_looking_names` (12 documents)
  - `negative_no_pii` (6 documents with `annotations: []`)

## Ground-Truth Annotation Format

Each document in `data/synthetic_documents.json` follows this schema:

```json
{
  "id": "DOC-001",
  "category": "KYC Form",
  "language": "en",
  "scenarios": ["english", "multiple_pii_entities"],
  "text": "...",
  "annotations": [
    {
      "entity_type": "PERSON",
      "value": "Diya Krishnan",
      "start": 108,
      "end": 121
    }
  ]
}
```

Every annotation guarantees `doc["text"][ann["start"]:ann["end"]] == ann["value"]` with zero overlapping spans.

## Identifier Validation Rules

`scripts/validate_dataset.py` enforces:

- **Aadhaar (`AADHAAR`):** 12-digit format starting with `2-9` (plain, spaced, or hyphenated) and valid **Verhoeff checksum**.
- **GSTIN (`GSTIN`):** 15-character format with valid Indian state code, embedded valid PAN, `Z` at position 14, and valid **Mod-36 checksum**.
- **PAN (`PAN`):** Structural validation `^[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]$`.
- **Voter ID (`VOTER_ID`):** Structural validation `^[A-Z]{3}[0-9]{7}$`.
- **Passport (`PASSPORT`):** Structural validation `^[A-PR-WY][1-9][0-9]{5}[1-9]$`.

## Usage

Requires Python 3.10+ (standard library only; no external dependencies needed).

1. **Generate the dataset:**
   ```powershell
   python scripts/generate_dataset.py
   ```

2. **Validate the dataset and produce the report:**
   ```powershell
   python scripts/validate_dataset.py
   ```
   Validation results are saved to `reports/dataset_validation_report.json`.

