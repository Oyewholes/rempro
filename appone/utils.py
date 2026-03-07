import random
import string
import requests
from django.core.mail import send_mail
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont
import io
from django.core.files.uploadedfile import InMemoryUploadedFile
import cloudinary.uploader

NIGERIA_COUNTRY_CODE = "NG"
NIGERIA_COUNTRY_NAME = "Nigeria"

_LOCAL_IP_PREFIXES = ("127.", "192.168.", "10.", "172.", "::1")


def _fetch_image_from_url(url: str) -> Image.Image | None:
    """
    Download an image from a URL and return a PIL Image.
    Returns None on any failure so callers can degrade gracefully.
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as exc:
        logger.warning("ID card: could not fetch live photo from %s — %s", url, exc)
        return None


def _make_circle_mask(size: tuple[int, int]) -> Image.Image:
    """Return a white-on-black circular mask for the given (width, height)."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0] - 1, size[1] - 1), fill=255)
    return mask

def generate_otp(length=6):
    """Generate a random OTP code"""
    return "".join(random.choices(string.digits, k=length))


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
        if not all(
            [
                getattr(settings, "TWILIO_ACCOUNT_SID", None),
                getattr(settings, "TWILIO_AUTH_TOKEN", None),
                getattr(settings, "TWILIO_PHONE_NUMBER", None),
            ]
        ):
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
        if settings.DEBUG and hasattr(http_client, "session"):
            http_client.session.verify = False

        # Create Twilio client
        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            http_client=http_client,
        )

        # Send SMS
        message = client.messages.create(
            body=f"Your Virtual Citizenship verification code is: {otp_code}\n"
            f"This code will expire in 10 minutes.\n"
            f"Do not share this code with anyone.",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number,
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
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "username": settings.SMS_USERNAME,
            "to": phone_number,
            "message": f"Your Virtual Citizenship verification code is: {otp_code}. Valid for 10 minutes.",
            "from": settings.SMS_SENDER_ID,
        }

        response = requests.post(url, headers=headers, data=data)
        return response.status_code == 200
    except Exception as e:
        return False


def send_otp_email(email, otp_code, otp_type="verification"):
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


def send_otp(contact_info, otp_code, method="auto"):
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
    if method == "auto":
        if "@" in contact_info:
            method = "email"
        elif contact_info.startswith("+"):
            method = "sms"
        else:
            return False, "unknown"

    # Try to send based on method
    if method == "email":
        success = send_otp_email(contact_info, otp_code)
        return success, "email"

    elif method in ["sms", "twilio"]:
        success = send_otp_sms(contact_info, otp_code)
        if success:
            return True, "twilio"

        # Fallback to Africa's Talking if Twilio fails
        if hasattr(settings, "SMS_API_KEY"):
            success = send_otp_sms_africas_talking(contact_info, otp_code)
            if success:
                return True, "africas_talking"

    elif method == "africas_talking":
        success = send_otp_sms_africas_talking(contact_info, otp_code)
        return success, "africas_talking"

    return False, "failed"


