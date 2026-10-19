# Subjectly

Subjectly organizes study PDFs into searchable notes, provides an AI study assistant, and creates practice quizzes with progress tracking.

## Run on Windows

Open PowerShell in this folder (`ai-learning-notebook`) and run:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

If `.venv` does not exist yet, create it and install the packages first:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Add a fresh API key to `.env`:

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_new_openrouter_key
OPENROUTER_MODEL=openrouter/free
```

For Groq, use `AI_PROVIDER=groq`, `GROQ_API_KEY`, and `GROQ_MODEL` instead. Keep API keys private. Open the app at [http://127.0.0.1:8000](http://127.0.0.1:8000).

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal, then activate again.

## Sign-in setup

Subjectly supports individual student accounts. Open `/login` and choose **Create an account**; each account has its own subjects, uploaded PDFs, extracted notes, chats, quizzes, and progress. Existing study material from the earlier single-account setup is assigned to the account in `SUBJECTLY_LOGIN_EMAIL` when the app starts.

Set `SUBJECTLY_SESSION_SECRET` in `.env` before creating accounts. Generate one with:

```powershell
python -m app.services.auth_service
```

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Add the generated value to `.env` as `SUBJECTLY_SESSION_SECRET=<value>`. The old configured login credentials remain available for the existing account and its saved materials.

Set `SUBJECTLY_SESSION_COOKIE_SECURE=true` when serving the app over HTTPS. For local HTTP, keep it `false`. Restart the server after editing `.env`, then sign in at [http://127.0.0.1:8000/login](http://127.0.0.1:8000/login).

## Features

- Create and switch between study subjects
- Upload and remove PDFs, extract notes, and open original files
- Ask questions grounded in a selected subject's notes, with study, doubt, notes, exam, and review modes
- Generate and evaluate multiple choice and short answer quizzes
- Track subject completion, quiz results, assistant usage, and topics to revisit
