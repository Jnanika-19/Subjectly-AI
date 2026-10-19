from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import AIInteraction, Chunk, Document, Note
from app.schemas.schemas import ChatRequest, ChatResponse
from app.services.ai_service import APIKeyNotConfiguredError, AIRequestFailedError, ai_service
from app.services.embedding_service import embedding_service
from app.utils.text import clean_answer_text, keyword_overlap_score


class RagService:
    def answer(self, db: Session, request: ChatRequest) -> ChatResponse:
        mode, query = self._parse_question(request.question)
        retrieved = embedding_service.search(
            db=db,
            question=query,
            subject_id=request.subject_id,
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
                f"Selected mode: {mode}. Adapt the answer to this mode: {self._mode_instruction(mode)}\n\n"
                f"Study context:\n{chr(10).join(context_sections)}\n\n"
                f"User question:\n{query}"
            )
            try:
                answer = clean_answer_text(ai_service.generate_answer(prompt))
            except (APIKeyNotConfiguredError, AIRequestFailedError) as exc:
                answer = self._answer_from_notes(query, context_sections)
                if answer:
                    answer = "The AI service is unavailable right now. Here are the closest passages from your notes:\n\n" + answer
                else:
                    answer = "The AI service is unavailable right now, and I couldn't find a relevant passage in your notes. Please try again later or ask about a specific topic."
            if not answer:
                answer = "I don't have enough information from the notes."

        db.add(
            AIInteraction(
                subject_id=request.subject_id,
                mode=mode,
                question=request.question,
                answer=answer,
                confidence=0.0,
            )
        )
        db.commit()
        return ChatResponse(answer=answer)

    def _build_context(self, db: Session, retrieved: list[tuple[Chunk, float]]) -> list[str]:
        sections: list[str] = []
        if not retrieved:
            return sections
        chunks = [chunk for chunk, _ in retrieved]
        document_ids = {chunk.document_id for chunk in chunks}
        note_ids = {chunk.note_id for chunk in chunks if chunk.note_id is not None}
        documents = {
            document.id: document
            for document in db.query(Document).filter(Document.id.in_(document_ids)).all()
        }
        notes = {
            note.id: note
            for note in db.query(Note).filter(Note.id.in_(note_ids)).all()
        } if note_ids else {}
        for chunk, score in retrieved:
            document = documents.get(chunk.document_id)
            note = notes.get(chunk.note_id) if chunk.note_id else None
            title = note.title if note else "Extracted chunk"
            excerpt = chunk.content[:700].strip()
            if self._is_relevant_excerpt(excerpt, score):
                sections.append(
                    f"Source: {document.filename if document else 'Unknown'} | Section: {title} | Page: {chunk.source_page}\n"
                    f"{excerpt}"
                )
        return sections

    @staticmethod
    def _answer_from_notes(question: str, context_sections: list[str]) -> str:
        passages = []
        for section in context_sections:
            header, _, content = section.partition("\n")
            match = re.search(r"Section:\s*(.*?)\s*\|\s*Page:\s*(\d+)", header)
            title, page = (match.group(1), match.group(2)) if match else ("Uploaded notes", "?")
            sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", content) if part.strip()]
            for sentence in sentences:
                score = keyword_overlap_score(question, sentence) + keyword_overlap_score(question, title) * 0.25
                if score > 0:
                    passages.append((score, title, page, sentence))
        passages.sort(key=lambda item: item[0], reverse=True)
        selected = []
        seen = set()
        for _, title, page, sentence in passages:
            normalized = sentence.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            selected.append(f"- **{title}, page {page}:** {sentence[:500]}")
            if len(selected) == 3:
                break
        if not selected:
            for section in context_sections[:2]:
                header, _, content = section.partition("\n")
                match = re.search(r"Section:\s*(.*?)\s*\|\s*Page:\s*(\d+)", header)
                title, page = (match.group(1), match.group(2)) if match else ("Uploaded notes", "?")
                excerpt = content.strip()[:500]
                if excerpt:
                    selected.append(f"- **{title}, page {page}:** {excerpt}")
        if not selected:
            return ""
        return "\n\n".join(selected)

    @staticmethod
    def _is_relevant_excerpt(excerpt: str, score: float) -> bool:
        return bool(excerpt.strip()) and score >= settings.min_relevance_score

    @staticmethod
    def _parse_question(question: str) -> tuple[str, str]:
        lines = [line.strip() for line in question.splitlines() if line.strip()]
        if lines and lines[0].startswith("[Mode:") and len(lines) > 1:
            mode = lines[0][6:-1].strip().lower()
            return mode, "\n".join(lines[1:]).strip()
        return "study", question.strip()

    @staticmethod
    def _mode_instruction(mode: str) -> str:
        instructions = {
            "study": "explain the concept clearly and build understanding",
            "doubt": "answer the specific doubt directly, then clarify the reasoning",
            "notes": "organize the answer as concise study notes with headings or bullets",
            "exam": "give a precise, exam-ready answer with key terms and points",
            "revision": "give a compact recap of the most important points",
        }
        return instructions.get(mode, instructions["study"])


rag_service = RagService()
