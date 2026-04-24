import base64

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from ipware import get_client_ip
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from appone.models import FreelancerProfile, ProfileAccessLog
from appone.permissions import IsFreelancer
from appone.serializers import (
    AddBankingDetailsSerializer,
    AddNINSerializer,
    AddPortfolioSerializer,
    FreelancerProfileSerializer,
    FreelancerProfileUpdateSerializer,
    FreelancerPublicProfileSerializer,
    UploadCVSerializer,
    UploadLivePhotoSerializer,
)
from appone.tasks import generate_id_card_task, upload_to_cloudinary_task
from appone.utils import (
    APIResponse,
    create_paystack_subaccount,
    generate_signed_download_url,
    generate_signed_url,
    verify_user_is_in_nigeria,
)
from RemPro import settings

_CV_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
CV_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _handle_file_upload(
    self, request, file_key, file_type, profile_field, allowed_types
):
    try:
        profile = request.user.freelancer_profile
    except FreelancerProfile.DoesNotExist:
        return APIResponse(
            message="Profile not found",
            status_code=status.HTTP_404_NOT_FOUND,
            status="error",
        )

    uploaded_file = request.FILES.get(file_key)
    if not uploaded_file:
        return APIResponse(
            message=f"{file_key} is required",
            status_code=status.HTTP_400_BAD_REQUEST,
            status="error",
        )

    if uploaded_file.content_type not in allowed_types:
        return APIResponse(
            message=f"Invalid file type. Accepted: {', '.join(allowed_types)}",
            status_code=status.HTTP_400_BAD_REQUEST,
            status="error",
        )

    if uploaded_file.size > CV_MAX_SIZE_BYTES:
        return APIResponse(
            message="File size must not exceed 10 MB.",
            status_code=status.HTTP_400_BAD_REQUEST,
            status="error",
        )

    try:
        file_bytes = uploaded_file.read()
        file_b64 = base64.b64encode(file_bytes).decode("utf-8")
    except Exception:
        return APIResponse(
            message="Failed to read uploaded file. Please try again.",
            status_code=status.HTTP_400_BAD_REQUEST,
            status="error",
        )

    try:
        upload_to_cloudinary_task.apply_async(
            args=[str(profile.id), file_b64, file_type, profile_field],
            ignore_result=True,
        )
    except Exception:
        return APIResponse(
            message="Upload queue unavailable. Please try again later.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            status="error",
        )

    return APIResponse(
        {
            "message": (
                f"Your {file_type.replace('_', ' ')} is being processed "
                "and will be available shortly."
            )
        },
        status=status.HTTP_202_ACCEPTED,
    )


