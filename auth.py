"""
auth.py — JWT-авторизация и хеширование паролей.
"""

import hashlib
import jwt
import time

SECRET = "starch-secret-change-me-in-prod"
ALGO = "HS256"
TOKEN_TTL = 60 * 60 * 24 * 30


def hash_password(пароль: str) -> str:
    соль = "starch_salt_v1"
    return hashlib.sha256((соль + пароль).encode()).hexdigest()


def create_token(user_id: int) -> str:
    payload = {"user_id": user_id, "exp": int(time.time()) + TOKEN_TTL}
    return jwt.encode(payload, SECRET, algorithm=ALGO)


def verify_token(токен: str):
    try:
        payload = jwt.decode(токен, SECRET, algorithms=[ALGO])
        return payload.get("user_id")
    except jwt.PyJWTError:
        return None