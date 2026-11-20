### Case Study - B

# CommuteIQ — Commute Policy Assistant

CommuteIQ is a multi-tenant commute-policy assistant built for the MoveInSync AI Developer Campus Case Study B. It uses FastAPI, SQLite, ChromaDB, hybrid retrieval (dense + BM25), Groq LLM integration, JWT-based tenant isolation and a React/Vite frontend.

## Demo Video

[Watch the CommuteIQ Demo](https://drive.google.com/file/d/1DJQHMSQeRGcBiee4bMurRc1dXd6s3J25/view?usp=sharing)

## 1. Quick Evaluation — Start Here

### A. Start the complete application

**Prerequisite:** Docker Desktop with Docker Compose v2.24.0 or newer.

From the repository root, run:

```bash
docker compose up --build
```

Wait for the backend health check to pass. The backend initializes the bundled sample policies and their Chroma indexes during startup.

Keep this terminal running.

### B. Run automated tests

Open a second terminal at the repository root. Use Python 3.11:

```bash
python -m pip install -r requirements.txt
python -m pytest -v tests
```

The test suite covers JWT authentication, tenant isolation, admin authorization, prompt-injection checks, policy parsing, retrieval, reranking, evidence-based answers and citation constraints.

### C. Run the fixed JSONL evaluation

In the second terminal:

```bash
docker compose exec backend python scripts/run_evaluation.py
```

The fixed dataset is `data/evaluation/questions.jsonl` and contains 36 cases. Each record uses exactly these fields:

`id`, `input`, `expected`, `actual`, `pass`, `notes`

The runner generates:

- `data/evaluation/results.jsonl`
- `data/evaluation/LAST_RUN_REPORT.json`

The evaluation uses active-policy selection, company/version-filtered Chroma retrieval, reranking and a deterministic fake answerer. It does not call the live `/ask` endpoint or an external LLM provider.

See `data/evaluation/EVALUATION_REPORT.md` for the recorded results, failed cases and retrieval comparison.

**Note:** Running the evaluation regenerates its result files. Keep the original question set unchanged when comparing results.

### D. Open the frontend

After the startup and verification steps:

- Employee/admin frontend: http://localhost:5173
- Backend health: http://localhost:8000/health
- Swagger API documentation: http://localhost:8000/docs

Press `Ctrl+C` to stop the services. To remove containers while retaining mounted policy/database data:

```bash
docker compose down
```

## 2. Environment Configuration

A `.env` file is **not required** to start the application and is intentionally not committed to GitHub. Docker Compose treats it as optional.

Without `.env`, the backend uses its local default configuration with `LLM_PROVIDER=none`. The application can demonstrate policy retrieval using its local extractive answer client. This mode does not make live Groq requests.

To enable live Groq responses, create a private root-level `.env` file:

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant
JWT_SECRET=replace_with_a_random_secret_of_at_least_32_characters
```

Optional timeout settings are `GROQ_TIMEOUT_SECONDS` and `RETRIEVAL_TIMEOUT_SECONDS` (both default to 8 seconds).

Never commit `.env`, API keys or production secrets to GitHub. The default JWT secret is for local demonstration only.

## 3. Employee Assistant Demonstration

1. Open http://localhost:5173.
2. Select a demo employee ID (for example, `emp-101`).
3. Select one of the fictional companies: TechNova, DataSphere or CloudAxis.
4. Continue as an employee. The frontend calls `POST /auth/demo-token` and receives a demo JWT.
5. Ask a commute-policy question and inspect the answer, active policy version and document/section citations.
6. Unsupported questions are directed to the transport desk rather than answered as policy facts.

The company identity used by `/ask` is taken from the verified JWT. The question request does not accept a client-selected company override.

## 4. Policy Administration Demonstration

The policy administration page requires a JWT with `role=admin`. Employee tokens are not accepted. An admin token is scoped to one company; ingestion, PDF upload and policy listing cannot be used to manage another company.

For a local demonstration, generate an admin token from the repository root:

```bash
python scripts/create_admin_token.py --employee-id admin-1 --company-id technova
```

Paste the generated token into the Policy Administration page. You can inspect the policy register or upload a new PDF version. The upload endpoint accepts PDF files up to 5 MB.

The admin-token helper and demo employee-token endpoint are development conveniences, not production identity management.

## 5. Architecture and Trust Boundaries

- **Authentication and tenant isolation:** `/ask` requires a signed bearer token. Employee and company identity come from verified JWT claims, not user-controlled request fields.
- **Admin authorization:** Admin operations require an admin-role token and enforce that the requested company matches the company in the token.
- **Policy versioning:** Policy documents are parsed and validated before activation. New-version chunks are written before SQLite switches the active policy pointer. Retrieval is restricted to the authenticated company and active version.
- **Hybrid retrieval:** Chroma dense retrieval is combined with BM25 over sections from the active company/version using reciprocal-rank fusion. A relevance gate limits the evidence passed to answer generation to at most three chunks.
- **Grounded citations:** The model returns source IDs rather than free-form citation strings. The backend validates those IDs against retrieved candidates, checks numeric values against cited evidence and builds citations from trusted metadata.
- **Prompt-injection handling:** User questions and policy excerpts are treated as untrusted data. Obvious instruction-like lines in retrieved excerpts are scrubbed before model submission.
- **Failure handling:** Retrieval and LLM operations have separate configurable timeouts. The live answer path makes one LLM call with retries disabled. Invalid or ungrounded output fails closed.

## 6. Design Decisions and Trade-offs

- **Tenant isolation over convenience:** Company identity is derived from the signed JWT and enforced in metadata lookup and retrieval. This prevents a client from switching tenants through a request parameter.
- **At most three evidence chunks:** Limiting context reduces prompt size and irrelevant passages, but a relevant fact split across distant sections may be missed.
- **Conservative answer validation:** Invalid citations and unsupported numeric claims are rejected. This improves grounding but can reject valid paraphrases.
- **One LLM call, no retry:** This reduces duplicate inference and helps bound request cost and latency. The trade-off is that malformed or ungrounded output returns a retryable error rather than attempting a second generation.
- **SQLite and local Chroma for the prototype:** These keep the case-study deployment simple. A production multi-instance deployment would need shared/scalable persistence, stronger identity management and operational monitoring.

## 7. API Summary

| Endpoint | Purpose | Access |
|---|---|---|
| `GET /health` | Health check | Public |
| `POST /auth/demo-token` | Issue local demo employee JWT | Public, demo only |
| `POST /ask` | Ask a policy question | Employee JWT |
| `GET /admin/policies` | List policies for the token's company | Admin JWT |
| `POST /admin/policies/ingest` | Ingest plain-text policy | Admin JWT |
| `POST /admin/policies/upload` | Upload a PDF policy | Admin JWT |

## 8. Optional Technical Experiments

### Live LLM latency benchmark

To measure actual `/ask` latency, configure the private `.env` with `LLM_PROVIDER=groq` and a valid `GROQ_API_KEY`, then restart the backend.

Run:

```bash
python scripts/benchmark_live.py
```

The script obtains a demo employee token, performs one warm-up request, then measures real `/ask` requests, including HTTP overhead, retrieval, reranking and LLM generation.

It reports p50, p95, maximum latency and failures. The 3-second p95 target must be verified using real-provider benchmark results. Offline evaluation does not establish live latency.

### Retrieval comparison

After the sample policies are initialized, run:

```bash
docker compose exec backend python scripts/compare_retrieval.py
```

This compares vector top-3 retrieval with the hybrid dense + BM25 and reranked top-3 path. It writes `data/evaluation/RETRIEVAL_COMPARISON.json`.

The comparison measures expected-section retrieval and local retrieval latency only; it excludes answer generation, the LLM and HTTP overhead.

## 9. Project Structure

```text
CommuteIQ/
├── app/
│   ├── core/              Configuration and JWT security
│   ├── database/          SQLite policy metadata store
│   └── services/          Policy ingestion, retrieval and answers
├── data/
│   ├── policies/          Fictional policy PDF fixtures
│   └── evaluation/        Questions, results and evaluation report
├── frontend/              React/Vite employee and admin interface
├── scripts/               Evaluation, benchmarks and admin token
├── tests/                 Automated backend tests
├── Dockerfile             Backend image
├── docker-compose.yml     One-command local deployment
├── requirements.txt
└── README.md
```


The bundled policies are fictional case-study fixtures, not real customer policies. The prototype does not implement enterprise SSO, production role provisioning, audit logging or distributed production storage.