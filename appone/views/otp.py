import random
from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from appone.models import OTPVerification
from appone.serializers import OTPValidateSerializer, SendPhoneOTPSerializer
from appone.tasks import send_otp_task
from appone.utils import APIResponse, generate_otp


@extend_schema(tags=["OTP / Verification"])
class OTPViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Send phone OTP",
        description="Generate and send an OTP to the phone number via SMS.",
        request=SendPhoneOTPSerializer,
        responses={
            200: OpenApiResponse(description="OTP dispatched."),
            400: OpenApiResponse(description="Invalid phone number."),
        },
    )
    @action(detail=False, methods=["post"])
    def send_phone_otp(self, request):
        """Send OTP to phone number for verification."""
        serializer = SendPhoneOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        phone_number = serializer.validated_data["phone_number"]

        otp_code = generate_otp()
        otp = OTPVerification.objects.create(
            user=request.user,
            otp_code=otp_code,
            otp_type="phone",
            phone_number=phone_number,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        try:
            send_otp_task.delay(otp.id)
            response_data = {
                "otp_id": str(otp.id),
                "expires_at": otp.expires_at,
            }
            return APIResponse(
                data=response_data,
                status_code=status.HTTP_200_OK,
                message="OTP is being sent to your phone",
                status="success",
            )

        except Exception:
            return APIResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Failed to send OTP. Please try again.",
                status="error",
            )

    @extend_schema(
        summary="Verify Registration OTP",
        description="Validate the OTP sent to the user.",
        request=OTPValidateSerializer,
        responses={
            200: OpenApiResponse(description="Phone verified successfully."),
            400: OpenApiResponse(description="Invalid or expired OTP."),
        },
    )
    @action(detail=False, methods=["post"])
    def verify_otp(self, request):
        """Verify Registration OTP."""
        serializer = OTPValidateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        otp_code = serializer.validated_data["otp_code"]
        expected_otp_type = (
            "company_email"
            if hasattr(
                request.user,
                "company_profile",
            )
            else "phone"
        )

        try:
            otp = OTPVerification.objects.get(
                user=request.user,
                otp_code=otp_code,
                otp_type=expected_otp_type,
                is_verified=False,
                expires_at__gte=timezone.now(),
            )
            otp.is_verified = True
            otp.save()

            user = request.user
            if expected_otp_type == "phone":
                user.phone_verified = True
                user.save(update_fields=["phone_verified"])
            else:
                user = user.company_profile
                user.company_email_verified = True
                user.save(update_fields=["company_email_verified"])

            if hasattr(user, "freelancer_profile"):
                profile = user.freelancer_profile
                profile.phone_number = otp.phone_number
                profile.phone_verified = True
                profile.save(update_fields=["phone_number", "phone_verified"])
                profile.calculate_profile_completion()
            elif hasattr(user, "company_profile"):
                company = user.company_profile
                company.company_email = otp.email
                company.company_email_verified = True
                company.save(
                    update_fields=[
                        "company_email",
                        "company_email_verified",
                    ]
                )

            return APIResponse(
                message="Verification Successful",
                status_code=status.HTTP_200_OK,
                status="success",
            )

        except OTPVerification.DoesNotExist:
            return APIResponse(
                message="Invalid or expired OTP",
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

    @extend_schema(
        summary="Resend OTP",
        description="Resend OTP to the user.",
        responses={
            200: OpenApiResponse(description="OTP dispatched."),
            400: OpenApiResponse(description="User already verified."),
        },
    )
    @action(detail=False, methods=["post"])
    def resend_otp(self, request):
        """Resend OTP."""
        user = request.user
        if hasattr(user, "freelancer_profile") and user.phone_verified:
            return APIResponse(
                message="Your phone number is already verified.",
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )
        if (
            hasattr(user, "company_profile")
            and user.company_profile.company_email_verified
        ):
            return APIResponse(
                message="Your company email is already verified.",
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        otp_type = (
            "company_email"
            if hasattr(
                user,
                "company_profile",
            )
            else "phone"
        )

        OTPVerification.objects.filter(
            user=user,
            otp_type=otp_type,
            is_verified=False,
        ).update(expires_at=timezone.now())

        otp = OTPVerification.objects.create(
            user=user,
            otp_code=generate_otp(),
            otp_type=otp_type,
            phone_number=user.phone_number if otp_type == "phone" else "",
            email=user.email,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        send_otp_task.delay(otp.id)
        return APIResponse(
            data={"otp_id": str(otp.id), "expires_at": otp.expires_at},
            status_code=status.HTTP_200_OK,
            status="success",
            message="OTP sent successfully",
        )

    @extend_schema(
        summary="Send company access OTP",
        description="Send an OTP to the company email.",
        responses={
            200: OpenApiResponse(description="OTP sent to company email."),
            403: OpenApiResponse(description=""),
        },
    )
    @action(detail=False, methods=["post"])
    def send_company_access_otp(self, request):
        """Send OTP to company email for profile access."""
        if not hasattr(request.user, "company_profile"):
            return APIResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                status="error",
                message="Only companies can request access OTP",
            )

        company_profile = request.user.company_profile
        otp_code = str(random.randint(100000, 999999))
        otp = OTPVerification.objects.create(
            user=request.user,
            otp_code=otp_code,
            otp_type="company_access",
            email=company_profile.company_email,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response_data = {
            "otp_id": str(otp.id),
            "expires_at": otp.expires_at,
            "otp_code": otp_code,
        }
        return APIResponse(
            data=response_data,
            status_code=status.HTTP_200_OK,
            status="success",
            message="OTP sent successfully",
        )

    @extend_schema(
        summary="Verify company access OTP",
        description="Validate the 6-digit OTP sent to the company email.",
        request=OTPValidateSerializer,
        responses={
            200: OpenApiResponse(description="Access verified successfully."),
            400: OpenApiResponse(description="Invalid or expired OTP."),
        },
    )
    @action(detail=False, methods=["post"])
    def verify_company_access_otp(self, request):
        """Verify company access OTP."""
        serializer = OTPValidateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
                message=serializer.errors,
            )

        otp_code = serializer.validated_data["otp_code"]

        try:
            otp = OTPVerification.objects.get(
                user=request.user,
                otp_code=otp_code,
                otp_type="company_access",
                is_verified=False,
                expires_at__gte=timezone.now(),
            )
            otp.is_verified = True
            otp.save()

            return APIResponse(
                message="Access verified successfully",
                status_code=status.HTTP_200_OK,
                status="success",
                data={"Access Code": otp_code},
            )

        except OTPVerification.DoesNotExist:
            return APIResponse(
                message="Invalid or expired OTP",
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )
