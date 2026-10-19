from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


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
    question: str = Field(min_length=1, max_length=5000)
    subject_id: int | None = Field(default=None, ge=1)


class ChatResponse(BaseModel):
    answer: str


class TestRequest(BaseModel):
    subject_id: int = Field(ge=1)
    count: int = Field(default=5, ge=3, le=10)


class QuizQuestion(BaseModel):
    id: str
    type: Literal["mcq", "short"]
    prompt: str
    options: list[str] = Field(default_factory=list)
    answer: str
    explanation: str
    topic: str


class QuizQuestionPublic(BaseModel):
    id: str
    type: Literal["mcq", "short"]
    prompt: str
    options: list[str] = Field(default_factory=list)
    topic: str


class TestResponse(BaseModel):
    quiz_id: str
    subject_id: int
    questions: list[QuizQuestionPublic]


class EvaluationRequest(BaseModel):
    quiz_id: str = Field(min_length=36, max_length=36)
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
