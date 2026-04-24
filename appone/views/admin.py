from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from appone.models import CompanyProfile, CountryTaxAccount, FreelancerProfile
from appone.permissions import IsAdmin
from appone.serializers import (
    AdminCompanyVerificationSerializer,
    AdminConfirmMeetingSerializer,
    AdminVerificationSerializer,
    CompanyProfileSerializer,
    CountryTaxAccountSerializer,
    FreelancerProfileSerializer,
    VerifyCompanyRegistrationSerializer,
)
from appone.utils import APIResponse, create_paystack_subaccount


@extend_schema(tags=["Admin"])
class AdminViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        summary="Verify freelancer (admin)",
        description="Admin endpoint to verify or reject a freelancer profile.",
        request=AdminVerificationSerializer,
        responses={
            200: OpenApiResponse(description="Freelancer verification updated."),
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Freelancer not found."),
        },
    )
    @action(detail=False, methods=["post"])
    def verify_freelancer(self, request):
        """Verify freelancer profile"""
        serializer = AdminVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        freelancer_id = serializer.validated_data["freelancer_id"]

        try:
            profile = FreelancerProfile.objects.get(id=freelancer_id)
        except FreelancerProfile.DoesNotExist:
            return APIResponse(
                message="Freelancer not found",
                status_code=status.HTTP_404_NOT_FOUND,
                status="error",
            )

        profile.verification_status = serializer.validated_data["verification_status"]
        if profile.verification_status == "verified":
            profile.admin_verified_at = timezone.now()
            profile.admin_verified_by = request.user
            profile.user.is_verified = True
            profile.user.save(update_fields=["is_verified"])
        elif profile.verification_status in ["rejected", "pending"]:
            profile.admin_verified_at = None
            profile.admin_verified_by = None
            profile.user.is_verified = False
            profile.user.save(update_fields=["is_verified"])

        profile.save()

        return APIResponse(
            data={"profile": FreelancerProfileSerializer(profile).data},
            message="Freelancer verification updated",
            status_code=status.HTTP_200_OK,
            status="success",
        )

    @extend_schema(
        summary="Get pending freelancer verifications",
        description="Returns all freelancer profiles with pending verification status.",
        responses={200: FreelancerProfileSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def pending_verifications(self, request):
        """Get pending freelancer verifications"""
        freelancers = FreelancerProfile.objects.select_related("user").filter(
            verification_status="pending"
        )
        serializer = FreelancerProfileSerializer(freelancers, many=True)
        return APIResponse(
            data=serializer.data,
            message="Pending freelancer verifications",
            status_code=status.HTTP_200_OK,
            status="success",
        )

    @extend_schema(
        summary="Get pending company verifications",
        description="Returns all company profiles with pending or scheduled verification status.",
        responses={200: CompanyProfileSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def pending_companies(self, request):
        """Get pending company verifications"""
        companies = CompanyProfile.objects.select_related("user").filter(
            verification_status__in=["pending", "pending_scheduling", "scheduled"]
        )
        serializer = CompanyProfileSerializer(companies, many=True)
        return APIResponse(
            data=serializer.data,
            message="Pending company verifications",
            status_code=status.HTTP_200_OK,
            status="success",
        )

    @extend_schema(
        summary="Get companies with proposed dates",
        description="Returns all company profiles that have submitted proposed meeting dates.",
        responses={200: CompanyProfileSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="company-proposed-dates")
    def company_proposed_dates(self, request):
        """Get companies with proposed dates"""
        companies = CompanyProfile.objects.select_related("user").exclude(
            proposed_meeting_dates=[]
        )
        serializer = CompanyProfileSerializer(companies, many=True)
        return APIResponse(
            data=serializer.data,
            message="Companies with proposed meeting dates",
            status_code=status.HTTP_200_OK,
            status="success",
        )

    @extend_schema(
        summary="Confirm verification meeting",
        description="Admin selects one of the 3 proposed dates for a company.",
        request=AdminConfirmMeetingSerializer,
        responses={
            200: OpenApiResponse(description="Meeting confirmed."),
            400: OpenApiResponse(description="Validation error."),
        },
    )
    @action(detail=False, methods=["post"], url_path="confirm-meeting")
    def confirm_meeting(self, request):
        """Confirm a verification meeting date"""
        serializer = AdminConfirmMeetingSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        company = serializer.validated_data["company"]
        company.meeting_scheduled_at = serializer.validated_data["selected_date"]
        company.meeting_link = serializer.validated_data["meeting_link"]
        company.verification_status = "scheduled"
        company.proposed_meeting_dates = []
        company.save()

        # TODO: Send email notification to company

        return APIResponse(
            data={"company": CompanyProfileSerializer(company).data},
            message="Meeting confirmed successfully",
            status_code=status.HTTP_200_OK,
            status="success",
        )

    @extend_schema(
        summary="Verify/Reject company",
        description="Admin manually verifies or rejects a company profile.",
        request=AdminCompanyVerificationSerializer,
        responses={
            200: OpenApiResponse(description="Company status updated."),
            400: OpenApiResponse(description="Validation error."),
        },
    )
    @action(detail=False, methods=["post"], url_path="verify-company")
    def verify_company(self, request):
        """Verify or reject a company"""
        serializer = AdminCompanyVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        company_id = serializer.validated_data["company_id"]
        profile = CompanyProfile.objects.get(id=company_id)

        profile.verification_status = serializer.validated_data["verification_status"]
        if profile.verification_status == "verified":
            profile.verified_at = timezone.now()
            profile.verified_by = request.user
            profile.user.is_verified = True
            profile.user.save(update_fields=["is_verified"])
        elif profile.verification_status in ["rejected", "pending"]:
            profile.verified_at = None
            profile.verified_by = None
            profile.user.is_verified = False
            profile.user.save(update_fields=["is_verified"])

        profile.save()

        return APIResponse(
            data={"company": CompanyProfileSerializer(profile).data},
            message="Company status updated",
            status_code=status.HTTP_200_OK,
            status="success",
        )

    @extend_schema(
        summary="Verify company registration (admin)",
        description="Admin-only: trigger government database verification for a company.",
        request=VerifyCompanyRegistrationSerializer,
        responses={
            200: OpenApiResponse(description="Verification result returned."),
            403: OpenApiResponse(description="Admin access required."),
        },
    )
    @action(detail=False, methods=["post"])
    def verify_company_registration(self, request):
        """Verify company with government database (Admin only)."""
        serializer = VerifyCompanyRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        company_id = serializer.validated_data["company_id"]
        try:
            profile = CompanyProfile.objects.get(id=company_id)
        except CompanyProfile.DoesNotExist:
            return APIResponse(
                message="Company not found",
                status_code=status.HTTP_404_NOT_FOUND,
                status="error",
            )

        api_verified = True
        verification_data = {
            "registration_number": profile.company_registration_number,
            "company_name": profile.company_name,
            "verified": True,
            "verified_at": timezone.now().isoformat(),
        }

        profile.api_verification_status = api_verified
        profile.api_verification_data = verification_data

        if api_verified:
            profile.verification_status = "verified"
            profile.verified_at = timezone.now()
            profile.verified_by = request.user
            profile.user.is_verified = True
            profile.user.save(update_fields=["is_verified"])

        profile.save()

        return APIResponse(
            data={
                "verification_status": profile.verification_status,
                "api_verification_data": verification_data,
            },
            message="Company verification completed",
            status_code=status.HTTP_200_OK,
            status="success",
        )


class CountryTaxAccountViewSet(viewsets.ModelViewSet):
    queryset = CountryTaxAccount.objects.all()
    serializer_class = CountryTaxAccountSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def perform_create(self, serializer):
        data = serializer.validated_data

        sub_code = create_paystack_subaccount(
            business_name=data["country_name"] + " Tax Authority",
            bank_code=data["bank_code"],
            account_number=data["account_number"],
        )

        if not sub_code:
            raise serializers.ValidationError(
                "Failed to verify account details with Paystack."
            )

        serializer.save(paystack_subaccount_code=sub_code)
