"""Chroma adapter. Each company/version gets a distinct collection; metadata is also filtered server-side."""
from functools import lru_cache
import logging
import os
from app.core.config import CHROMA_PATH

@lru_cache(maxsize=1)
def _client():
    # Disable Chroma telemetry before importing/initializing its client. Some
    # Chroma/PostHog combinations emit a harmless capture() signature warning.
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    for logger_name in (
        "chromadb.telemetry",
        "chromadb.telemetry.product",
        "chromadb.telemetry.product.posthog",
    ):
        logging.getLogger(logger_name).disabled = True
    import chromadb
    from chromadb.config import Settings
    return chromadb.PersistentClient(
        path=str(CHROMA_PATH),
        settings=Settings(anonymized_telemetry=False),
    )

def _collection(company_id: str):
    safe = ''.join(ch for ch in company_id.lower() if ch.isalnum() or ch == '-')[:40]
    return _client().get_or_create_collection(f"policy-{safe}", metadata={"hnsw:space":"cosine"})

def replace_company_chunks(company_id: str, version: str, chunks: list[dict]):
    col = _collection(company_id)
    # Add new version first; caller switches SQLite active pointer only after successful add.
    ids = [f"{version}-{i}" for i in range(len(chunks))]
    col.upsert(ids=ids, documents=[x["text"] for x in chunks],
               metadatas=[{"company_id":company_id,"version":version,"section":x["section"],"document":x["document"]} for x in chunks])

def search(company_id: str, version: str, query: str, k: int = 3):
    col = _collection(company_id)
    # Chroma rejects no request here, but logs a warning when n_results is
    # larger than the entire collection. Clamp before querying so small
    # collections (including freshly ingested policies) stay quiet.
    collection_size = col.count()
    if collection_size <= 0:
        return []
    requested = max(1, min(int(k), 30, collection_size))
    result = col.query(query_texts=[query], n_results=requested,
                       where={"$and":[{"company_id":company_id},{"version":version}]})
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    return [{"text":d,"metadata":m,"distance":distances[i] if i < len(distances) else None} for i,(d,m) in enumerate(zip(docs,metas))]



def hybrid_search(company_id: str, version: str, query: str, k: int = 20):
    """Return active-version chunks with dense distances for hybrid reranking.

    Chroma's dense top-k is combined with a metadata-filtered read of all
    sections in the active version. The caller applies BM25 + dense reranking.
    No other tenant or version is read or returned.
    """
    col = _collection(company_id)
    where = {"$and": [{"company_id": company_id}, {"version": version}]}
    dense = search(company_id, version, query, k)
    dense_distances = {}
    for item in dense:
        meta = item.get("metadata", {})
        key = (meta.get("document"), meta.get("section"), item.get("text"))
        dense_distances[key] = item.get("distance")

    result = col.get(where=where, include=["documents", "metadatas"])
    documents = result.get("documents", []) or []
    metadatas = result.get("metadatas", []) or []
    chunks = []
    for document, metadata in zip(documents, metadatas):
        key = (metadata.get("document"), metadata.get("section"), document)
        chunks.append({
            "text": document,
            "metadata": metadata,
            "distance": dense_distances.get(key),
        })
    return chunks


def version_chunk_count(company_id: str, version: str) -> int:
    """Count indexed chunks for one company/version without reading other tenants."""
    col = _collection(company_id)
    result = col.get(
        where={"$and": [{"company_id": company_id}, {"version": version}]},
        include=["metadatas"],
    )
    return len(result.get("ids", []) or result.get("documents", []) or [])
