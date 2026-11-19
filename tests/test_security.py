from app.core.security import create_token
import jwt
from app.core.config import JWT_SECRET, JWT_ALGORITHM

def test_token_contains_company_claim():
    token=create_token("emp-1","technova")
    payload=jwt.decode(token,JWT_SECRET,algorithms=[JWT_ALGORITHM])
    assert payload["company"]=="technova"

def test_token_company_is_not_client_question_field():
    token=create_token("emp-1","datasphere")
    payload=jwt.decode(token,JWT_SECRET,algorithms=[JWT_ALGORITHM])
    assert payload["company"]!="technova"
