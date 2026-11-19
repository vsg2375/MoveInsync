import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

JWT_SECRET = os.getenv("JWT_SECRET", "local-demo-secret-change-me-please-32chars")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# External LLM and local retrieval have separate timeout budgets.
GROQ_TIMEOUT_SECONDS = float(os.getenv("GROQ_TIMEOUT_SECONDS", "8.0"))
RETRIEVAL_TIMEOUT_SECONDS = float(os.getenv("RETRIEVAL_TIMEOUT_SECONDS", "8.0"))

DB_PATH = ROOT / "data" / "commuteiq.db"
CHROMA_PATH = ROOT / "chroma_db"
POLICY_DIR = ROOT / "data" / "policies"
