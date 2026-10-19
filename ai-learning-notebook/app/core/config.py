from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
DATA_DIR = Path(os.getenv("SUBJECTLY_DATA_DIR", str(PROJECT_ROOT / "data"))).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
FAISS_DIR = DATA_DIR / "faiss"

for directory in (DATA_DIR, UPLOAD_DIR, FAISS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


class Settings:
    app_name: str = "Subjectly"
    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(DATA_DIR / 'study_assistant.db').as_posix()}"
    )
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "hf").lower()
    hf_embed_model: str = os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    ai_provider: str = os.getenv(
        "AI_PROVIDER", "openrouter" if os.getenv("OPENROUTER_API_KEY") else "groq"
    ).lower()
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_embed_model: str = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    chunk_words: int = int(os.getenv("CHUNK_WORDS", "380"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "60"))
    retrieve_top_k: int = int(os.getenv("RETRIEVE_TOP_K", "3"))
    retrieve_candidates: int = int(os.getenv("RETRIEVE_CANDIDATES", "10"))
    min_relevance_score: float = float(os.getenv("MIN_RELEVANCE_SCORE", "0.24"))
    login_email: str = os.getenv("SUBJECTLY_LOGIN_EMAIL", "").strip().lower()
    login_password_hash: str = os.getenv("SUBJECTLY_LOGIN_PASSWORD_HASH", "").strip()
    session_secret: str = os.getenv("SUBJECTLY_SESSION_SECRET", "").strip()
    session_cookie_secure: bool = os.getenv("SUBJECTLY_SESSION_COOKIE_SECURE", "false").lower() == "true"


settings = Settings()
