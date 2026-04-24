from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from appone.models import CompanyProfile
from appone.permissions import IsCompany
from appone.serializers import (
    CompanyProfileSerializer,
    CompanyProfileUpdateSerializer,
    ProposedMeetingDatesSerializer,
)
from appone.utils import APIResponse


@extend_schema(tags=["Company Profile"])
class CompanyProfileViewSet(viewsets.GenericViewSet):
    queryset = CompanyProfile.objects.all()
    serializer_class = CompanyProfileSerializer

    def get_permissions(self):
        if self.action in ["create"]:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsCompany()]

    def get_queryset(self):
        if self.request.user.is_authenticated and hasattr(
            self.request.user, "company_profile"
        ):
            return CompanyProfile.objects.select_related("user").filter(
                user=self.request.user
            )
        return CompanyProfile.objects.none()

    @extend_schema(
        summary="Get or update my company profile",
        description="GET returns the current company profile. PUT/PATCH updates it.",
        responses={
            200: CompanyProfileSerializer,
            404: OpenApiResponse(description="Profile not found."),
        },
    )
    @action(detail=False, methods=["get", "put", "patch"])
    def me(self, request):
        """Get or update current company's profile."""
        try:
            profile = request.user.company_profile
        except CompanyProfile.DoesNotExist:
            return APIResponse(
                message="Profile not found",
                status_code=status.HTTP_404_NOT_FOUND,
                status="error",
            )

        if request.method == "GET":
            return APIResponse(
                data=CompanyProfileSerializer(profile).data,
                message="Profile retrieved successfully",
                status_code=status.HTTP_200_OK,
                status="success",
            )

        serializer = CompanyProfileUpdateSerializer(
            profile, data=request.data, partial=(request.method == "PATCH")
        )
        if serializer.is_valid():
            sensitive_fields = ["company_name", "company_registration_number"]
            needs_reverification = False
            if profile.verification_status == "verified":
                for field in sensitive_fields:
                    if field in serializer.validated_data:
                        new_value = serializer.validated_data[field]
                        old_value = getattr(profile, field)
                        if new_value != old_value:
                            needs_reverification = True
                            break
            profile = serializer.save()
            if needs_reverification:
                profile.verification_status = "pending"
                profile.verified_at = None
                profile.verified_by = None
                profile.save(
                    update_fields=["verification_status", "verified_at", "verified_by"]
                )

                profile.user.is_verified = False
                profile.user.save(update_fields=["is_verified"])

            return APIResponse(
                data=CompanyProfileSerializer(profile).data,
                message="Profile updated successfully",
                status_code=status.HTTP_200_OK,
                status="success",
            )
        return APIResponse(
            message=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            status="error",
        )

    @extend_schema(
        summary="Propose meeting dates",
        description=(
            "Submit 1-3 proposed meeting date/time options for the admin "
            "verification meeting."
        ),
        request=ProposedMeetingDatesSerializer,
        responses={
            200: OpenApiResponse(description="Proposed meeting dates submitted."),
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Profile not found."),
        },
    )
    @action(detail=False, methods=["post"], url_path="propose-meeting-dates")
    def propose_meeting_dates(self, request):
        """Submit proposed meeting date/time options."""
        try:
            profile = request.user.company_profile
        except CompanyProfile.DoesNotExist:
            return APIResponse(
                message="Profile not found",
                status_code=status.HTTP_404_NOT_FOUND,
                status="error",
            )

        if profile.verification_status in ("verified", "rejected"):
            return APIResponse(
                message=(
                    f"Your company is already '{profile.verification_status}'. "
                    "Meeting dates can only be proposed while status is pending or scheduled."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        serializer = ProposedMeetingDatesSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        proposed = serializer.validated_data["proposed_dates"]
        profile.proposed_meeting_dates = [dt.isoformat() for dt in proposed]
        profile.verification_status = "pending_scheduling"
        profile.save(
            update_fields=[
                "proposed_meeting_dates",
                "verification_status",
                "updated_at",
            ]
        )

        return APIResponse(
            data={
                "proposed_dates": profile.proposed_meeting_dates,
                "verification_status": profile.verification_status,
            },
            message=(
                "Your proposed meeting dates have been submitted. "
                "An admin will confirm one of the slots."
            ),
            status_code=status.HTTP_200_OK,
            status="success",
        )
