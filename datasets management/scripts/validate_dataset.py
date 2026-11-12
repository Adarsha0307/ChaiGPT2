"""Validate the synthetic Indian PII dataset and generate a validation report."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

REQUIRED_CATEGORIES = (
    "Loan Application",
    "KYC Form",
    "Customer Support Ticket",
    "Insurance Claim",
)

REQUIRED_ENTITY_TYPES = (
    "PERSON",
    "ADDRESS",
    "AADHAAR",
    "PAN",
    "GSTIN",
    "VOTER_ID",
    "PASSPORT",
)

REQUIRED_SCENARIOS = (
    "english",
    "hinglish",
    "multiple_people",
    "repeated_names",
    "multiple_pii_entities",
    "similar_looking_names",
    "negative_no_pii",
)

EXPECTED_DOCUMENT_COUNT = 50

# Verhoeff tables for 12-digit Aadhaar checksum calculation and verification.
VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)

VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)

VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)

GSTIN_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

VALID_GSTIN_STATE_CODES = {f"{code:02d}" for code in range(1, 39)} | {"97", "99"}

PAN_PATTERN = re.compile(r"^[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]$")
VOTER_ID_PATTERN = re.compile(r"^[A-Z]{3}[0-9]{7}$")
PASSPORT_PATTERN = re.compile(r"^[A-PR-WY][1-9][0-9]{5}[1-9]$")
AADHAAR_DISPLAY_PATTERN = re.compile(r"^[2-9][0-9]{3}(?:[ -]?[0-9]{4}){2}$")
GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)


def compute_verhoeff_check_digit(eleven_digits: str) -> str:
    """Compute the Verhoeff check digit for an 11-digit Aadhaar prefix."""
    if len(eleven_digits) != 11 or not eleven_digits.isdigit():
        raise ValueError("Aadhaar prefix must be exactly 11 digits.")
    c = 0
    for idx, ch in enumerate(reversed(eleven_digits)):
        c = VERHOEFF_D[c][VERHOEFF_P[(idx + 1) % 8][int(ch)]]
    return str(VERHOEFF_INV[c])


def verify_verhoeff(digits: str) -> bool:
    """Return True if the numeric string passes the Verhoeff checksum."""
    if not digits or not digits.isdigit():
        return False
    c = 0
    for idx, ch in enumerate(reversed(digits)):
        c = VERHOEFF_D[c][VERHOEFF_P[idx % 8][int(ch)]]
    return c == 0


def is_valid_aadhaar(value: str) -> tuple[bool, str]:
    """Validate Indian Aadhaar display format and 12-digit Verhoeff checksum."""
    if not AADHAAR_DISPLAY_PATTERN.match(value):
        return False, "Does not match Aadhaar 12-digit format starting with 2-9."
    normalized = value.replace(" ", "").replace("-", "")
    if len(normalized) != 12 or not verify_verhoeff(normalized):
        return False, "Failed Verhoeff checksum."
    return True, "Valid Aadhaar (format and Verhoeff checksum)."


def compute_gstin_check_char(fourteen_chars: str) -> str:
    """Compute the 15th Mod-36 checksum character for a 14-character GSTIN prefix."""
    if len(fourteen_chars) != 14:
        raise ValueError("GSTIN prefix must be exactly 14 characters.")
    total = 0
    for idx, ch in enumerate(fourteen_chars):
        code_point = GSTIN_ALPHABET.index(ch)
        factor = 1 if idx % 2 == 0 else 2
        product = code_point * factor
        total += (product // 36) + (product % 36)
    check_code_point = (36 - (total % 36)) % 36
    return GSTIN_ALPHABET[check_code_point]


def is_valid_gstin(value: str) -> tuple[bool, str]:
    """Validate Indian GSTIN structure, state code, embedded PAN, and Mod-36 checksum."""
    if not GSTIN_PATTERN.match(value):
        return False, "Does not match 15-character GSTIN structure."
    state_code = value[:2]
    if state_code not in VALID_GSTIN_STATE_CODES:
        return False, f"Invalid GSTIN state code: {state_code}."
    embedded_pan = value[2:12]
    if not PAN_PATTERN.match(embedded_pan):
        return False, f"Invalid embedded PAN inside GSTIN: {embedded_pan}."
    expected_check = compute_gstin_check_char(value[:14])
    if value[14] != expected_check:
        return False, f"Invalid GSTIN checksum: expected {expected_check}, got {value[14]}."
    return True, "Valid GSTIN (structure, embedded PAN, and Mod-36 checksum)."


def is_valid_pan(value: str) -> tuple[bool, str]:
    """Validate Indian PAN structural format."""
    if not PAN_PATTERN.match(value):
        return False, "Does not match PAN format ^[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]$."
    return True, "Valid PAN format."


def is_valid_voter_id(value: str) -> tuple[bool, str]:
    """Validate Indian Voter ID (EPIC) structural format."""
    if not VOTER_ID_PATTERN.match(value):
        return False, "Does not match Voter ID format ^[A-Z]{3}[0-9]{7}$."
    return True, "Valid Voter ID format."


def is_valid_passport(value: str) -> tuple[bool, str]:
    """Validate Indian Passport structural format."""
    if not PASSPORT_PATTERN.match(value):
        return False, "Does not match Indian Passport format ^[A-PR-WY][1-9][0-9]{5}[1-9]$."
    return True, "Valid Passport format."


IDENTIFIER_VALIDATORS = {
    "AADHAAR": is_valid_aadhaar,
    "GSTIN": is_valid_gstin,
    "PAN": is_valid_pan,
    "VOTER_ID": is_valid_voter_id,
    "PASSPORT": is_valid_passport,
}


def _has_similar_names(person_values: list[str]) -> bool:
    """Return True if at least two distinct person names are visually/lexically similar."""
    unique_names = sorted(set(person_values))
    for i in range(len(unique_names)):
        for j in range(i + 1, len(unique_names)):
            name_a = unique_names[i]
            name_b = unique_names[j]
            parts_a = name_a.lower().split()
            parts_b = name_b.lower().split()
            if parts_a and parts_b and (parts_a[0] == parts_b[0] or parts_a[-1] == parts_b[-1]):
                return True
            if SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio() >= 0.72:
                return True
    return False


def validate_dataset(dataset_path: Path) -> dict[str, Any]:
    """Run all structural, annotation, scenario, and identifier checks on the dataset."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    with dataset_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise ValueError("Dataset JSON must contain a top-level 'documents' list.")

    errors: list[str] = []
    category_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()
    scenario_counts: Counter[str] = Counter()

    identifier_stats: dict[str, dict[str, int]] = {
        entity_type: {"total": 0, "valid": 0, "invalid": 0}
        for entity_type in IDENTIFIER_VALIDATORS
    }

    seen_doc_ids: set[str] = set()
    total_annotations = 0
    exact_span_matches = 0
    non_overlapping_docs = 0

    for doc_idx, doc in enumerate(documents):
        doc_id = doc.get("id", f"<missing-id-{doc_idx}>")
        if doc_id in seen_doc_ids:
            errors.append(f"{doc_id}: duplicate document id.")
        seen_doc_ids.add(doc_id)

        category = doc.get("category")
        if category not in REQUIRED_CATEGORIES:
            errors.append(f"{doc_id}: unknown or missing category '{category}'.")
        else:
            category_counts[category] += 1

        language = doc.get("language")
        if language not in {"en", "hinglish"}:
            errors.append(f"{doc_id}: unexpected language '{language}'.")
        else:
            language_counts[language] += 1

        text = doc.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{doc_id}: 'text' must be a non-empty string.")
            continue

        annotations = doc.get("annotations")
        if not isinstance(annotations, list):
            errors.append(f"{doc_id}: 'annotations' must be a list.")
            continue

        scenarios = doc.get("scenarios", [])
        if not isinstance(scenarios, list):
            errors.append(f"{doc_id}: 'scenarios' must be a list.")
            scenarios = []
        for scenario in scenarios:
            scenario_counts[scenario] += 1

        spans: list[tuple[int, int, str]] = []
        person_values: list[str] = []
        doc_entity_types: set[str] = set()

        for ann_idx, ann in enumerate(annotations):
            total_annotations += 1
            entity_type = ann.get("entity_type")
            value = ann.get("value")
            start = ann.get("start")
            end = ann.get("end")

            if entity_type not in REQUIRED_ENTITY_TYPES:
                errors.append(f"{doc_id} annotation[{ann_idx}]: invalid entity_type '{entity_type}'.")
                continue

            if not isinstance(value, str) or not value:
                errors.append(f"{doc_id} annotation[{ann_idx}]: 'value' must be a non-empty string.")
                continue

            if value != value.strip():
                errors.append(
                    f"{doc_id} annotation[{ann_idx}]: value has leading/trailing whitespace: '{value}'."
                )

            if not isinstance(start, int) or not isinstance(end, int):
                errors.append(f"{doc_id} annotation[{ann_idx}]: start/end offsets must be integers.")
                continue

            if not (0 <= start < end <= len(text)):
                errors.append(
                    f"{doc_id} annotation[{ann_idx}]: invalid offset range [{start}, {end}) for text length {len(text)}."
                )
                continue

            extracted = text[start:end]
            if extracted != value:
                errors.append(
                    f"{doc_id} annotation[{ann_idx}]: span mismatch for {entity_type} at [{start}, {end}): "
                    f"expected '{value}', got '{extracted}'."
                )
            else:
                exact_span_matches += 1

            entity_counts[entity_type] += 1
            doc_entity_types.add(entity_type)
            spans.append((start, end, entity_type))

            if entity_type == "PERSON":
                person_values.append(value)

            validator = IDENTIFIER_VALIDATORS.get(entity_type)
            if validator is not None:
                identifier_stats[entity_type]["total"] += 1
                ok, reason = validator(value)
                if ok:
                    identifier_stats[entity_type]["valid"] += 1
                else:
                    identifier_stats[entity_type]["invalid"] += 1
                    errors.append(f"{doc_id} annotation[{ann_idx}] ({entity_type}='{value}'): {reason}")

        # Verify no overlapping spans within this document.
        spans.sort(key=lambda item: (item[0], item[1]))
        has_overlap = False
        for prev, curr in zip(spans, spans[1:]):
            if curr[0] < prev[1]:
                has_overlap = True
                errors.append(
                    f"{doc_id}: overlapping spans {prev} and {curr}."
                )
        if not has_overlap:
            non_overlapping_docs += 1

        # Verify scenario assertions against actual document contents.
        if "negative_no_pii" in scenarios and len(annotations) != 0:
            errors.append(f"{doc_id}: tagged 'negative_no_pii' but has {len(annotations)} annotations.")
        if "negative_no_pii" not in scenarios and len(annotations) == 0:
            errors.append(f"{doc_id}: has 0 annotations but is not tagged 'negative_no_pii'.")
        if "multiple_people" in scenarios and len(set(person_values)) < 2:
            errors.append(f"{doc_id}: tagged 'multiple_people' but has < 2 distinct PERSON entities.")
        if "repeated_names" in scenarios:
            name_freq = Counter(person_values)
            if not any(count >= 2 for count in name_freq.values()):
                errors.append(f"{doc_id}: tagged 'repeated_names' but no PERSON repeats >= 2 times.")
        if "multiple_pii_entities" in scenarios and (len(annotations) < 3 or len(doc_entity_types) < 2):
            errors.append(
                f"{doc_id}: tagged 'multiple_pii_entities' but lacks >= 3 annotations across >= 2 types."
            )
        if "similar_looking_names" in scenarios and not _has_similar_names(person_values):
            errors.append(
                f"{doc_id}: tagged 'similar_looking_names' but PERSON names are not similar: {person_values}."
            )

    if len(documents) != EXPECTED_DOCUMENT_COUNT:
        errors.append(f"Expected {EXPECTED_DOCUMENT_COUNT} documents, found {len(documents)}.")

    for category in REQUIRED_CATEGORIES:
        if category_counts[category] == 0:
            errors.append(f"Missing required category: {category}.")

    for entity_type in REQUIRED_ENTITY_TYPES:
        if entity_counts[entity_type] == 0:
            errors.append(f"Missing required entity type: {entity_type}.")

    for scenario in REQUIRED_SCENARIOS:
        if scenario_counts[scenario] == 0:
            errors.append(f"Missing required tricky scenario: {scenario}.")

    checks = {
        "exact_document_count": len(documents) == EXPECTED_DOCUMENT_COUNT,
        "all_categories_represented": all(category_counts[c] > 0 for c in REQUIRED_CATEGORIES),
        "all_entity_types_represented": all(entity_counts[e] > 0 for e in REQUIRED_ENTITY_TYPES),
        "all_offsets_and_spans_exact": (
            exact_span_matches == total_annotations and non_overlapping_docs == len(documents)
        ),
        "all_tricky_scenarios_represented": all(scenario_counts[s] > 0 for s in REQUIRED_SCENARIOS),
        "all_identifiers_valid": all(
            stats["invalid"] == 0 and stats["total"] > 0 for stats in identifier_stats.values()
        ),
    }

    passed = len(errors) == 0 and all(checks.values())

    return {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "status": "PASSED" if passed else "FAILED",
        "checks": checks,
        "summary": {
            "total_documents": len(documents),
            "total_annotations": total_annotations,
            "exact_span_matches": exact_span_matches,
            "non_overlapping_documents": non_overlapping_docs,
            "category_counts": {c: category_counts[c] for c in REQUIRED_CATEGORIES},
            "language_counts": dict(sorted(language_counts.items())),
            "entity_type_counts": {e: entity_counts[e] for e in REQUIRED_ENTITY_TYPES},
            "scenario_counts": {s: scenario_counts[s] for s in REQUIRED_SCENARIOS},
            "identifier_validation": identifier_stats,
        },
        "error_count": len(errors),
        "errors": errors,
    }


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    dataset_path = project_root / "data" / "synthetic_documents.json"
    report_path = project_root / "reports" / "dataset_validation_report.json"

    report = validate_dataset(dataset_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Validation status: {report['status']}")
    print(f"Documents: {report['summary']['total_documents']}")
    print(f"Annotations: {report['summary']['total_annotations']}")
    print(f"Categories: {report['summary']['category_counts']}")
    print(f"Entities: {report['summary']['entity_type_counts']}")
    print(f"Scenarios: {report['summary']['scenario_counts']}")
    print(f"Identifiers: {report['summary']['identifier_validation']}")
    print(f"Report written to: {report_path}")

    if report["errors"]:
        print(f"Errors ({report['error_count']}):", file=sys.stderr)
        for err in report["errors"]:
            print(f"  - {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

