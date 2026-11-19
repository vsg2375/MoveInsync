from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import JWT_SECRET, JWT_ALGORITHM

bearer = HTTPBearer(auto_error=False)

def create_token(employee_id: str, company_id: str, role: str = "employee") -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": employee_id, "company": company_id, "role": role,
                       "iat": now, "exp": now + timedelta(hours=8)}, JWT_SECRET, algorithm=JWT_ALGORITHM)

def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Bearer token required")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if not payload.get("company") or not payload.get("sub"):
            raise ValueError("missing claims")
        return {"employee_id": payload["sub"], "company_id": payload["company"], "role": payload.get("role", "employee")}
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
