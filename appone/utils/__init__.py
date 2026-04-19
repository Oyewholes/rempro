# Utils package — re-exports every utility function so that
# existing imports of the form `from appone.utils import X` keep working.

from .otp import (
    generate_otp,
    send_otp_sms,
    send_otp_sms_africas_talking,
    send_otp_email,
    send_otp,
)
from .cloudinary import (
    upload_to_cloudinary,
    generate_signed_url,
    generate_signed_download_url,
)
from .verification import (
    get_ip_location,
    verify_user_is_in_nigeria,
    verify_nigerian_nin,
    verify_company_registration,
)
from .id_card import generate_digital_id_card
from .payment import calculate_payment_breakdown, process_paystack_payment
from .messaging import flag_suspicious_message, send_notification_email
from .tax import calculate_tax_split

__all__ = [
    # OTP
    'generate_otp',
    'send_otp_sms',
    'send_otp_sms_africas_talking',
    'send_otp_email',
    'send_otp',
    # Cloudinary
    'upload_to_cloudinary',
    'generate_signed_url',
    'generate_signed_download_url',
    # Verification
    'get_ip_location',
    'verify_user_is_in_nigeria',
    'verify_nigerian_nin',
    'verify_company_registration',
    # ID Card
    'generate_digital_id_card',
    # Payment
    'calculate_payment_breakdown',
    'process_paystack_payment',
    # Messaging
    'flag_suspicious_message',
    'send_notification_email',
    # Tax
    'calculate_tax_split',
]
