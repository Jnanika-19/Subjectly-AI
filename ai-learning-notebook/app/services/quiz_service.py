from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.models import Note, QuizAttempt, QuizSession, Subject
from app.schemas.schemas import (
    EvaluationRequest,
    EvaluationResponse,
    QuizQuestion,
    QuizQuestionPublic,
    TestResponse,
)
from app.services.ai_service import ai_service
from app.utils.text import keyword_signature


logger = logging.getLogger(__name__)
QUIZ_SESSION_TTL = timedelta(hours=24)
MAX_CONTEXT_CHARS = 18_000


class QuizService:
    def generate_test(self, db: Session, subject_id: int, count: int) -> TestResponse:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if subject is None:
            raise ValueError("Subject not found.")
        notes = db.query(Note).filter(Note.subject_id == subject_id).order_by(Note.id.asc()).all()
        if not notes:
            return TestResponse(quiz_id=str(uuid.uuid4()), subject_id=subject_id, questions=[])

        db.query(QuizSession).filter(
            QuizSession.created_at < datetime.utcnow() - QUIZ_SESSION_TTL
        ).delete(synchronize_session=False)
        questions = self._generate_ai_questions(subject.name, notes, count)
        if len(questions) < count:
            questions.extend(self._fallback_questions(notes, count - len(questions), start=len(questions)))
        questions = questions[:count]

        quiz_id = str(uuid.uuid4())
        db.add(
            QuizSession(
                id=quiz_id,
                subject_id=subject_id,
                questions_json=json.dumps([question.model_dump() for question in questions]),
            )
        )
        db.commit()
        return TestResponse(
            quiz_id=quiz_id,
            subject_id=subject_id,
            questions=[
                QuizQuestionPublic(
                    id=question.id,
                    type=question.type,
                    prompt=question.prompt,
                    options=question.options,
                    topic=question.topic,
                )
                for question in questions
            ],
        )

    def _generate_ai_questions(self, subject_name: str, notes: list[Note], count: int) -> list[QuizQuestion]:
        context_parts = []
        used_chars = 0
        for note in notes:
            section = f"## {note.title}\n{note.content.strip()}"
            remaining = MAX_CONTEXT_CHARS - used_chars
            if remaining <= 0:
                break
            context_parts.append(section[:remaining])
            used_chars += min(len(section), remaining)

        prompt = (
            "Create an exam practice quiz using only the study notes below. Do not use outside facts. "
            "Make questions test understanding, definitions, processes, causes, or comparisons when supported. "
            "Return only valid JSON in this shape: "
            '{"questions":[{"type":"mcq","prompt":"...","options":["...","...","...","..."],'
            '"answer":"exactly one option","explanation":"...","topic":"note heading"}]}. '
            "Use type 'short' for a short-answer question; it should have options=[] and a concise answer key. "
            f"Create exactly {count} varied questions for subject {subject_name!r}. "
            "Every answer and explanation must be supported by the notes.\n\n"
            f"STUDY NOTES:\n{'\n\n'.join(context_parts)}"
        )
        try:
            raw = ai_service.generate_answer(prompt)
            decoded = self._decode_json(raw)
            items = decoded.get("questions", []) if isinstance(decoded, dict) else decoded
            questions = []
            for item in items:
                question = self._validate_generated_question(item)
                if question:
                    questions.append(question)
                if len(questions) == count:
                    break
            return questions
        except Exception as exc:
            logger.info("Using note-based quiz fallback: %s", exc)
            return []

    @staticmethod
    def _decode_json(raw: str):
        content = raw.strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
        return json.loads(content)

    @staticmethod
    def _validate_generated_question(item) -> QuizQuestion | None:
        if not isinstance(item, dict):
            return None
        question_type = item.get("type")
        prompt = str(item.get("prompt", "")).strip()
        answer = str(item.get("answer", "")).strip()
        topic = str(item.get("topic", "Study notes")).strip()[:120]
        explanation = str(item.get("explanation", "Review the related section in your notes.")).strip()
        options = item.get("options", [])
        if not prompt or not answer or question_type not in {"mcq", "short"}:
            return None
        if question_type == "mcq":
            if not isinstance(options, list):
                return None
            options = list(dict.fromkeys(str(option).strip() for option in options if str(option).strip()))
            if len(options) != 4 or answer not in options:
                return None
        else:
            options = []
        return QuizQuestion(
            id=str(uuid.uuid4()),
            type=question_type,
            prompt=prompt[:1000],
            options=options,
            answer=answer[:2000],
            explanation=explanation[:2000],
            topic=topic or "Study notes",
        )

    @staticmethod
    def _fallback_questions(notes: list[Note], count: int, start: int = 0) -> list[QuizQuestion]:
        prepared = []
        for note in notes:
            source = note.summary.strip() or note.content.strip()
            source = re.sub(r"\s+", " ", source)
            if source:
                prepared.append((note.title.strip() or "Study notes", source[:500]))
        if not prepared:
            return []

        unique_summaries = list(dict.fromkeys(summary for _, summary in prepared))
        questions = []
        for offset in range(count):
            index = (start + offset) % len(prepared)
            topic, answer_text = prepared[index]
            if len(unique_summaries) >= 4 and (start + offset) % 2 == 0:
                distractors = [text for text in unique_summaries if text != answer_text][:3]
                options = [answer_text, *distractors]
                while len(options) < 4:
                    options.append("This detail is not stated in the uploaded notes.")
                questions.append(
                    QuizQuestion(
                        id=str(uuid.uuid4()),
                        type="mcq",
                        prompt=f"Which statement best summarizes '{topic}' in your uploaded notes?",
                        options=options,
                        answer=answer_text,
                        explanation=f"This summary comes from the '{topic}' section of your notes.",
                        topic=topic,
                    )
                )
            else:
                questions.append(
                    QuizQuestion(
                        id=str(uuid.uuid4()),
                        type="short",
                        prompt=f"Explain '{topic}' in your own words. Include its main idea and one detail from your notes.",
                        options=[],
                        answer=answer_text,
                        explanation=f"Compare your response with the summary from the '{topic}' section.",
                        topic=topic,
                    )
                )
        return questions

    def evaluate(self, db: Session, payload: EvaluationRequest) -> EvaluationResponse:
        quiz_session = db.query(QuizSession).filter(QuizSession.id == payload.quiz_id).first()
        if quiz_session is None:
            raise ValueError("This quiz is no longer available. Generate a new quiz and try again.")
        if quiz_session.created_at < datetime.utcnow() - QUIZ_SESSION_TTL:
            db.delete(quiz_session)
            db.commit()
            raise ValueError("This quiz expired. Generate a new quiz and try again.")

        questions = [QuizQuestion.model_validate(item) for item in json.loads(quiz_session.questions_json)]
        results = []
        score = 0.0
        weak_topics: list[str] = []

        for question in questions:
            user_answer = str(payload.answers.get(question.id, "")).strip()[:10_000]
            if question.type == "mcq":
                is_correct = user_answer.casefold() == question.answer.casefold()
                earned = 1.0 if is_correct else 0.0
                explanation = question.explanation
            else:
                expected_terms = set(keyword_signature(question.answer, limit=6))
                provided_terms = set(keyword_signature(user_answer, limit=8))
                overlap = len(expected_terms & provided_terms)
                ratio = overlap / max(len(expected_terms), 1)
                earned = 1.0 if ratio >= 0.5 else 0.5 if ratio >= 0.25 else 0.0
                is_correct = earned >= 0.5
                explanation = f"Expected ideas: {', '.join(sorted(expected_terms)) or 'core concepts from notes'}."

            if earned < 1.0:
                weak_topics.append(question.topic)
            score += earned
            results.append(
                {
                    "question_id": question.id,
                    "topic": question.topic,
                    "correct_answer": question.answer,
                    "user_answer": user_answer,
                    "earned": earned,
                    "max_score": 1,
                    "is_correct": is_correct,
                    "explanation": explanation,
                }
            )

        db.add(
            QuizAttempt(
                subject_id=quiz_session.subject_id,
                score=round(score, 2),
                total_questions=len(questions),
                weak_topics_json=json.dumps(sorted(set(weak_topics))),
                details_json=json.dumps(results),
            )
        )
        db.delete(quiz_session)
        db.commit()
        return EvaluationResponse(
            score=round(score, 2),
            total_questions=len(questions),
            results=results,
            weak_topics=sorted(set(weak_topics)),
        )


quiz_service = QuizService()
