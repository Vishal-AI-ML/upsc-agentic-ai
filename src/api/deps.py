"""Auth dependency - protects routes."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.core.security import decode_access_token
from src.core.db import get_db  # noqa: F401  re-exported for route convenience

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Validate JWT and return current user claims. Raises 401 if invalid.

    Returns {id, email, name}. `id` is the stable user id (token 'sub').
    """
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "id": payload["sub"],
        "email": payload.get("email", ""),
        "name": payload.get("name", ""),
    }
