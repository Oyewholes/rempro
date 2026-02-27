import random
import string
import requests
from django.core.mail import send_mail
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont
import io
from django.core.files.uploadedfile import InMemoryUploadedFile
import cloudinary.uploader



def generate_otp(length=6):
    """Generate a random OTP code"""
    return ''.join(random.choices(string.digits, k=length))


def send_otp_sms(phone_number, otp_code):
    """
    Send OTP via SMS using Twilio (with Windows SSL error handling)

    Args:
        phone_number (str): Phone number in format +234XXXXXXXXXX
        otp_code (str): The OTP code to send

    Returns:
        bool: True if SMS sent successfully, False otherwise
    """
    try:
        # Check if Twilio is configured
        if not all([
            getattr(settings, 'TWILIO_ACCOUNT_SID', None),
            getattr(settings, 'TWILIO_AUTH_TOKEN', None),
            getattr(settings, 'TWILIO_PHONE_NUMBER', None)
        ]):

            # In development, just log the OTP
            if settings.DEBUG:
                return True
            return False

        # Import Twilio here to avoid import errors if not installed
        try:
            from twilio.rest import Client
            from twilio.http.http_client import TwilioHttpClient
        except ImportError:
            if settings.DEBUG:
                return True
            return False

        # Create HTTP client with SSL handling for Windows
        http_client = TwilioHttpClient()

        # In development on Windows, disable SSL verification to avoid SSL errors
        # WARNING: Never do this in production!
        if settings.DEBUG and hasattr(http_client, 'session'):
            http_client.session.verify = False

        # Create Twilio client
        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            http_client=http_client
        )

        # Send SMS
        message = client.messages.create(
            body=f"Your Virtual Citizenship verification code is: {otp_code}\n"
                 f"This code will expire in 10 minutes.\n"
                 f"Do not share this code with anyone.",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )

        return True

    except Exception as e:
        if settings.DEBUG:
            return True

        return False


def send_otp_sms_africas_talking(phone_number, otp_code):
    """
    Send OTP via SMS using Africa's Talking or similar service
    """
    try:
        # Example: Africa's Talking integration
        url = "https://api.africastalking.com/version1/messaging"
        headers = {
            "ApiKey": settings.SMS_API_KEY,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "username": settings.SMS_USERNAME,
            "to": phone_number,
            "message": f"Your Virtual Citizenship verification code is: {otp_code}. Valid for 10 minutes.",
            "from": settings.SMS_SENDER_ID
        }

        response = requests.post(url, headers=headers, data=data)
        return response.status_code == 200
    except Exception as e:
        return False


def send_otp_email(email, otp_code, otp_type='verification'):
    """
    Send OTP via email
    """
    try:
        subject = f"Virtual Citizenship - {otp_type.title()} Code"
        message = f"""
        Your Virtual Citizenship verification code is: {otp_code}

        This code will expire in 10 minutes.

        If you didn't request this code, please ignore this email.

        Best regards,
        Virtual Citizenship Team
        """

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        return False


def send_otp(contact_info, otp_code, method='auto'):
    """
    Universal OTP sender - automatically detects phone vs email and tries multiple methods

    Args:
        contact_info (str): Phone number or email
        otp_code (str): The OTP code
        method (str): 'auto', 'sms', 'email', 'twilio', 'africas_talking'

    Returns:
        tuple: (success: bool, method_used: str)
    """
    # Detect if it's a phone number or email
    if method == 'auto':
        if '@' in contact_info:
            method = 'email'
        elif contact_info.startswith('+'):
            method = 'sms'
        else:
            logger.error(f"Could not detect contact type: {contact_info}")
            return False, 'unknown'

    # Try to send based on method
    if method == 'email':
        success = send_otp_email(contact_info, otp_code)
        return success, 'email'

    elif method in ['sms', 'twilio']:
        success = send_otp_sms(contact_info, otp_code)
        if success:
            return True, 'twilio'

        # Fallback to Africa's Talking if Twilio fails
        if hasattr(settings, 'SMS_API_KEY'):
            success = send_otp_sms_africas_talking(contact_info, otp_code)
            if success:
                return True, 'africas_talking'

    elif method == 'africas_talking':
        success = send_otp_sms_africas_talking(contact_info, otp_code)
        return success, 'africas_talking'

    return False, 'failed'

