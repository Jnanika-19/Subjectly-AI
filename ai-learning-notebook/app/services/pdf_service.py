from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from pathlib import Path

import pdfplumber
from fastapi import UploadFile
from pypdf import PdfReader

from app.core.config import UPLOAD_DIR, settings
from app.models.models import Chunk, Document, Note
from app.utils.text import chunk_text, clean_text, detect_sections, summarize_section


logger = logging.getLogger(__name__)


class PDFService:
    def save_upload(self, subject_name: str, upload: UploadFile) -> Path:
        subject_slug = re.sub(r"[^a-z0-9_-]+", "_", subject_name.lower()).strip("_") or "subject"
        subject_dir = (UPLOAD_DIR / subject_slug).resolve()
        subject_dir.relative_to(UPLOAD_DIR.resolve())
        subject_dir.mkdir(parents=True, exist_ok=True)
        original_name = Path((upload.filename or "upload.pdf").replace("\\", "/")).name
        suffix = Path(original_name).suffix.lower() or ".pdf"
        target = subject_dir / f"{uuid.uuid4().hex}{suffix}"
        with target.open("wb") as file_handle:
            shutil.copyfileobj(upload.file, file_handle)
        return target

    def extract_text(self, file_path: Path) -> str:
        pages: list[str] = []
        try:
            reader = PdfReader(str(file_path))
            for page_number, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                pages.append(f"[Page {page_number}]\n{page_text}")
        except Exception:
            with pdfplumber.open(file_path) as pdf:
                for page_number, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text() or ""
                    pages.append(f"[Page {page_number}]\n{page_text}")
        return clean_text("\n\n".join(pages))

    def create_document_bundle(self, db, subject, upload: UploadFile) -> Document:
        file_path = self.save_upload(subject.name, upload)
        try:
            extracted_text = self.extract_text(file_path)
            content_text = re.sub(r"\[Page \d+\]", "", extracted_text).strip()
            if not content_text:
                raise ValueError("No selectable text was found in this PDF. Scanned PDFs need OCR before upload.")
            sections = detect_sections(extracted_text)

            relative_path = file_path.relative_to(UPLOAD_DIR.parent)
            original_name = Path((upload.filename or "upload.pdf").replace("\\", "/")).name
            document = Document(
                subject_id=subject.id,
                filename=original_name,
                file_path=f"/{relative_path.as_posix()}",
                extracted_text=extracted_text,
                structure_json=json.dumps(sections),
            )
            db.add(document)
            db.flush()

            for section in sections:
                note = Note(
                    subject_id=subject.id,
                    document_id=document.id,
                    title=section["title"],
                    chapter=section.get("chapter", ""),
                    unit=section.get("unit", ""),
                    content=section["content"],
                    summary=summarize_section(section["content"]),
                )
                db.add(note)
                db.flush()

                for index, chunk in enumerate(
                    chunk_text(section["content"], settings.chunk_words, settings.chunk_overlap)
                ):
                    db.add(
                        Chunk(
                            subject_id=subject.id,
                            document_id=document.id,
                            note_id=note.id,
                            chunk_index=index,
                            source_page=section.get("page", 1),
                            content=chunk,
                            metadata_json=json.dumps({"title": note.title, "page": section.get("page", 1)}),
                        )
                    )

            db.flush()
            return document
        except Exception:
            db.rollback()
            file_path.unlink(missing_ok=True)
            raise

    def delete_document_bundle(self, db, document: Document) -> None:
        relative_path = document.file_path.lstrip("/").replace("\\", "/")
        if relative_path.startswith("uploads/"):
            file_path = (UPLOAD_DIR / relative_path.removeprefix("uploads/")).resolve()
            try:
                file_path.relative_to(UPLOAD_DIR.resolve())
            except ValueError:
                file_path = None
        else:
            file_path = None
        db.delete(document)
        db.commit()
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                logger.warning("Could not remove deleted PDF file from disk: %s", file_path, exc_info=True)

    def remove_uploaded_file(self, file_url: str) -> None:
        relative_path = file_url.lstrip("/").replace("\\", "/")
        if not relative_path.startswith("uploads/"):
            return
        file_path = (UPLOAD_DIR / relative_path.removeprefix("uploads/")).resolve()
        try:
            file_path.relative_to(UPLOAD_DIR.resolve())
        except ValueError:
            return
        file_path.unlink(missing_ok=True)


pdf_service = PDFService()
