from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(
    regex=r"^\+234\d{10}$",
    message="Phone must be in format: '+234XXXXXXXXXX'",
)


class CompanyProfile(models.Model):
    VERIFICATION_STATUS = (
        ("pending", "Pending"),
        ("pending_scheduling", "Pending Scheduling"),
        ("scheduled", "Meeting Scheduled"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    )

    user = models.OneToOneField(
        "appone.User",
        on_delete=models.CASCADE,
        related_name="company_profile",
    )

    company_name = models.CharField(max_length=255, blank=True)
    company_email = models.EmailField(unique=True)
    company_registration_number = models.CharField(
        max_length=100, unique=False, blank=True
    )
    company_email_verified = models.BooleanField(default=False)
    country = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    phone_number = models.CharField(
        validators=[phone_validator], max_length=14, unique=True, blank=True
    )
    website = models.URLField(blank=True)

    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS, default="pending"
    )
    meeting_scheduled_at = models.DateTimeField(null=True, blank=True)
    proposed_meeting_dates = models.JSONField(default=list, blank=True)
    meeting_link = models.URLField(blank=True)
    api_verification_status = models.BooleanField(default=False)
    api_verification_data = models.JSONField(default=dict, blank=True)

    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        "appone.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="verified_companies",
    )

    industry = models.CharField(max_length=100, blank=True)
    company_size = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name
