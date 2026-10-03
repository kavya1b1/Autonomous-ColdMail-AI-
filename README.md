# ColdMail AI Pro v3.0

AI-assisted cold outreach with a FastAPI backend, LangGraph workflow, and vanilla HTML/CSS/JS frontend.

## P0 improvements

This version focuses on AI quality and reliability without adding external CRM/email integrations:

- AI opportunity extraction from unstructured recruiter messages
- Evidence-backed company research from public company pages
- Source/provenance records for company claims
- Semantic resume-to-JD matching with normalized skills
- Hybrid BM25 + dense retrieval over candidate resume evidence
- Structured Pydantic outputs for generated emails and reviews
- Evidence-aware email generation
- LLM review plus deterministic quality gates
- Automatic rewrite loop
- Explicit human approval before sending
- Safer environment configuration and regression tests

## Architecture

```text
Frontend
   |
   v
FastAPI
   |
   v
LangGraph
   |
   +--> Opportunity extraction
   +--> Company research --> Evidence
   +--> Resume/JD matching
   +--> Hybrid portfolio retrieval
   +--> Structured email generation
   +--> AI + deterministic review
   +--> Rewrite when needed
   +--> Human approval
   +--> SMTP send
```

## Quick start

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Add GROQ_API_KEY. SMTP credentials are optional; without them sending is demo mode.
uvicorn api.main:app --reload
```

Open `http://localhost:8000` in your browser. API docs are at `http://localhost:8000/docs`.

## Environment variables

At minimum, set:

```text
GROQ_API_KEY=...
```

For real SMTP sending, also set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and optionally `SENDER_NAME` / `SENDER_EMAIL`.

Never commit `.env`, API keys, SMTP passwords, uploaded resumes, logs, or generated vector data.

## Tests

```bash
GROQ_API_KEY='' pytest -q
```

The test suite covers schema validation, extraction parsing, semantic matching, evidence research (mocked), hybrid retrieval, and the human-approval gate.

## Docker

```bash
docker compose up --build
```

The application container exposes port 8000. PostgreSQL and Redis are included as infrastructure for future persistence/background-job work; the current P0 request path remains intentionally lightweight and uses the LangGraph memory checkpointer.
