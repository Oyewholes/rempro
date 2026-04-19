from django.db import models
from django.core.validators import RegexValidator

phone_validator = RegexValidator(
    regex=r'^\+234\d{10}$',
    message="Phone must be in format: '+234XXXXXXXXXX'",
)


class OTPVerification(models.Model):
    OTP_TYPE_CHOICES = (
        ('phone', 'Phone Verification'),
        ('company_access', 'Company Access'),
        ('profile_access', 'Profile Access'),
    )

    user = models.ForeignKey('appone.User', on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=20, choices=OTP_TYPE_CHOICES)
    phone_number = models.CharField(
        validators=[phone_validator], max_length=14, unique=False
    )
    email = models.EmailField(blank=True)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OTP for {self.user.email} - {self.otp_type}"
