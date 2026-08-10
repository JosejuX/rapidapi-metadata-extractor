"""
Phone number normalization (Plan section 19), using Google's libphonenumber
via the `phonenumbers` package: E.164 formatting, country detection, and
validity — no SMTP-style verification, no external requests, no geolocation.

Numbers without a leading '+' (no explicit country code) can't be reliably
parsed without knowing which country the page belongs to, which this
fast-path extractor has no cheap way to determine — those are returned with
normalized=None/country=None rather than guessed, to avoid silently wrong
country assignments.
"""
from typing import Any, Dict, List

import phonenumbers

MAX_PHONES = 5


def normalize_phones(raw_phones: List[str]) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    for raw in raw_phones[:MAX_PHONES]:
        entry: Dict[str, Any] = {"raw": raw, "normalized": None, "country": None, "possible": False, "valid": False}
        try:
            parsed = phonenumbers.parse(raw, None)
        except phonenumbers.NumberParseException:
            details.append(entry)
            continue
        entry["possible"] = phonenumbers.is_possible_number(parsed)
        entry["valid"] = phonenumbers.is_valid_number(parsed)
        if entry["possible"]:
            entry["normalized"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            entry["country"] = phonenumbers.region_code_for_number(parsed)
        details.append(entry)
    return details
