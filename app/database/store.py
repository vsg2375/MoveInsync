import sqlite3
from app.core.config import DB_PATH

SCHEMA = '''
CREATE TABLE IF NOT EXISTS companies(company_id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS policies(
 id INTEGER PRIMARY KEY AUTOINCREMENT, company_id TEXT NOT NULL, version TEXT NOT NULL,
 document TEXT NOT NULL, effective_date TEXT, status TEXT NOT NULL CHECK(status IN ('active','inactive')),
 created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(company_id, version));
'''

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with connect() as c:
        c.executescript(SCHEMA)

def active_policy(company_id):
    with connect() as c:
        row = c.execute("SELECT * FROM policies WHERE company_id=? AND status='active' ORDER BY id DESC LIMIT 1", (company_id,)).fetchone()
        return dict(row) if row else None

def list_policies(company_id: str | None = None):
    with connect() as c:
        if company_id:
            rows = c.execute("SELECT * FROM policies WHERE company_id=? ORDER BY id", (company_id,))
        else:
            rows = c.execute("SELECT * FROM policies ORDER BY company_id,id")
        return [dict(row) for row in rows]

def company_names():
    """Return company IDs/names for the DB-only cross-tenant mention guard."""
    with connect() as c:
        try:
            rows = c.execute("SELECT company_id,name FROM companies ORDER BY company_id").fetchall()
        except sqlite3.OperationalError:
            # Unit tests may exercise retrieval before initializing the schema.
            return []
        return [(row["company_id"], row["name"]) for row in rows]
