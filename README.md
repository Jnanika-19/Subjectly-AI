# Subjectly

Subjectly is a study workspace for organizing course PDFs, asking questions about your notes, and practicing with quizzes.

## Requirements

- Python 3.12
- An API key from OpenRouter or Groq for AI answers

## Run locally on Windows

Open PowerShell in the repository root (the folder containing this README), then run:

```powershell
cd .\ai-learning-notebook
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-local.txt
Copy-Item .env.example .env
```

Open `ai-learning-notebook/.env` and add your AI provider key. OpenRouter is the default:

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_api_key
```

For Groq, set `AI_PROVIDER=groq` and add `GROQ_API_KEY` instead. Keep this file private; never commit API keys.

Create a session secret and add it to `.env`:

```powershell
py -3.12 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the printed value into `.env`:

```env
SUBJECTLY_SESSION_SECRET=paste_the_generated_value_here
```

Start the server from the `ai-learning-notebook` folder:

```powershell
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000), select **Create an account**, and register with an email and a password of at least 12 characters. Account creation does not send an email verification message.

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal and activate again. If `py -3.12` is unavailable, install Python 3.12 and reopen PowerShell.

## Run locally on macOS or Linux

From the repository root:

```bash
cd ai-learning-notebook
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-local.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Add your AI provider key and the generated value as `SUBJECTLY_SESSION_SECRET` in `.env`, then start the server with `uvicorn app.main:app --reload`.

## Deployment notes

Subjectly is a FastAPI application. On Vercel, set the Root Directory to `ai-learning-notebook` and the Framework Preset to **FastAPI**. Leave the **Install Command override off** so Vercel can optimize the function bundle. The standard `requirements.txt` omits the large local `sentence-transformers` model; for local development, install `requirements-local.txt` instead.

Add `EMBEDDING_PROVIDER=mock` in Vercel's environment variables to use the lightweight built-in embedding option. It avoids the local model; semantic retrieval quality is lower, while keyword matching remains available. For OpenAI embeddings instead, use `EMBEDDING_PROVIDER=openai` and provide `OPENAI_API_KEY`.

Configure `SUBJECTLY_SESSION_SECRET` and your chat provider key as private environment variables in the host dashboard. Set `SUBJECTLY_SESSION_COOKIE_SECURE=true` when serving over HTTPS.

The app stores its SQLite database, uploaded PDFs, and search indexes under `ai-learning-notebook/data`. Use persistent storage for that directory, or configure external database and file storage, so user data survives restarts and redeployments. Do not commit `.env` or personal study data.

See [ai-learning-notebook/README.md](ai-learning-notebook/README.md) for the app feature list and additional account details.
