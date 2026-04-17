from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    name: str
    description: str = ""


class SubjectRead(BaseModel):
    id: int
    name: str
    description: str
    document_count: int = 0
    note_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class NoteRead(BaseModel):
    id: int
    document_id: int
    subject_id: int
    title: str
    chapter: str
    unit: str
    content: str
    summary: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentRead(BaseModel):
    id: int
    subject_id: int
    filename: str
    file_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class NotesResponse(BaseModel):
    notes: list[NoteRead]
    documents: list[DocumentRead]


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


class TestRequest(BaseModel):
    subject_id: int
    count: int = Field(default=5, ge=3, le=10)


class QuizQuestion(BaseModel):
    id: str
    type: str
    prompt: str
    options: list[str] = []
    answer: str
    explanation: str
    topic: str


class TestResponse(BaseModel):
    subject_id: int
    questions: list[QuizQuestion]


class EvaluationRequest(BaseModel):
    subject_id: int
    questions: list[QuizQuestion]
    answers: dict[str, Any]


class EvaluationResponse(BaseModel):
    score: float
    total_questions: int
    results: list[dict[str, Any]]
    weak_topics: list[str]


class ProgressResponse(BaseModel):
    overall_completion: float
    subject_progress: list[dict[str, Any]]
    improvement_plan: list[str]


class AnalyticsResponse(BaseModel):
    notes_activity: list[dict[str, Any]]
    subject_distribution: list[dict[str, Any]]
    ai_usage: list[dict[str, Any]]
    weak_topics: list[dict[str, Any]]
    progress_summary: list[dict[str, Any]]
