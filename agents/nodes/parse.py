"""Parser Agent Nodes - Resume and Job Description"""
from utils.pdf_utils import extract_text_from_pdf_path
import re
from typing import Optional
from agents.state import AgentState
from models.schemas import ResumeParseResult, JobDescription, UserProfile
from config.logging import logger


class ResumeParserNode:
    """Parse PDF resume and extract structured information"""

    def __init__(self):
        logger.info("ResumeParserNode initialized")

    def __call__(self, state: AgentState) -> dict:
        """Parse resume from path"""
        resume_path = state.get("resume_path")
        if not resume_path:
            return {"logs": ["ResumeParser: No resume path provided"]}

        logger.info(f"ResumeParser: Parsing {resume_path}")

        try:
            result = self._parse_pdf(resume_path)

            # Create user profile from parsed data
            profile = UserProfile(
                name=result.name or "",
                email=result.email or "",
                phone=result.phone,
                linkedin=result.linkedin,
                github=result.github,
                portfolio=result.portfolio,
                leetcode=result.leetcode,
                resume_path=resume_path,
                resume_text=result.raw_text,
                college="",
                degree="",
                graduation_year=2026,
                skills=result.skills,
                objective="",
                tone="professional"
            )

            return {
                "user_profile": profile,
                "logs": [f"ResumeParser: Parsed resume for {result.name}"]
            }

        except Exception as e:
            logger.error(f"ResumeParser error: {e}")
            return {
                "errors": [f"Resume parsing failed: {e}"],
                "logs": ["ResumeParser: Failed"]
            }

    def _parse_pdf(self, path: str) -> ResumeParseResult:
        """Extract text and structure from PDF"""
        text = extract_text_from_pdf_path(path)
        if text.startswith("[Error"):
            raise ValueError(text)

        result = ResumeParseResult(raw_text=text)

        # Extract email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            result.email = email_match.group()

        # Extract phone
        phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
        if phone_match:
            result.phone = phone_match.group()

        # Extract LinkedIn
        linkedin_match = re.search(r'linkedin\.com/in/[\w-]+', text)
        if linkedin_match:
            result.linkedin = f"https://{linkedin_match.group()}"

        # Extract GitHub
        github_match = re.search(r'github\.com/[\w-]+', text)
        if github_match:
            result.github = f"https://{github_match.group()}"

        # Extract LeetCode profile
        leetcode_match = re.search(r'(?:https?://)?(?:www\.)?leetcode\.com/u?/([A-Za-z0-9_-]+)\/?', text, re.I)
        if leetcode_match:
            result.leetcode = f"https://leetcode.com/u/{leetcode_match.group(1)}/"

        # Extract skills (common tech keywords)
        tech_skills = [
            "python", "javascript", "typescript", "react", "vue", "angular",
            "node.js", "django", "flask", "fastapi", "java", "go", "rust",
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
            "postgresql", "mysql", "mongodb", "redis",
            "machine learning", "deep learning", "tensorflow", "pytorch",
            "html", "css", "sass", "tailwind", "bootstrap"
        ]

        text_lower = text.lower()
        found_skills = []
        for skill in tech_skills:
            if skill in text_lower:
                found_skills.append(skill.title() if skill != "node.js" else "Node.js")

        result.skills = list(dict.fromkeys(found_skills))

        # Extract name (first line or after "Name:")
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if lines:
            result.name = lines[0]

        return result


class JobDescriptionParserNode:
    """Parse job description from text, PDF, or URL"""

    def __init__(self):
        logger.info("JobDescriptionParserNode initialized")

    def __call__(self, state: AgentState) -> dict:
        """Parse job description"""
        jd = state.get("job_description")
        if not jd or not jd.raw_text:
            return {"logs": ["JDParser: No job description provided"]}

        logger.info("JDParser: Parsing job description")

        try:
            parsed = self._parse_jd(jd.raw_text)
            return {
                "job_description": parsed,
                "logs": ["JDParser: Parsed successfully"]
            }
        except Exception as e:
            logger.error(f"JDParser error: {e}")
            return {
                "errors": [f"JD parsing failed: {e}"],
                "logs": ["JDParser: Failed"]
            }

    def _parse_jd(self, text: str) -> JobDescription:
        """Extract structured info from job description text"""
        text_lower = text.lower()

        jd = JobDescription(raw_text=text)

        # Extract title
        title_patterns = [
            r'(?:job title|position|role)[\s:]+([^\n]+)',
            r'^([^\n]+)(?:\n|\r)',
        ]
        for pattern in title_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                jd.title = match.group(1).strip()
                break

        # Extract required skills
        req_section = re.search(r'(?:requirements|required skills|qualifications)[\s:]*([^#]+?)(?=preferred|responsibilities|benefits|$)', text, re.I)
        if req_section:
            req_text = req_section.group(1)
            jd.required_skills = self._extract_skills(req_text)

        # Extract preferred skills
        pref_section = re.search(r'(?:preferred|nice to have|bonus)[\s:]*([^#]+?)(?=responsibilities|benefits|$)', text, re.I)
        if pref_section:
            jd.preferred_skills = self._extract_skills(pref_section.group(1))

        # Extract responsibilities
        resp_section = re.search(r'(?:responsibilities|what you.ll do|role)[\s:]*([^#]+?)(?=requirements|qualifications|benefits|$)', text, re.I)
        if resp_section:
            resp_text = resp_section.group(1)
            jd.responsibilities = [r.strip() for r in resp_text.split('\n') if r.strip() and len(r.strip()) > 10]

        # Extract experience
        exp_match = re.search(r'(\d+)\+?\s*years?(?:\s*of)?\s*(?:experience|exp)', text, re.I)
        if exp_match:
            jd.experience_level = f"{exp_match.group(1)}+ years"

        # Extract tech stack
        jd.tech_stack = self._extract_skills(text)

        return jd

    def _extract_skills(self, text: str) -> list:
        """Extract skills from text"""
        tech_skills = [
            "python", "javascript", "typescript", "react", "vue", "angular",
            "node.js", "django", "flask", "fastapi", "spring", "java", "go",
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
            "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
            "machine learning", "deep learning", "tensorflow", "pytorch",
            "graphql", "rest api", "microservices", "serverless",
            "ci/cd", "github actions", "jenkins", "gitlab"
        ]

        text_lower = text.lower()
        found = []
        for skill in tech_skills:
            if skill in text_lower:
                found.append(skill.title() if skill != "node.js" else "Node.js")
        return list(dict.fromkeys(found))
