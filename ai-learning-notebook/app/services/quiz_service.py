from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.models.models import QuizAttempt, Subject
from app.schemas.schemas import EvaluationRequest, EvaluationResponse, QuizQuestion, TestResponse
from app.services.embedding_service import embedding_service
from app.utils.text import keyword_signature


class QuizService:
    def generate_test(self, db: Session, subject_id: int, count: int) -> TestResponse:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        retrieved = embedding_service.search(db, subject.name if subject else "", subject_id, max(count * 2, 6))
        questions: list[QuizQuestion] = []

        for index, (chunk, _) in enumerate(retrieved[:count]):
            topic = json.loads(chunk.metadata_json or "{}").get("title", f"Topic {index + 1}")
            keywords = keyword_signature(chunk.content, limit=4)
            mcq_answer = keywords[0] if keywords else topic
            distractors = (keywords[1:] + [topic, "None of the above", "Both A and B"])[:4]
            options = [mcq_answer] + [item for item in distractors if item != mcq_answer]
            while len(options) < 4:
                options.append(f"Option {len(options) + 1}")
            if index % 2 == 0:
                prompt = f"Which keyword is most strongly connected to the topic '{topic}' in the uploaded notes?"
                questions.append(
                    QuizQuestion(
                        id=str(uuid.uuid4()),
                        type="mcq",
                        prompt=prompt,
                        options=options[:4],
                        answer=mcq_answer,
                        explanation=f"The chunk emphasizes {mcq_answer} while discussing {topic}.",
                        topic=topic,
                    )
                )
            else:
                prompt = f"Write a short answer explaining '{topic}' using the uploaded notes."
                answer = chunk.content[:220]
                questions.append(
                    QuizQuestion(
                        id=str(uuid.uuid4()),
                        type="short",
                        prompt=prompt,
                        answer=answer,
                        explanation=f"A good answer should mention the core ideas present in the {topic} note.",
                        topic=topic,
                    )
                )

        return TestResponse(subject_id=subject_id, questions=questions)

    def evaluate(self, db: Session, payload: EvaluationRequest) -> EvaluationResponse:
        results = []
        score = 0.0
        weak_topics: list[str] = []

        for question in payload.questions:
            user_answer = str(payload.answers.get(question.id, "")).strip()
            if question.type == "mcq":
                is_correct = user_answer.lower() == question.answer.lower()
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
                subject_id=payload.subject_id,
                score=round(score, 2),
                total_questions=len(payload.questions),
                weak_topics_json=json.dumps(sorted(set(weak_topics))),
                details_json=json.dumps(results),
            )
        )
        db.commit()
        return EvaluationResponse(
            score=round(score, 2),
            total_questions=len(payload.questions),
            results=results,
            weak_topics=sorted(set(weak_topics)),
        )


quiz_service = QuizService()
