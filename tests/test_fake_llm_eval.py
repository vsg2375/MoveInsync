import asyncio
from scripts.run_evaluation import fake_llm_answer


def test_answer_uses_retrieved_policy_evidence():
    chunks = [
        {"text": "Employees must cancel at least 60 minutes before pickup."},
        {"text": "Unrelated office attendance rule."},
    ]
    result = asyncio.run(fake_llm_answer("When should I cancel?", chunks))
    assert result == "Employees must cancel at least 60 minutes before pickup."


def test_returns_not_covered_without_evidence():
    assert asyncio.run(fake_llm_answer("unknown", [])) == "NOT_COVERED"


def test_distinguishes_eligibility_from_policy_referral_detail():
    chunks = [{"text": "This policy does not specify transport arrangements for contractors. Contractor transport must be approved under the site procurement process."}]
    result = asyncio.run(fake_llm_answer("Are contractors eligible for commute?", chunks))
    assert result == "NOT_COVERED"


def test_can_explain_the_referral_rule_when_asked_about_policy_coverage():
    chunks = [{"text": "This policy does not specify transport arrangements for contractors. Contractor transport must be approved under the site procurement process."}]
    result = asyncio.run(fake_llm_answer("Does the policy explain contractor transport?", chunks))
    assert "procurement process" in result
