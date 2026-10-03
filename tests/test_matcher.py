from agents.matcher import PersonalizationMatcher, normalize_skill
from models.schemas import CompanyInfo, JobDescription, UserProfile

def profile():
    return UserProfile(name="Test User", email="test@example.com", college="VIT", degree="B.Tech", graduation_year=2027, skills=["Python", "GenAI", "FastAPI"], objective="AI engineering")

def test_skill_normalization():
    assert normalize_skill("GenAI") == "generative ai"
    assert normalize_skill("LLMs") == "llm"

def test_match_produces_explainable_scores():
    job = JobDescription(required_skills=["Python", "Generative AI"], preferred_skills=["Docker"], responsibilities=["Build AI applications"])
    result = PersonalizationMatcher().match(profile(), CompanyInfo(name="Example", domain="example.com", industry="technology"), job)
    assert 0 <= result.overall_score <= 100
    assert result.required_skill_match > 0
    assert result.talking_points
