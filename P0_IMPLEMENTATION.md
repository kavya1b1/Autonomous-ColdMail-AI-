# ColdMail AI — P0 Implementation

This release is based on the updated project architecture supplied by the author. It intentionally stops at P0; no CRM, enrichment, follow-up, analytics-learning, or other P1 work is included.

## Implemented

1. **Security hardening** — removed the local `.env` and credential-bearing `test.py` from the distributable project, added `.gitignore`, and made SMTP credentials optional for startup/demo mode.
2. **Evidence-backed company research** — fetches public company pages, extracts main content with `trafilatura` when available, falls back to BeautifulSoup, detects industry/technology signals, and records source-backed evidence.
3. **Semantic candidate matching** — normalized skill aliases plus Sentence Transformers similarity for required/preferred/JD technology matching, with explainable strengths and gaps.
4. **Hybrid portfolio retrieval** — BM25 + dense retrieval over resume/profile evidence, with cached embedding model initialization.
5. **Structured generation** — Pydantic-validated JSON output for subject/body/key points/evidence IDs.
6. **Grounding-aware generation** — company-specific claims are instructed to use supplied evidence IDs and neutral language when evidence is missing.
7. **AI reviewer** — LLM-based review for grammar, professionalism, personalization, clarity, spam, grounding, hallucination risk, and unsupported claims, combined with deterministic gates.
8. **Human approval gate** — explicit approval submission state prevents an empty default list from being mistaken for a completed approval action.
9. **Frontend transparency** — campaign review responses now include match scores, review scores, research confidence, and evidence metadata.
10. **Regression tests** — tests cover schemas, extraction parsing, semantic matching, research behavior, hybrid retrieval, and approval behavior.
11. **Docker fixes** — healthcheck now has `curl`; the broken Celery service reference was removed because no `workers.tasks` implementation exists in this P0 codebase.

## Validation

- `python -m compileall -q .` passes.
- `GROQ_API_KEY='' python -m pytest -q` passes: **10 tests passed** in the local validation environment.

## Final P0 hardening patch

- Research is now bounded and concurrent (`RESEARCH_MAX_CONCURRENCY`, `RESEARCH_HTTP_TIMEOUT`) so slow public pages cannot stall the entire campaign.
- Review uses strict JSON Schema output, a smaller completion budget, and defensive normalization for numeric/list fields.
- Real email delivery is explicitly opt-in via `ENABLE_REAL_EMAIL_SEND=true`; `DEMO_MODE=true` is the safe default.
- SendNode has a hard approval gate independent of the UI/API route.
- SMTP content is UTF-8 encoded and normalizes non-breaking/zero-width spaces; SMTP connections have a timeout.
- Campaign approval validates indices against the email count, not company metadata.
- LangGraph checkpoint deserialization explicitly allowlists first-party Pydantic models.
- Added P0 regression tests for demo-mode safety and approval gating.

Validation: `14 passed`; Python `compileall` passed. Live LangGraph runtime compilation was not executed in the build container because LangGraph is not installed there; the user's runtime environment should install the pinned requirement before launch.
