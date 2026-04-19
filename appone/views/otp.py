import random
import re
from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from appone.models import OTPVerification
from appone.serializers import OTPValidateSerializer, SendPhoneOTPSerializer
from appone.tasks import send_otp_task
from appone.utils import generate_otp, send_otp_sms
from RemPro import settings


@extend_schema(tags=["OTP / Verification"])
class OTPViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Send phone OTP",
        description="Generate and send a 6-digit OTP to the given Nigerian phone number via SMS.",
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
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
                "message": "OTP is being sent to your phone",
                "otp_id": str(otp.id),
                "expires_at": otp.expires_at,
            }
            if settings.DEBUG:
                response_data["otp_code"] = otp_code
                response_data["dev_note"] = "OTP code shown only in DEBUG mode"
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception:
            success = send_otp_sms(phone_number, otp_code)
            if success or settings.DEBUG:
                return Response(
                    {
                        "message": "OTP sent successfully",
                        "otp_id": str(otp.id),
                        "expires_at": otp.expires_at,
                        "otp_code": otp_code if settings.DEBUG else None,
                    },
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"error": "Failed to send OTP. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Verify phone OTP",
        description="Validate the 6-digit OTP sent to the user's phone. Marks phone as verified.",
        request=OTPValidateSerializer,
        responses={
            200: OpenApiResponse(description="Phone verified successfully."),
            400: OpenApiResponse(description="Invalid or expired OTP."),
        },
    )
    @action(detail=False, methods=["post"])
    def verify_phone_otp(self, request):
        """Verify phone OTP."""
        serializer = OTPValidateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        otp_code = serializer.validated_data["otp_code"]

        try:
            otp = OTPVerification.objects.get(
                user=request.user,
                otp_code=otp_code,
                otp_type="phone",
                is_verified=False,
                expires_at__gte=timezone.now(),
            )
            otp.is_verified = True
            otp.save()

            user = request.user
            user.phone_verified = True
            user.save(update_fields=["phone_verified"])

            if hasattr(user, "freelancer_profile"):
                profile = user.freelancer_profile
                profile.phone_number = otp.phone_number
                profile.phone_verified = True
                profile.save(update_fields=["phone_number", "phone_verified"])
                profile.calculate_profile_completion()
            elif hasattr(user, "company_profile"):
                company = user.company_profile
                company.phone_number = otp.phone_number
                company.phone_verified = True
                company.save(update_fields=["phone_number", "phone_verified"])

            return Response(
                {"message": "Phone verified successfully"}, status=status.HTTP_200_OK
            )

        except OTPVerification.DoesNotExist:
            return Response(
                {"error": "Invalid or expired OTP"}, status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        summary="Send company access OTP",
        description="Send a 6-digit OTP to the company email for freelancer profile access.",
        responses={
            200: OpenApiResponse(description="OTP sent to company email."),
            403: OpenApiResponse(description="Only companies can request access OTP."),
        },
    )
    @action(detail=False, methods=["post"])
    def send_company_access_otp(self, request):
        """Send OTP to company email for profile access."""
        if not hasattr(request.user, "company_profile"):
            return Response(
                {"error": "Only companies can request access OTP"},
                status=status.HTTP_403_FORBIDDEN,
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

        return Response(
            {
                "message": "OTP sent to company email",
                "otp_id": str(otp.id),
                "expires_at": otp.expires_at,
                "otp_code": otp_code,  # Remove in production
            },
            status=status.HTTP_200_OK,
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
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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

            return Response(
                {"message": "Access verified successfully", "access_token": otp_code},
                status=status.HTTP_200_OK,
            )

        except OTPVerification.DoesNotExist:
            return Response(
                {"error": "Invalid or expired OTP"}, status=status.HTTP_400_BAD_REQUEST
            )
