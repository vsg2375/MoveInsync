"""Run CommuteIQ's isolated, deterministic evaluation (no API server or LLM).

Run from the project root:
    python scripts/run_evaluation.py

The evaluation uses the real active-policy lookup and tenant/version-filtered
ChromaDB retrieval, followed by a deterministic evidence-only fake answerer.
It does not call /ask, create JWTs, import a provider SDK, or make network calls.
Each JSONL result retains exactly: id, input, expected, actual, pass, notes.
"""
import os

# Set telemetry controls before importing ChromaDB or project modules.
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "FALSE"

import json
import logging
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Keep the evaluation terminal focused on the report, not Chroma's optional
# telemetry compatibility warnings. Application exceptions still surface.
for logger_name in (
    "chromadb",
    "chromadb.telemetry",
    "chromadb.telemetry.product",
    "chromadb.telemetry.product.posthog",
    "posthog",
):
    logger = logging.getLogger(logger_name)
    logger.disabled = True
    logger.propagate = False

from app.database.store import init_db, active_policy
from app.services.evaluation_service import evaluate_question

SOURCE = ROOT / "data/evaluation/questions.jsonl"
OUT = ROOT / "data/evaluation/results.jsonl"
REPORT = ROOT / "data/evaluation/LAST_RUN_REPORT.json"
REQUIRED_FIELDS = {"id", "input", "expected", "actual", "pass", "notes"}


async def fake_llm_answer(question, chunks):
    """Deterministic evidence-only test double; never calls an external model."""
    if not chunks:
        return "NOT_COVERED"

    stop_words = {
        "a", "an", "the", "is", "are", "was", "were", "be", "to", "of",
        "for", "in", "on", "at", "and", "or", "do", "does", "did", "what",
        "when", "where", "how", "who", "i", "we", "you", "my", "our",
        "it", "this", "that", "with", "from", "about",
    }

    def tokens(value):
        return {
            word for word in re.findall(r"[a-z0-9]+", str(value).lower())
            if word not in stop_words and len(word) > 1
        }

    question_terms = tokens(question)
    candidates = []
    for chunk in chunks:
        text = str(chunk.get("text", "")) if isinstance(chunk, dict) else str(chunk)
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for sentence in sentences:
            overlap = len(question_terms & tokens(sentence))
            if overlap:
                candidates.append((overlap, sentence.strip(), text.strip()))

    if not candidates:
        return "NOT_COVERED"

    _, best_sentence, best_chunk = max(candidates, key=lambda item: item[0])
    negative_markers = ("does not specify", "does not define", "does not cover", "not eligible")
    if any(marker in best_chunk.lower() for marker in negative_markers):
        if question_terms & {"eligible", "eligibility"}:
            return "NOT_COVERED"
        sentences = re.split(r"(?<=[.!?])\s+", best_chunk)
        additional_guidance = [
            sentence.strip() for sentence in sentences
            if sentence.strip() and not any(marker in sentence.lower() for marker in negative_markers)
        ]
        if additional_guidance:
            return " ".join(additional_guidance)

    return best_sentence


def percentile(values, p):
    values = sorted(values)
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, int((len(values) - 1) * p + 0.9999)))
    return values[index]


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Evaluation dataset not found: {SOURCE}")
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if set(row) != REQUIRED_FIELDS:
            raise ValueError(
                f"{row.get('id', 'unknown')}: JSONL fields must be exactly {sorted(REQUIRED_FIELDS)}"
            )

    init_db()
    companies = sorted({row["input"]["company"] for row in rows})
    missing = [company for company in companies if not active_policy(company)]
    if missing:
        raise RuntimeError(
            "Evaluation stopped: no active policy for " + ", ".join(missing)
            + ". Start the application once to ingest the sample policies, then rerun."
        )

    latencies = []
    failures = []
    passed = coverage_correct = citation_correct = retrieval_hits = 0
    covered_total = sum(bool(row["expected"]["covered"]) for row in rows)

    with OUT.open("w", encoding="utf-8") as output:
        for row in rows:
            company = row["input"]["company"]
            question = row["input"]["question"]
            started = time.perf_counter()
            actual = evaluate_question(company, question)
            latencies.append((time.perf_counter() - started) * 1000)

            expected = row["expected"]
            answer = str(actual.get("answer", "")).lower()
            citations = actual.get("citations", [])
            coverage_ok = actual.get("covered") is expected["covered"]
            if expected["covered"]:
                facts_ok = all(str(term).lower() in answer for term in expected["keywords"])
            else:
                facts_ok = actual.get("covered") is False and (
                    "does not cover" in answer or "not covered" in answer
                    or "does not specify" in answer or "does not define" in answer
                )
            section_ok = (not expected["covered"]) or any(
                citation.get("section") == expected["section"] for citation in citations
            )
            tenant_ok = all(
                company in str(citation.get("document", "")).lower()
                for citation in citations
            )
            citation_limit_ok = len(citations) <= 3
            case_pass = bool(
                coverage_ok and facts_ok and section_ok and tenant_ok and citation_limit_ok
            )

            row["actual"] = actual
            row["pass"] = case_pass
            row["notes"] = (
                f"{row.get('notes', '')} | isolated_fake_answer_evaluation; "
                f"coverage={coverage_ok}; expected_facts={facts_ok}; "
                f"expected_section_cited={section_ok}; tenant_docs={tenant_ok}; "
                f"citations<=3={citation_limit_ok}"
            ).strip(" |")
            output.write(json.dumps(row, ensure_ascii=False) + "\n")

            passed += int(case_pass)
            coverage_correct += int(coverage_ok)
            citation_correct += int(section_ok)
            retrieval_hits += int(section_ok and expected["covered"])
            if not case_pass:
                failures.append({
                    "id": row["id"],
                    "question": question,
                    "answer": actual.get("answer", ""),
                    "checks": {
                        "coverage": coverage_ok,
                        "expected_facts": facts_ok,
                        "expected_section_cited": section_ok,
                        "tenant_documents": tenant_ok,
                        "citation_limit": citation_limit_ok,
                    },
                })

    report = {
        "evaluation_mode": "isolated_deterministic_fake_answer",
        "cases": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "pass_rate": round(passed / max(1, len(rows)), 3),
        "coverage_classification_accuracy": round(coverage_correct / max(1, len(rows)), 3),
        "expected_section_retrieval_and_citation_accuracy_on_covered_cases": round(
            retrieval_hits / max(1, covered_total), 3
        ),
        "citation_check_accuracy_all_cases": round(citation_correct / max(1, len(rows)), 3),
        "latency_ms": {
            "p50": round(percentile(latencies, 0.50), 1),
            "p95": round(percentile(latencies, 0.95), 1),
            "max": round(max(latencies, default=0), 1),
        },
        "results_file": str(OUT.relative_to(ROOT)),
        "failures": failures,
        "interpretation": (
            "This standalone evaluation exercises active-policy selection, company/version-filtered "
            "ChromaDB retrieval, reranking, evidence-grounded deterministic answer behaviour, "
            "coverage and citations. It does not call the /ask endpoint, an external LLM provider, "
            "or any network service. Authentication/API contract tests remain separate. "
            "Latency measures this local retrieval-and-fake-answer path only."
        ),
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
