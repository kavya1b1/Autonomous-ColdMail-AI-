from models.schemas import GeneratedEmail
from agents.sender import EmailSender
from agents.nodes.send import SendNode


def _email():
    return GeneratedEmail(
        recipient_email="test@example.com",
        company_name="Example",
        subject="Test",
        body="Hello",
        personalization_score=50,
    )


def test_sender_defaults_to_safe_demo_mode(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("ENABLE_REAL_EMAIL_SEND", raising=False)
    sender = EmailSender()
    result = sender.send(_email())
    assert result["success"] is True
    assert result["demo"] is True


def test_sender_cannot_send_without_explicit_real_send_opt_in(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("ENABLE_REAL_EMAIL_SEND", "false")
    sender = EmailSender()
    result = sender.send(_email(), approval_verified=True)
    assert result["success"] is True
    assert result["demo"] is True


def test_send_node_blocks_without_human_approval():
    node = SendNode()
    state = {"generated_emails": [_email()], "approved_indices": [], "approval_submitted": False}
    result = node(state)
    assert result["send_results"]["blocked"] is True
    assert result["send_results"]["sent"] == 0
