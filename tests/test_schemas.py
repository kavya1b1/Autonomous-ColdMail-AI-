from models.schemas import CompanyInfo, GeneratedEmail, GeneratedEmailPayload, ResearchEvidence

def test_generated_email_supports_evidence_provenance():
    email = GeneratedEmail(recipient_email="recruiter@example.com", company_name="Example", subject="AI Engineer application", body="Hello, I am interested in the AI Engineer role at Example.", personalization_score=82, evidence_ids=["company_technology"])
    assert email.evidence_ids == ["company_technology"]

def test_company_evidence_schema():
    company = CompanyInfo(name="Example", domain="example.com", evidence=[ResearchEvidence(id="about", claim="Example builds software.", source_url="https://example.com/about")])
    assert company.evidence[0].source_url.startswith("https://")

def test_structured_email_payload_validation():
    payload = GeneratedEmailPayload(subject="Application", body="This is a sufficiently long email body for schema validation.")
    assert payload.subject == "Application"
