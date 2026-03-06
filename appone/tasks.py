from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import (
    FreelancerProfile, CompanyProfile, OTPVerification,
    Payment, Message, Contract
)
from .utils import (
    send_otp_sms, send_otp_email, verify_nigerian_nin,
    verify_company_registration, generate_digital_id_card,
    process_paystack_payment,upload_to_cloudinary,
send_notification_email
)
import os

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_otp_task(self, otp_id):
    """
    Async task to send OTP via SMS or Email

    Args:
        otp_id: ID of the OTPVerification object

    Returns:
        dict: Status of the operation
    """
    try:
        otp = OTPVerification.objects.get(id=otp_id)

        # Check if OTP is still valid
        if otp.is_verified:
            return{'success': True, 'message': 'OTP already verified'}

        if otp.expires_at < timezone.now():
            return {'success': False, 'message': 'OTP expired'}
        success = False

        if otp.otp_type == 'phone':
            success = send_otp_sms(otp.phone_number, otp.otp_code)
        elif otp.otp_type in ['company_access', 'profile_access']:
            success = send_otp_email(otp.email, otp.otp_code, otp.otp_type)

        else:
            return {'success': False, 'error': 'Unknown OTP type'}

        if success:
            return {
                'success': True,
                'otp_id': str(otp_id),
                'otp_type': otp.otp_type
            }
        else:
            # Only retry if not in final attempt
            if self.request.retries < self.max_retries:
                raise self.retry(exc=Exception("SMS/Email sending failed"))

            return {
                'success': False,
                'error': 'Failed to send OTP after retries'
            }

    except OTPVerification.DoesNotExist:
        return {'success': False, 'error': 'OTP not found'}

    except Exception as e:

        # Retry on unexpected errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'success': False, 'error': str(e)}

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def upload_to_cloudinary_task(self, profile_id, file_path, file_type, profile_field):
    """
       Generic async task to upload any file to Cloudinary and save the URL
       to the specified field on FreelancerProfile.

       Args:
           profile_id:    FreelancerProfile primary key (string)
           file_path:     Absolute path to the temp file on disk
           file_type:     Cloudinary public_id prefix, e.g. 'cv', 'live_photo', 'id_card'
           profile_field: The FreelancerProfile field to save the URL to,
                          e.g. 'cv_file', 'live_photo', 'id_card_image'
       """
    try:
        profile = FreelancerProfile.objects.get(id=profile_id)

        with open(file_path, 'rb') as f:
            url = upload_to_cloudinary(f, file_type, profile.id)

        setattr(profile, profile_field, url)
        profile.save(update_fields=[profile_field])
        profile.calculate_profile_completion()

        # Clean up temp file
        if os.path.exists(file_path):
            os.remove(file_path)

        # send_notification_email(
        #     profile.user.email,
        #     "CV Uploaded Successfully",
        #     f"Dear {profile.first_name}, your CV has been uploaded successfully."
        # )

        return {'success': True, 'url': url, 'field': profile_field}

    except FreelancerProfile.DoesNotExist:
        if os.path.exists(file_path):
            os.remove(file_path)
        return {'success': False, 'error': 'Profile not found'}

    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        if os.path.exists(file_path):
            os.remove(file_path)
        return {'success': False, 'error': str(exc)}

@shared_task
def verify_nin_task(profile_id):
    """
    Async task to verify NIN with government API
    """
    try:
        profile = FreelancerProfile.objects.get(id=profile_id)
        result = verify_nigerian_nin(profile.nin)

        if result and result.get('verified'):
            # Update profile with verification data
            profile.nin_verified = True
            profile.save()

            # Send notification to user
            send_notification_email(
                profile.user.email,
                "NIN Verification Successful",
                f"Dear {profile.first_name}, your NIN has been successfully verified."
            )

        return {'success': True, 'verified': result.get('verified', False)}
    except FreelancerProfile.DoesNotExist:
        return {'success': False, 'error': 'Profile not found'}

@shared_task
def verify_company_registration_task(company_id):
    """
    Async task to verify company registration with government API
    """
    try:
        company = CompanyProfile.objects.get(id=company_id)
        result = verify_company_registration(
            company.company_registration_number,
            company.country
        )

        if result and result.get('verified'):
            company.api_verification_status = True
            company.api_verification_data = result
            company.save()

            # Send notification to company
            send_notification_email(
                company.company_email,
                "Company Verification Successful",
                f"Your company {company.company_name} has been successfully verified."
            )

        return {'success': True, 'verified': result.get('verified', False)}
    except CompanyProfile.DoesNotExist:
        return {'success': False, 'error': 'Company not found'}


@shared_task
def generate_id_card_task(profile_id):
    """
    Async task to generate digital ID card for freelancer
    """
    try:
        profile = FreelancerProfile.objects.get(id=profile_id)

        if profile.verification_status == 'verified':
            id_card = generate_digital_id_card(profile)
            if id_card:
                profile.id_card_image = id_card
                profile.save()

                # Send notification
                send_notification_email(
                    profile.user.email,
                    "Digital ID Card Generated",
                    f"Dear {profile.first_name}, your digital ID card has been generated and is ready for download."
                )

                return {'success': True, 'profile_id': str(profile_id)}

        return {'success': False, 'error': 'Profile not verified'}
    except FreelancerProfile.DoesNotExist:
        return {'success': False, 'error': 'Profile not found'}


