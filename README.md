# Subjectly

Subjectly is a FastAPI + vanilla frontend project that turns uploaded study PDFs into a polished AI study workspace. The app now uses secure backend-only Groq access, a simplified production-style service flow, and a modern chat-first interface.

## Folder Structure

```text
ai-learning-notebook/
├── app/
│   ├── api/
│   │   └── routes.py
│   ├── core/
│   │   └── config.py
│   ├── db/
│   │   └── database.py
│   ├── models/
│   │   └── models.py
│   ├── schemas/
│   │   └── schemas.py
│   ├── services/
│   │   ├── ai_service.py
│   │   ├── analytics_service.py
│   │   ├── embedding_service.py
│   │   ├── pdf_service.py
│   │   ├── quiz_service.py
│   │   └── rag_service.py
│   └── main.py
├── data/
│   ├── faiss/
│   └── uploads/
├── frontend/
│   ├── static/
│   │   ├── app.js
│   │   └── styles.css
│   └── templates/
│       └── index.html
├── .env.example
├── README.md
└── requirements.txt
```

## Architecture

Request flow:

1. Frontend sends only `{"question": "..."}` to `POST /chat`
2. `routes.py` handles request validation and error shaping
3. `rag_service.py` retrieves notebook context from FAISS + SQLite
4. `ai_service.py` sends the final prompt to Groq
5. FastAPI returns `{"answer": "..."}` or a clean `{"error": "..."}` response

## Security

- The frontend does not collect or store API keys
- Groq keys are loaded only from backend environment variables
- Missing-key error: `{"error": "API key not configured"}`
- Provider failure error: `{"error": "AI request failed. Check server logs."}`
- Actual Groq exceptions are logged server-side

## Environment Setup

Create `.env` in the project root:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant
EMBEDDING_PROVIDER=hf
HF_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

## Features

- Secure backend-managed Groq integration
- Subjectly brand redesign with sticky navbar
- Subject sidebar with upload workflow
- ChatGPT-style chat bubbles and markdown responses
- Local chat history with auto-scroll
- Loading spinner, toast errors, ripple buttons, and card animations
- RAG answer generation from uploaded notes
- File delete confirmation modal and smooth removal animation

## Run Locally

```bash
cd /Users/deekshasn/Documents/New\ project/ai-learning-notebook
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000)
