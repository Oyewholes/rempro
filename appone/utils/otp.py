import random
import string
import requests
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def generate_otp(length=6):
    """Generate a random numeric OTP code."""
    return "".join(random.choices(string.digits, k=length))


def send_otp_sms(phone_number, otp_code):
    """
    Send OTP via SMS using Twilio (with Windows SSL error handling).

    Args:
        phone_number (str): Phone number in format +234XXXXXXXXXX
        otp_code (str): The OTP code to send

    Returns:
        bool: True if SMS sent successfully, False otherwise
    """
    try:
        if not all([
            getattr(settings, "TWILIO_ACCOUNT_SID", None),
            getattr(settings, "TWILIO_AUTH_TOKEN", None),
            getattr(settings, "TWILIO_PHONE_NUMBER", None),
        ]):
            if settings.DEBUG:
                return True
            return False

        try:
            from twilio.rest import Client
            from twilio.http.http_client import TwilioHttpClient
        except ImportError:
            if settings.DEBUG:
                return True
            return False

        http_client = TwilioHttpClient()
        if settings.DEBUG and hasattr(http_client, "session"):
            http_client.session.verify = False

        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            http_client=http_client,
        )
        client.messages.create(
            body=(
                f"Your Virtual Citizenship verification code is: {otp_code}\n"
                "This code will expire in 10 minutes.\n"
                "Do not share this code with anyone."
            ),
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number,
        )
        return True
    except Exception:
        if settings.DEBUG:
            return True
        return False


def send_otp_sms_africas_talking(phone_number, otp_code):
    """Send OTP via SMS using Africa's Talking."""
    try:
        url = "https://api.africastalking.com/version1/messaging"
        headers = {
            "ApiKey": settings.SMS_API_KEY,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "username": settings.SMS_USERNAME,
            "to": phone_number,
            "message": (
                f"Your Virtual Citizenship verification code is: {otp_code}."
                " Valid for 10 minutes."
            ),
            "from": settings.SMS_SENDER_ID,
        }
        response = requests.post(url, headers=headers, data=data)
        return response.status_code == 200
    except Exception:
        return False


def send_otp_email(email: str, otp_code: str, otp_type: str = "verification") -> bool:
    """
    Send an OTP code to the given email address via Gmail SMTP.

    Returns True on success, False on failure (error is logged).
    """
    type_label = otp_type.replace("_", " ").title()
    subject = f"Virtual Citizenship - {type_label} Code"
    message = (
        f"Your Virtual Citizenship verification code is: {otp_code}\n\n"
        "This code expires in 10 minutes.\n\n"
        "If you did not request this, please ignore this email.\n\n"
        "— Virtual Citizenship Team"
    )
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        logger.info("OTP email sent to %s (type=%s)", email, otp_type)
        return True
    except Exception as exc:
        logger.error(
            "send_otp_email FAILED | to=%s type=%s | %s",
            email,
            otp_type,
            exc,
            exc_info=True,
        )
        return False


def send_otp(contact_info, otp_code, method="auto"):
    """
    Universal OTP sender — automatically detects phone vs email.

    Returns:
        tuple: (success: bool, method_used: str)
    """
    if method == "auto":
        if "@" in contact_info:
            method = "email"
        elif contact_info.startswith("+"):
            method = "sms"
        else:
            return False, "unknown"

    if method == "email":
        return send_otp_email(contact_info, otp_code), "email"

    if method in ["sms", "twilio"]:
        if send_otp_sms(contact_info, otp_code):
            return True, "twilio"
        if hasattr(settings, "SMS_API_KEY"):
            if send_otp_sms_africas_talking(contact_info, otp_code):
                return True, "africas_talking"

    if method == "africas_talking":
        return send_otp_sms_africas_talking(contact_info, otp_code), "africas_talking"

    return False, "failed"
