from pydantic import BaseModel, Field

class TokenRequest(BaseModel):
    employee_id: str = Field(min_length=1, max_length=80)
    company_id: str = Field(min_length=2, max_length=40)

class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)

class IngestRequest(BaseModel):
    company_id: str = Field(min_length=2, max_length=40)
    version: str = Field(min_length=1, max_length=20)
    document: str = Field(min_length=1, max_length=120)
    effective_date: str | None = None
    text: str = Field(min_length=30, max_length=100000)
