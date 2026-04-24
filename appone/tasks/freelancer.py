import base64
import io

from celery import shared_task

from appone.models import FreelancerProfile
from appone.utils import (
    generate_digital_id_card,
    generate_signed_download_url,
    send_notification_email,
    upload_to_cloudinary,
    verify_nigerian_nin,
)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def upload_to_cloudinary_task(
    self,
    profile_id,
    file_b64,
    file_type,
    profile_field,
):
    try:
        profile = FreelancerProfile.objects.get(id=profile_id)
        file_bytes = base64.b64decode(file_b64.encode("utf-8"))
        file_like = io.BytesIO(file_bytes)

        url = upload_to_cloudinary(file_like, file_type, profile.id)
        setattr(profile, profile_field, url)
        profile.save(update_fields=[profile_field])
        profile.calculate_profile_completion()

        try:
            send_notification_email(
                profile.user.email,
                f"Your {file_type.replace('_', ' ').title()} is Uploaded",
                (
                    f"Dear {profile.first_name},\n\n"
                    f"Your Virtual Citizenship {file_type.replace('_', ' ').upper()}"
                    " has been uploaded successfully.\n\n"
                    "Best regards,\nVirtual Citizenship Team"
                ),
            )
        except Exception as exc:
            raise exc

        return {"success": True, "url": url, "field": profile_field}

    except FreelancerProfile.DoesNotExist:
        return {"success": False, "error": "Profile not found"}
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"success": False, "error": str(exc)}


@shared_task
def verify_nin_task(profile_id):
    try:
        profile = FreelancerProfile.objects.get(id=profile_id)
        result = verify_nigerian_nin(profile.nin)

        if result and result.get("verified"):
            profile.nin_verified = True
            profile.save()
            send_notification_email(
                profile.user.email,
                "NIN Verification Successful",
                f"Dear {profile.first_name}, your NIN has been successfully verified.",
            )

        return {
            "success": True,
            "verified": result.get("verified", False) if result else False,
        }
    except FreelancerProfile.DoesNotExist:
        return {"success": False, "error": "Profile not found"}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_id_card_task(self, profile_id):
    try:
        profile = FreelancerProfile.objects.get(id=profile_id)
    except FreelancerProfile.DoesNotExist:
        return {"success": False, "error": "Profile not found"}

    if profile.verification_status != "verified":
        return {
            "success": False,
            "error": "Profile is not verified — cannot generate ID card",
        }

    img_bytes = generate_digital_id_card(profile)
    if img_bytes is None:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=Exception("ID card generation returned None"))
        return {"success": False, "error": "Failed to generate ID card image"}

    try:
        id_card_url = upload_to_cloudinary(img_bytes, "id_card", profile.id)
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"success": False, "error": f"Cloudinary upload failed: {exc}"}

    profile.id_card_image = id_card_url
    profile.save(update_fields=["id_card_image"])

    download_link = generate_signed_download_url(
        id_card_url,
        filename=f"Virtual_Citizenship_ID_{profile.digital_id}.png",
        resource_type="image",
        expiry_seconds=86400,
    )

    try:
        send_notification_email(
            profile.user.email,
            "Your Digital ID Card is Ready",
            (
                f"Dear {profile.first_name},\n\n"
                "Your Virtual Citizenship Digital ID Card has been generated.\n\n"
                f"Download link: {download_link}\n\n"
                "Best regards,\nVirtual Citizenship Team"
            ),
        )
    except Exception as exc:
        raise exc

    return {
        "success": True,
        "profile_id": str(profile_id),
        "id_card_url": id_card_url,
    }


@shared_task
def send_profile_completion_reminders():
    incomplete = FreelancerProfile.objects.filter(
        profile_completion_percentage__lt=100, verification_status="pending"
    )
    sent_count = 0
    for profile in incomplete:
        send_notification_email(
            profile.user.email,
            "Complete Your Profile",
            (
                f"Dear {profile.first_name}, your profile is "
                f"{profile.profile_completion_percentage}% complete. "
                "Please complete your profile to start applying for jobs."
            ),
        )
        sent_count += 1
    return {"sent": sent_count}


@shared_task
def backup_user_data():
    from django.core.serializers import serialize

    serialize("json", FreelancerProfile.objects.all())
    serialize(
        "json",
        __import__(
            "appone.models", fromlist=["CompanyProfile"]
        ).CompanyProfile.objects.all(),
    )

    return {
        "freelancers_backed_up": FreelancerProfile.objects.count(),
    }
