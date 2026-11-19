from app.services import evaluation_service


def test_evaluation_uses_deterministic_answer_without_live_llm(monkeypatch):
    chunks = [{
        "text": "Employees must attend the office at least three days in a workweek.",
        "metadata": {"document": "technova_policy_v2.pdf", "section": "2. Transport eligibility"},
        "distance": 0.1,
    }]
    monkeypatch.setattr(evaluation_service, "active_policy", lambda company: {"version": "2.0"})
    monkeypatch.setattr(evaluation_service, "hybrid_search", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(evaluation_service, "_rank_chunks", lambda question, found: [
        {**found[0], "_relevance": 10.0, "_lexical_score": 1.0, "_matched_query_terms": 2}
    ])

    # The evaluator must not need or invoke the live answer service/provider path.
    result = evaluation_service.evaluate_question(
        "technova", "What is the minimum office attendance?"
    )
    assert result["covered"] is True
    assert "three days" in result["answer"].lower()
    assert result["citations"][0]["section"] == "2. Transport eligibility"


def test_evaluation_returns_not_covered_when_no_active_policy(monkeypatch):
    monkeypatch.setattr(evaluation_service, "active_policy", lambda company: None)
    result = evaluation_service.evaluate_question("unknownco", "What is the cab policy?")
    assert result["covered"] is False
    assert result["citations"] == []
