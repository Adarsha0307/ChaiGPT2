"""Generate 50 synthetic Indian documents with exact ground-truth PII annotations."""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from validate_dataset import (  # noqa: E402
    compute_gstin_check_char,
    compute_verhoeff_check_digit,
    is_valid_aadhaar,
    is_valid_gstin,
    is_valid_pan,
    is_valid_passport,
    is_valid_voter_id,
)

SEED = 20261112

PAN_STATUS_CODES_INDIVIDUAL = "P"
PAN_STATUS_CODES_BUSINESS = ("C", "F", "P")

STATE_CODES = (
    "07",  # Delhi
    "09",  # Uttar Pradesh
    "19",  # West Bengal
    "24",  # Gujarat
    "27",  # Maharashtra
    "29",  # Karnataka
    "33",  # Tamil Nadu
    "36",  # Telangana
)

VOTER_PREFIXES = ("KRN", "MHA", "DLH", "TND", "UPR", "WBG", "GJR", "TLG", "RJS", "KRL")
PASSPORT_PREFIXES = "ABCDEFGHJKLMNPRSTUVWY"

PRIMARY_NAMES = [
    "Aarav Sharma",
    "Diya Krishnan",
    "Vivaan Deshmukh",
    "Ishita Chatterjee",
    "Aditya Kulkarni",
    "Kavya Subramanian",
    "Pranav Joshi",
    "Nandini Reddy",
    "Rohan Verma",
    "Ananya Deshpande",
    "Karan Malhotra",
    "Pooja Nair",
    "Arjun Patel",
    "Sneha Kulkarni",
    "Vikram Singh",
    "Meera Iyer",
    "Deepak Gupta",
    "Rahul Mehta",
    "Siddharth Joshi",
    "Neha Sharma",
    "Harshvardhan Rao",
    "Tanvi Saxena",
    "Nikhil Banerjee",
    "Shruti Agarwal",
    "Manish Tiwari",
    "Ritika Kapoor",
    "Suresh Menon",
    "Gayatri Pillai",
    "Abhishek Pandey",
    "Swati Mishra",
]

SECONDARY_NAMES = [
    "Devika Nair",
    "Raghavendra Rao",
    "Pallavi Kulkarni",
    "Sumit Bhardwaj",
    "Lakshmi Narayanan",
    "Varun Chawla",
    "Sonal Kulkarni",
    "Gaurav Hegde",
    "Nisha Venkatesh",
    "Tarun Bansal",
    "Aparna Sen",
    "Yashwant Thakur",
    "Rekha Choudhary",
    "Mohit Jindal",
    "Bhavana Shetty",
    "Kunal Gokhale",
]

SIMILAR_NAME_PAIRS = [
    ("Rohan Verma", "Rohan Varma"),
    ("Ananya Deshmukh", "Ananya Deshpande"),
    ("Karan Malhotra", "Karan Mehrotra"),
    ("Pooja Nair", "Pooja Nayar"),
    ("Arjun Patel", "Arjun Patil"),
    ("Sneha Kulkarni", "Sneha Kulshreshtha"),
    ("Vikram Singh", "Vikram Sinha"),
    ("Meera Iyer", "Meera Iyengar"),
    ("Deepak Gupta", "Deepak Goel"),
    ("Rahul Mehta", "Rahul Mittal"),
    ("Siddharth Joshi", "Siddharth Joglekar"),
    ("Neha Sharma", "Neha Varma"),
]

CITIES_AND_PINS = [
    ("Indiranagar", "Bengaluru", "Karnataka", "560038"),
    ("Andheri West", "Mumbai", "Maharashtra", "400053"),
    ("Kothrud", "Pune", "Maharashtra", "411038"),
    ("Saket", "New Delhi", "Delhi", "110017"),
    ("Adyar", "Chennai", "Tamil Nadu", "600020"),
    ("Banjara Hills", "Hyderabad", "Telangana", "500034"),
    ("Satellite", "Ahmedabad", "Gujarat", "380015"),
    ("Salt Lake Sector V", "Kolkata", "West Bengal", "700091"),
    ("Gomti Nagar", "Lucknow", "Uttar Pradesh", "226010"),
    ("Vaishali Nagar", "Jaipur", "Rajasthan", "302021"),
    ("Edappally", "Kochi", "Kerala", "682024"),
    ("Shivaji Nagar", "Nagpur", "Maharashtra", "440010"),
]

BUILDING_PREFIXES = [
    "Lotus Residency",
    "Surya Enclave",
    "Ashoka Heights",
    "Kaveri Apartments",
    "Narmada Towers",
    "Vindhya Chambers",
    "Gulmohar Greens",
    "Chinar Plaza",
    "Shanti Niketan",
    "Parijat Arcade",
    "Deccan Court",
    "Neelgiri Bhavan",
]

STREET_NAMES = [
    "MG Link Road",
    "Station Cross Lane",
    "Temple View Marg",
    "Lakefront Avenue",
    "Heritage Market Road",
    "Vidya Mandir Marg",
    "Banyan Grove Street",
    "Parkside Extension",
]

