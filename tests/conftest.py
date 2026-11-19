import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
import app.services.vector_store as vs

class FakeCollection:
    def __init__(self): self.rows={}
    def upsert(self,ids,documents,metadatas):
        for i,d,m in zip(ids,documents,metadatas): self.rows[i]=(d,m)
    def count(self):
        return len(self.rows)
    def query(self,query_texts,n_results,where):
        company=where['$and'][0]['company_id']; version=where['$and'][1]['version']
        q=set(query_texts[0].lower().split())
        rows=[(d,m) for d,m in self.rows.values() if m['company_id']==company and m['version']==version]
        rows.sort(key=lambda x:len(q & set(x[0].lower().split())),reverse=True)
        rows=rows[:n_results]
        return {'ids':[[str(i) for i in range(len(rows))]],
                'documents':[[x[0] for x in rows]],'metadatas':[[x[1] for x in rows]],
                'distances':[[0.2 for _ in rows]]}
    def get(self,where,include=None):
        company=where['$and'][0]['company_id']; version=where['$and'][1]['version']
        rows=[(d,m) for d,m in self.rows.values() if m['company_id']==company and m['version']==version]
        return {'documents':[x[0] for x in rows],'metadatas':[x[1] for x in rows]}

class FakeClient:
    def __init__(self): self.cols={}
    def get_or_create_collection(self,name,metadata=None):
        return self.cols.setdefault(name,FakeCollection())

@pytest.fixture(autouse=True)
def fake_chroma(monkeypatch,tmp_path):
    client=FakeClient()
    monkeypatch.setattr(vs,'_client',lambda:client)
    # Isolate sqlite state per test.
    import app.database.store as store
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'test.db')
    yield
