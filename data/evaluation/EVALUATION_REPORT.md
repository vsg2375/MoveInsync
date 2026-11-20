# CommuteIQ — Evaluation Report

## 1. Evaluation Design

The fixed evaluation set contains **36 questions** derived from the TechNova, DataSphere and CloudAxis policy PDFs.

It covers:
- Employee eligibility, night transport, escorts, booking rules, cost limits, weekends, guests and cancellations.
- Company-specific and contradictory policy rules.
- Unsupported questions and cross-company access attempts.
- Prompt-injection attempts and paraphrased questions.

Each JSONL record contains exactly six fields: `id`, `input`, `expected`, `actual`, `pass` and `notes`.

The evaluation uses active-policy selection, company/version-filtered ChromaDB retrieval, hybrid retrieval, reranking and a deterministic evidence-only answerer. It checks expected facts, coverage classification, citations and tenant ownership.

Run the evaluation using:

```powershell
docker compose exec backend python scripts/run_evaluation.py
```

Results are saved in `data/evaluation/results.jsonl` and `data/evaluation/LAST_RUN_REPORT.json`.

## 2. Evaluation Results

The recorded evaluation achieved **33 passed and 3 failed cases out of 36 (91.7%)**.

| Metric | Result |
|---|---:|
| Total cases | 36 |
| Passed | 33 |
| Failed | 3 |
| Pass rate | 91.7% |
| Coverage classification accuracy | 91.7% |
| Expected-section retrieval and citation accuracy on covered cases | 100% |
| Citation check accuracy | 100% |
| Local evaluation p50 | 34.6 ms |
| Local evaluation p95 | 120.8 ms |

The evaluation is deterministic and offline. It does not call the live `/ask` endpoint or an external LLM. Therefore, its latency represents the local retrieval-and-answer path, not complete application response time.

### Known Failures

- **T11 — Inter-city reimbursement:** Correctly identifies that air and rail reimbursement is unspecified, but includes unrelated reimbursement details.
- **D04 — Contractor eligibility:** Retrieves guest restrictions and general employee rules instead of a precise contractor-specific response.
- **D11 — Airport reimbursement:** Identifies that home-to-airport reimbursement is undefined, but includes unrelated policy details.

All three failures are retained in the evaluation results.

## 3. Automated Tests

Run the test suite using:

```powershell
python -m pytest -v tests
```

The tests cover API contracts, JWT tenant isolation, admin authorization, prompt injection, policy parsing, retrieval, reranking, evidence validation and citation constraints.

## 4. Retrieval Comparison and Trade-off

The baseline Chroma vector retrieval was compared with hybrid dense + BM25 retrieval and reranking on the same 36 cases.

| Metric | Vector baseline | Hybrid + reranking |
|---|---:|---:|
| Expected-section recall@3 | 100% | 100% |
| Local p50 latency | 18.64 ms | 18.83 ms |
| Local p95 latency | 37.66 ms | 37.80 ms |

**Trade-off:** Hybrid retrieval combines semantic similarity with keyword matching. This improves the range of matching signals and handles policy terminology and paraphrases more flexibly, but adds ranking complexity and a small processing overhead. No recall improvement was measured on this particular dataset, so the approach is retained for its general retrieval flexibility rather than a demonstrated benchmark gain.

Reproduce the comparison using:

```powershell
docker compose exec backend python scripts/compare_retrieval.py
```

## 5. Safety and Reliability

- Employee identity and company scope are derived from the verified JWT.
- Admin operations are restricted to the admin's company.
- Retrieval is filtered by company and active policy version.
- Policy version activation is managed through SQLite, preserving the previous active version if new vector ingestion fails.
- Citations are generated from trusted metadata and limited to three.
- Model-provided source IDs and numeric claims are validated against retrieved evidence.
- User questions and retrieved policy content are treated as untrusted input.
- Retrieval and LLM failures return a retry response rather than an unsupported answer.

## 6. Technical Limitations and Future Improvements

- Related policy sections can sometimes introduce irrelevant information into answers.
- Ambiguous or incomplete policy wording can make precise eligibility decisions difficult.
- Poorly structured PDF documents may affect parsing and retrieval.
- The current SQLite and ChromaDB setup may require distributed storage and infrastructure for larger deployments.
- A broader evaluation dataset would improve confidence across additional real-world queries.

Future improvements include more precise evidence selection, stronger semantic validation, broader evaluation coverage and scalability improvements.

## 7. Live Demonstration

The application supports real-time policy queries using Groq LLM inference, with one LLM call per question.

During the live demonstration, real policy questions will be tested through the application to observe answer quality, citations and end-to-end response latency. The live benchmark can also be run using:

```powershell
python scripts/benchmark_live.py
```

This allows performance to be evaluated against the **3-second p95 response-time target** using the real LLM provider.

## 8. Conclusion

CommuteIQ demonstrates a multi-tenant commute-policy assistant with company-scoped retrieval, policy versioning, JWT-based access control and evidence-grounded answers.

The recorded evaluation achieved **91.7% accuracy (33/36 cases)**, with known failures retained transparently. The design prioritizes tenant isolation, traceable evidence and conservative failure handling, while leaving opportunities for improved retrieval precision and scalability.