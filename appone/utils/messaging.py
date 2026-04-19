import re
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

_SUSPICIOUS_KEYWORDS = [
    "email", "e-mail", "@", "gmail", "yahoo", "outlook",
    "phone", "call me", "whatsapp", "telegram", "skype",
    "facebook", "linkedin", "instagram", "twitter",
    "+234", "+1", "contact me at", "reach me",
]


def flag_suspicious_message(message_content: str) -> tuple[bool, str]:
    """
    Check if message contains suspicious content (personal contact info).

    Returns:
        (is_flagged: bool, reason: str)
    """
    content_lower = message_content.lower()

    for keyword in _SUSPICIOUS_KEYWORDS:
        if keyword in content_lower:
            return True, f"Detected potential personal information: '{keyword}'"

    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    if re.search(email_pattern, message_content):
        return True, "Email address detected in message"

    phone_pattern = r"\+?[\d\s\-\(\)]{10,}"
    if re.search(phone_pattern, message_content):
        return True, "Phone number detected in message"

    return False, ""


def send_notification_email(user_email: str, subject: str, message: str) -> bool:
    """
    Send a plain-text notification email via Gmail SMTP.

    Returns True on success, False on failure (error is logged).
    """
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=False,
        )
        logger.info("Notification email sent to %s | subject=%r", user_email, subject)
        return True
    except Exception as exc:
        logger.error(
            "send_notification_email FAILED | to=%s subject=%r | %s",
            user_email,
            subject,
            exc,
            exc_info=True,
        )
        return False
