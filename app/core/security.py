from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.settings import settings

password_hasher = PasswordHash.recommended()

def hash_password(plain_password: str) -> str:
    return password_hasher.hash(plain_password)

DUMMY_PASSWORD_HASH = hash_password("dummy-password-not-for-login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hasher.verify(plain_password, hashed_password)

JWT_ALGORITHM = "HS256"
def create_access_token(user_id:int) -> str:
    now = datetime.now(UTC)
    payload ={
        "sub":str(user_id),
        "iat":now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY.get_secret_value(), JWT_ALGORITHM)

def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, key=settings.JWT_SECRET_KEY.get_secret_value(), algorithms=JWT_ALGORITHM,
                    options={"require": ["sub","iat","exp"]})
