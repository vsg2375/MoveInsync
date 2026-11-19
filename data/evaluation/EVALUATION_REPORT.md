# CommuteIQ Evaluation Report

## 1. Evaluation Design

The fixed evaluation set contains **36 questions** derived from the bundled TechNova, DataSphere and CloudAxis policy PDFs. Expected answers and section references were prepared from those source policies.

Coverage includes direct questions and paraphrases across eligibility, night transport, escorts, booking cut-offs, cost caps, weekends, guests, cancellations/no-shows and ad-hoc approvals; contradictory rules across companies; unsupported topics; cross-company bait; prompt-injection attempts; and everyday wording such as "miss my cab" mapped to "no-show".

Each JSONL record has exactly `id`, `input`, `expected`, `actual`, `pass` and `notes`. The isolated runner checks coverage classification, expected answer terms, expected section citation, tenant ownership of citations and the three-citation limit.

## 2. Recorded Isolated Evaluation Result

The uploaded `results.jsonl` contains **33 passed and 3 failed cases out of 36 (91.7%)**. The failed cases are **T11**, **D04** and **D11**. They are retained in the evaluation set and results; they have not been removed to increase the score.

The matching `LAST_RUN_REPORT.json` records:

| Metric | Recorded result |
|---|---:|
| Cases | 36 |
| Passed | 33 |
| Failed | 3 |
| Pass rate | 91.7% |
| Coverage classification accuracy | 91.7% |
| Expected-section retrieval and citation accuracy on covered cases | 100% |
| Citation check accuracy across all cases | 100% |
| Local fake-answer path p50 | 34.6 ms |
| Local fake-answer path p95 | 120.8 ms |
| Local fake-answer path maximum | 2,242.2 ms |

This is a deterministic, offline evaluation. It reads the active policy from SQLite, performs company/version-filtered Chroma retrieval and reranking, and uses an evidence-only fake answerer. It does **not** start FastAPI, create JWTs, call `/ask`, invoke a real LLM provider or make network requests. Its latency measures only the local retrieval-and-fake-answer path and must not be presented as live endpoint latency.

### Failed Cases and Observed Behaviour

- **T11 — Inter-city travel reimbursement:** The answer correctly retrieved a statement that the policy does not specify inter-city rail or air reimbursement, but also included unrelated ad-hoc reimbursement details and policy metadata. The expected unsupported-topic response was therefore not satisfied.
- **D04 — Contractor commute eligibility:** Retrieval returned guest/visitor restrictions and general employee-scope statements, rather than a precise contractor-specific not-covered response.
- **D11 — Home-to-airport reimbursement:** The answer retrieved a statement that the policy does not define home-to-airport reimbursement, but also included unrelated ad-hoc reimbursement details and policy metadata.

These failures indicate that the deterministic answerer can concatenate related retrieved passages without sufficiently separating directly relevant policy statements from adjacent material. They remain visible in the JSONL evidence.

## 3. Automated Tests

Run the suite from the project root:

```powershell
python -m pytest -v
```

The test files supplied for this review cover API/JWT tenant isolation, admin scope, prompt-injection and cross-company checks, isolated evaluation, evidence-answer behaviour, policy parsing, retrieval reranking, citation limits and fail-closed LLM validation.

A fresh test-suite result for the exact final project snapshot has not been established in this report. Run the command above and record the actual result from the submission environment. Do not reuse an earlier test count as if it applied to the final snapshot.

## 4. Retrieval Comparison and Trade-off

The comparison uses the same fixed 36-case set and active company/version policies. The baseline is Chroma vector top-3. The current path retrieves hybrid dense + BM25 candidates over the active policy sections, applies local domain-aware reranking and selects the top 3. This measurement covers expected-section retrieval only; it excludes answer generation, the LLM and HTTP overhead.

Recorded comparison:

| Metric | Vector top-3 baseline | Hybrid + reranked top-3 |
|---|---:|---:|
| Expected-section recall@3 | 1.0000 | 1.0000 |
| Local retrieval p50 | 18.64 ms | 18.83 ms |
| Local retrieval p95 | 37.66 ms | 37.80 ms |
| Maximum local retrieval latency | 3,485.96 ms | 3,486.20 ms |

On this dataset, reranking produced **no measured recall@3 improvement**. Its recorded p50 and p95 overheads were small (0.19 ms and 0.14 ms respectively), while the maximum was dominated by a high-latency outlier. The hybrid approach is retained as a general retrieval strategy, but this experiment does not demonstrate an accuracy gain on this particular fixed set.

To reproduce the comparison after sample policies are initialized:

```powershell
python scripts/compare_retrieval.py
```

The script writes `data/evaluation/RETRIEVAL_COMPARISON.json`.

## 5. Live LLM Latency and Answer Quality

CommuteIQ is designed to support real-time policy queries using Groq LLM inference. The answer pipeline makes a **single LLM call per question**, with retries disabled, to reduce unnecessary inference overhead and avoid repeated generation attempts.

The current configuration uses an **8-second retrieval timeout** and an **8-second Groq client timeout**. These settings provide bounds for handling slow or unavailable services.

The offline evaluation measures local retrieval and deterministic answer generation. It does not represent the latency of the complete application with a live LLM.

The live benchmark can be executed with `LLM_PROVIDER=groq` and a valid `GROQ_API_KEY` configured in the existing `.env` file:

```powershell
python scripts/benchmark_live.py
```

This benchmark measures actual `/ask` response times, including HTTP overhead, retrieval, reranking and LLM generation. It warms up the system before collecting measurements.

The 3-second p95 target is an optimization objective for the live system. The single-call design and bounded timeouts help control inference overhead and failure duration. Actual performance depends on the LLM provider, selected model, network conditions, prompt size and generation time. The target should be confirmed using benchmark results from the deployment environment rather than inferred from offline measurements.

## 6. Safety and Reliability Decisions

- Employee company identity comes from the verified JWT; `/ask` has no tenant override.
- Admin ingestion, upload and policy listing are restricted to the company in the admin JWT.
- Chroma retrieval and the BM25 section scan are scoped to the authenticated company and active policy version.
- A new version's vectors are written before SQLite switches the active policy pointer. A vector-write failure therefore does not deactivate the previous active pointer. Old vector records are not returned by active-version retrieval.
- Citations are assembled from trusted retrieval metadata and capped at three.
- The model returns source IDs rather than citation strings. The backend verifies IDs against the retrieved candidate list and checks numeric values in the answer against cited evidence. This is a conservative lexical check, not a complete semantic proof.
- Obvious instruction-like lines in retrieved policy excerpts are scrubbed before model submission. User questions and retrieved excerpts are framed as untrusted data.
- Retrieval or LLM failures return a clear retry response. The model has no tools or authority over identity, policy activation or authorization.

## Known Limitations

- The fake evaluation answerer is intentionally deterministic and cannot establish real LLM answer quality.
- Automated expected-answer checks are used for consistent evaluation, while actual answers and citations are also manually reviewed to assess relevance, factual correctness and policy grounding. Manual review remains important for identifying semantic errors that automated checks may miss.
- The lexical post-generation check can reject valid paraphrases and cannot prove complete semantic entailment.
- The fixed evaluation has three known failures (T11, D04 and D11), described above.
- The 3-second live p95 target requires confirmation through real-provider benchmarking. Offline evaluation results cannot establish live LLM latency.
.