from __future__ import annotations

import logging

from sqlalchemy import func
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.database import get_db
from app.models.models import Document, Note, Subject, QuizSession
from app.schemas.schemas import (
    AnalyticsResponse,
    ChatRequest,
    ChatResponse,
    EvaluationRequest,
    EvaluationResponse,
    NotesResponse,
    ProgressResponse,
    SubjectCreate,
    SubjectRead,
    TestRequest,
    TestResponse,
)
from app.services.analytics_service import analytics_service
from app.services.ai_service import AIRequestFailedError, APIKeyNotConfiguredError
from app.services.embedding_service import embedding_service
from app.services.pdf_service import pdf_service
from app.services.quiz_service import quiz_service
from app.services.rag_service import rag_service


router = APIRouter()
logger = logging.getLogger(__name__)


def owned_subject(db: Session, user_id: int, subject_id: int) -> Subject | None:
    return db.query(Subject).filter(Subject.id == subject_id, Subject.user_id == user_id).first()


@router.post("/subjects", response_model=SubjectRead)
def create_subject(payload: SubjectCreate, request: Request, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Subject name cannot be blank.")
    user_id = request.state.user_id
    existing = db.query(Subject).filter(Subject.user_id == user_id, Subject.name.ilike(name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Subject already exists.")
    subject = Subject(name=name, description=payload.description.strip(), user_id=user_id)
    db.add(subject)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Subject already exists.")
    db.refresh(subject)
    return subject


@router.get("/subjects", response_model=list[SubjectRead])
def list_subjects(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(
            Subject,
            func.count(func.distinct(Document.id)).label("document_count"),
            func.count(func.distinct(Note.id)).label("note_count"),
        )
        .outerjoin(Document, Document.subject_id == Subject.id)
        .outerjoin(Note, Note.subject_id == Subject.id)
        .filter(Subject.user_id == request.state.user_id)
        .group_by(Subject.id)
        .order_by(Subject.name.asc())
        .all()
    )
    return [
        SubjectRead(
            id=subject.id,
            name=subject.name,
            description=subject.description,
            document_count=document_count,
            note_count=note_count,
            created_at=subject.created_at,
        )
        for subject, document_count, note_count in rows
    ]


@router.post("/upload-pdf")
def upload_pdf(
    request: Request,
    subject_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    subject = owned_subject(db, request.state.user_id, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF files must be 25 MB or smaller.")
    if b"%PDF-" not in file.file.read(1024):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")
    file.file.seek(0)

    document = None
    try:
        document = pdf_service.create_document_bundle(db, subject, file)
        try:
            embedding_service.rebuild_subject_index(db, subject.id)
        except Exception:
            logger.warning(
                "Could not build vector index for subject %s; the uploaded notes remain searchable by keywords.",
                subject.id,
                exc_info=True,
            )
        db.commit()
        db.refresh(document)
    except ValueError as exc:
        db.rollback()
        if document:
            pdf_service.remove_uploaded_file(document.file_path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        if document:
            pdf_service.remove_uploaded_file(document.file_path)
        raise HTTPException(status_code=503, detail="PDF could not be processed. Check that it is a readable PDF and the embedding model is available.") from exc
    return {
        "message": "PDF uploaded and indexed successfully.",
        "document_id": document.id,
        "filename": document.filename,
        "note_count": len(document.notes),
    }


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, request: Request, db: Session = Depends(get_db)):
    document = db.query(Document).join(Subject).filter(Document.id == document_id, Subject.user_id == request.state.user_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    subject_id = document.subject_id
    pdf_service.delete_document_bundle(db, document)
    try:
        embedding_service.rebuild_subject_index(db, subject_id)
    except Exception:
        # The database deletion is already committed. Retrieval filters missing
        # chunk rows, so a stale index is safe until it can be rebuilt later.
        logger.exception("Could not refresh search index after deleting document %s", document_id)
    return {"message": "Document deleted successfully."}


@router.get("/notes", response_model=NotesResponse)
def get_notes(request: Request, subject_id: int | None = None, db: Session = Depends(get_db)):
    notes_query = db.query(Note).join(Subject).filter(Subject.user_id == request.state.user_id)
    docs_query = db.query(Document).join(Subject).filter(Subject.user_id == request.state.user_id)
    if subject_id:
        if not owned_subject(db, request.state.user_id, subject_id):
            raise HTTPException(status_code=404, detail="Subject not found.")
        notes_query = notes_query.filter(Note.subject_id == subject_id)
        docs_query = docs_query.filter(Document.subject_id == subject_id)
    return NotesResponse(notes=notes_query.order_by(Note.created_at.desc()).all(), documents=docs_query.all())


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db)):
    user_id = request.state.user_id
    if payload.subject_id is not None and not owned_subject(db, user_id, payload.subject_id):
        raise HTTPException(status_code=404, detail="Subject not found.")
    if payload.subject_id is None:
        subject = db.query(Subject).filter(Subject.user_id == user_id).order_by(Subject.id).first()
        if subject is None:
            return ChatResponse(answer="Upload a subject PDF first so I can answer from your notes.")
        payload = payload.model_copy(update={"subject_id": subject.id})
    try:
        return rag_service.answer(db, payload)
    except APIKeyNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIRequestFailedError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/test", response_model=TestResponse)
def generate_test(payload: TestRequest, request: Request, db: Session = Depends(get_db)):
    if not owned_subject(db, request.state.user_id, payload.subject_id):
        raise HTTPException(status_code=404, detail="Subject not found.")
    try:
        return quiz_service.generate_test(db, payload.subject_id, payload.count)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evaluate", response_model=EvaluationResponse)
def evaluate(payload: EvaluationRequest, request: Request, db: Session = Depends(get_db)):
    quiz = db.query(QuizSession).join(Subject).filter(QuizSession.id == payload.quiz_id, Subject.user_id == request.state.user_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="This quiz is no longer available.")
    try:
        return quiz_service.evaluate(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/progress", response_model=ProgressResponse)
def progress(request: Request, db: Session = Depends(get_db)):
    return analytics_service.progress(db, request.state.user_id)


@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(request: Request, db: Session = Depends(get_db)):
    return analytics_service.analytics(db, request.state.user_id)
