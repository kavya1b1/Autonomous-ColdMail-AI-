from agents.extractor import OpportunityExtractor

def test_safe_parse_json():
    extractor = OpportunityExtractor()
    data = extractor._safe_parse_json('[{"company":"Example","email":"hr@example.com","role":"AI Intern","job_description":"Build AI systems"}]')
    assert data[0]["company"] == "Example"


def test_extraction_budget_defaults():
    extractor = OpportunityExtractor()
    assert extractor.max_input_chars == 12000
    assert extractor.max_output_tokens == 1200