@shared_task
def process_payment_task(payment_id):
    """
    Async task to process payment via payment gateway
    """
    try:
        payment = Payment.objects.get(id=payment_id)

        if payment.status != 'pending':
            return {'success': False, 'error': 'Payment already processed'}

        payment.status = 'processing'
        payment.save()

        # Process via Paystack
        result = process_paystack_payment(payment)

        if result and result.get('status'):
            payment.status = 'completed'
            payment.processed_at = timezone.now()
            payment.save()

            # Send notifications
            freelancer = payment.contract.freelancer
            send_notification_email(
                freelancer.user.email,
                "Payment Received",
                f"Dear {freelancer.first_name}, you have received a payment of {payment.net_amount} {payment.currency}."
            )

            company = payment.contract.company
            send_notification_email(
                company.company_email,
                "Payment Processed",
                f"Your payment of {payment.amount} {payment.currency} has been processed successfully."
            )

            return {'success': True, 'payment_id': str(payment_id)}
        else:
            payment.status = 'failed'
            payment.save()
            return {'success': False, 'error': 'Payment processing failed'}

    except Payment.DoesNotExist:
        return {'success': False, 'error': 'Payment not found'}


@shared_task
def check_flagged_messages():
    """
    Periodic task to check and flag suspicious messages
    """
    from .utils import flag_suspicious_message

    # Get recent unflagged messages
    recent_messages = Message.objects.filter(
        flagged=False,
        created_at__gte=timezone.now() - timedelta(hours=1)
    )

    flagged_count = 0
    for message in recent_messages:
        is_flagged, reason = flag_suspicious_message(message.content)
        if is_flagged:
            message.flagged = True
            message.flag_reason = reason
            message.save()
            flagged_count += 1

            # Notify admin
            send_notification_email(
                'admin@virtualcitizenship.com',
                'Suspicious Message Detected',
                f"Message ID: {message.id}\nWorkspace: {message.workspace.name}\nReason: {reason}"
            )

    return {'checked': recent_messages.count(), 'flagged': flagged_count}


@shared_task
def cleanup_expired_otps():
    """
    Periodic task to clean up expired OTPs
    Run this every hour via Celery Beat

    """
    try:
        expired_otps = OTPVerification.objects.filter(
            is_verified=False,
            expires_at__lt=timezone.now()
        )

        count = expired_otps.count()
        expired_otps.delete()

        return {'deleted': count}

    except Exception as e:
        return {'error': str(e)}


@shared_task
def send_profile_completion_reminders():
    """
    Periodic task to remind freelancers to complete their profiles
    """
    incomplete_profiles = FreelancerProfile.objects.filter(
        profile_completion_percentage__lt=100,
        verification_status='pending'
    )

    sent_count = 0
    for profile in incomplete_profiles:
        send_notification_email(
            profile.user.email,
            "Complete Your Profile",
            f"Dear {profile.first_name}, your profile is {profile.profile_completion_percentage}% complete. "
            f"Please complete your profile to start applying for jobs."
        )
        sent_count += 1

    return {'sent': sent_count}


@shared_task
def send_contract_expiry_notifications():
    """
    Periodic task to notify about expiring contracts
    """
    expiring_soon = Contract.objects.filter(
        status='active',
        end_date__lte=timezone.now() + timedelta(days=7),
        end_date__gte=timezone.now()
    )

    notified_count = 0
    for contract in expiring_soon:
        # Notify freelancer
        send_notification_email(
            contract.freelancer.user.email,
            "Contract Expiring Soon",
            f"Dear {contract.freelancer.first_name}, your contract with {contract.company.company_name} "
            f"will expire on {contract.end_date}."
        )

        # Notify company
        send_notification_email(
            contract.company.company_email,
            "Contract Expiring Soon",
            f"Your contract with {contract.freelancer.first_name} {contract.freelancer.last_name} "
            f"will expire on {contract.end_date}."
        )

        notified_count += 1

    return {'notified': notified_count}


@shared_task
def generate_monthly_payment_reports():
    """
    Generate monthly payment reports for accounting
    """
    from datetime import date

    current_month = timezone.now().month
    current_year = timezone.now().year

    payments = Payment.objects.filter(
        status='completed',
        payment_date__month=current_month,
        payment_date__year=current_year
    )

    total_amount = sum(p.amount for p in payments)
    total_platform_tax = sum(p.platform_tax for p in payments)
    total_dwelling_tax = sum(p.dwelling_country_tax for p in payments)
    total_work_tax = sum(p.work_country_tax for p in payments)

    report = {
        'month': current_month,
        'year': current_year,
        'total_transactions': payments.count(),
        'total_amount': float(total_amount),
        'total_platform_tax': float(total_platform_tax),
        'total_dwelling_tax': float(total_dwelling_tax),
        'total_work_tax': float(total_work_tax),
    }

    # Send report to admin
    send_notification_email(
        'admin@virtualcitizenship.com',
        f'Monthly Payment Report - {date.today().strftime("%B %Y")}',
        f"Payment Report:\n{report}"
    )

    return report


@shared_task
def backup_user_data():
    """
    Periodic task to backup important user data
    """
    import json
    from django.core.serializers import serialize

    # Backup freelancer profiles
    freelancers = serialize('json', FreelancerProfile.objects.all())

    # Backup company profiles
    companies = serialize('json', CompanyProfile.objects.all())

    # Save to file or cloud storage
    # This is a placeholder - implement actual backup logic

    return {
        'freelancers_backed_up': FreelancerProfile.objects.count(),
        'companies_backed_up': CompanyProfile.objects.count()
    }