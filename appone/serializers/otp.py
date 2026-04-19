from rest_framework import serializers
from django.utils import timezone
from appone.models import OTPVerification


class OTPVerificationSerializer(serializers.ModelSerializer):
    """Serializer for requesting a new OTP."""

    class Meta:
        model = OTPVerification
        fields = ('id', 'user', 'otp_type', 'phone_number', 'email', 'expires_at')
        read_only_fields = ('id', 'expires_at')

    def validate(self, data):
        if data['otp_type'] == 'phone' and not data.get('phone_number'):
            raise serializers.ValidationError(
                "Phone number is required for phone verification."
            )
        if data['otp_type'] != 'phone' and not data.get('email'):
            raise serializers.ValidationError(
                "Email is required for this type of verification."
            )
        data['expires_at'] = timezone.now() + timezone.timedelta(minutes=10)
        return data


class OTPValidateSerializer(serializers.Serializer):
    """Serializer for validating an existing OTP."""
    otp_code = serializers.CharField(max_length=6, required=True)
    contact_info = serializers.CharField(
        required=True,
        help_text="The phone number or email used for the OTP.",
    )


class AdminVerificationSerializer(serializers.Serializer):
    """Serializer for admin to verify/reject a profile."""
    freelancer_id = serializers.UUIDField(required=True)
    verification_status = serializers.ChoiceField(
        choices=[('verified', 'Verified'), ('rejected', 'Rejected')]
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class SendPhoneOTPSerializer(serializers.Serializer):
    """Serializer for requesting phone OTP."""
    phone_number = serializers.CharField(
        required=True,
        max_length=14,
        help_text="Nigerian format: +234XXXXXXXXXX"
    )

    def validate_phone_number(self, value):
        import re
        if not re.match(r'^\+234\d{10}$', value):
            raise serializers.ValidationError(
                "Invalid Nigerian phone format. Use +234XXXXXXXXXX"
            )
        return value
