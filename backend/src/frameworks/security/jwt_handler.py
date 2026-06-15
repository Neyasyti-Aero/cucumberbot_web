from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from config import settings


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str


def create_token_pair(user_id: str, role: str) -> TokenPair:
    now = datetime.now(timezone.utc)
    access_payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    refresh_payload = {
        "sub": user_id,
        "role": role,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    return TokenPair(
        access_token=jwt.encode(access_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm),
        refresh_token=jwt.encode(refresh_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Недействительный токен") from exc
