import uuid

from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(
    regex=r"^\+234\d{10}$",
    message="Phone must be in format: '+234XXXXXXXXXX'",
)


class FreelancerProfile(models.Model):
    VERIFICATION_STATUS = (
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    )

    user = models.OneToOneField(
        "appone.User",
        on_delete=models.CASCADE,
        related_name="freelancer_profile",
    )
    phone_number = models.CharField(
        validators=[phone_validator], max_length=14, unique=False, blank=True
    )
    phone_verified = models.BooleanField(default=False)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    nin = models.CharField(
        max_length=11,
        unique=True,
        help_text="National Identification Number",
        blank=True,
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    country_code = models.CharField(max_length=3, default="NGA")
    location_verified = models.BooleanField(default=False)
    cv_file = models.URLField(null=True, blank=True)
    live_photo = models.URLField(null=True, blank=True)
    portfolio_files = models.JSONField(default=list, blank=True)
    digital_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    digital_id_link = models.CharField(max_length=500, blank=True)
    id_card_image = models.URLField(null=True, blank=True)
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS, default="pending"
    )
    admin_verified_at = models.DateTimeField(null=True, blank=True)
    admin_verified_by = models.ForeignKey(
        "appone.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="verified_freelancers",
    )
    profile_completion_percentage = models.IntegerField(default=0)
    paystack_email = models.EmailField(null=True, blank=True)
    payoneer_email = models.EmailField(null=True, blank=True)
    bank_details_verified = models.BooleanField(default=False)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_code = models.CharField(max_length=20, blank=True)
    account_number = models.CharField(max_length=20, blank=True)
    paystack_subaccount_code = models.CharField(max_length=50, blank=True)
    skills = models.JSONField(default=list, blank=True)
    bio = models.TextField(blank=True)
    approved_countries = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def calculate_profile_completion(self):
        fields = [
            self.phone_verified,
            bool(self.cv_file),
            bool(self.live_photo),
            bool(self.nin),
            self.location_verified,
            bool(self.paystack_email or self.payoneer_email),
            bool(self.portfolio_files),
            bool(self.skills),
            bool(self.bio),
        ]
        completed = sum(fields)
        self.profile_completion_percentage = int((completed / len(fields)) * 100)
        self.save(update_fields=["profile_completion_percentage"])
        return self.profile_completion_percentage
