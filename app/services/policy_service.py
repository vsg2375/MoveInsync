import re
from pathlib import Path
from pypdf import PdfReader
from app.database.store import connect
from app.services.vector_store import replace_company_chunks

SECTION_RE = re.compile(r"(?m)^\s*(\d+)\.\s+([^\n]+)")

def parse_policy(text: str, document: str):
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', text).strip()
    matches = list(SECTION_RE.finditer(text))
    if not matches: raise ValueError("Policy must contain numbered sections (for example, '1. Scope').")
    chunks=[]
    for i,m in enumerate(matches):
        body=text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
        body=re.sub(r"\s+", " ", body)
        if body:
            chunks.append({"section":f"{m.group(1)}. {m.group(2).strip()}","text":body,"document":document})
    if not chunks: raise ValueError("No usable policy sections found")
    return chunks

def ingest_text(company_id: str, version: str, document: str, text: str, effective_date: str | None = None):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{2,40}", company_id): raise ValueError("Invalid company_id")
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,20}", version): raise ValueError("Invalid version")
    chunks=parse_policy(text, document)
    with connect() as c:
        if c.execute("SELECT 1 FROM policies WHERE company_id=? AND version=?", (company_id,version)).fetchone():
            raise ValueError("This company/version already exists")
    # Prepare vectors before changing the active SQLite pointer. A failed vector write leaves old active policy intact.
    replace_company_chunks(company_id, version, chunks)
    with connect() as c:
        c.execute("INSERT OR IGNORE INTO companies(company_id,name) VALUES(?,?)", (company_id, company_id))
        c.execute("UPDATE policies SET status='inactive' WHERE company_id=? AND status='active'",(company_id,))
        c.execute("INSERT INTO policies(company_id,version,document,effective_date,status) VALUES(?,?,?,?, 'active')",
                  (company_id,version,document,effective_date))
    return {"company_id":company_id,"version":version,"chunks":len(chunks),"status":"active"}

def load_pdf(path: Path):
    reader=PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
