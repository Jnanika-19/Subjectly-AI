from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from dotenv import dotenv_values
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import PROJECT_ROOT, settings
from app.db.database import get_db
from app.models.models import User
from app.services.auth_service import (
    COOKIE_NAME,
    SESSION_MAX_AGE,
    configuration_ready,
    create_session,
    verify_password,
    hash_password,
)


router = APIRouter()


def refresh_auth_settings() -> None:
    """Pick up account settings edited in .env without restarting local Uvicorn."""
    values = dotenv_values(PROJECT_ROOT / ".env")
    for key, attribute in (
        ("SUBJECTLY_LOGIN_EMAIL", "login_email"),
        ("SUBJECTLY_LOGIN_PASSWORD_HASH", "login_password_hash"),
        ("SUBJECTLY_SESSION_SECRET", "session_secret"),
    ):
        value = values.get(key)
        if value and value.strip():
            setattr(settings, attribute, value.strip().lower() if attribute == "login_email" else value.strip())


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=1024)


@router.post("/auth/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    refresh_auth_settings()
    if not settings.session_secret:
        raise HTTPException(
            status_code=503,
            detail="Sign-in is not configured. Set SUBJECTLY_SESSION_SECRET in .env.",
        )
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")

    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session(user.id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"message": "Signed in."}


@router.post("/auth/register")
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    refresh_auth_settings()
    if not settings.session_secret:
        raise HTTPException(status_code=503, detail="Sign-in is not configured. Set SUBJECTLY_SESSION_SECRET in .env.")
    email = payload.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    db.refresh(user)
    response.set_cookie(key=COOKIE_NAME, value=create_session(user.id), max_age=SESSION_MAX_AGE,
                        httponly=True, secure=settings.session_cookie_secure, samesite="lax", path="/")
    return {"message": "Account created."}


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax")
    return {"message": "Signed out."}
