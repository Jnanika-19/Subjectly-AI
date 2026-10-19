# Subjectly

Subjectly is a FastAPI study workspace for uploading study PDFs and asking questions about them.

## Requirements

- Python 3.12 (the pinned NumPy and FAISS versions require a compatible Python version)
- An OpenRouter or Groq API key for AI-generated answers

## Run on Windows (PowerShell)

From the repository root, run:

```powershell
cd ai-learning-notebook
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `ai-learning-notebook/.env` and add your provider key. The default is OpenRouter; set `OPENROUTER_API_KEY` to your key. For Groq, set `AI_PROVIDER=groq` and configure `GROQ_API_KEY`. Then run:

```powershell
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

If PowerShell blocks virtual environment activation, run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal and activate again. If `py -3.12` is unavailable, install Python 3.12 first.

## Run on macOS or Linux

```bash
cd ai-learning-notebook
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Add your Groq API key to `.env`, then start the app with `uvicorn app.main:app --reload`.

## Sign-in setup

Subjectly requires a configured local account. In `ai-learning-notebook/.env`, set `SUBJECTLY_LOGIN_EMAIL` and `SUBJECTLY_SESSION_SECRET`. Generate a password hash from the `ai-learning-notebook` folder by running `python -m app.services.auth_service`, then paste the printed `SUBJECTLY_LOGIN_PASSWORD_HASH` into `.env`. Generate a session secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Restart the app and sign in at `http://127.0.0.1:8000/login`. Set `SUBJECTLY_SESSION_COOKIE_SECURE=true` when using HTTPS; keep it `false` for local HTTP.
