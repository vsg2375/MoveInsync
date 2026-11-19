"""Compare vector top-3 retrieval with the current reranked top-3 on one fixed set.

Run after the sample policies are initialized:
    python scripts/compare_retrieval.py

This measures section retrieval accuracy and local retrieval latency only. It
is not an LLM answer-quality or live API latency benchmark.
"""
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database.store import init_db, active_policy
from app.services.vector_store import search, hybrid_search
from app.services.answer_service import _rank_chunks

SOURCE = ROOT / "data/evaluation/questions.jsonl"
OUTPUT = ROOT / "data/evaluation/RETRIEVAL_COMPARISON.json"


def percentile(values, fraction):
    values = sorted(values)
    if not values:
        return 0.0
    index = min(len(values) - 1, int((len(values) - 1) * fraction + 0.9999))
    return round(values[index], 2)


def main():
    init_db()
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = {"cases": len(rows), "baseline": {"hits": 0, "latencies_ms": []},
               "reranked": {"hits": 0, "latencies_ms": []}, "case_results": []}
    for row in rows:
        company = row["input"]["company"]
        question = row["input"]["question"]
        expected = row["expected"]
        policy = active_policy(company)
        if not policy:
            raise RuntimeError(f"No active policy for {company}; start the app once first")

        started = time.perf_counter()
        candidates = search(company, policy["version"], question, 3)
        baseline = candidates[:3]
        baseline_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        hybrid_candidates = hybrid_search(company, policy["version"], question, 20)
        reranked = _rank_chunks(question, hybrid_candidates)[:3]
        reranked_ms = (time.perf_counter() - started) * 1000

        if expected["covered"]:
            baseline_hit = any(c.get("metadata", {}).get("section") == expected["section"] for c in baseline)
            reranked_hit = any(c.get("metadata", {}).get("section") == expected["section"] for c in reranked)
            results["baseline"]["hits"] += int(baseline_hit)
            results["reranked"]["hits"] += int(reranked_hit)
        else:
            # For unsupported questions, retrieval should not be interpreted as a hit.
            baseline_hit = reranked_hit = None
        results["baseline"]["latencies_ms"].append(baseline_ms)
        results["reranked"]["latencies_ms"].append(baseline_ms + reranked_ms)
        results["case_results"].append({"id": row["id"], "baseline_section_hit": baseline_hit,
                                         "reranked_section_hit": reranked_hit,
                                         "baseline_ms": round(baseline_ms, 2),
                                         "reranked_total_ms": round(baseline_ms + reranked_ms, 2)})

    covered = sum(bool(row["expected"]["covered"]) for row in rows)
    for name in ("baseline", "reranked"):
        times = results[name].pop("latencies_ms")
        results[name]["covered_cases"] = covered
        results[name]["expected_section_recall_at_3"] = round(results[name]["hits"] / max(1, covered), 4)
        results[name]["latency_ms"] = {"p50": percentile(times, .50), "p95": percentile(times, .95),
                                       "max": round(max(times, default=0), 2)}
    results["interpretation"] = (
        "Same fixed dataset and active company/version policies. Baseline is vector top-3; "
        "reranked is active-version hybrid retrieval (Chroma dense candidates plus BM25 over "
        "all active sections), followed by top-3 selection. Latency is local retrieval/reranking "
        "only and excludes the LLM and HTTP overhead."
    )
    OUTPUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in results.items() if k != "case_results"}, indent=2))
    print(f"Detailed comparison: {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
