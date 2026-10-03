"""Safe UTF-8 SMTP sender with explicit real-send opt-in."""
import os
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, List
from dotenv import load_dotenv
from models.schemas import GeneratedEmail
from config.logging import logger

load_dotenv()


class EmailSender:
    """Handles demo/real SMTP sending. Real sending is opt-in and approval-gated."""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USERNAME", "")
        self.smtp_pass = os.getenv("SMTP_PASSWORD", "")
        # Google displays App Passwords in groups of four characters; SMTP
        # authentication expects the underlying 16-character value.
        if self.smtp_host.lower() == "smtp.gmail.com":
            self.smtp_pass = "".join(self.smtp_pass.split())
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.sender_email = os.getenv("SENDER_EMAIL", self.smtp_user)
        self.sender_name = os.getenv("SENDER_NAME", "ColdMail AI")
        self.demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"
        self.real_send_enabled = os.getenv("ENABLE_REAL_EMAIL_SEND", "false").lower() == "true"

    def send(self, email: GeneratedEmail, resume_path: str = None, approval_verified: bool = False) -> Dict[str, Any]:
        logger.info(f"Preparing email to {email.recipient_email}...")

        if self.demo_mode or not self.real_send_enabled:
            reason = "DEMO_MODE is enabled" if self.demo_mode else "real email sending is disabled"
            logger.info(f"SAFE SEND: {reason}; simulating delivery to {email.recipient_email}")
            return {"success": True, "demo": True, "recipient": email.recipient_email, "subject": email.subject, "message": f"Email simulated ({reason})."}

        if not approval_verified:
            return {"success": False, "demo": False, "recipient": email.recipient_email, "error": "Real email sending requires explicit human approval."}

        if not all([self.smtp_host, self.smtp_user, self.smtp_pass, self.sender_email]):
            return {"success": False, "demo": False, "recipient": email.recipient_email, "error": "SMTP is not fully configured."}

        try:
            msg = MIMEMultipart("mixed")
            msg["From"] = f"{str(Header(self.sender_name, 'utf-8'))} <{self.sender_email}>"
            msg["To"] = email.recipient_email
            msg["Subject"] = str(Header(self._clean(email.subject), "utf-8"))
            clean_body = self._clean(email.body)

            body_part = MIMEMultipart("alternative")
            body_part.attach(MIMEText(clean_body, "plain", "utf-8"))
            body_part.attach(MIMEText(self._body_to_html(clean_body), "html", "utf-8"))
            msg.attach(body_part)

            if resume_path and os.path.exists(resume_path):
                with open(resume_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                filename = os.path.basename(resume_path)
                part.add_header("Content-Disposition", "attachment", filename=str(Header(filename, "utf-8")))
                msg.attach(part)

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)

            logger.info(f"Email sent to {email.recipient_email}")
            return {"success": True, "demo": False, "recipient": email.recipient_email, "subject": email.subject}
        except Exception as exc:
            logger.error(f"Failed to send email to {email.recipient_email}: {type(exc).__name__}: {exc}", exc_info=True)
            return {"success": False, "demo": False, "recipient": email.recipient_email, "error": str(exc)}

    @staticmethod
    def _body_to_html(body: str) -> str:
        """Create a lightweight HTML alternative with genuinely clickable URLs."""
        import html as html_lib
        import re
        escaped = html_lib.escape(body or "")
        url_pattern = r"(https?://[^\s<>]+)"

        def make_link(match):
            raw = match.group(1)
            url = raw.rstrip(".,;)")
            trailing = raw[len(url):]
            safe_url = html_lib.escape(url, quote=True)
            return f'<a href="{safe_url}" style="color:#2563eb;text-decoration:none;">{safe_url}</a>{trailing}'

        linked = re.sub(url_pattern, make_link, escaped)
        paragraphs = [part for part in re.split(r"\n\s*\n", linked) if part.strip()]
        body_html = "".join(
            f'<p style="margin:0 0 16px">{part.replace(chr(10), "<br>")}</p>'
            for part in paragraphs
        )
        return (
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.7;'
            'color:#202124;max-width:680px">' + body_html + '</div>'
        )

    @staticmethod
    def _clean(value: str) -> str:
        return (value or "").replace("\xa0", " ").replace("\u200b", "").strip()

    def send_batch(self, emails: List[GeneratedEmail], resume_path: str = None, approval_verified: bool = False) -> List[Dict[str, Any]]:
        return [self.send(e, resume_path, approval_verified=approval_verified) for e in emails]
