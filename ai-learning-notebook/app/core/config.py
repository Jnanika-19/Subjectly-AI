from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
FAISS_DIR = DATA_DIR / "faiss"

for directory in (DATA_DIR, UPLOAD_DIR, FAISS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    app_name: str = "Subjectly"
    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(DATA_DIR / 'study_assistant.db').as_posix()}"
    )
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "hf").lower()
    hf_embed_model: str = os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    openai_embed_model: str = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    chunk_words: int = int(os.getenv("CHUNK_WORDS", "380"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "60"))
    retrieve_top_k: int = int(os.getenv("RETRIEVE_TOP_K", "3"))
    retrieve_candidates: int = int(os.getenv("RETRIEVE_CANDIDATES", "10"))
    min_relevance_score: float = float(os.getenv("MIN_RELEVANCE_SCORE", "0.24"))


settings = Settings()
