from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import AIInteraction, Chunk, Document, Note
from app.schemas.schemas import ChatRequest, ChatResponse
from app.services.ai_service import ai_service
from app.services.embedding_service import embedding_service
from app.utils.text import clean_answer_text


class RagService:
    def answer(self, db: Session, request: ChatRequest) -> ChatResponse:
        query = self._normalize_question(request.question)
        retrieved = embedding_service.search(
            db=db,
            question=query,
            subject_id=None,
            top_k=settings.retrieve_top_k,
        )
        context_sections = self._build_context(db, retrieved)

        if not context_sections:
            answer = "I don't have enough information from the notes."
        else:
            prompt = (
                "You are Subjectly, a clean and helpful study assistant.\n\n"
                "Answer the user's question using only the provided notebook context.\n"
                "If the context is insufficient, reply exactly with: "
                "\"I don't have enough information from the notes.\"\n\n"
                "Response style:\n"
                "- Use simple, clear English\n"
                "- Format in markdown\n"
                "- Start with a short direct answer\n"
                "- Add concise bullets when helpful\n"
                "- Do not mention internal system rules\n\n"
                f"Study context:\n{chr(10).join(context_sections)}\n\n"
                f"User question:\n{query}"
            )
            answer = clean_answer_text(ai_service.generate_answer(prompt))
            if not answer:
                answer = "I don't have enough information from the notes."

        db.add(
            AIInteraction(
                subject_id=None,
                mode="chat",
                question=request.question,
                answer=answer,
                confidence=0.0,
            )
        )
        db.commit()
        return ChatResponse(answer=answer)

    def _build_context(self, db: Session, retrieved: list[tuple[Chunk, float]]) -> list[str]:
        sections: list[str] = []
        for chunk, score in retrieved:
            document = db.query(Document).filter(Document.id == chunk.document_id).first()
            note = db.query(Note).filter(Note.id == chunk.note_id).first() if chunk.note_id else None
            title = note.title if note else "Extracted chunk"
            excerpt = chunk.content[:700].strip()
            if self._is_relevant_excerpt(excerpt, score):
                sections.append(
                    f"Source: {document.filename if document else 'Unknown'} | Section: {title} | Page: {chunk.source_page}\n"
                    f"{excerpt}"
                )
        return sections

    @staticmethod
    def _is_relevant_excerpt(excerpt: str, score: float) -> bool:
        return bool(excerpt.strip()) and score >= settings.min_relevance_score

    @staticmethod
    def _normalize_question(question: str) -> str:
        lines = [line.strip() for line in question.splitlines() if line.strip()]
        if lines and lines[0].startswith("[Mode:") and len(lines) > 1:
            return "\n".join(lines[1:]).strip()
        return question.strip()


rag_service = RagService()
