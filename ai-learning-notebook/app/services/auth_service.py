from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from getpass import getpass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.models import User


COOKIE_NAME = "subjectly_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7
PASSWORD_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
    )


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds_text, salt_text, digest_text = encoded.split("$", 3)
        rounds = int(rounds_text)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= rounds <= 2_000_000:
            return False
        salt = _decode(salt_text)
        expected = _decode(digest_text)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(actual, expected)


def configuration_ready() -> bool:
    return bool(settings.login_email and settings.login_password_hash and settings.session_secret)


def create_session(user_id: int) -> str:
    expires = str(int(time.time()) + SESSION_MAX_AGE)
    subject = str(user_id)
    payload = f"{subject}.{expires}"
    signature = hmac.new(settings.session_secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    return f"{payload}.{base64.urlsafe_b64encode(signature).decode('ascii').rstrip('=')}"


def session_user_id(token: str | None) -> int | None:
    if not token or not settings.session_secret:
        return None
    try:
        subject, expires, signature_text = token.split(".", 2)
        payload = f"{subject}.{expires}"
        expected = hmac.new(settings.session_secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode(signature_text)) or int(expires) < int(time.time()):
            return None
        return int(subject)
    except (ValueError, UnicodeDecodeError):
        return None


def current_user_id(request: Request) -> int | None:
    return session_user_id(request.cookies.get(COOKIE_NAME))


def is_authenticated(request: Request) -> bool:
    user_id = current_user_id(request)
    if user_id is None:
        return False
    from app.db.database import SessionLocal
    with SessionLocal() as db:
        return db.query(User.id).filter(User.id == user_id).first() is not None


def require_login(request: Request, db: Session = Depends(get_db)) -> None:
    user_id = current_user_id(request)
    if user_id is None or db.query(User.id).filter(User.id == user_id).first() is None:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    request.state.user_id = user_id


if __name__ == "__main__":
    first = getpass("Choose a Subjectly password: ")
    second = getpass("Confirm password: ")
    if len(first) < 12:
        raise SystemExit("Use at least 12 characters for the password.")
    if not hmac.compare_digest(first, second):
        raise SystemExit("The passwords did not match.")
    print("Add this line to your .env file:\nSUBJECTLY_LOGIN_PASSWORD_HASH=" + hash_password(first))
