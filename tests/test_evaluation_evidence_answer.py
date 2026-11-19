from app.services.evaluation_service import _fake_llm_answer


def test_guest_exclusion_is_an_answer_not_automatic_abstention():
    chunks = [{"text": "Personal guests are not eligible for company-funded commute transport."}]
    answer, covered = _fake_llm_answer("Can I take my personal friend?", chunks)
    assert covered is True
    assert "not eligible" in answer


def test_contractor_referral_is_preserved_as_covered_policy_information():
    chunks = [{"text": (
        "This policy does not specify transport arrangements for contractors. "
        "Contractor transport must be approved under the site procurement process."
    )}]
    answer, covered = _fake_llm_answer("Does the policy explain contractor transport?", chunks)
    assert covered is True
    assert "procurement process" in answer


def test_combines_top_retrieved_evidence_for_paraphrased_questions():
    chunks = [
        {"text": "Standard commute bookings must be submitted at least 3 hours before pickup."},
        {"text": "A no-show without timely cancellation may result in a charge of INR 500."},
    ]
    answer, covered = _fake_llm_answer("What happens if I miss my scheduled cab pickup?", chunks)
    assert covered is True
    assert "INR 500" in answer
