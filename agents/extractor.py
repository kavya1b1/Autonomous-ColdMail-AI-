"""Opportunity Extraction Agent

Takes a single blob of unstructured, possibly-mixed text (recruiter emails,
LinkedIn messages, WhatsApp chats, job descriptions, forwarded threads, etc.)
and uses the Groq LLM to intelligently identify every distinct job/internship
opportunity contained in it, returning structured data:

    { "company": ..., "email": ..., "role": ..., "job_description": ... }

This is intentionally LLM-first (not regex-first): unstructured human text
(chat exports, forwarded emails, casual phrasing) does not follow a fixed
grammar, so a language model is far more robust than pattern matching at
telling "this is a company offering a role" apart from surrounding noise.
Regex is only used defensively, to clean up the model's raw output (e.g.
stripping markdown code fences) — never to do the actual extraction.
"""
import json
import os
import re
from typing import List

from dotenv import load_dotenv
try:
    from groq import Groq
except ImportError:
    Groq = None

from config.logging import logger
from config.settings import settings
from models.schemas import ExtractedOpportunity

load_dotenv()


EXTRACTION_SYSTEM_PROMPT = """You are an expert information-extraction assistant for a job-application \
assistant tool. You will be given a raw blob of text that may contain one or more of the following, \
mixed together in any order: recruiter emails, LinkedIn messages, WhatsApp/Slack chat exports, job \
postings, forwarded email threads, or plain notes.

Your job is to carefully read the ENTIRE text and identify every DISTINCT job/internship opportunity \
mentioned. A single opportunity is defined by a unique combination of a company (or hiring contact) and \
a role. If the same company/contact appears multiple times about the same role, merge it into ONE \
opportunity and combine any extra details. If a company has multiple different open roles, list them as \
separate opportunities.

For every opportunity, extract:
- "company": The company name. If it's a personal/individual contact rather than a company, use the \
person's name or "Unknown" only if truly nothing identifies them.
- "email": The best email address to send a cold outreach / application email to. Prefer a recruiter's \
or HR's direct email over a generic careers@ address if both are present. If no email address appears \
anywhere for this opportunity, return an empty string "" — do NOT invent one.
- "role": The job title / position being discussed. If not explicitly stated, infer the most likely \
role title from context (e.g. from required skills). If truly unclear, use "Not specified".
- "job_description": A consolidated plain-text summary of any responsibilities, requirements, skills, \
qualifications, or other job-relevant details mentioned for this opportunity. If none are present, \
return an empty string "".

Rules:
- Never fabricate an email address, company name, or requirement that is not supported by the text.
- Ignore irrelevant chit-chat, greetings, or signatures that don't carry opportunity information.
- If the text contains no identifiable opportunities at all, return an object with an empty "opportunities" array.
- Output ONLY a valid JSON object with exactly one key, "opportunities", whose value is an array of objects with exactly the keys: company, email, role, job_description.
- Do NOT wrap the JSON in markdown code fences. Do NOT include any explanation, preamble, or commentary.
"""


class OpportunityExtractor:
    """LLM-powered extraction of structured job opportunities from raw pasted text."""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.client = Groq(api_key=self.api_key) if self.api_key and Groq else None
        # Extraction is a high-volume, structured task. Keep the prompt well below
        # Groq's on-demand TPM ceiling instead of spending most of the budget on
        # a large completion that is rarely needed for opportunity extraction.
        self.model = getattr(settings, "GROQ_MODEL", None) or "llama-3.3-70b-versatile"
        self.max_input_chars = int(getattr(settings, "GROQ_EXTRACTION_MAX_INPUT_CHARS", 12000))
        self.max_output_tokens = int(getattr(settings, "GROQ_EXTRACTION_MAX_TOKENS", 1200))

    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)

    def extract(self, raw_text: str) -> List[ExtractedOpportunity]:
        """Extract structured opportunities from raw text using the LLM."""
        if not raw_text or not raw_text.strip():
            return []

        if not self.is_available():
            raise RuntimeError("GROQ_API_KEY is not configured on the server; AI extraction is unavailable.")

        text = raw_text.strip()
        if len(text) > self.max_input_chars:
            logger.warning(f"Extraction input truncated from {len(text)} to {self.max_input_chars} chars")
            text = text[: self.max_input_chars]

        user_prompt = f"Extract every job/internship opportunity from the following text:\n\n---\n{text}\n---"

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "job_opportunities",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "opportunities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "company": {"type": "string"},
                                    "email": {"type": "string"},
                                    "role": {"type": "string"},
                                    "job_description": {"type": "string"},
                                },
                                "required": ["company", "email", "role", "job_description"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["opportunities"],
                    "additionalProperties": False,
                },
            },
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=self.max_output_tokens,
                reasoning_effort="low",
                response_format=response_format,
            )
            content = (response.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error(f"Groq extraction call failed: {e}")
            raise RuntimeError(f"AI extraction request failed: {e}")

        if not content:
            logger.warning("Groq returned an empty extraction response; retrying with a compact prompt")
            compact_text = self._compact_input(text)
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": "Extract opportunities from this compacted text. Return only the requested structured JSON.\n\n" + compact_text,
                        },
                    ],
                    temperature=0.0,
                    max_tokens=min(self.max_output_tokens, 800),
                    reasoning_effort="low",
                    response_format=response_format,
                )
                content = (response.choices[0].message.content or "").strip()
            except Exception as e:
                logger.error(f"Groq extraction retry failed: {e}")
                raise RuntimeError(f"AI extraction retry failed: {e}")

        raw_items = self._safe_parse_json(content)

        opportunities: List[ExtractedOpportunity] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            try:
                opportunities.append(
                    ExtractedOpportunity(
                        company=str(item.get("company") or "").strip(),
                        email=str(item.get("email") or "").strip(),
                        role=str(item.get("role") or "").strip(),
                        job_description=str(item.get("job_description") or "").strip(),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping malformed extracted opportunity: {e}")

        logger.info(f"OpportunityExtractor: extracted {len(opportunities)} opportunit(y/ies)")
        return opportunities

    def _compact_input(self, text: str) -> str:
        """Keep the highest-signal portions for a retry after an empty response."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        priority = []
        remainder = []
        signal = re.compile(r"(?:@|https?://|\b(?:role|position|job|intern|engineer|developer|recruiter|hiring|skills?|experience|responsibilit(?:y|ies)|requirements?|company)\b)", re.I)
        for line in lines:
            (priority if signal.search(line) else remainder).append(line)
        compact = "\n".join(priority + remainder[:80])
        return compact[:8000]

    def _safe_parse_json(self, content: str) -> list:
        """Defensively clean up the model's output before json.loads.

        This is NOT the extraction logic (the LLM did that) — it just strips
        markdown fences / stray prose the model might still emit despite
        instructions, so we can reliably parse the JSON it produced.
        """
        cleaned = content.strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Extraction JSON parse failed: {e}\nRaw content (first 500 chars): {content[:500]}")
            raise ValueError(
                "The AI's extraction response could not be parsed. Please try again, "
                "or paste a smaller / cleaner excerpt of the text."
            )

        if isinstance(data, dict):
            data = data.get("opportunities", [data])

        if not isinstance(data, list):
            raise ValueError("The AI's extraction response was not in the expected list format.")

        return data
