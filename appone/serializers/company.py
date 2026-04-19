from rest_framework import serializers
from appone.models import CompanyProfile
from .user import UserInfoSerializer


class CompanyProfileSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for Company profile creation/detail (Private View)."""
    user = UserInfoSerializer(read_only=True)

    class Meta:
        model = CompanyProfile
        exclude = ('verified_by', 'api_verification_data')
        read_only_fields = (
            'user', 'verification_status', 'api_verification_status',
            'verified_at', 'created_at', 'updated_at',
        )


class CompanyProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating common company fields."""

    class Meta:
        model = CompanyProfile
        fields = (
            'company_name', 'company_email', 'company_registration_number',
            'country', 'address', 'phone_number', 'website',
            'industry', 'company_size', 'description',
        )


class ScheduleMeetingSerializer(serializers.Serializer):
    """Serializer for admin to schedule a verification meeting for a company."""
    meeting_scheduled_at = serializers.DateTimeField()
    meeting_link = serializers.URLField(max_length=500)


class VerifyCompanyRegistrationSerializer(serializers.Serializer):
    """Serializer for verifying company registration."""
    company_id = serializers.UUIDField(required=True)