@extend_schema(tags=["Freelancer Profile"])
class FreelancerProfileViewSet(viewsets.ModelViewSet):
    queryset = FreelancerProfile.objects.all()
    serializer_class = FreelancerProfileSerializer

    def get_permissions(self):
        if self.action in ["retrieve_by_digital_id", "public_profile"]:
            return [AllowAny()]
        return [IsAuthenticated(), IsFreelancer()]

    def get_queryset(self):
        if self.request.user.is_authenticated and hasattr(
            self.request.user, "freelancer_profile"
        ):
            return FreelancerProfile.objects.filter(user=self.request.user)
        return FreelancerProfile.objects.none()

    def update(self, request, *args, **kwargs):
        profile = self.get_object()
        bank_code = request.data.get("bank_code")
        account_number = request.data.get("account_number")

        if (
            bank_code
            and account_number
            and (
                bank_code != profile.bank_code
                or account_number != profile.account_number
            )
        ):
            business_name = f"{profile.first_name} {profile.last_name}"
            sub_code = create_paystack_subaccount(
                business_name, bank_code, account_number
            )

            if not sub_code:
                return APIResponse(
                    message="Invalid bank account details provided.",
                    status_code=400,
                    status="error",
                )
            profile.paystack_subaccount_code = sub_code
            profile.bank_details_verified = True
            profile.save(
                update_fields=["paystack_subaccount_code", "bank_details_verified"]
            )

        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Get or update my profile",
        description="GET returns the current freelancer profile. PUT/PATCH updates it.",
        responses={
            200: FreelancerProfileSerializer,
            404: OpenApiResponse(description="Profile not found."),
        },
    )
    @action(detail=False, methods=["get", "put", "patch"])
    def me(self, request):
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return APIResponse(
                message="Profile not found",
                status_code=status.HTTP_404_NOT_FOUND,
                status="error",
            )

        if request.method == "GET":
            serializer = FreelancerProfileSerializer(
                profile, context={"request": request}
            )
            return APIResponse(
                data=serializer.data,
                message="Profile retrieved successfully",
                status_code=status.HTTP_200_OK,
                status="success",
            )

        serializer = FreelancerProfileUpdateSerializer(
            profile, data=request.data, partial=(request.method == "PATCH")
        )
        if serializer.is_valid():
            serializer.save()
            profile.calculate_profile_completion()
            return APIResponse(
                data=FreelancerProfileSerializer(
                    profile, context={"request": request}
                ).data,
                status_code=status.HTTP_200_OK,
                message="Profile updated successfully",
                status="success",
            )
        return APIResponse(
            message=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            status="error",
        )

    @extend_schema(
        summary="Verify freelancer location",
        description=("Checks that the freelancer is located in Nigeria"),
        responses={
            200: OpenApiResponse(description="Location verified — user is in Nigeria."),
            403: OpenApiResponse(description="Location is outside Nigeria."),
            503: OpenApiResponse(description="Geolocation service unavailable."),
        },
    )
    @action(detail=False, methods=["post"])
    def verify_location(self, request):
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return APIResponse(
                message="Profile not found",
                status_code=status.HTTP_404_NOT_FOUND,
                status="error",
            )

        if settings.DEBUG and request.data.get("test_ip"):
            ip_address = request.data.get("test_ip")
        else:
            ip_address, is_routable = get_client_ip(request)
            if ip_address is None:
                return APIResponse(
                    message="Could not determine IP",
                    status="error",
                    status_code=400,
                )
        is_nigeria, location_data, message = verify_user_is_in_nigeria(ip_address)

        if location_data is None:
            return APIResponse(
                data=f"ip_address: {ip_address}",
                message=(
                    "Location verification service is temporarily unavailable."
                    "Please try again in a few minutes."
                ),
                status="error",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not is_nigeria:
            return APIResponse(
                data={
                    "country": location_data.get("country_name"),
                    "country_code": location_data.get("country_code"),
                    "city": location_data.get("city"),
                },
                status_code=status.HTTP_403_FORBIDDEN,
                status="error",
                message=message,
            )

        profile.ip_address = ip_address
        profile.country_code = location_data.get("country_code", "NGA")
        profile.location_verified = True
        profile.save(
            update_fields=[
                "ip_address",
                "country_code",
                "location_verified",
            ]
        )
        profile.calculate_profile_completion()

        return APIResponse(
            data={
                "location": {
                    "country": location_data.get("country_name"),
                    "country_code": location_data.get("country_code"),
                    "city": location_data.get("city"),
                    "region": location_data.get("region"),
                },
                "ip_address": ip_address,
                "profile_completion": profile.profile_completion_percentage,
            },
            message=message,
            status="success",
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Upload CV",
        description="Upload a PDF/Word CV file.",
        request={"multipart/form-data": UploadCVSerializer},
        responses={
            202: OpenApiResponse(description="Upload accepted and queued."),
            400: OpenApiResponse(description="Missing or invalid file."),
        },
    )
    @action(detail=False, methods=["post"])
    def upload_cv(self, request):
        """Upload CV file (PDF/Word)."""
        return _handle_file_upload(
            self,
            request,
            file_key="cv_file",
            file_type="cv",
            profile_field="cv_file",
            allowed_types=_CV_ALLOWED_CONTENT_TYPES,
        )

    @extend_schema(
        summary="Upload live photo",
        description="Upload a JPEG/PNG live photo.",
        request={"multipart/form-data": UploadLivePhotoSerializer},
        responses={
            202: OpenApiResponse(description="Upload accepted and queued."),
            400: OpenApiResponse(description="Missing or invalid file."),
        },
    )
    @action(detail=False, methods=["post"])
    def upload_live_photo(self, request):
        """Upload live photo (JPEG/PNG)."""
        return _handle_file_upload(
            self,
            request,
            file_key="live_photo",
            file_type="live_photo",
            profile_field="live_photo",
            allowed_types={"image/jpeg", "image/png"},
        )

    @extend_schema(
        summary="Add NIN",
        description="Submit the freelancer's 11-digit National Identification Number.",
        request=AddNINSerializer,
        responses={
            200: OpenApiResponse(description="NIN added successfully."),
            400: OpenApiResponse(description="Invalid NIN."),
        },
    )
    @action(detail=False, methods=["post"])
    def add_nin(self, request):
        """Add National Identification Number."""
        serializer = AddNINSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                status="error",
            )

        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return APIResponse(
                message="Profile not found",
                status_code=status.HTTP_404_NOT_FOUND,
                status="error",
            )

        nin = serializer.validated_data["nin"]
        profile.nin = nin
        profile.save(update_fields=["nin"])
        profile.calculate_profile_completion()
        return APIResponse(
            message="NIN added successfully",
            status_code=status.HTTP_200_OK,
            status="success",
        )

    @extend_schema(
        summary="Add portfolio item",
        description="Append a portfolio item to the freelancer's portfolio list.",
        request=AddPortfolioSerializer,
        responses={
            200: OpenApiResponse(description="Portfolio item added."),
            400: OpenApiResponse(description="Missing portfolio item."),
        },
    )
    @action(detail=False, methods=["post"])
    def add_portfolio(self, request):
        """Add portfolio items."""
        serializer = AddPortfolioSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        portfolio_item = serializer.validated_data["portfolio_item"]

        if not isinstance(profile.portfolio_files, list):
            profile.portfolio_files = []
        profile.portfolio_files.append(portfolio_item)
        profile.save(update_fields=["portfolio_files"])
        profile.calculate_profile_completion()

        return Response(
            {
                "message": "Portfolio item added successfully",
                "portfolio": profile.portfolio_files,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Add banking details",
        description="Add Paystack or Payoneer email for payment disbursement.",
        request=AddBankingDetailsSerializer,
        responses={
            200: OpenApiResponse(description="Banking details added."),
            400: OpenApiResponse(description="At least one payment method required."),
        },
    )
    @action(detail=False, methods=["post"])
    def add_banking_details(self, request):
        """Add banking details (Paystack/Payoneer)."""
        serializer = AddBankingDetailsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        paystack_email = serializer.validated_data.get("paystack_email")
        payoneer_email = serializer.validated_data.get("payoneer_email")

        if paystack_email:
            profile.paystack_email = paystack_email
        if payoneer_email:
            profile.payoneer_email = payoneer_email
        profile.bank_details_verified = True
        profile.save(
            update_fields=["paystack_email", "payoneer_email", "bank_details_verified"]
        )
        profile.calculate_profile_completion()

        return Response(
            {"message": "Banking details added successfully"}, status=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Retrieve freelancer by digital ID",
        description="Public endpoint: retrieve a freelancer's public profile by their digital UUID.",
        parameters=[
            OpenApiParameter(
                "digital_id", str, description="The freelancer's digital UUID"
            ),
        ],
        responses={
            200: FreelancerPublicProfileSerializer,
            404: OpenApiResponse(description="Profile not found."),
        },
    )
    @action(detail=False, methods=["get"], url_path="digital-id/(?P<digital_id>[^/.]+)")
    def retrieve_by_digital_id(self, request, digital_id=None):
        """Retrieve freelancer profile by digital ID (public access)."""
        try:
            profile = FreelancerProfile.objects.get(digital_id=digital_id)
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if request.user.is_authenticated and hasattr(request.user, "company_profile"):
            ProfileAccessLog.objects.create(
                company=request.user.company_profile,
                freelancer=profile,
                otp_verified=True,
            )

        serializer = FreelancerPublicProfileSerializer(profile)
        return Response(serializer.data)

    @extend_schema(
        summary="Generate digital ID card",
        description=(
            "Trigger asynchronous generation of the freelancer's digital ID card image. "
            "Only available for verified profiles. You will receive an email when ready."
        ),
        responses={
            202: OpenApiResponse(description="ID card generation started."),
            403: OpenApiResponse(description="Profile must be verified first."),
            503: OpenApiResponse(description="Task queue unavailable."),
        },
    )
    @action(detail=False, methods=["post"])
    def generate_id_card(self, request):
        """Trigger asynchronous generation of the freelancer's digital ID card."""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if profile.verification_status != "verified":
            return Response(
                {
                    "error": (
                        "Your profile must be verified before an ID card can be generated. "
                        f"Current status: {profile.verification_status}"
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            generate_id_card_task.apply_async(
                args=[str(profile.id)], ignore_result=False
            )
        except Exception as exc:
            return Response(
                {
                    "error": "ID card generation queue is unavailable. Please try again later."
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": (
                    "ID card generation started. You will receive an email when it's ready, "
                    "and it will be available for download from GET /api/freelancers/download_id_card/."
                ),
                "status": "processing",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        summary="Download digital ID card",
        description="Retrieve a signed Cloudinary URL for the freelancer's digital ID card PNG.",
        responses={
            200: OpenApiResponse(description="Signed download URL returned."),
            404: OpenApiResponse(description="ID card not yet generated."),
        },
    )
    @action(detail=False, methods=["get"])
    def download_id_card(self, request):
        """Return the Cloudinary download URL for the freelancer's digital ID card."""
        try:
            profile = request.user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if not profile.id_card_image:
            hint = (
                "Your ID card has not been generated yet. "
                "Call POST /api/freelancers/generate_id_card/ to create one."
                if profile.verification_status == "verified"
                else (
                    "Your profile must be verified before an ID card can be generated. "
                    f"Current status: {profile.verification_status}."
                )
            )
            return Response(
                {"error": "ID card not available.", "hint": hint},
                status=status.HTTP_404_NOT_FOUND,
            )

        signed_url = generate_signed_url(
            profile.id_card_image, resource_type="image", expiry_seconds=120
        )
        download_url = generate_signed_download_url(
            profile.id_card_image,
            filename=f"Virtual_Citizenship_ID_{profile.digital_id}.png",
            resource_type="image",
            expiry_seconds=120,
        )

        return Response(
            {
                "id_card_url": signed_url,
                "download_url": download_url,
                "profile_name": f"{profile.first_name} {profile.last_name}".strip(),
                "digital_id": str(profile.digital_id),
                "generated": True,
                "expires_in_seconds": 120,
            },
            status=status.HTTP_200_OK,
        )
