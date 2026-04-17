from __future__ import annotations

from sqlalchemy import func
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Document, Note, Subject
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


@router.post("/subjects", response_model=SubjectRead)
def create_subject(payload: SubjectCreate, db: Session = Depends(get_db)):
    existing = db.query(Subject).filter(Subject.name.ilike(payload.name.strip())).first()
    if existing:
        raise HTTPException(status_code=400, detail="Subject already exists.")
    subject = Subject(name=payload.name.strip(), description=payload.description.strip())
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.get("/subjects", response_model=list[SubjectRead])
def list_subjects(db: Session = Depends(get_db)):
    rows = (
        db.query(
            Subject,
            func.count(func.distinct(Document.id)).label("document_count"),
            func.count(func.distinct(Note.id)).label("note_count"),
        )
        .outerjoin(Document, Document.subject_id == Subject.id)
        .outerjoin(Note, Note.subject_id == Subject.id)
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
    subject_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    document = pdf_service.create_document_bundle(db, subject, file)
    embedding_service.rebuild_subject_index(db, subject.id)
    return {
        "message": "PDF uploaded and indexed successfully.",
        "document_id": document.id,
        "filename": document.filename,
    }


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    subject_id = document.subject_id
    pdf_service.delete_document_bundle(db, document)
    embedding_service.rebuild_subject_index(db, subject_id)
    return {"message": "Document deleted successfully."}


@router.get("/notes", response_model=NotesResponse)
def get_notes(subject_id: int | None = None, db: Session = Depends(get_db)):
    notes_query = db.query(Note)
    docs_query = db.query(Document)
    if subject_id:
        notes_query = notes_query.filter(Note.subject_id == subject_id)
        docs_query = docs_query.filter(Document.subject_id == subject_id)
    return NotesResponse(notes=notes_query.order_by(Note.created_at.desc()).all(), documents=docs_query.all())


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    try:
        return rag_service.answer(db, payload)
    except APIKeyNotConfiguredError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    except AIRequestFailedError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})


@router.post("/test", response_model=TestResponse)
def generate_test(payload: TestRequest, db: Session = Depends(get_db)):
    return quiz_service.generate_test(db, payload.subject_id, payload.count)


@router.post("/evaluate", response_model=EvaluationResponse)
def evaluate(payload: EvaluationRequest, db: Session = Depends(get_db)):
    return quiz_service.evaluate(db, payload)


@router.get("/progress", response_model=ProgressResponse)
def progress(db: Session = Depends(get_db)):
    return analytics_service.progress(db)


@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(db: Session = Depends(get_db)):
    return analytics_service.analytics(db)
