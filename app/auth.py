"""
Authentication & Role-Based Access Control (RBAC) Module
=========================================================
Implements Ferraiolo & Kuhn's RBAC security model with cryptographic
password hashing (bcrypt) and stateless JWT bearer token verification.
"""

import os
import time
from typing import Optional, Dict, Any, List
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database.db import get_connection

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "restaurant_dbms_ultra_secure_jwt_secret_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 86400  # 24 hours

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Generates a secure bcrypt hash for passwords."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: Dict[str, Any]) -> str:
    """Creates a JWT access token containing user identity and role claim."""
    to_encode = data.copy()
    expire = time.time() + ACCESS_TOKEN_EXPIRE_SECONDS
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """Dependency to retrieve and authenticate the current user from Bearer token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.UserID, u.Username, u.EmployeeID, u.RoleID, r.RoleName, s.Name AS StaffName, s.IsActive
        FROM Users u
        JOIN Roles r ON u.RoleID = r.RoleID
        JOIN Staff s ON u.EmployeeID = s.EmployeeID
        WHERE u.UserID = ?;
    """, (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account no longer exists.")
    if not user["IsActive"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Personnel account is retired / inactive.")

    return dict(user)


def require_roles(allowed_roles: List[str]):
    """RBAC Guard: Restricts endpoint access strictly to specified role names."""
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_role = current_user.get("RoleName")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Role '{user_role}' lacks required permissions. Expected one of: {allowed_roles}."
            )
        return current_user
    return role_checker
