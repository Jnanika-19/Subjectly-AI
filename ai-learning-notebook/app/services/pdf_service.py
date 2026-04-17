from __future__ import annotations

import json
import shutil
from pathlib import Path

import pdfplumber
from fastapi import UploadFile
from pypdf import PdfReader

from app.core.config import PROJECT_ROOT, UPLOAD_DIR, settings
from app.models.models import Chunk, Document, Note
from app.utils.text import chunk_text, clean_text, detect_sections, summarize_section


class PDFService:
    def save_upload(self, subject_name: str, upload: UploadFile) -> Path:
        subject_dir = UPLOAD_DIR / subject_name.replace(" ", "_").lower()
        subject_dir.mkdir(parents=True, exist_ok=True)
        target = subject_dir / upload.filename
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
        extracted_text = self.extract_text(file_path)
        sections = detect_sections(extracted_text)

        relative_path = file_path.relative_to(UPLOAD_DIR.parent)
        document = Document(
            subject_id=subject.id,
            filename=upload.filename,
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

        db.commit()
        db.refresh(document)
        return document

    def delete_document_bundle(self, db, document: Document) -> None:
        file_url = document.file_path.lstrip("/")
        file_path = PROJECT_ROOT / file_url
        db.delete(document)
        db.commit()
        if file_path.exists():
            file_path.unlink()


pdf_service = PDFService()
