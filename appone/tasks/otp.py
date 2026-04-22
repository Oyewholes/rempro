import logging

from celery import shared_task
from django.utils import timezone

from appone.models import OTPVerification
from appone.utils import send_otp_email, send_otp_sms

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_otp_task(self, otp_id):
    try:
        otp = OTPVerification.objects.get(id=otp_id)

        if otp.is_verified:
            return {"success": True, "message": "OTP already verified"}

        if otp.expires_at < timezone.now():
            return {"success": False, "message": "OTP expired"}

        success = False
        if otp.otp_type == "phone":
            success = send_otp_sms(otp.phone_number, otp.otp_code)
        elif otp.otp_type in [
            "company_access",
            "profile_access",
            "company_email",
        ]:
            success = send_otp_email(otp.email, otp.otp_code, otp.otp_type)
        else:
            return {"success": False, "error": "Unknown OTP type"}

        if success:
            return {
                "success": True,
                "otp_id": str(otp_id),
                "otp_type": otp.otp_type,
            }

        if self.request.retries < self.max_retries:
            raise self.retry(exc=Exception("SMS/Email sending failed"))

        return {"success": False, "error": "Failed to send OTP after retries"}

    except OTPVerification.DoesNotExist:
        return {"success": False, "error": "OTP not found"}
    except Exception as e:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {"success": False, "error": str(e)}


@shared_task
def cleanup_expired_otps():
    try:
        expired = OTPVerification.objects.filter(
            is_verified=False, expires_at__lt=timezone.now()
        )
        count = expired.count()
        expired.delete()
        return {"deleted": count}
    except Exception as e:
        return {"error": str(e)}
