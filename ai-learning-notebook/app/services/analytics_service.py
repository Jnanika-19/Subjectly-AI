from __future__ import annotations

import json
from collections import Counter, defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import AIInteraction, Note, QuizAttempt, Subject
from app.schemas.schemas import AnalyticsResponse, ProgressResponse


class AnalyticsService:
    def progress(self, db: Session, user_id: int) -> ProgressResponse:
        subjects = db.query(Subject).filter(Subject.user_id == user_id).all()
        subject_ids = [subject.id for subject in subjects]
        note_counts = dict(db.query(Note.subject_id, func.count(Note.id)).filter(Note.subject_id.in_(subject_ids)).group_by(Note.subject_id).all())
        interaction_counts = dict(
            db.query(AIInteraction.subject_id, func.count(AIInteraction.id))
            .filter(AIInteraction.subject_id.is_not(None))
            .filter(AIInteraction.subject_id.in_(subject_ids))
            .group_by(AIInteraction.subject_id)
            .all()
        )
        average_scores = dict(
            db.query(
                QuizAttempt.subject_id,
                func.avg(QuizAttempt.score / func.nullif(QuizAttempt.total_questions, 0)),
            )
            .group_by(QuizAttempt.subject_id)
            .filter(QuizAttempt.subject_id.in_(subject_ids))
            .all()
        )
        subject_progress = []
        completion_values = []
        weak_counter = Counter()

        for subject in subjects:
            notes_count = note_counts.get(subject.id, 0)
            interactions = interaction_counts.get(subject.id, 0)
            average_score = float(average_scores.get(subject.id) or 0.0)
            completion = min(100.0, round((notes_count * 8) + (interactions * 3) + (average_score * 30), 2))
            completion_values.append(completion)
            subject_progress.append(
                {
                    "subject": subject.name,
                    "notes_count": notes_count,
                    "ai_interactions": interactions,
                    "average_quiz_score": round(average_score * 100, 2),
                    "completion": completion,
                }
            )

        for (topics_json,) in db.query(QuizAttempt.weak_topics_json).filter(QuizAttempt.subject_id.in_(subject_ids)).all():
            weak_counter.update(json.loads(topics_json or "[]"))
        improvement_plan = [
            f"Revise {topic} and retake one short quiz to strengthen recall."
            for topic, _ in weak_counter.most_common(5)
        ]
        if not improvement_plan:
            improvement_plan.append("Upload more subject material and take a test to unlock personalized revision plans.")

        overall = round(sum(completion_values) / len(completion_values), 2) if completion_values else 0.0
        return ProgressResponse(
            overall_completion=overall,
            subject_progress=subject_progress,
            improvement_plan=improvement_plan,
        )

    def analytics(self, db: Session, user_id: int) -> AnalyticsResponse:
        subjects = db.query(Subject).filter(Subject.user_id == user_id).all()
        subject_ids = [subject.id for subject in subjects]
        notes_activity = (
            db.query(func.date(Note.created_at), func.count(Note.id))
            .group_by(func.date(Note.created_at))
            .filter(Note.subject_id.in_(subject_ids))
            .order_by(func.date(Note.created_at))
            .all()
        )
        note_counts = dict(db.query(Note.subject_id, func.count(Note.id)).filter(Note.subject_id.in_(subject_ids)).group_by(Note.subject_id).all())
        subject_distribution = [
            {"subject": subject.name, "notes": note_counts.get(subject.id, 0)}
            for subject in subjects
        ]
        ai_usage_rows = (
            db.query(AIInteraction.mode, func.count(AIInteraction.id))
            .group_by(AIInteraction.mode)
            .filter(AIInteraction.subject_id.in_(subject_ids))
            .all()
        )
        weak_topics_counter = Counter()
        score_totals: dict[int, list[float]] = defaultdict(list)
        for subject_id, score, total, topics_json in db.query(
            QuizAttempt.subject_id,
            QuizAttempt.score,
            QuizAttempt.total_questions,
            QuizAttempt.weak_topics_json,
        ).filter(QuizAttempt.subject_id.in_(subject_ids)).all():
            score_totals[subject_id].append(score / max(total, 1))
            weak_topics_counter.update(json.loads(topics_json or "[]"))

        progress_summary = []
        for subject in subjects:
            scores = score_totals[subject.id]
            average = sum(scores) / len(scores) if scores else 0.0
            progress_summary.append({"subject": subject.name, "avg_score": round(average * 100, 2)})

        return AnalyticsResponse(
            notes_activity=[{"date": date, "count": count} for date, count in notes_activity],
            subject_distribution=subject_distribution,
            ai_usage=[{"mode": mode, "count": count} for mode, count in ai_usage_rows],
            weak_topics=[{"topic": topic, "count": count} for topic, count in weak_topics_counter.most_common(6)],
            progress_summary=progress_summary,
        )


analytics_service = AnalyticsService()
