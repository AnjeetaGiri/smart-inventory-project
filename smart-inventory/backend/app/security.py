from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from typing import Optional
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import JWT_SECRET, ACCESS_TOKEN_MINUTES, REFRESH_TOKEN_DAYS

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def create_token(subject: str, token_type: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": subject, "type": token_type, "iat": now, "exp": now + lifetime}, JWT_SECRET, algorithm="HS256")


def token_pair(username: str) -> dict:
    return {
        "access_token": create_token(username, "access", timedelta(minutes=ACCESS_TOKEN_MINUTES)),
        "refresh_token": create_token(username, "refresh", timedelta(days=REFRESH_TOKEN_DAYS)),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
    }


def current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> str:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Access token required")
        return payload["sub"]
    except (jwt.InvalidTokenError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