FINTECH_INSTITUTIONS = [
    "NavaBharat FinServe Ltd.",
    "IndusTrust Housing Finance",
    "Suraksha MicroCredit Corp.",
    "ArthSetu Capital Services",
]

INSURERS = [
    "NavaJeevan General Insurance",
    "ArogyaKavach Health & Life",
    "Pragati Shield Assurance",
]

BUSINESS_NAMES = [
    "Kaveri Precision Components Pvt. Ltd.",
    "Deccan Agro Logistics LLP",
    "Narmada Textile Traders",
    "Vindhya MedTech Supplies",
    "Sahyadri Hardware & Tools",
    "Surya Solar Systems",
    "Chinar Packaging Solutions",
    "Parijat Retail Ventures",
]


class DocumentBuilder:
    """Builds document text incrementally while tracking exact character offsets."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._length = 0
        self.annotations: list[dict[str, Any]] = []

    def text(self, s: str) -> "DocumentBuilder":
        self._parts.append(s)
        self._length += len(s)
        return self

    def entity(self, entity_type: str, value: str) -> "DocumentBuilder":
        start = self._length
        self._parts.append(value)
        self._length += len(value)
        end = self._length
        self.annotations.append(
            {
                "entity_type": entity_type,
                "value": value,
                "start": start,
                "end": end,
            }
        )
        return self

    def build(self) -> tuple[str, list[dict[str, Any]]]:
        return "".join(self._parts), self.annotations


class SyntheticIdentityFactory:
    """Generates clearly synthetic yet structurally & checksum-valid Indian PII."""

    def __init__(self, seed: int = SEED) -> None:
        self.rng = random.Random(seed)
        self._used_ids: set[str] = set()

    def _unique(self, generator_fn) -> str:
        for _ in range(100):
            candidate = generator_fn()
            if candidate not in self._used_ids:
                self._used_ids.add(candidate)
                return candidate
        raise RuntimeError("Unable to generate unique synthetic identifier.")

    def aadhaar(self, style: str | None = None) -> str:
        def _make() -> str:
            first_digit = str(self.rng.randint(2, 9))
            body = "".join(str(self.rng.randint(0, 9)) for _ in range(10))
            prefix = first_digit + body
            digits = prefix + compute_verhoeff_check_digit(prefix)
            fmt = style or self.rng.choice(["spaced", "hyphenated", "plain"])
            if fmt == "spaced":
                val = f"{digits[0:4]} {digits[4:8]} {digits[8:12]}"
            elif fmt == "hyphenated":
                val = f"{digits[0:4]}-{digits[4:8]}-{digits[8:12]}"
            else:
                val = digits
            ok, reason = is_valid_aadhaar(val)
            if not ok:
                raise AssertionError(f"Generated invalid Aadhaar {val}: {reason}")
            return val

        return self._unique(_make)

    def pan(self, surname: str = "", status: str = PAN_STATUS_CODES_INDIVIDUAL) -> str:
        def _make() -> str:
            letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            first_three = "".join(self.rng.choice(letters) for _ in range(3))
            fifth = (
                surname[0].upper()
                if surname and surname[0].isalpha()
                else self.rng.choice(letters)
            )
            digits = f"{self.rng.randint(1000, 9999)}"
            last = self.rng.choice(letters)
            val = f"{first_three}{status}{fifth}{digits}{last}"
            ok, reason = is_valid_pan(val)
            if not ok:
                raise AssertionError(f"Generated invalid PAN {val}: {reason}")
            return val

        return self._unique(_make)

    def gstin(self, business_name: str = "") -> str:
        def _make() -> str:
            state = self.rng.choice(STATE_CODES)
            status = self.rng.choice(PAN_STATUS_CODES_BUSINESS)
            embedded_pan = self.pan(surname=business_name, status=status)
            entity_num = self.rng.choice("123456789ABC")
            fourteen = f"{state}{embedded_pan}{entity_num}Z"
            val = fourteen + compute_gstin_check_char(fourteen)
            ok, reason = is_valid_gstin(val)
            if not ok:
                raise AssertionError(f"Generated invalid GSTIN {val}: {reason}")
            return val

        return self._unique(_make)

    def voter_id(self) -> str:
        def _make() -> str:
            prefix = self.rng.choice(VOTER_PREFIXES)
            digits = f"{self.rng.randint(1000000, 9999999)}"
            val = f"{prefix}{digits}"
            ok, reason = is_valid_voter_id(val)
            if not ok:
                raise AssertionError(f"Generated invalid Voter ID {val}: {reason}")
            return val

        return self._unique(_make)

    def passport(self) -> str:
        def _make() -> str:
            letter = self.rng.choice(PASSPORT_PREFIXES)
            d1 = str(self.rng.randint(1, 9))
            mid = "".join(str(self.rng.randint(0, 9)) for _ in range(5))
            d7 = str(self.rng.randint(1, 9))
            val = f"{letter}{d1}{mid}{d7}"
            ok, reason = is_valid_passport(val)
            if not ok:
                raise AssertionError(f"Generated invalid Passport {val}: {reason}")
            return val

        return self._unique(_make)

    def address(self) -> str:
        locality, city, state, pin = self.rng.choice(CITIES_AND_PINS)
        unit_label = self.rng.choice(["Flat", "House No.", "Plot", "Unit"])
        unit_num = f"{self.rng.randint(10, 899)}"
        if unit_label == "Flat":
            unit_num = f"{self.rng.choice(['A', 'B', 'C', ''])}-{self.rng.randint(101, 904)}".lstrip("-")
        building = self.rng.choice(BUILDING_PREFIXES)
        street = self.rng.choice(STREET_NAMES)
        sep = self.rng.choice([" - ", " "])
        return f"{unit_label} {unit_num}, {building}, {street}, {locality}, {city}, {state}{sep}{pin}"


def _build_loan_en(
    idx: int, rng: random.Random, ids: SyntheticIdentityFactory, spec: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    b = DocumentBuilder()
    inst = rng.choice(FINTECH_INSTITUTIONS)
    p1 = spec["p1"]
    p2 = spec.get("p2")
    addr1 = ids.address()
    aadhaar1 = ids.aadhaar()
    pan1 = ids.pan(p1.split()[-1])
    loan_amt = rng.choice(["Rs. 8,50,000", "Rs. 14,25,000", "Rs. 22,00,000", "Rs. 6,75,000"])
    tenure = rng.choice(["36 months", "60 months", "84 months"])
    variant = idx % 3

    if variant == 0:
        b.text(f"{inst} - Personal & MSME Loan Application\n")
        b.text(f"Application Ref: LN-2026-{1040 + idx}\n\n")
        b.text("Primary Applicant: ").entity("PERSON", p1).text("\n")
        b.text("Residential Address: ").entity("ADDRESS", addr1).text("\n")
        b.text("PAN Card Number: ").entity("PAN", pan1).text("\n")
        b.text("Aadhaar Number: ").entity("AADHAAR", aadhaar1).text("\n")
        if spec.get("include_voter"):
            b.text("Voter ID (EPIC): ").entity("VOTER_ID", ids.voter_id()).text("\n")
        if spec.get("include_passport"):
            b.text("Passport Number: ").entity("PASSPORT", ids.passport()).text("\n")
        if spec.get("include_gstin"):
            biz = rng.choice(BUSINESS_NAMES)
            b.text(f"Enterprise Name: {biz}\n")
            b.text("Business GSTIN: ").entity("GSTIN", ids.gstin(biz)).text("\n")
        if p2:
            b.text("\nCo-Applicant / Guarantor Details:\n")
            b.text("Co-Applicant Name: ").entity("PERSON", p2).text("\n")
            b.text("Co-Applicant PAN: ").entity("PAN", ids.pan(p2.split()[-1])).text("\n")
            if spec.get("multi_addr"):
                b.text("Co-Applicant Address: ").entity("ADDRESS", ids.address()).text("\n")
        b.text(f"\nRequested Facility: {loan_amt} for {tenure}.\n")
        if spec.get("repeat_p1"):
            b.text("Declaration: I, ").entity("PERSON", p1).text(
                ", confirm that the particulars submitted above are accurate and consent to KYC verification.\n"
            )
            b.text("Signed by: ").entity("PERSON", p1)
    elif variant == 1:
        b.text(f"Subject: Home Improvement Loan Request - Applicant ").entity("PERSON", p1).text("\n")
        b.text(f"Lender: {inst} | File ID: HLF-{3100 + idx}\n\n")
        b.text("Dear Credit Underwriting Team,\n")
        b.text("Please review the loan dossier for ").entity("PERSON", p1)
        b.text(", residing at ").entity("ADDRESS", addr1).text(". ")
        b.text("The applicant has enclosed PAN ").entity("PAN", pan1)
        b.text(" and Aadhaar ").entity("AADHAAR", aadhaar1).text(" for e-KYC.\n")
        if spec.get("include_passport"):
            b.text("Overseas employment verification is supported via Passport ")
            b.entity("PASSPORT", ids.passport()).text(".\n")
        if spec.get("include_voter"):
            b.text("Secondary address proof submitted: Voter ID ").entity("VOTER_ID", ids.voter_id()).text(".\n")
        if spec.get("include_gstin"):
            biz = rng.choice(BUSINESS_NAMES)
            b.text(f"Self-employed income proof comes from {biz} (GSTIN: ")
            b.entity("GSTIN", ids.gstin(biz)).text(").\n")
        if p2:
            b.text("Joint borrower ").entity("PERSON", p2)
            b.text(" (Aadhaar: ").entity("AADHAAR", ids.aadhaar())
            b.text(", PAN: ").entity("PAN", ids.pan(p2.split()[-1])).text(") has co-signed the mandate.\n")
        if spec.get("repeat_p1"):
            b.text("Kindly release the sanction letter to ").entity("PERSON", p1).text(f" for {loan_amt}.")
    else:
        b.text(f"WORKING CAPITAL LOAN APPLICATION ({inst})\n")
        b.text(f"Submission Date: 10-11-2026 | Branch Code: BR-{200 + idx}\n\n")
        b.text("1. Borrower Name: ").entity("PERSON", p1).text("\n")
        b.text("2. Registered Office / Residence: ").entity("ADDRESS", addr1).text("\n")
        b.text("3. Tax ID (PAN): ").entity("PAN", pan1).text("\n")
        b.text("4. UIDAI Aadhaar: ").entity("AADHAAR", aadhaar1).text("\n")
        if spec.get("include_gstin"):
            biz = rng.choice(BUSINESS_NAMES)
            b.text(f"5. Firm: {biz} | GSTIN: ").entity("GSTIN", ids.gstin(biz)).text("\n")
        if spec.get("include_voter"):
            b.text("6. Elector ID: ").entity("VOTER_ID", ids.voter_id()).text("\n")
        if spec.get("include_passport"):
            b.text("7. Passport Ref: ").entity("PASSPORT", ids.passport()).text("\n")
        if p2:
            b.text("Authorized Co-Signatory: ").entity("PERSON", p2).text(" | ")
            b.text("Address: ").entity("ADDRESS", ids.address()).text("\n")
        b.text(f"Loan Amount Requested: {loan_amt} ({tenure}).\n")
        if spec.get("repeat_p1"):
            b.text("Primary contact for disbursement queries: ").entity("PERSON", p1).text(".")
    return b.build()


def _build_loan_hinglish(
    idx: int, rng: random.Random, ids: SyntheticIdentityFactory, spec: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    b = DocumentBuilder()
    inst = rng.choice(FINTECH_INSTITUTIONS)
    p1 = spec["p1"]
    p2 = spec.get("p2")
    addr1 = ids.address()
    aadhaar1 = ids.aadhaar()
    pan1 = ids.pan(p1.split()[-1])
    amt = rng.choice(["Rs. 5,00,000", "Rs. 9,50,000", "Rs. 12,00,000"])

    b.text(f"{inst} - Loan Application Follow-up (Ref: LN-HN-{500 + idx})\n")
    b.text("Namaste Team,\n")
    b.text("Mera naam ").entity("PERSON", p1).text(f" hai aur maine {amt} ke business loan ke liye apply kiya hai. ")
    b.text("Mera current address ").entity("ADDRESS", addr1).text(" hai.\n")
    b.text("Verification ke liye maine apna PAN ").entity("PAN", pan1)
    b.text(" aur Aadhaar number ").entity("AADHAAR", aadhaar1).text(" upload kar diya hai.\n")
    if spec.get("include_gstin"):
        biz = rng.choice(BUSINESS_NAMES)
        b.text(f"Hamari firm {biz} ka GSTIN ").entity("GSTIN", ids.gstin(biz)).text(" bhi portal par dala hai.\n")
    if spec.get("include_voter"):
        b.text("Address confirmation ke liye Voter ID ").entity("VOTER_ID", ids.voter_id()).text(" attach hai.\n")
    if spec.get("include_passport"):
        b.text("Passport copy (No. ").entity("PASSPORT", ids.passport()).text(") bhi scan karke bhej di hai.\n")
    if p2:
        b.text("Is loan mein co-applicant ").entity("PERSON", p2).text(" hain, jinka PAN ")
        b.entity("PAN", ids.pan(p2.split()[-1])).text(" hai.\n")
    if spec.get("repeat_p1"):
        b.text("Kripya sanction status ").entity("PERSON", p1).text(" ko email par update karein. Dhanyavaad, ")
        b.entity("PERSON", p1).text(".")
    return b.build()


def _build_kyc_en(
    idx: int, rng: random.Random, ids: SyntheticIdentityFactory, spec: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    b = DocumentBuilder()
    inst = rng.choice(FINTECH_INSTITUTIONS)
    p1 = spec["p1"]
    p2 = spec.get("p2")
    addr1 = ids.address()
    aadhaar1 = ids.aadhaar()
    pan1 = ids.pan(p1.split()[-1])
    variant = idx % 2

    if variant == 0:
        b.text(f"CKYC & RE-KYC VERIFICATION FORM - {inst}\n")
        b.text(f"CKYC Request ID: KYC-2026-{4100 + idx}\n\n")
        b.text("Customer Full Name: ").entity("PERSON", p1).text("\n")
        b.text("Permanent Address: ").entity("ADDRESS", addr1).text("\n")
        b.text("PAN: ").entity("PAN", pan1).text("\n")
        b.text("Aadhaar: ").entity("AADHAAR", aadhaar1).text("\n")
        if spec.get("include_voter"):
            b.text("Voter ID Card: ").entity("VOTER_ID", ids.voter_id()).text("\n")
        if spec.get("include_passport"):
            b.text("Indian Passport No.: ").entity("PASSPORT", ids.passport()).text("\n")
        if spec.get("include_gstin"):
            biz = rng.choice(BUSINESS_NAMES)
            b.text(f"Linked Entity: {biz} | GSTIN: ").entity("GSTIN", ids.gstin(biz)).text("\n")
        if p2:
            b.text("\nJoint Account Holder / Nominee: ").entity("PERSON", p2).text("\n")
            b.text("Joint Holder Voter ID: ").entity("VOTER_ID", ids.voter_id()).text("\n")
            if spec.get("multi_addr"):
                b.text("Correspondence Address: ").entity("ADDRESS", ids.address()).text("\n")
        if spec.get("repeat_p1"):
            b.text("\nKYC Officer Note: Biometric match completed for ").entity("PERSON", p1)
            b.text(". Customer ").entity("PERSON", p1).text(" acknowledged the updated CKYC record.")
    else:
        b.text(f"Merchant Onboarding KYC Dossier ({inst})\n")
        b.text(f"Onboarding Ticket: ONB-{7200 + idx}\n\n")
        b.text("Beneficial Owner: ").entity("PERSON", p1).text("\n")
        b.text("Communication Address: ").entity("ADDRESS", addr1).text("\n")
        b.text("Individual PAN: ").entity("PAN", pan1).text("\n")
        b.text("Aadhaar Ref: ").entity("AADHAAR", aadhaar1).text("\n")
        if spec.get("include_gstin"):
            biz = rng.choice(BUSINESS_NAMES)
            b.text(f"Merchant Legal Name: {biz}\n")
            b.text("Registered GSTIN: ").entity("GSTIN", ids.gstin(biz)).text("\n")
        if spec.get("include_passport"):
            b.text("Passport OVD: ").entity("PASSPORT", ids.passport()).text("\n")
        if spec.get("include_voter"):
            b.text("EPIC / Voter ID: ").entity("VOTER_ID", ids.voter_id()).text("\n")
        if p2:
            b.text("Second Signatory: ").entity("PERSON", p2).text(" (PAN: ")
            b.entity("PAN", ids.pan(p2.split()[-1])).text(")\n")
        if spec.get("repeat_p1"):
            b.text("Compliance Sign-off: PEP screening cleared for ").entity("PERSON", p1).text(".")
    return b.build()


def _build_kyc_hinglish(
    idx: int, rng: random.Random, ids: SyntheticIdentityFactory, spec: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    b = DocumentBuilder()
    inst = rng.choice(FINTECH_INSTITUTIONS)
    p1 = spec["p1"]
    p2 = spec.get("p2")
    addr1 = ids.address()
    aadhaar1 = ids.aadhaar()
    pan1 = ids.pan(p1.split()[-1])

    b.text(f"{inst} - Video KYC Update Request (KYC-HN-{600 + idx})\n")
    b.text("Hello Support,\n")
    b.text("Mera naam ").entity("PERSON", p1).text(" hai aur mujhe apna annual re-KYC complete karwana hai. ")
    b.text("Naya address ").entity("ADDRESS", addr1).text(" update kar dijiye.\n")
    b.text("Maine Aadhaar ").entity("AADHAAR", aadhaar1).text(" aur PAN card ")
    b.entity("PAN", pan1).text(" verify kar liya hai.\n")
    if spec.get("include_voter"):
        b.text("Purane proof mein Voter ID ").entity("VOTER_ID", ids.voter_id()).text(" diya tha.\n")
    if spec.get("include_passport"):
        b.text("NRI verification ke liye Passport number ").entity("PASSPORT", ids.passport()).text(" bhi note kar lein.\n")
    if spec.get("include_gstin"):
        biz = rng.choice(BUSINESS_NAMES)
        b.text(f"Current account {biz} ka GSTIN ").entity("GSTIN", ids.gstin(biz)).text(" link karna hai.\n")
    if p2:
        b.text("Joint holder ").entity("PERSON", p2).text(" ka Aadhaar ")
        b.entity("AADHAAR", ids.aadhaar()).text(" bhi pending hai.\n")
    if spec.get("repeat_p1"):
        b.text("Please ").entity("PERSON", p1).text(" ka KYC link SMS par bhej dein.")
    return b.build()


def _build_support_en(
    idx: int, rng: random.Random, ids: SyntheticIdentityFactory, spec: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    b = DocumentBuilder()
    inst = rng.choice(FINTECH_INSTITUTIONS)
    p1 = spec["p1"]
    p2 = spec.get("p2")
    addr1 = ids.address()
    aadhaar1 = ids.aadhaar()
    pan1 = ids.pan(p1.split()[-1])

    b.text(f"Ticket ID: TKT-2026-{8400 + idx} | Service Desk: {inst}\n")
    b.text("Subject: Profile & Document Mismatch Correction for ").entity("PERSON", p1).text("\n\n")
    b.text("Hi Team,\n")
    b.text("My account dashboard shows a spelling mismatch on PAN ").entity("PAN", pan1)
    b.text(" and Aadhaar ").entity("AADHAAR", aadhaar1).text(". ")
    b.text("Please update my mailing address to ").entity("ADDRESS", addr1).text(".\n")
    if spec.get("include_voter"):
        b.text("I am attaching my Voter ID ").entity("VOTER_ID", ids.voter_id()).text(" as supporting ID.\n")
    if spec.get("include_passport"):
        b.text("You may also cross-check my Passport ").entity("PASSPORT", ids.passport()).text(" on file.\n")
    if spec.get("include_gstin"):
        biz = rng.choice(BUSINESS_NAMES)
        b.text(f"Kindly link my proprietorship {biz} GSTIN ").entity("GSTIN", ids.gstin(biz)).text(" to the invoice profile.\n")
    if p2:
        b.text("Note: Do not confuse my profile with ").entity("PERSON", p2)
        b.text(" (PAN: ").entity("PAN", ids.pan(p2.split()[-1])).text("), who holds a separate folio.\n")
    if spec.get("repeat_p1"):
        b.text("Thanks,\n").entity("PERSON", p1)
    return b.build()


def _build_support_hinglish(
    idx: int, rng: random.Random, ids: SyntheticIdentityFactory, spec: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    b = DocumentBuilder()
    inst = rng.choice(FINTECH_INSTITUTIONS)
    p1 = spec["p1"]
    p2 = spec.get("p2")
    addr1 = ids.address()
    aadhaar1 = ids.aadhaar()
    pan1 = ids.pan(p1.split()[-1])

    b.text(f"Support Ticket #TKT-HN-{9100 + idx} ({inst})\n")
    b.text("Hi Customer Care,\n")
    b.text("Mera naam ").entity("PERSON", p1).text(" hai. Mera statement aur debit card galat ghar par dispatch ho gaya hai.\n")
    b.text("Asli delivery address yeh hai: ").entity("ADDRESS", addr1).text(".\n")
    b.text("Confirmation ke liye PAN ").entity("PAN", pan1)
    b.text(" aur Aadhaar ").entity("AADHAAR", aadhaar1).text(" verify kar sakte hain.\n")
    if spec.get("include_passport"):
        b.text("International card activate karne ke liye Passport ").entity("PASSPORT", ids.passport()).text(" bhi diya tha.\n")
    if spec.get("include_voter"):
        b.text("Backup ID mein Voter ID ").entity("VOTER_ID", ids.voter_id()).text(" uploaded hai.\n")
    if spec.get("include_gstin"):
        biz = rng.choice(BUSINESS_NAMES)
        b.text(f"Tax invoice par {biz} ka GSTIN ").entity("GSTIN", ids.gstin(biz)).text(" print hona chahiye.\n")
    if p2:
        b.text("Shayad aapne galti se ").entity("PERSON", p2).text(" ka record merge kar diya hai.\n")
    if spec.get("repeat_p1"):
        b.text("Please ").entity("PERSON", p1).text(" ke ticket ko priority par resolve karein.")
    return b.build()


def _build_claim_en(
    idx: int, rng: random.Random, ids: SyntheticIdentityFactory, spec: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    b = DocumentBuilder()
    insurer = rng.choice(INSURERS)
    p1 = spec["p1"]
    p2 = spec.get("p2")
    addr1 = ids.address()
    aadhaar1 = ids.aadhaar()
    pan1 = ids.pan(p1.split()[-1])
    claim_amt = rng.choice(["Rs. 2,45,000", "Rs. 4,80,000", "Rs. 1,65,500", "Rs. 7,10,000"])

    b.text(f"{insurer} - Health & Motor Claim Settlement Form\n")
    b.text(f"Claim Reference: CLM-2026-{6300 + idx} | Claimed Amount: {claim_amt}\n\n")
    b.text("Insured / Policyholder Name: ").entity("PERSON", p1).text("\n")
    b.text("Insured Residential Address: ").entity("ADDRESS", addr1).text("\n")
    b.text("Policyholder PAN: ").entity("PAN", pan1).text("\n")
    b.text("Policyholder Aadhaar: ").entity("AADHAAR", aadhaar1).text("\n")
    if spec.get("include_passport"):
        b.text("Travel / Overseas Policy Passport No.: ").entity("PASSPORT", ids.passport()).text("\n")
    if spec.get("include_voter"):
        b.text("Claimant Voter ID: ").entity("VOTER_ID", ids.voter_id()).text("\n")
    if spec.get("include_gstin"):
        biz = rng.choice(BUSINESS_NAMES)
        b.text(f"Commercial Fleet Owner: {biz} | GSTIN: ").entity("GSTIN", ids.gstin(biz)).text("\n")
    if p2:
        b.text("Nominee / Secondary Claimant: ").entity("PERSON", p2).text("\n")
        b.text("Nominee Aadhaar: ").entity("AADHAAR", ids.aadhaar()).text("\n")
        if spec.get("multi_addr"):
            b.text("Nominee Address: ").entity("ADDRESS", ids.address()).text("\n")
    if spec.get("repeat_p1"):
        b.text("\nSettlement Note: NEFT reimbursement approved in favour of ").entity("PERSON", p1)
        b.text(". Discharge voucher signed by ").entity("PERSON", p1).text(".")
    return b.build()


def _build_claim_hinglish(
    idx: int, rng: random.Random, ids: SyntheticIdentityFactory, spec: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    b = DocumentBuilder()
    insurer = rng.choice(INSURERS)
    p1 = spec["p1"]
    p2 = spec.get("p2")
    addr1 = ids.address()
    aadhaar1 = ids.aadhaar()
    pan1 = ids.pan(p1.split()[-1])
    claim_amt = rng.choice(["Rs. 1,90,000", "Rs. 3,40,000", "Rs. 5,20,000"])

    b.text(f"{insurer} - Claim Desk Escalation (CLM-HN-{2200 + idx})\n")
    b.text("Namaste Claim Team,\n")
    b.text("Main ").entity("PERSON", p1).text(f" bol raha hoon. Mera {claim_amt} ka hospitalization claim abhi tak pending hai.\n")
    b.text("Discharge summary ke saath maine address ").entity("ADDRESS", addr1)
    b.text(", PAN ").entity("PAN", pan1)
    b.text(" aur Aadhaar ").entity("AADHAAR", aadhaar1).text(" bhej diya hai.\n")
    if spec.get("include_voter"):
        b.text("Identity ke liye Voter ID ").entity("VOTER_ID", ids.voter_id()).text(" bhi attach kiya tha.\n")
    if spec.get("include_passport"):
        b.text("Travel medical cover ke liye Passport ").entity("PASSPORT", ids.passport()).text(" number check karein.\n")
    if spec.get("include_gstin"):
        biz = rng.choice(BUSINESS_NAMES)
        b.text(f"Group corporate policy {biz} (GSTIN: ").entity("GSTIN", ids.gstin(biz)).text(") ke under hai.\n")
    if p2:
        b.text("Hospital desk par nominee ").entity("PERSON", p2).text(" ne saare forms sign kiye the.\n")
    if spec.get("repeat_p1"):
        b.text("Kripya ").entity("PERSON", p1).text(" ka claim jaldi process karein.")
    return b.build()


NEGATIVE_TEMPLATES: list[tuple[str, str, str]] = [
    (
        "Loan Application",
        "en",
        "NavaBharat FinServe Ltd. - Loan Eligibility & Rate Schedule\n"
        "Reference Code: SCH-HL-2026-04\n\n"
        "Dear Credit Desk,\n"
        "Please share the updated interest rate slab and processing fee waiver table for salaried housing loan "
        "applications between Rs. 15,00,000 and Rs. 35,00,000 for a 120-month tenure. "
        "No borrower KYC packet is attached to this pre-sanction inquiry. "
        "All standard verification guidelines under internal circular CIRC-2026-19 apply.",
    ),
    (
        "Loan Application",
        "hinglish",
        "ArthSetu Capital Services - Pre-Application Query (Ref: INQ-90412)\n"
        "Namaste Team,\n"
        "Kya aap bata sakte hain ki MSME machinery loan ke liye minimum turnover requirement kitna hai? "
        "Interest rate floating rahega ya fixed aur processing fee kitni lagti hai? "
        "Abhi humne koi document ya applicant details submit nahi kiye hain, bas general jankari chahiye.",
    ),
    (
        "KYC Form",
        "en",
        "IndusTrust Housing Finance - Standard CKYC Document Checklist\n"
        "Form Template Version: CKYC-TMP-2026.2\n\n"
        "Required Officially Valid Documents (OVDs) for individual onboarding:\n"
        "1. Proof of Identity and Address (any one government-issued photo ID).\n"
        "2. Recent passport-size photograph and signed declaration.\n"
        "3. Tax registration document for proprietorship or corporate entities.\n"
        "Note: Leave all fields blank until customer consent is recorded on the digital portal.",
    ),
    (
        "Customer Support Ticket",
        "en",
        "Ticket ID: TKT-2026-99014 | Portal Downtime Report\n"
        "Subject: Unable to download monthly statement PDF after 18:00 IST\n\n"
        "Hi Technical Support,\n"
        "Whenever I click the 'Download Statement' button under the Accounts tab, the portal returns HTTP 504 "
        "Gateway Timeout for statement cycle October 2026. Cache clearing did not resolve the issue. "
        "Please investigate the backend export queue.",
    ),
    (
        "Customer Support Ticket",
        "hinglish",
        "Support Ticket #TKT-HN-99021\n"
        "Hi Team,\n"
        "Mobile app update hone ke baad OTP screen par timer freeze ho raha hai aur login nahi ho paa raha. "
        "Network strong hai phir bhi error code E-408 aa raha hai. "
        "Kripya app team ko inform karein taaki next patch mein yeh bug fix ho sake.",
    ),
    (
        "Insurance Claim",
        "en",
        "NavaJeevan General Insurance - Cashless Claim Process Guidelines\n"
        "Circular ID: CLM-SOP-2026-11\n\n"
        "For planned hospitalizations, pre-authorization requests must be submitted at least 48 hours prior "
        "to admission through the TPA desk. Emergency admissions require intimation within 24 hours. "
        "Itemized hospital bills, diagnostic reports, and pharmacy invoices should be uploaded as clear PDFs.",
    ),
]


def build_document_specs(rng: random.Random) -> list[dict[str, Any]]:
    """Construct a balanced specification list for exactly 50 documents."""
    specs: list[dict[str, Any]] = []

    # 6 negative documents (distributed across all 4 categories, both English and Hinglish)
    for neg_idx, (category, language, text) in enumerate(NEGATIVE_TEMPLATES):
        specs.append(
            {
                "category": category,
                "language": language,
                "negative": True,
                "negative_text": text,
                "scenarios": [
                    "english" if language == "en" else "hinglish",
                    "negative_no_pii",
                ],
            }
        )

    # Remaining 44 PII-containing documents:
    # Target totals: Loan Application=13 (2 neg + 11 pii), KYC Form=13 (1 neg + 12 pii),
    # Customer Support Ticket=12 (2 neg + 10 pii), Insurance Claim=12 (1 neg + 11 pii)
    category_plan = (
        [("Loan Application", "en")] * 8
        + [("Loan Application", "hinglish")] * 3
        + [("KYC Form", "en")] * 9
        + [("KYC Form", "hinglish")] * 3
        + [("Customer Support Ticket", "en")] * 7
        + [("Customer Support Ticket", "hinglish")] * 3
        + [("Insurance Claim", "en")] * 8
        + [("Insurance Claim", "hinglish")] * 3
    )
    assert len(category_plan) == 44

    for idx, (category, language) in enumerate(category_plan):
        use_similar = idx < 12
        use_multi_people = use_similar or (idx % 2 == 0)
        repeat_p1 = (idx % 3 == 0)
        include_gstin = (idx % 2 == 0)
        include_voter = (idx % 2 == 1) or (idx % 5 == 0)
        include_passport = (idx % 3 == 1) or (idx % 4 == 0)
        multi_addr = (idx % 4 == 0) and use_multi_people

        if use_similar:
            p1, p2 = SIMILAR_NAME_PAIRS[idx]
        else:
            p1 = PRIMARY_NAMES[(idx * 7) % len(PRIMARY_NAMES)]
            p2 = (
                SECONDARY_NAMES[(idx * 5) % len(SECONDARY_NAMES)]
                if use_multi_people
                else None
            )
            if p2 == p1:
                p2 = SECONDARY_NAMES[(idx * 5 + 1) % len(SECONDARY_NAMES)]

        scenarios = ["english" if language == "en" else "hinglish", "multiple_pii_entities"]
        if use_multi_people:
            scenarios.append("multiple_people")
        if repeat_p1:
            scenarios.append("repeated_names")
        if use_similar:
            scenarios.append("similar_looking_names")

        specs.append(
            {
                "category": category,
                "language": language,
                "negative": False,
                "p1": p1,
                "p2": p2,
                "repeat_p1": repeat_p1,
                "include_gstin": include_gstin,
                "include_voter": include_voter,
                "include_passport": include_passport,
                "multi_addr": multi_addr,
                "scenarios": scenarios,
            }
        )

    rng.shuffle(specs)
    return specs


def generate_dataset() -> dict[str, Any]:
    """Generate the 50 synthetic Indian PII documents dataset."""
    rng = random.Random(SEED)
    ids = SyntheticIdentityFactory(seed=SEED)
    specs = build_document_specs(rng)

    documents: list[dict[str, Any]] = []
    for doc_num, spec in enumerate(specs, start=1):
        doc_id = f"DOC-{doc_num:03d}"
        category = spec["category"]
        language = spec["language"]

        if spec["negative"]:
            text = spec["negative_text"]
            annotations: list[dict[str, Any]] = []
        elif category == "Loan Application":
            text, annotations = (
                _build_loan_en(doc_num, rng, ids, spec)
                if language == "en"
                else _build_loan_hinglish(doc_num, rng, ids, spec)
            )
        elif category == "KYC Form":
            text, annotations = (
                _build_kyc_en(doc_num, rng, ids, spec)
                if language == "en"
                else _build_kyc_hinglish(doc_num, rng, ids, spec)
            )
        elif category == "Customer Support Ticket":
            text, annotations = (
                _build_support_en(doc_num, rng, ids, spec)
                if language == "en"
                else _build_support_hinglish(doc_num, rng, ids, spec)
            )
        elif category == "Insurance Claim":
            text, annotations = (
                _build_claim_en(doc_num, rng, ids, spec)
                if language == "en"
                else _build_claim_hinglish(doc_num, rng, ids, spec)
            )
        else:
            raise ValueError(f"Unsupported category: {category}")

        documents.append(
            {
                "id": doc_id,
                "category": category,
                "language": language,
                "scenarios": spec["scenarios"],
                "text": text,
                "annotations": annotations,
            }
        )

    return {
        "metadata": {
            "dataset_name": "synthetic_indian_pii_dataset",
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "seed": SEED,
            "total_documents": len(documents),
            "categories": [
                "Loan Application",
                "KYC Form",
                "Customer Support Ticket",
                "Insurance Claim",
            ],
            "entity_types": [
                "PERSON",
                "ADDRESS",
                "AADHAAR",
                "PAN",
                "GSTIN",
                "VOTER_ID",
                "PASSPORT",
            ],
            "synthetic_only": True,
        },
        "documents": documents,
    }


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    output_path = project_root / "data" / "synthetic_documents.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dataset = generate_dataset()
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
        f.write("\n")

    total_anns = sum(len(doc["annotations"]) for doc in dataset["documents"])
    print(f"Generated {len(dataset['documents'])} synthetic documents ({total_anns} annotations).")
    print(f"Saved dataset to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

