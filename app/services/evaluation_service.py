"""Isolated deterministic evaluation. Never imports or calls a live LLM provider."""
from app.database.store import active_policy
from app.services.vector_store import hybrid_search
from app.services.answer_service import (
    NOT_COVERED, rank_hybrid, _is_relevant, _citations, ExtractiveFakeLLMClient,
)

# Kept as a named seam for older tests and evaluation tooling.
_rank_chunks = rank_hybrid


def _fake_llm_answer(question: str, evidence_chunks: list[dict]) -> tuple[str, bool]:
    if not evidence_chunks:
        return NOT_COVERED, False
    # Deterministic evidence-only stand-in: it does not use topic-specific rules.
    excerpts = []
    for chunk in evidence_chunks[:3]:
        text = str(chunk.get("text", "")).strip()
        if text and text not in excerpts:
            excerpts.append(text)
    answer = " ".join(excerpts)
    return (answer[:1200], True) if answer else (NOT_COVERED, False)


def evaluate_question(company_id: str, question: str) -> dict:
    policy = active_policy(company_id)
    if not policy:
        return {"answer": NOT_COVERED, "covered": False, "citations": [], "version": None}
    chunks = hybrid_search(company_id, policy["version"], question, 30)
    ranked = rank_hybrid(question, chunks)
    if not ranked or not _is_relevant(ranked[0]):
        return {"answer": NOT_COVERED, "covered": False, "citations": [], "version": policy["version"]}
    selected = ranked[:3]
    answer, covered = _fake_llm_answer(question, selected)
    return {
        "answer": answer if covered else NOT_COVERED,
        "covered": covered,
        "citations": _citations(selected) if covered else [],
        "version": policy["version"],
    }


