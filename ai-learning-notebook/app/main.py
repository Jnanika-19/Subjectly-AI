from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import inspect, text

from app.api.auth_routes import router as auth_router
from app.api.routes import router
from app.core.config import UPLOAD_DIR, settings
from app.db.database import Base, engine
from app.db.database import SessionLocal
from app.models.models import User
from app.services.auth_service import is_authenticated, require_login


Base.metadata.create_all(bind=engine)

# Upgrade older local databases without discarding existing subjects or notes.
if "user_id" not in {column["name"] for column in inspect(engine).get_columns("subjects")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE subjects ADD COLUMN user_id INTEGER REFERENCES users(id)"))

# Older installs enforced globally unique subject names. Rebuild that table so
# two students can each create a subject called (for example) "Biology".
if engine.dialect.name == "sqlite" and inspect(engine).get_unique_constraints("subjects"):
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE subjects_new (id INTEGER NOT NULL PRIMARY KEY, name TEXT NOT NULL, user_id INTEGER REFERENCES users(id), description TEXT NOT NULL, created_at DATETIME NOT NULL)"))
        connection.execute(text("INSERT INTO subjects_new (id, name, user_id, description, created_at) SELECT id, name, user_id, description, created_at FROM subjects"))
        connection.execute(text("DROP TABLE subjects"))
        connection.execute(text("ALTER TABLE subjects_new RENAME TO subjects"))
        connection.execute(text("CREATE INDEX ix_subjects_id ON subjects (id)"))
        connection.execute(text("CREATE INDEX ix_subjects_user_id ON subjects (user_id)"))

# Preserve the old installation account and attach its existing study material to it.
if settings.login_email and settings.login_password_hash:
    with SessionLocal() as db:
        legacy_user = db.query(User).filter(User.email == settings.login_email).first()
        if legacy_user is None:
            legacy_user = User(email=settings.login_email, password_hash=settings.login_password_hash)
            db.add(legacy_user)
            db.commit()
            db.refresh(legacy_user)
        db.execute(text("UPDATE subjects SET user_id = :user_id WHERE user_id IS NULL"), {"user_id": legacy_user.id})
        db.commit()

app = FastAPI(title=settings.app_name)
frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
templates = Jinja2Templates(directory=str(frontend_dir / "templates"))
app.mount("/static", StaticFiles(directory=str(frontend_dir / "static")), name="static")
app.include_router(auth_router)
app.include_router(router, dependencies=[Depends(require_login)])


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.app_name})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "app_name": settings.app_name})


@app.get("/uploads/{file_path:path}", dependencies=[Depends(require_login)])
def open_upload(file_path: str, request: Request):
    resolved_path = (UPLOAD_DIR / file_path).resolve()
    try:
        resolved_path.relative_to(UPLOAD_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="File not found.") from exc
    if not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    from app.db.database import SessionLocal
    from app.models.models import Document, Subject
    relative_url = "/" + resolved_path.relative_to(UPLOAD_DIR.parent).as_posix()
    with SessionLocal() as db:
        allowed = db.query(Document.id).join(Subject).filter(
            Document.file_path == relative_url, Subject.user_id == request.state.user_id
        ).first()
    if not allowed:
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(resolved_path, media_type="application/pdf")
