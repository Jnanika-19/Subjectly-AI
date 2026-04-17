from __future__ import annotations

import json
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from app.models.models import AIInteraction, Note, QuizAttempt, Subject
from app.schemas.schemas import AnalyticsResponse, ProgressResponse


class AnalyticsService:
    def progress(self, db: Session) -> ProgressResponse:
        subjects = db.query(Subject).all()
        subject_progress = []
        completion_values = []
        weak_counter = Counter()

        for subject in subjects:
            notes_count = db.query(Note).filter(Note.subject_id == subject.id).count()
            interactions = db.query(AIInteraction).filter(AIInteraction.subject_id == subject.id).count()
            attempts = db.query(QuizAttempt).filter(QuizAttempt.subject_id == subject.id).all()
            average_score = (
                sum(attempt.score / max(attempt.total_questions, 1) for attempt in attempts) / len(attempts)
                if attempts
                else 0.0
            )
            for attempt in attempts:
                weak_counter.update(json.loads(attempt.weak_topics_json or "[]"))
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

        improvement_plan = []
        for topic, count in weak_counter.most_common(5):
            improvement_plan.append(f"Revise {topic} and retake one short quiz to strengthen recall.")
        if not improvement_plan:
            improvement_plan.append("Upload more subject material and take a test to unlock personalized revision plans.")

        overall = round(sum(completion_values) / len(completion_values), 2) if completion_values else 0.0
        return ProgressResponse(
            overall_completion=overall,
            subject_progress=subject_progress,
            improvement_plan=improvement_plan,
        )

    def analytics(self, db: Session) -> AnalyticsResponse:
        subjects = db.query(Subject).all()
        notes = db.query(Note).all()
        interactions = db.query(AIInteraction).all()
        attempts = db.query(QuizAttempt).all()

        notes_activity_counter = defaultdict(int)
        for note in notes:
            notes_activity_counter[note.created_at.strftime("%Y-%m-%d")] += 1

        subject_distribution = []
        for subject in subjects:
            note_count = sum(1 for note in notes if note.subject_id == subject.id)
            subject_distribution.append({"subject": subject.name, "notes": note_count})

        ai_usage_counter = Counter(interaction.mode for interaction in interactions)
        weak_topics_counter = Counter()
        for attempt in attempts:
            weak_topics_counter.update(json.loads(attempt.weak_topics_json or "[]"))

        progress_summary = []
        for subject in subjects:
            subject_attempts = [attempt for attempt in attempts if attempt.subject_id == subject.id]
            if subject_attempts:
                avg_score = sum(a.score / max(a.total_questions, 1) for a in subject_attempts) / len(subject_attempts)
            else:
                avg_score = 0.0
            progress_summary.append({"subject": subject.name, "avg_score": round(avg_score * 100, 2)})

        return AnalyticsResponse(
            notes_activity=[
                {"date": date, "count": count}
                for date, count in sorted(notes_activity_counter.items())
            ],
            subject_distribution=subject_distribution,
            ai_usage=[{"mode": mode, "count": count} for mode, count in ai_usage_counter.items()],
            weak_topics=[{"topic": topic, "count": count} for topic, count in weak_topics_counter.most_common(6)],
            progress_summary=progress_summary,
        )


analytics_service = AnalyticsService()
