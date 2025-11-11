from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
import os
os.environ["PASSLIB_PURE_PYTHON"] = "true"

JWT_SECRET = "super-secret-key-change-me"
JWT_ALG = "HS256"
JWT_EXPIRE_MIN = 120

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    """
    bcrypt는 최대 72바이트까지만 허용.
    초과할 경우 자동으로 잘라내어 해싱.
    """
    if not isinstance(plain, str):
        plain = str(plain)

    if len(plain.encode("utf-8")) > 72:
        plain = plain.encode("utf-8")[:72].decode("utf-8", errors="ignore")

    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(sub: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MIN)
    payload = {"sub": sub, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