def upload_to_cloudinary(file, file_type, freelancer_id):
    """
    Upload any file to Cloudinary and return the secure URL.

    Args:
        file:          File-like object opened in binary mode.
        file_type:     Used as the public_id prefix and subfolder,
                       e.g. 'cv', 'live_photo', 'id_card'
        freelancer_id: UUID that makes the public_id unique per freelancer.

    Returns:
        str: Cloudinary secure_url on success.

    Raises:
        Exception: Propagates Cloudinary errors — never swallows silently.
    """

    resource_type = "image" if file_type in ("live_photo", "id_card") else "raw"

    result = cloudinary.uploader.upload(
        file,
        folder=f"virtual_citizenship/{file_type}s",
        public_id=f"{file_type}_{freelancer_id}",
        resource_type=resource_type,
        overwrite=True,
    )
    return result["secure_url"]


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
            "Content-Type": "application/json",
        }
        data = {"nin": nin}

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
            "USA": f"{settings.GOVT_API_BASE_URL}us/company/verify",
            "UK": f"{settings.GOVT_API_BASE_URL}uk/company/verify",
            "NG": f"{settings.GOVT_API_BASE_URL}ng/cac/verify",
            # Add more countries as needed
        }

        url = api_endpoints.get(country, api_endpoints["USA"])
        headers = {
            "Authorization": f"Bearer {settings.GOVT_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {"registration_number": registration_number}

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error verifying company: {e}")
        return None


def get_ip_location(ip_address: str) -> dict | None:
    """
    Resolve a public IP address to location data.

    Strategy:
        1. Return a dev stub for loopback / private IPs so local testing
           doesn't fail.
        2. Try ipapi.co  (1 000 req / day free, no key needed).
        3. Fall back to ip-api.com (45 req / min free, HTTP only).

    Returns a dict with at least:
        {
            'country_code': 'NG',       # ISO-2
            'country_name': 'Nigeria',
            'city': '...',
            'region': '...',
            'latitude': 6.45,
            'longitude': 3.39,
            'is_nigeria': True | False,
        }
    or None when both services fail.
    """
    # ── 1. Dev / private IP fast-path ──────────────────────────────────────
    # if not ip_address or any(ip_address.startswith(p) for p in _LOCAL_IP_PREFIXES):
    #     return _build_location_result(
    #         country_code='NG',
    #         country_name='Nigeria',
    #         city='Lagos',
    #         region='Lagos',
    #         latitude=6.5244,
    #         longitude=3.3792,
    #     )

    # ── 2. Primary: ipapi.co ───────────────────────────────────────────────
    try:
        resp = requests.get(
            f"https://ipapi.co/{ip_address}/json/",
            timeout=5,
            headers={"User-Agent": "VirtualCitizenship/1.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            # ipapi.co returns {'error': True} for reserved / invalid IPs
            if not data.get("error"):
                return _build_location_result(
                    country_code=data.get("country_code", ""),
                    country_name=data.get("country_name", ""),
                    city=data.get("city", ""),
                    region=data.get("region", ""),
                    latitude=data.get("latitude"),
                    longitude=data.get("longitude"),
                )
    except requests.RequestException as exc:
        return None
    # ── 3. Fallback: ip-api.com (HTTP, no key, 45 req/min) ─────────────────
    try:
        resp = requests.get(
            f"http://ip-api.com/json/{ip_address}?fields=status,country,countryCode,regionName,city,lat,lon",
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                return _build_location_result(
                    country_code=data.get("countryCode", ""),
                    country_name=data.get("country", ""),
                    city=data.get("city", ""),
                    region=data.get("regionName", ""),
                    latitude=data.get("lat"),
                    longitude=data.get("lon"),
                )
    except requests.RequestException as exc:
        return None


def _build_location_result(
    country_code: str,
    country_name: str,
    city: str,
    region: str,
    latitude,
    longitude,
) -> dict:
    """Normalise the result dict and add the convenience `is_nigeria` flag."""
    return {
        "country_code": country_code,
        "country_name": country_name,
        "city": city,
        "region": region,
        "latitude": latitude,
        "longitude": longitude,
        "is_nigeria": country_code.upper() == NIGERIA_COUNTRY_CODE,
    }


def verify_user_is_in_nigeria(ip_address: str) -> tuple[bool, dict | None, str]:
    """
    High-level helper used by the view.

    Returns:
        (is_verified: bool, location_data: dict | None, reason: str)

    Examples:
        (True,  {...}, "Location verified: Lagos, Nigeria")
        (False, {...}, "Access restricted: your location (US) is outside Nigeria")
        (False, None,  "Unable to determine location. Please try again.")
    """
    location = get_ip_location(ip_address)

    if location is None:
        return False, None, "Unable to determine your location. Please try again later."

    if location["is_nigeria"]:
        msg = f"Location verified: {location['city']}, {location['country_name']}"
        return True, location, msg

    country = location.get("country_name") or location.get("country_code") or "Unknown"
    msg = (
        f"Access restricted: your detected location ({country}) is outside Nigeria. "
        "You must be physically located in Nigeria to register."
    )
    return False, location, msg


def generate_digital_id_card(freelancer_profile):
    """
    Generate a digital ID card image for the freelancer.

    Improvements over the original:
    - Fetches the freelancer's live photo from its Cloudinary URL and
      composites it onto the card as a circular avatar.
    - Returns a raw ``io.BytesIO`` (PNG bytes) instead of an
      ``InMemoryUploadedFile``, so the caller can pass it straight to
      ``upload_to_cloudinary`` without any extra wrapping.
    - Falls back gracefully when the live photo is unavailable.

    Returns:
        io.BytesIO with PNG data on success, or None on failure.
    """
    try:
        # ── Canvas ────────────────────────────────────────────────────────
        WIDTH, HEIGHT = 700, 420
        DARK_BG = "#1a1a2e"
        HEADER_BG = "#16213e"
        ACCENT = "#00d9ff"
        WHITE = "#ffffff"
        GREY = "#a0a0b0"

        img = Image.new("RGB", (WIDTH, HEIGHT), color=DARK_BG)
        draw = ImageDraw.Draw(img)

        # ── Fonts ─────────────────────────────────────────────────────────
        try:
            font_title = ImageFont.truetype("arial.ttf", 22)
            font_sub = ImageFont.truetype("arial.ttf", 13)
            font_label = ImageFont.truetype("arial.ttf", 14)
            font_value = ImageFont.truetype("arial.ttf", 16)
            font_small = ImageFont.truetype("arial.ttf", 12)
        except OSError:
            font_title = font_sub = font_label = font_value = font_small = (
                ImageFont.load_default()
            )

        # ── Header bar ────────────────────────────────────────────────────
        draw.rectangle([(0, 0), (WIDTH, 72)], fill=HEADER_BG)
        draw.text((20, 16), "VIRTUAL CITIZENSHIP", fill=ACCENT, font=font_title)
        draw.text((20, 48), "Digital Work Permit", fill=WHITE, font=font_sub)

        # Thin accent line below header
        draw.rectangle([(0, 72), (WIDTH, 75)], fill=ACCENT)

        # ── Live photo (circular avatar) ──────────────────────────────────
        PHOTO_SIZE = 110  # diameter
        PHOTO_X = WIDTH - PHOTO_SIZE - 30
        PHOTO_Y = 90
        BORDER_PAD = 4  # coloured ring around the circle

        live_photo_loaded = False
        if freelancer_profile.live_photo:
            raw_photo = _fetch_image_from_url(freelancer_profile.live_photo)
            if raw_photo:
                # Crop to square, then resize to target
                raw_photo = ImageOps.fit(
                    raw_photo,
                    (PHOTO_SIZE, PHOTO_SIZE),
                    method=Image.LANCZOS,
                )
                # Draw accent-coloured border circle behind photo
                draw.ellipse(
                    [
                        PHOTO_X - BORDER_PAD,
                        PHOTO_Y - BORDER_PAD,
                        PHOTO_X + PHOTO_SIZE + BORDER_PAD,
                        PHOTO_Y + PHOTO_SIZE + BORDER_PAD,
                    ],
                    fill=ACCENT,
                )
                # Composite with circular mask
                mask = _make_circle_mask((PHOTO_SIZE, PHOTO_SIZE))
                img.paste(raw_photo, (PHOTO_X, PHOTO_Y), mask)
                live_photo_loaded = True

        if not live_photo_loaded:
            # Placeholder silhouette circle
            draw.ellipse(
                [PHOTO_X, PHOTO_Y, PHOTO_X + PHOTO_SIZE, PHOTO_Y + PHOTO_SIZE],
                fill=HEADER_BG,
                outline=ACCENT,
                width=2,
            )
            draw.text(
                (PHOTO_X + PHOTO_SIZE // 2 - 20, PHOTO_Y + PHOTO_SIZE // 2 - 8),
                "NO PHOTO",
                fill=GREY,
                font=font_small,
            )

        # ── Info fields ───────────────────────────────────────────────────
        TEXT_X = 30
        TEXT_RIGHT = PHOTO_X - 20  # stay left of the photo
        y = 95
        LINE_GAP = 38

        def draw_field(label: str, value: str, y_pos: int):
            draw.text((TEXT_X, y_pos), label, fill=ACCENT, font=font_label)
            draw.text((TEXT_X, y_pos + 16), value, fill=WHITE, font=font_value)

        full_name = f"{freelancer_profile.first_name} {freelancer_profile.last_name}".strip()
        draw_field("Full Name", full_name or "—", y)
        y += LINE_GAP + 6

        draw_field("Digital ID", str(freelancer_profile.digital_id), y)
        y += LINE_GAP + 6

        status_label = freelancer_profile.verification_status.upper()
        status_color = "#00ff88" if freelancer_profile.verification_status == "verified" else "#ff9900"
        draw.text((TEXT_X, y), "Status", fill=ACCENT, font=font_label)
        draw.text((TEXT_X, y + 16), status_label, fill=status_color, font=font_value)
        y += LINE_GAP + 6

        if freelancer_profile.approved_countries:
            countries = ", ".join(freelancer_profile.approved_countries[:4])
            draw_field("Approved For", countries, y)
            y += LINE_GAP + 6

        if freelancer_profile.skills:
            skills_str = ", ".join(str(s) for s in freelancer_profile.skills[:5])
            # Truncate if too wide
            if len(skills_str) > 45:
                skills_str = skills_str[:42] + "…"
            draw_field("Skills", skills_str, y)

        # ── Footer bar ────────────────────────────────────────────────────
        draw.rectangle([(0, HEIGHT - 48), (WIDTH, HEIGHT)], fill=HEADER_BG)
        draw.text(
            (20, HEIGHT - 32),
            "Issued by Virtual Citizenship Platform  |  virtualcitizenship.com",
            fill=GREY,
            font=font_small,
        )

        # ── Serialise to PNG bytes ─────────────────────────────────────────
        output = io.BytesIO()
        img.save(output, format="PNG", optimize=True)
        output.seek(0)
        return output

    except Exception as exc:
        logger.error("generate_digital_id_card failed for profile %s: %s", freelancer_profile.id, exc)
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
        "gross_amount": float(amount),
        "platform_tax": float(platform_tax),
        "dwelling_country_tax": float(dwelling_tax),
        "work_country_tax": float(work_tax),
        "total_tax": float(total_tax),
        "net_amount": float(net_amount),
        "breakdown": {
            "Platform Fee ({}%)".format(contract.platform_tax_rate): float(
                platform_tax
            ),
            "Dwelling Country Tax ({}%)".format(
                contract.dwelling_country_tax_rate
            ): float(dwelling_tax),
            "Work Country Tax ({}%)".format(contract.work_country_tax_rate): float(
                work_tax
            ),
        },
    }


def process_paystack_payment(payment):
    """
    Process payment via Paystack
    """
    try:
        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        # Get freelancer email
        freelancer_email = payment.contract.freelancer.paystack_email

        data = {
            "email": freelancer_email,
            "amount": int(
                payment.net_amount * 100
            ),  # Paystack expects amount in kobo/cents
            "reference": payment.transaction_reference,
            "currency": payment.currency,
            "callback_url": f"{settings.FRONTEND_URL}/payment/callback",
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
        "email",
        "e-mail",
        "@",
        "gmail",
        "yahoo",
        "outlook",
        "phone",
        "call me",
        "whatsapp",
        "telegram",
        "skype",
        "facebook",
        "linkedin",
        "instagram",
        "twitter",
        "+234",
        "+1",
        "contact me at",
        "reach me",
    ]

    content_lower = message_content.lower()

    for keyword in suspicious_keywords:
        if keyword in content_lower:
            return True, f"Detected potential personal information: '{keyword}'"

    # Check for email patterns
    import re

    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    if re.search(email_pattern, message_content):
        return True, "Email address detected in message"

    # Check for phone patterns
    phone_pattern = r"\+?[\d\s\-\(\)]{10,}"
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
