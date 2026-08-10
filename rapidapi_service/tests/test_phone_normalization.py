"""Phone number normalization (Plan §19): E.164 formatting + country
detection via libphonenumber, without SMTP-style verification or geolocation."""
from app.extraction.phones import normalize_phones


def test_valid_international_number_is_normalized_to_e164():
    details = normalize_phones(["+34 600 123 456"])
    assert len(details) == 1
    entry = details[0]
    assert entry["raw"] == "+34 600 123 456"
    assert entry["normalized"] == "+34600123456"
    assert entry["country"] == "ES"
    assert entry["valid"] is True
    assert entry["possible"] is True


def test_number_without_country_code_is_not_guessed():
    details = normalize_phones(["555-123-4567"])
    entry = details[0]
    assert entry["raw"] == "555-123-4567"
    assert entry["normalized"] is None
    assert entry["country"] is None
    assert entry["possible"] is False
    assert entry["valid"] is False


def test_garbage_input_does_not_raise():
    details = normalize_phones(["not a phone number at all"])
    entry = details[0]
    assert entry["normalized"] is None
    assert entry["valid"] is False


def test_possible_but_not_valid_number_is_distinguished():
    # A plausible-looking but not-assignable US number: possible=True (right
    # length/shape) yet valid=False (fails libphonenumber's real validation).
    details = normalize_phones(["+1 555-555-5555"])
    entry = details[0]
    assert entry["possible"] is True
    assert entry["valid"] is False


def test_truncates_to_max_five_and_preserves_order():
    raw = [f"+34 60000000{i}" for i in range(8)]
    details = normalize_phones(raw)
    assert len(details) == 5
    assert [d["raw"] for d in details] == raw[:5]


def test_empty_list_returns_empty_list():
    assert normalize_phones([]) == []
