from rest_framework import serializers
from appone.models import FreelancerProfile
from .user import UserInfoSerializer


class FreelancerProfileSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for Freelancer profile creation/detail (Private View)."""
    user = UserInfoSerializer(read_only=True)

    class Meta:
        model = FreelancerProfile
        exclude = ('admin_verified_by',)
        read_only_fields = (
            'user', 'digital_id', 'digital_id_link', 'id_card_image',
            'verification_status', 'profile_completion_percentage',
            'created_at', 'updated_at', 'admin_verified_at',
        )


class FreelancerProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating common freelancer fields."""

    class Meta:
        model = FreelancerProfile
        fields = (
            'first_name', 'last_name', 'phone_number', 'nin',
            'cv_file', 'live_photo', 'portfolio_files', 'bio',
            'skills', 'paystack_email', 'payoneer_email', 'approved_countries',
        )


class FreelancerPublicProfileSerializer(serializers.ModelSerializer):
    """Minimal serializer for viewing by Company (Public View)."""
    user_id = serializers.ReadOnlyField(source='user.id')

    class Meta:
        model = FreelancerProfile
        fields = (
            'user_id', 'first_name', 'last_name', 'skills', 'bio',
            'verification_status', 'digital_id', 'profile_completion_percentage',
        )
        read_only_fields = fields


class AddNINSerializer(serializers.Serializer):
    """Serializer for adding National Identification Number."""
    nin = serializers.CharField(
        required=True,
        max_length=11,
        min_length=11,
        help_text="11-digit National Identification Number"
    )

    def validate_nin(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("NIN must contain only digits.")
        return value


class AddPortfolioSerializer(serializers.Serializer):
    """Serializer for adding a portfolio item."""
    portfolio_item = serializers.DictField(
        required=True,
        help_text="Dictionary containing portfolio item details"
    )


class AddBankingDetailsSerializer(serializers.Serializer):
    """Serializer for adding banking details."""
    paystack_email = serializers.EmailField(required=False, allow_blank=True)
    payoneer_email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, data):
        if not data.get('paystack_email') and not data.get('payoneer_email'):
            raise serializers.ValidationError(
                "At least one payment method (paystack_email or payoneer_email) is required."
            )
        return data
