from contextlib import asynccontextmanager
import logging
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from app.core.security import create_token, current_user
from app.schemas.api import TokenRequest, QuestionRequest, IngestRequest
from app.database.store import init_db, active_policy, list_policies
from app.services.policy_service import ingest_text, load_pdf, parse_policy
from app.services.answer_service import answer_question, RETRY, CrossTenantMentionError
from app.core.config import POLICY_DIR
from app.services.vector_store import replace_company_chunks, version_chunk_count

logger = logging.getLogger("commuteiq")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    samples = [
        ("technova", "1.0", "technova_policy_v1.pdf"),
        ("datasphere", "1.0", "datasphere_policy_v1.pdf"),
        ("cloudaxis", "1.0", "cloudaxis_policy_v1.pdf"),
    ]
    for company, version, filename in samples:
        current = active_policy(company)
        if not current:
            path = POLICY_DIR / filename
            if not path.exists():
                raise RuntimeError(f"Required sample policy is missing: {path}")
            ingest_text(company, version, filename, load_pdf(path), "2026-10-01")
            current = active_policy(company)
        if current and version_chunk_count(company, current["version"]) == 0:
            source = POLICY_DIR / Path(current["document"]).name
            if not source.exists():
                raise RuntimeError(f"Active policy source PDF is missing: {source}")
            chunks = parse_policy(load_pdf(source), current["document"])
            replace_company_chunks(company, current["version"], chunks)

    current = active_policy("technova")
    if current and current["version"] == "1.0":
        path = POLICY_DIR / "technova_policy_v2.pdf"
        if not path.exists():
            raise RuntimeError(f"Required sample policy is missing: {path}")
        ingest_text("technova", "2.0", path.name, load_pdf(path), "2026-11-01")
    yield

app = FastAPI(title="CommuteIQ – Commute Policy Assistant", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173"],
    allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.get("/")
def home():
    return {"name": "CommuteIQ", "status": "running", "docs": "/docs"}

@app.get("/health")
def health():
    companies = ("technova", "datasphere", "cloudaxis")
    missing = [company for company in companies if not active_policy(company)]
    if missing:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "missing_policies": missing})
    return {"status": "healthy", "active_companies": len(companies)}

@app.post("/auth/demo-token")
def demo_token(body: TokenRequest):
    return {"access_token": create_token(body.employee_id, body.company_id), "token_type": "bearer"}

@app.post("/ask")
async def ask(body: QuestionRequest, user=Depends(current_user)):
    try:
        result = await answer_question(user["company_id"], body.question)
        return {**result, "company_id": user["company_id"], "employee_id": user["employee_id"]}
    except CrossTenantMentionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception:
        logger.exception("Policy answer request failed")
        raise HTTPException(status_code=503, detail=RETRY)

@app.post("/admin/policies/ingest")
def ingest(body: IngestRequest, user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    if body.company_id != user["company_id"]:
        raise HTTPException(status_code=403, detail="Admin token cannot manage another company")
    try:
        return ingest_text(body.company_id, body.version, body.document, body.text, body.effective_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Policy ingestion failed")
        raise HTTPException(status_code=503, detail=RETRY)

@app.post("/admin/policies/upload")
async def upload(company_id: str, version: str, document: str, effective_date: str | None = None,
                 file: UploadFile = File(...), user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    if company_id != user["company_id"]:
        raise HTTPException(status_code=403, detail="Admin token cannot manage another company")
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Upload a PDF policy")
    raw = await file.read(5_000_001)
    if len(raw) > 5_000_000:
        raise HTTPException(status_code=413, detail="PDF exceeds 5 MB")
    from pypdf import PdfReader
    import io
    try:
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read the uploaded PDF")
    try:
        return ingest_text(company_id, version, document, text, effective_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Policy ingestion failed")
        raise HTTPException(status_code=503, detail=RETRY)

@app.get("/admin/policies")
def policies(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return list_policies(user["company_id"])
