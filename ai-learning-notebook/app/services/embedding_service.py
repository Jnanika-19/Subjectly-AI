from __future__ import annotations

import json
import logging
from pathlib import Path
import time
from typing import Any

import faiss
import numpy as np
import requests
from sqlalchemy.orm import Session

from app.core.config import FAISS_DIR, settings
from app.models.models import Chunk
from app.utils.text import keyword_overlap_score, stable_hash


logger = logging.getLogger(__name__)


class EmbeddingService:
    dimension = 256
    _hf_model: Any = None
    _embedding_retry_after = 0.0

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype="float32")
        if settings.embedding_provider == "hf":
            return self._hf_embeddings(texts)
        if settings.embedding_provider == "openai":
            if not settings.openai_api_key.strip():
                raise RuntimeError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai.")
            return self._openai_embeddings(texts)
        if settings.embedding_provider == "mock":
            return self._mock_embeddings(texts)
        raise RuntimeError(
            f"Unsupported EMBEDDING_PROVIDER: {settings.embedding_provider}. Choose hf, openai, or mock."
        )

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_texts([text])[0]

    def _openai_embeddings(self, texts: list[str]) -> np.ndarray:
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_embed_model,
                "input": texts,
                "encoding_format": "float",
            },
            timeout=60,
        )
        response.raise_for_status()
        vectors = [item["embedding"] for item in response.json()["data"]]
        array = np.array(vectors, dtype="float32")
        self.dimension = array.shape[1]
        return array

    def _mock_embeddings(self, texts: list[str]) -> np.ndarray:
        matrix = []
        for text in texts:
            vector = np.zeros(self.dimension, dtype="float32")
            for token in text.lower().split():
                vector[stable_hash(token) % self.dimension] += 1.0
            norm = np.linalg.norm(vector)
            matrix.append(vector / norm if norm else vector)
        return np.array(matrix, dtype="float32")

    def _hf_embeddings(self, texts: list[str]) -> np.ndarray:
        model = self._get_hf_model()
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        array = np.array(vectors, dtype="float32")
        self.dimension = array.shape[1]
        return array

    def rebuild_subject_index(self, db: Session, subject_id: int) -> None:
        chunks = (
            db.query(Chunk)
            .filter(Chunk.subject_id == subject_id)
            .order_by(Chunk.id.asc())
            .all()
        )
        if not chunks:
            self.index_path(subject_id).unlink(missing_ok=True)
            self.metadata_path(subject_id).unlink(missing_ok=True)
            return
        vectors = self.embed_texts([chunk.content for chunk in chunks])
        faiss.normalize_L2(vectors)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss.write_index(index, str(self.index_path(subject_id)))
        self.metadata_path(subject_id).write_text(
            json.dumps([chunk.id for chunk in chunks], indent=2), encoding="utf-8"
        )

    def search(self, db: Session, question: str, subject_id: int | None, top_k: int) -> list[tuple[Chunk, float]]:
        if subject_id is not None:
            if not db.query(Chunk.id).filter(Chunk.subject_id == subject_id).first():
                return []
            subject_ids = [subject_id]
        else:
            subject_ids = self._available_subject_ids(db)
        if not subject_ids or top_k <= 0:
            return []
        results: list[tuple[Chunk, float]] = []
        if time.monotonic() < self._embedding_retry_after:
            return self._keyword_search(db, question, subject_ids, top_k)
        try:
            query_vector = self.embed_query(question).reshape(1, -1).astype("float32")
        except Exception as exc:
            self._embedding_retry_after = time.monotonic() + 60
            logger.warning("Embeddings are unavailable; using notes keyword search: %s", exc)
            return self._keyword_search(db, question, subject_ids, top_k)
        faiss.normalize_L2(query_vector)

        for item_subject_id in subject_ids:
            index_file = self.index_path(item_subject_id)
            metadata_file = self.metadata_path(item_subject_id)
            if not index_file.exists() or not metadata_file.exists():
                continue
            index = faiss.read_index(str(index_file))
            if index.d != query_vector.shape[1]:
                logger.warning(
                    "FAISS dimension mismatch for subject %s: index=%s query=%s. Rebuilding index.",
                    item_subject_id,
                    index.d,
                    query_vector.shape[1],
                )
                self.rebuild_subject_index(db, item_subject_id)
                if not index_file.exists() or not metadata_file.exists():
                    continue
                index = faiss.read_index(str(index_file))
                if index.d != query_vector.shape[1]:
                    logger.error(
                        "FAISS dimension mismatch persists for subject %s after rebuild. Skipping subject.",
                        item_subject_id,
                    )
                    continue
            candidate_count = min(settings.retrieve_candidates, index.ntotal)
            distances, indices = index.search(query_vector, candidate_count)
            chunk_ids = json.loads(metadata_file.read_text(encoding="utf-8"))
            candidates = [
                (chunk_ids[idx], float(score))
                for score, idx in zip(distances[0], indices[0])
                if 0 <= idx < len(chunk_ids)
            ]
            candidate_map = dict(candidates)
            if not candidate_map:
                continue
            chunks_by_id = {
                chunk.id: chunk
                for chunk in db.query(Chunk).filter(Chunk.id.in_(candidate_map)).all()
            }
            for chunk_id, score in candidates:
                chunk = chunks_by_id.get(chunk_id)
                if chunk:
                    results.append((chunk, self._hybrid_score(question, chunk, score)))

        results.sort(key=lambda item: item[1], reverse=True)
        filtered = [item for item in results if item[1] >= settings.min_relevance_score]
        deduped: list[tuple[Chunk, float]] = []
        seen: set[int] = set()
        for chunk, score in filtered:
            if chunk.id in seen:
                continue
            seen.add(chunk.id)
            deduped.append((chunk, round(score, 3)))
            if len(deduped) >= top_k:
                break
        return deduped

    def _keyword_search(
        self, db: Session, question: str, subject_ids: list[int], top_k: int
    ) -> list[tuple[Chunk, float]]:
        """Search the selected student's chunks when a vector model is unavailable."""
        chunks = (
            db.query(Chunk)
            .filter(Chunk.subject_id.in_(subject_ids))
            .order_by(Chunk.id.asc())
            .all()
        )
        scored = []
        for chunk in chunks:
            metadata = json.loads(chunk.metadata_json or "{}")
            content_score = keyword_overlap_score(question, chunk.content)
            title_score = keyword_overlap_score(question, str(metadata.get("title", "")))
            phrase_bonus = 0.1 if question.strip() and question.casefold() in chunk.content.casefold() else 0.0
            score = min(1.0, content_score * 0.8 + title_score * 0.2 + phrase_bonus)
            if score >= settings.min_relevance_score:
                scored.append((chunk, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [(chunk, round(score, 3)) for chunk, score in scored[:top_k]]

    def _available_subject_ids(self, db: Session) -> list[int]:
        rows = db.query(Chunk.subject_id).distinct().all()
        return [row[0] for row in rows]

    def _get_hf_model(self):
        if self._hf_model is not None:
            return self._hf_model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. Run 'pip install -r requirements.txt'."
            ) from exc
        # The model is cached locally after first use. Requiring local files
        # prevents a blocked Hugging Face HEAD request from disabling chat.
        self._hf_model = SentenceTransformer(settings.hf_embed_model, local_files_only=True)
        return self._hf_model

    @staticmethod
    def index_path(subject_id: int) -> Path:
        return FAISS_DIR / f"subject_{subject_id}.index"

    @staticmethod
    def metadata_path(subject_id: int) -> Path:
        return FAISS_DIR / f"subject_{subject_id}.json"

    @staticmethod
    def _hybrid_score(question: str, chunk: Chunk, vector_score: float) -> float:
        lexical = keyword_overlap_score(question, chunk.content)
        metadata = json.loads(chunk.metadata_json or "{}")
        title = metadata.get("title", "")
        title_overlap = keyword_overlap_score(question, title)
        phrase_bonus = 0.12 if question.strip() and question.lower() in chunk.content.lower() else 0.0
        vector_component = max(0.0, min(1.0, (vector_score + 1) / 2))
        return (vector_component * 0.42) + (lexical * 0.43) + (title_overlap * 0.15) + phrase_bonus


embedding_service = EmbeddingService()
