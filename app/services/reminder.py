import smtplib
import time
from email.message import EmailMessage
from typing import Optional

from app.core.config import settings


class EmailReminderService:
    def is_configured(self) -> bool:
        return bool(
            settings.smtp_host
            and settings.smtp_username
            and settings.smtp_password
            and settings.email_from
            and settings.email_to
        )

    def send_email(self, subject: str, body: str) -> None:
        if not self.is_configured():
            raise ValueError("Email settings are incomplete. Please fill .env.")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.email_from
        message["To"] = settings.email_to
        message.set_content(body)

        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                if settings.smtp_use_ssl:
                    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20) as client:
                        client.login(settings.smtp_username, settings.smtp_password)
                        client.send_message(message)
                else:
                    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as client:
                        client.starttls()
                        client.login(settings.smtp_username, settings.smtp_password)
                        client.send_message(message)
                return
            except (smtplib.SMTPException, OSError) as exc:
                last_error = exc
                # Brief backoff for transient SMTP/network errors.
                if attempt < 2:
                    time.sleep(1.5)
        raise RuntimeError(f"Failed to send email after retries: {last_error}")
