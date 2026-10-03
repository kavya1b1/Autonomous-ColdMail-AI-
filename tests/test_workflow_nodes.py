from agents.nodes.human_approval import HumanApprovalNode
from models.schemas import GeneratedEmail


def test_human_approval_requires_explicit_submission():
    state = {
        "generated_emails": [GeneratedEmail(recipient_email="a@example.com", company_name="A", subject="s", body="This is a valid enough body for approval testing.", personalization_score=80)],
        "awaiting_approval": False,
        "approved_indices": [],
        "approval_submitted": False,
    }
    result = HumanApprovalNode()(state)
    assert result["awaiting_approval"] is True
    assert result["approval_submitted"] is False
