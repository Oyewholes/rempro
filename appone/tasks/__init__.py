# Tasks package — re-exports every task so that existing references of the
# form `from appone.tasks import X` or `appone.tasks.X` keep working.
# Celery Beat schedule keys must also reference the full dotted path
# (e.g. "appone.tasks.otp.cleanup_expired_otps").

from .otp import send_otp_task, cleanup_expired_otps
from .freelancer import (
    upload_to_cloudinary_task,
    verify_nin_task,
    generate_id_card_task,
    send_profile_completion_reminders,
    backup_user_data,
)
from .company import verify_company_registration_task
from .payment import process_payment_task, generate_monthly_payment_reports
from .notifications import check_flagged_messages, send_contract_expiry_notifications

__all__ = [
    # OTP
    'send_otp_task',
    'cleanup_expired_otps',
    # Freelancer
    'upload_to_cloudinary_task',
    'verify_nin_task',
    'generate_id_card_task',
    'send_profile_completion_reminders',
    'backup_user_data',
    # Company
    'verify_company_registration_task',
    # Payment
    'process_payment_task',
    'generate_monthly_payment_reports',
    # Notifications
    'check_flagged_messages',
    'send_contract_expiry_notifications',
]
