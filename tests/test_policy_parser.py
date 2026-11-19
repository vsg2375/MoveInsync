import pytest
from app.services.policy_service import parse_policy

def test_sections_are_preserved():
    chunks=parse_policy("1. Scope\nApplies to employees.\n2. Guests\nNo guests.","demo.pdf")
    assert [x["section"] for x in chunks]==["1. Scope","2. Guests"]
    assert "No guests" in chunks[1]["text"]

def test_unstructured_policy_rejected():
    with pytest.raises(ValueError): parse_policy("No headings here", "bad.pdf")


def test_pdf_control_characters_are_removed_from_policy_chunks():
    chunks = parse_policy("1. Scope\n\x07 Applies to employees.\n2. Guests\nNo guests.", "demo.pdf")
    assert "\x07" not in chunks[0]["text"]
    assert "Applies to employees" in chunks[0]["text"]
