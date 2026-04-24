from rest_framework import serializers

from appone.models import FreelancerProfile
from appone.utils import generate_signed_url

from .user import UserInfoSerializer


class FreelancerProfileSerializer(serializers.ModelSerializer):
    user = UserInfoSerializer(read_only=True)
    cv_download_url = serializers.SerializerMethodField()
    live_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = FreelancerProfile
        exclude = ("admin_verified_by",)
        read_only_fields = (
            "user",
            "digital_id",
            "digital_id_link",
            "id_card_image",
            "verification_status",
            "profile_completion_percentage",
            "created_at",
            "updated_at",
            "admin_verified_at",
        )

    def get_cv_download_url(self, obj):
        if obj.cv_file:
            return generate_signed_url(
                obj.cv_file, resource_type="raw", expiry_seconds=3600
            )
        return None

    def get_live_photo_url(self, obj):
        if obj.live_photo:
            return generate_signed_url(
                obj.live_photo, resource_type="image", expiry_seconds=3600
            )
        return None


class FreelancerProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FreelancerProfile
        fields = (
            "first_name",
            "last_name",
            "phone_number",
            "nin",
            "cv_file",
            "live_photo",
            "portfolio_files",
            "bio",
            "skills",
            "paystack_email",
            "payoneer_email",
            "approved_countries",
        )
        read_only_fields = ("cv_file", "live_photo")


class FreelancerPublicProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.ReadOnlyField(source="user.id")

    class Meta:
        model = FreelancerProfile
        fields = (
            "user_id",
            "first_name",
            "last_name",
            "skills",
            "bio",
            "verification_status",
            "digital_id",
            "profile_completion_percentage",
        )
        read_only_fields = fields


class AddNINSerializer(serializers.Serializer):
    nin = serializers.CharField(
        required=True,
        max_length=11,
        min_length=11,
        help_text="11-digit National Identification Number",
    )

    def validate_nin(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("NIN must contain only digits.")
        return value


class AddPortfolioSerializer(serializers.Serializer):
    portfolio_item = serializers.DictField(
        required=True, help_text="Dictionary containing portfolio item details"
    )


class AddBankingDetailsSerializer(serializers.Serializer):
    paystack_email = serializers.EmailField(required=False, allow_blank=True)
    payoneer_email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, data):
        if not data.get("paystack_email") and not data.get("payoneer_email"):
            raise serializers.ValidationError(
                "At least one payment method (paystack_email or payoneer_email) is required."
            )
        return data


class UploadCVSerializer(serializers.Serializer):
    cv_file = serializers.FileField(
        required=True, help_text="Upload CV file (PDF/Word). Max size 10MB."
    )


class UploadLivePhotoSerializer(serializers.Serializer):
    live_photo = serializers.FileField(
        required=True, help_text="Upload live photo (JPEG/PNG). Max size 10MB."
    )
