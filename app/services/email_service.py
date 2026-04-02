import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """Send password reset email via configured SMTP server."""
    if not settings.smtp_host:
        logger.warning("SMTP_HOST is not configured; password reset email was not sent")
        return False

    sender = settings.smtp_from_email or settings.smtp_user
    if not sender:
        logger.warning("SMTP sender is not configured; password reset email was not sent")
        return False

    message = EmailMessage()
    message["Subject"] = "Reset your password"
    message["From"] = sender
    message["To"] = to_email
    message.set_content(
        "We received a request to reset your password.\n\n"
        f"Reset your password here: {reset_link}\n\n"
        "This link expires in 15 minutes.\n\n"
        "If you did not request this, you can ignore this email."
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        return True
    except Exception as exc:
        logger.error("Failed to send password reset email: %s", str(exc))
        return False
