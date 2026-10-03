from agents.researcher import CompanyResearcher

def test_personal_email_is_not_researched_as_company():
    result = CompanyResearcher().research("person@gmail.com")
    assert result["is_personal_email"] is True
    assert result["evidence"] == []

def test_company_research_can_be_mocked(monkeypatch):
    researcher = CompanyResearcher()
    monkeypatch.setattr(researcher, "_fetch", lambda url: "Example is a SaaS company using Python and FastAPI. We build AI products.")
    result = researcher.research("jobs@example.com", known_name="Example")
    assert result["name"] == "Example"
    assert result["evidence"]
    assert "Python" in result["tech_stack"]
