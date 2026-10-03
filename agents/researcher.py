"""Evidence-backed company research using public company web pages."""
import re
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urljoin

import httpx
try:
    import trafilatura
except ImportError:
    trafilatura = None
from bs4 import BeautifulSoup

from config.logging import logger
from models.schemas import ResearchEvidence

PERSONAL_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "hotmail.com",
    "outlook.com", "live.com", "icloud.com", "me.com", "mac.com",
    "protonmail.com", "zoho.com", "aol.com", "mail.com", "yandex.com",
    "qq.com", "163.com", "126.com", "foxmail.com",
}

TECH_TERMS = [
    "python", "javascript", "typescript", "react", "next.js", "node.js", "django", "flask",
    "fastapi", "java", "go", "rust", "aws", "azure", "gcp", "docker", "kubernetes",
    "terraform", "postgresql", "mysql", "mongodb", "redis", "kafka", "graphql", "rest api",
    "microservices", "serverless", "machine learning", "deep learning", "tensorflow", "pytorch",
    "generative ai", "genai", "llm", "rag", "langchain", "langgraph", "computer vision",
]

class CompanyResearcher:
    """Research company facts and retain source evidence for downstream grounding."""

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self.max_chars_per_page = 12000
        self.max_pages = 8

    def _extract_name_from_email(self, email: str) -> str:
        prefix = email.split("@")[0]
        cleaned = re.sub(r"[0-9._\-]+", " ", prefix).strip()
        words = [w.capitalize() for w in cleaned.split() if len(w) > 1]
        return " ".join(words) if words else prefix.capitalize()

    def _candidate_urls(self, domain: str) -> List[str]:
        base = f"https://{domain}/"
        paths = ["", "about", "company", "careers", "jobs", "products", "solutions"]
        return [urljoin(base, p) for p in paths]

    def _fetch(self, url: str) -> str:
        try:
            headers = {"User-Agent": "ColdMailAI/3.0 (+https://localhost)"}
            with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                response = client.get(url)
                response.raise_for_status()
            extracted = trafilatura.extract(response.text, include_links=True, include_tables=False) if trafilatura else None
            if extracted:
                return extracted[: self.max_chars_per_page]
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "noscript"]):
                tag.decompose()
            return soup.get_text(" ", strip=True)[: self.max_chars_per_page]
        except Exception as exc:
            logger.debug(f"Research fetch failed for {url}: {exc}")
            return ""

    def research(self, email: str, known_name: str = None) -> Dict[str, Any]:
        logger.info(f"Researching {email}...")
        known_name = known_name.strip() if known_name and known_name.strip() else None

        if "@" not in email:
            return {"name": known_name or email.capitalize(), "domain": email, "description": None,
                    "tech_stack": [], "is_personal_email": False, "role": None, "evidence": [], "research_confidence": 0.0}

        domain = email.split("@", 1)[1].lower().strip()
        if domain in PERSONAL_DOMAINS:
            person = known_name or self._extract_name_from_email(email)
            return {"name": person, "domain": domain, "description": f"Personal contact: {person}",
                    "tech_stack": [], "is_personal_email": True, "role": None, "evidence": [], "research_confidence": 0.2}

        company_name = known_name or domain.split(".")[0].replace("-", " ").replace("_", " ").title()
        evidence: List[ResearchEvidence] = []
        pages: Dict[str, str] = {}
        # Fetch candidate pages concurrently so one slow page cannot block the entire domain.
        urls = self._candidate_urls(domain)[: self.max_pages]
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=min(4, len(urls)), thread_name_prefix="company-page") as pool:
            future_map = {pool.submit(self._fetch, url): url for url in urls}
            for future in as_completed(future_map):
                url = future_map[future]
                try:
                    text = future.result()
                except Exception as exc:
                    logger.debug(f"Research page task failed for {url}: {exc}")
                    text = ""
                if text:
                    pages[url] = text

        homepage_url = next(iter(pages), f"https://{domain}/")
        homepage_text = pages.get(homepage_url, "")
        combined = "\n".join(pages.values())
        description = self._summary(combined, company_name)
        industry = self._infer_industry(combined)
        tech_stack = self._extract_tech(combined)
        careers_page = next((u for u in pages if any(x in u.lower() for x in ("career", "job"))), None)

        if description:
            evidence.append(self._evidence("company_description", description, homepage_url, combined))
        if industry:
            evidence.append(self._evidence("company_industry", f"{company_name} operates in {industry}.", homepage_url, combined))
        if tech_stack:
            evidence.append(self._evidence("company_technology", f"Public company pages mention {', '.join(tech_stack[:8])}.", homepage_url, combined))
        if careers_page:
            evidence.append(self._evidence("careers_page", f"A careers/jobs page is available at {careers_page}.", careers_page, pages[careers_page]))

        confidence = min(1.0, 0.35 + 0.15 * min(len(pages), 4) + 0.1 * min(len(evidence), 4)) if pages else 0.1
        return {
            "name": company_name,
            "domain": domain,
            "description": description or f"Public research was unavailable for {company_name}.",
            "tech_stack": tech_stack,
            "careers_page": careers_page,
            "industry": industry,
            "is_personal_email": False,
            "role": None,
            "evidence": evidence,
            "research_confidence": round(confidence, 2),
        }

    def _evidence(self, evidence_id: str, claim: str, url: str, text: str) -> ResearchEvidence:
        supporting = re.sub(r"\s+", " ", text).strip()[:500] if text else None
        return ResearchEvidence(id=evidence_id, claim=claim, source_url=url, supporting_text=supporting, confidence=0.8, retrieved_at=datetime.now())

    def _summary(self, text: str, company: str) -> str:
        if not text:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
        useful = [s for s in sentences if len(s) > 80]
        return " ".join(useful[:2])[:600]

    def _infer_industry(self, text: str) -> str:
        lower = text.lower()
        mapping = {
            "fintech": "financial technology", "healthcare": "healthcare", "cybersecurity": "cybersecurity",
            "edtech": "education technology", "e-commerce": "e-commerce", "saas": "SaaS",
            "cloud": "cloud technology", "artificial intelligence": "artificial intelligence",
            "machine learning": "artificial intelligence", "logistics": "logistics",
        }
        for term, label in mapping.items():
            if term in lower:
                return label
        return "technology" if lower else ""

    def _extract_tech(self, text: str) -> List[str]:
        lower = text.lower()
        found = []
        for term in TECH_TERMS:
            if term in lower:
                found.append(term.title() if term not in {"node.js", "next.js", "rest api", "generative ai", "machine learning", "deep learning", "computer vision"} else term)
        return list(dict.fromkeys(found))[:15]

    def research_batch(self, emails: List[str], known_names: List[str] = None) -> List[Dict[str, Any]]:
        known_names = known_names or [None] * len(emails)
        return [self.research(e, known_names[i] if i < len(known_names) else None) for i, e in enumerate(emails)]
