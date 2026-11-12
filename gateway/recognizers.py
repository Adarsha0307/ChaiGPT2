"""Presidio analyzer for Indian IDs, phone and email (tasks 5 and 6).

Only the recognizers we need are registered, so Presidio's other defaults
(credit cards, IP addresses, dates, US IDs...) cannot add false positives.
"""
from __future__ import annotations

from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.context_aware_enhancers import LemmaContextAwareEnhancer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    EmailRecognizer,
    InAadhaarRecognizer,
    InGstinRecognizer,
    InPanRecognizer,
    InPassportRecognizer,
    InVoterRecognizer,
    PhoneRecognizer,
)

SPACY_MODEL = "en_core_web_lg"

# Presidio entity name -> gateway entity type
TYPE_MAP = {
    "IN_AADHAAR": "AADHAAR",
    "IN_PAN": "PAN",
    "IN_GSTIN": "GSTIN",
    "IN_VOTER": "VOTER_ID",
    "IN_PASSPORT": "PASSPORT",
    "PHONE_NUMBER": "PHONE",
    "EMAIL_ADDRESS": "EMAIL",
}

# A hit must reach this score. Strong patterns (checksummed Aadhaar, GSTIN,
# a PAN with a valid holder-type letter, email) pass on their own; weak ones
# (passport, generic PAN shape) need a context word nearby to get boosted.
SCORE_THRESHOLD = 0.4

# Context words, English + common Hinglish spellings. Lowercase.
CONTEXT = {
    "AADHAAR": ["aadhaar", "aadhar", "adhaar", "adhar", "uid", "uidai"],
    "PAN": ["pan", "permanent account number"],
    "GSTIN": ["gstin", "gst", "goods and services tax", "gst number", "gst registration"],
    "VOTER_ID": ["voter", "epic", "election", "elector photo identity card", "matdata"],
    "PASSPORT": ["passport", "indian passport", "passport number"],
    "PHONE": ["phone", "mobile", "mob", "contact", "call", "whatsapp", "ph", "tel", "number"],
    "EMAIL": ["email", "e-mail", "mail"],
}

# Presidio's lowest-confidence PAN pattern matches almost any 10-character
# word that has 4 digits in it, so keep only the two real PAN shapes.
PAN_PATTERNS = [
    Pattern("PAN (High)", r"\b([A-Za-z]{3}[AaBbCcFfGgHhJjLlPpTt][A-Za-z][0-9]{4}[A-Za-z])\b", 0.5),
    Pattern("PAN (Medium)", r"\b([A-Za-z]{5}[0-9]{4}[A-Za-z])\b", 0.1),
]


# Presidio drops a 12-digit number whose Verhoeff checksum fails. A mistyped
# or made-up Aadhaar next to the word "Aadhaar" is still personal data, so
# this backup only fires with a context word: 0.05 base + 0.35 boost = 0.40.
AADHAAR_CONTEXT_ONLY = PatternRecognizer(
    supported_entity="IN_AADHAAR",
    name="AadhaarContextRecognizer",
    patterns=[Pattern("AADHAAR (context only)", r"\b[2-9][0-9]{3}[ -]?[0-9]{4}[ -]?[0-9]{4}\b", 0.05)],
    context=CONTEXT["AADHAAR"],
)


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    nlp_engine = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
    }).create_engine()

    registry = RecognizerRegistry(supported_languages=["en"])
    for rec in (
        InAadhaarRecognizer(context=CONTEXT["AADHAAR"]),
        AADHAAR_CONTEXT_ONLY,
        InPanRecognizer(patterns=PAN_PATTERNS, context=CONTEXT["PAN"]),
        InGstinRecognizer(context=CONTEXT["GSTIN"]),
        InVoterRecognizer(context=CONTEXT["VOTER_ID"]),
        InPassportRecognizer(context=CONTEXT["PASSPORT"]),
        PhoneRecognizer(supported_regions=("IN",), context=CONTEXT["PHONE"]),
        EmailRecognizer(context=CONTEXT["EMAIL"]),
    ):
        registry.add_recognizer(rec)

    return AnalyzerEngine(
        registry=registry,
        nlp_engine=nlp_engine,
        supported_languages=["en"],
        context_aware_enhancer=LemmaContextAwareEnhancer(
            context_similarity_factor=0.35, min_score_with_context_similarity=0.4,
            context_prefix_count=6, context_suffix_count=2,
        ),
    )


def registered_entities() -> list[str]:
    """Presidio entity names in the registry (task 5's done-check)."""
    return sorted(get_analyzer().get_supported_entities(language="en"))