def upload_cv_to_cloudinary(file, freelancer_id):
    """
    Upload a CV file to Cloudinary and return the secure URL.

    Args:
        file: The uploaded file object
        freelancer_id: Used to create a unique public_id

    Returns:
        str: The Cloudinary secure URL, or None on failure
    """
    try:
        result = cloudinary.uploader.upload(
            file,
            folder="virtual_citizenship/cvs",
            public_id=f"cv_{freelancer_id}",
            resource_type="raw",
            allowed_formats=["pdf", "doc", "docx"],
            overwrite=True,
        )
        return result['secure_url']

    except Exception as e:
        return None

def verify_nigerian_nin(nin):
    """
    Verify Nigerian NIN with government API
    This is a placeholder - integrate with actual Nigerian government API
    """
    try:
        # Example API call structure
        url = f"{settings.GOVT_API_BASE_URL}nin/verify"
        headers = {
            "Authorization": f"Bearer {settings.GOVT_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "nin": nin
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error verifying NIN: {e}")
        return None


def verify_company_registration(registration_number, country):
    """
    Verify company registration with government database
    This is a placeholder - integrate with actual government APIs
    """
    try:
        # Different APIs for different countries
        api_endpoints = {
            'USA': f"{settings.GOVT_API_BASE_URL}us/company/verify",
            'UK': f"{settings.GOVT_API_BASE_URL}uk/company/verify",
            'NG': f"{settings.GOVT_API_BASE_URL}ng/cac/verify",
            # Add more countries as needed
        }

        url = api_endpoints.get(country, api_endpoints['USA'])
        headers = {
            "Authorization": f"Bearer {settings.GOVT_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "registration_number": registration_number
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error verifying company: {e}")
        return None


def get_ip_location(ip_address):
    """
    Get location information from IP address
    Using ipapi.co or similar service
    """
    try:
        response = requests.get(f"https://ipapi.co/{ip_address}/json/")
        if response.status_code == 200:
            data = response.json()
            return {
                'country_code': data.get('country_code'),
                'country_name': data.get('country_name'),
                'city': data.get('city'),
                'region': data.get('region'),
                'latitude': data.get('latitude'),
                'longitude': data.get('longitude')
            }
        return None
    except Exception as e:
        print(f"Error getting IP location: {e}")
        return None


def generate_digital_id_card(freelancer_profile):
    """
    Generate a digital ID card image for the freelancer
    """
    try:
        # Create image
        width, height = 600, 400
        img = Image.new('RGB', (width, height), color='#1a1a2e')
        draw = ImageDraw.Draw(img)

        # Try to load a font, fallback to default if not available
        try:
            title_font = ImageFont.truetype("arial.ttf", 24)
            text_font = ImageFont.truetype("arial.ttf", 18)
            small_font = ImageFont.truetype("arial.ttf", 14)
        except:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Draw header
        draw.rectangle([(0, 0), (width, 80)], fill='#16213e')
        draw.text((20, 25), "VIRTUAL CITIZENSHIP", fill='#00d9ff', font=title_font)
        draw.text((20, 55), "Digital Work Permit", fill='#ffffff', font=small_font)

        # Draw profile section
        y_offset = 120

        # Name
        draw.text((20, y_offset), "Name:", fill='#00d9ff', font=text_font)
        draw.text((150, y_offset), f"{freelancer_profile.first_name} {freelancer_profile.last_name}",
                  fill='#ffffff', font=text_font)

        # Digital ID
        y_offset += 40
        draw.text((20, y_offset), "Digital ID:", fill='#00d9ff', font=text_font)
        draw.text((150, y_offset), str(freelancer_profile.digital_id), fill='#ffffff', font=small_font)

        # Status
        y_offset += 40
        draw.text((20, y_offset), "Status:", fill='#00d9ff', font=text_font)
        status_color = '#00ff00' if freelancer_profile.verification_status == 'verified' else '#ff9900'
        draw.text((150, y_offset), freelancer_profile.verification_status.upper(),
                  fill=status_color, font=text_font)

        # Approved Countries
        if freelancer_profile.approved_countries:
            y_offset += 40
            draw.text((20, y_offset), "Approved for:", fill='#00d9ff', font=text_font)
            countries = ', '.join(freelancer_profile.approved_countries[:3])
            draw.text((150, y_offset), countries, fill='#ffffff', font=small_font)

        # Footer
        draw.rectangle([(0, height - 60), (width, height)], fill='#16213e')
        draw.text((20, height - 40), "Verified Virtual Work Permit", fill='#ffffff', font=small_font)

        # Save to bytes
        img_io = io.BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)

        # Create InMemoryUploadedFile
        img_file = InMemoryUploadedFile(
            img_io, None, f'id_card_{freelancer_profile.digital_id}.png',
            'image/png', img_io.getbuffer().nbytes, None
        )

        return img_file
    except Exception as e:
        print(f"Error generating ID card: {e}")
        return None


def calculate_payment_breakdown(amount, contract):
    """
    Calculate payment breakdown with taxes
    """
    platform_tax = (amount * contract.platform_tax_rate) / 100
    dwelling_tax = (amount * contract.dwelling_country_tax_rate) / 100
    work_tax = (amount * contract.work_country_tax_rate) / 100

    total_tax = platform_tax + dwelling_tax + work_tax
    net_amount = amount - total_tax

    return {
        'gross_amount': float(amount),
        'platform_tax': float(platform_tax),
        'dwelling_country_tax': float(dwelling_tax),
        'work_country_tax': float(work_tax),
        'total_tax': float(total_tax),
        'net_amount': float(net_amount),
        'breakdown': {
            'Platform Fee ({}%)'.format(contract.platform_tax_rate): float(platform_tax),
            'Dwelling Country Tax ({}%)'.format(contract.dwelling_country_tax_rate): float(dwelling_tax),
            'Work Country Tax ({}%)'.format(contract.work_country_tax_rate): float(work_tax)
        }
    }


def process_paystack_payment(payment):
    """
    Process payment via Paystack
    """
    try:
        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        # Get freelancer email
        freelancer_email = payment.contract.freelancer.paystack_email

        data = {
            "email": freelancer_email,
            "amount": int(payment.net_amount * 100),  # Paystack expects amount in kobo/cents
            "reference": payment.transaction_reference,
            "currency": payment.currency,
            "callback_url": f"{settings.FRONTEND_URL}/payment/callback"
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error processing Paystack payment: {e}")
        return None


def flag_suspicious_message(message_content):
    """
    Check if message contains suspicious content
    Returns tuple: (is_flagged, reason)
    """
    suspicious_keywords = [
        'email', 'e-mail', '@', 'gmail', 'yahoo', 'outlook',
        'phone', 'call me', 'whatsapp', 'telegram', 'skype',
        'facebook', 'linkedin', 'instagram', 'twitter',
        '+234', '+1', 'contact me at', 'reach me'
    ]

    content_lower = message_content.lower()

    for keyword in suspicious_keywords:
        if keyword in content_lower:
            return True, f"Detected potential personal information: '{keyword}'"

    # Check for email patterns
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    if re.search(email_pattern, message_content):
        return True, "Email address detected in message"

    # Check for phone patterns
    phone_pattern = r'\+?[\d\s\-\(\)]{10,}'
    if re.search(phone_pattern, message_content):
        return True, "Phone number detected in message"

    return False, ""


def send_notification_email(user_email, subject, message):
    """
    Send notification email to user
    """
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False